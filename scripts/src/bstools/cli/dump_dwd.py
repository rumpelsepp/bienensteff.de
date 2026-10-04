"""
Downloads hourly temperature/humidity/precipitation data for a DWD weather
station (opendata.dwd.de) and writes out an hourly and a daily-aggregated
NDJSON file. With --meta also what the station is: its name, position and
height, as a JSON file.

Usage:
  dump-dwd --station-id 03379 --meta static/klima/03379_meta.json \\
      static/klima/03379_hourly.json static/klima/03379_daily.json
"""

import argparse
import io
import json
import zipfile
from pathlib import Path
from string import Template

import polars as pl

from bstools import httpclient

BASE_URL = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly"

URL_TEMP_TPL = Template(BASE_URL + "/air_temperature/recent/stundenwerte_TU_${station_id}_akt.zip")
URL_PREC_TPL = Template(BASE_URL + "/precipitation/recent/stundenwerte_RR_${station_id}_akt.zip")


def fetch_dwd_zip(url: str) -> zipfile.ZipFile:
    with httpclient.Client() as client:
        response = client.get(url)
        response.raise_for_status()

    return zipfile.ZipFile(io.BytesIO(response.content))


def read_dwd_csv(z: zipfile.ZipFile) -> pl.DataFrame:
    product_file = next(name for name in z.namelist() if name.startswith("produkt_"))
    with z.open(product_file) as f:
        return pl.read_csv(f, separator=";", infer_schema_length=0)


def read_station(z: zipfile.ZipFile, station_id: str) -> dict[str, str | float]:
    """What the station is, from the Metadaten_Geographie file every archive
    comes with: a line per period the station stood somewhere, the last one
    being where it stands now."""
    geo_file = next(name for name in z.namelist() if name.startswith("Metadaten_Geographie_"))
    lines = z.read(geo_file).decode("latin-1").splitlines()
    header = [column.strip() for column in lines[0].split(";")]
    rows = [
        dict(zip(header, (value.strip() for value in line.split(";")), strict=True))
        for line in lines[1:]
        if line.strip()
    ]
    current = rows[-1]
    return {
        "id": station_id,
        "name": current["Stationsname"],
        "latitude": float(current["Geogr.Breite"]),
        "longitude": float(current["Geogr.Laenge"]),
        "height": float(current["Stationshoehe"]),
    }


def parse_dwd_timestamp(column_name: str = "MESS_DATUM") -> pl.Expr:
    return (
        pl.col(column_name)
        .str.strip_chars()
        .cast(pl.Int64)
        .pipe(
            lambda c: pl.datetime(
                year=c // 1000000,
                month=(c // 10000) % 100,
                day=(c // 100) % 100,
                hour=c % 100,
            )
        )
        .dt.replace_time_zone("UTC")
    )


def clean_dwd_value(column_name: str) -> pl.Expr:
    parsed_float = pl.col(column_name).str.strip_chars().cast(pl.Float64, strict=False)
    return pl.when(parsed_float == -999.0).then(None).otherwise(parsed_float)


def clean_and_prepare_data(station_id: str) -> tuple[pl.DataFrame, dict[str, str | float]]:
    url_temp = URL_TEMP_TPL.substitute(station_id=station_id)
    url_prec = URL_PREC_TPL.substitute(station_id=station_id)
    with fetch_dwd_zip(url_temp) as z:
        df_temp_raw = read_dwd_csv(z)
        station = read_station(z, station_id)
    with fetch_dwd_zip(url_prec) as z:
        df_prec_raw = read_dwd_csv(z)

    df_temp_raw = df_temp_raw.rename({c: c.strip() for c in df_temp_raw.columns})
    df_prec_raw = df_prec_raw.rename({c: c.strip() for c in df_prec_raw.columns})
    df_temp = df_temp_raw.select(
        [
            parse_dwd_timestamp().alias("timestamp"),
            clean_dwd_value("TT_TU").alias("temperature"),
            clean_dwd_value("RF_TU").alias("rh"),
        ]
    )

    df_prec = df_prec_raw.select(
        [
            parse_dwd_timestamp().alias("timestamp"),
            clean_dwd_value("R1").alias("precipitation"),
        ]
    )

    df = df_temp.join(df_prec, on="timestamp", how="inner")

    # FIXME: Taupunkt Berechnung ist falsch.
    # 5. Berechnung des Taupunkts (Magnus-Formel)
    # a, b = 17.625, 243.04
    # alpha = ((a * pl.col("temperature")) / (b + pl.col("temperature"))) + (
    #     pl.col("rh") / 100.0
    # ).log()

    # df = df.with_columns(((b * alpha) / (a - alpha)).round(2).alias("dew_point"))

    return df.sort("timestamp").select(["timestamp", "temperature", "precipitation"]), station


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--station-id",
        required=True,
        help="station ID according to DWD, ask AI or look in the DWD READMEs. Munich is 03379",
    )
    parser.add_argument(
        "--meta",
        type=Path,
        metavar="FILE",
        help="path to write name, position and height of the station (JSON)",
    )
    parser.add_argument("FILE_HOURLY", type=Path, help="path to write the hourly data")
    parser.add_argument("FILE_DAILY", type=Path, help="path to write the daily data")
    args = parser.parse_args()

    df_hourly, station = clean_and_prepare_data(args.station_id)
    df_daily = df_hourly.group_by_dynamic(
        index_column="timestamp",
        every="1d",
    ).agg(
        [
            pl.col("temperature").mean().round(1).alias("temperature_mean"),
            pl.col("temperature").max().round(1).alias("temperature_max"),
            pl.col("temperature").min().round(1).alias("temperature_min"),
            # pl.col("dew_point").mean().round(1).alias("dew_point_mean"),
            pl.col("precipitation").sum().round(1).alias("precipitation_sum"),
        ]
    )

    with args.FILE_HOURLY.open(mode="wb") as f:
        df_hourly.write_ndjson(f)
    with args.FILE_DAILY.open(mode="wb") as f:
        df_daily.write_ndjson(f)
    if args.meta:
        args.meta.write_text(json.dumps(station, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
