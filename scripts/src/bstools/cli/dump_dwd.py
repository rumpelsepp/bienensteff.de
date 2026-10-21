"""
Downloads hourly temperature/humidity/precipitation data for a DWD weather
station (opendata.dwd.de) and writes out an hourly and a daily-aggregated
NDJSON file. With --meta also what the station is: its name, position and
height, as a JSON file.

The DWD splits its data in two: "recent" (about the last 500 days, updated
daily) and "historical" (everything before, up to the end of last year,
updated once a year). Both are fetched and joined, "recent" winning where
they overlap. The daily file goes back to --since-year; the hourly file
covers only the "recent" period, back to 2011 it would be ~11 MB.

Usage:
  bscli dump dwd --station-id 03379 --since-year 2011 \\
      --meta static/klima/03379_meta.json \\
      static/klima/03379_hourly.json static/klima/03379_daily.json
"""

import argparse
import io
import json
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from string import Template

lazy import polars as pl

from bstools import httpclient

BASE_URL = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly"

# The product's directory and the code in its file names.
PRODUCT_TEMP = ("air_temperature", "TU")
PRODUCT_PREC = ("precipitation", "RR")

URL_RECENT_TPL = Template(
    BASE_URL + "/${directory}/recent/stundenwerte_${code}_${station_id}_akt.zip"
)
URL_HISTORICAL_DIR_TPL = Template(BASE_URL + "/${directory}/historical/")


def historical_url(product: tuple[str, str], station_id: str) -> str | None:
    """The "historical" archive of a station. Its name carries the period it
    covers (stundenwerte_TU_03379_19970701_20251231_hist.zip), which moves
    every year, so it is looked up in the directory listing. None where the
    station has none."""
    directory, code = product
    url = URL_HISTORICAL_DIR_TPL.substitute(directory=directory)
    with httpclient.Client() as client:
        response = client.get(url)
        response.raise_for_status()
    names = sorted(
        set(
            re.findall(
                rf"stundenwerte_{code}_{station_id}_\d{{8}}_\d{{8}}_hist\.zip", response.text
            )
        )
    )
    return url + names[-1] if names else None


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


def read_product(
    product: tuple[str, str], station_id: str, historical: bool
) -> tuple[pl.DataFrame, dict[str, str | float], str]:
    """The raw rows of a product, "recent" and with "historical" also the
    archive before, with what the station is ("recent" knows it best) and
    the first MESS_DATUM of "recent"."""
    directory, code = product
    with fetch_dwd_zip(
        URL_RECENT_TPL.substitute(directory=directory, code=code, station_id=station_id)
    ) as z:
        recent = read_dwd_csv(z)
        station = read_station(z, station_id)
    frames = [recent]
    if historical and (url := historical_url(product, station_id)):
        with fetch_dwd_zip(url) as z:
            frames.insert(0, read_dwd_csv(z))
    frames = [
        df.rename({c: c.strip() for c in df.columns}).with_columns(
            pl.col("MESS_DATUM").str.strip_chars()
        )
        for df in frames
    ]
    recent_start = frames[-1]["MESS_DATUM"].min()
    # Where both have an hour, "recent" comes last and is kept.
    df = pl.concat(frames, how="diagonal").unique(
        subset="MESS_DATUM", keep="last", maintain_order=True
    )
    return df, station, recent_start


def clean_and_prepare_data(
    station_id: str, historical: bool = False
) -> tuple[pl.DataFrame, dict[str, str | float], str]:
    """The hourly data, what the station is and where its "recent" period
    starts (MESS_DATUM, of the temperature)."""
    df_temp_raw, station, recent_start = read_product(PRODUCT_TEMP, station_id, historical)
    df_prec_raw, _, _ = read_product(PRODUCT_PREC, station_id, historical)

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

    # Hours with only one of the two still count: the station has gaps in
    # either.
    df = df_temp.join(df_prec, on="timestamp", how="full", coalesce=True)

    # FIXME: Taupunkt Berechnung ist falsch.
    # 5. Berechnung des Taupunkts (Magnus-Formel)
    # a, b = 17.625, 243.04
    # alpha = ((a * pl.col("temperature")) / (b + pl.col("temperature"))) + (
    #     pl.col("rh") / 100.0
    # ).log()

    # df = df.with_columns(((b * alpha) / (a - alpha)).round(2).alias("dew_point"))

    return (
        df.sort("timestamp").select(["timestamp", "temperature", "precipitation"]),
        station,
        recent_start,
    )


def main(argv: list[str] | None = None, prog: str | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog=prog, description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--station-id",
        required=True,
        help="station ID according to DWD, ask AI or look in the DWD READMEs. Munich is 03379",
    )
    parser.add_argument(
        "--since-year",
        type=int,
        metavar="YEAR",
        help="also fetch the DWD's historical archive and write daily data from this year on "
        "(default: only the recent ~500 days)",
    )
    parser.add_argument(
        "--meta",
        type=Path,
        metavar="FILE",
        help="path to write name, position and height of the station (JSON)",
    )
    parser.add_argument("FILE_HOURLY", type=Path, help="path to write the hourly data")
    parser.add_argument("FILE_DAILY", type=Path, help="path to write the daily data")
    args = parser.parse_args(argv)

    historical = args.since_year is not None
    df_all, station, recent_start = clean_and_prepare_data(args.station_id, historical)
    if historical:
        df_all = df_all.filter(pl.col("timestamp").dt.year() >= args.since_year)
    df_daily = df_all.group_by_dynamic(
        index_column="timestamp",
        every="1d",
    ).agg(
        [
            pl.col("temperature").mean().round(1).alias("temperature_mean"),
            pl.col("temperature").max().round(1).alias("temperature_max"),
            pl.col("temperature").min().round(1).alias("temperature_min"),
            # pl.col("dew_point").mean().round(1).alias("dew_point_mean"),
            # A day without any value is unknown, not dry.
            pl.when(pl.col("precipitation").count() > 0)
            .then(pl.col("precipitation").sum().round(1))
            .alias("precipitation_sum"),
        ]
    )

    # The hourly data only as far back as "recent" goes, as before.
    since = datetime.strptime(recent_start, "%Y%m%d%H").replace(tzinfo=UTC)
    df_hourly = df_all.filter(pl.col("timestamp") >= since)
    with args.FILE_HOURLY.open(mode="wb") as f:
        df_hourly.write_ndjson(f)
    with args.FILE_DAILY.open(mode="wb") as f:
        df_daily.write_ndjson(f)
    if args.meta:
        args.meta.write_text(json.dumps(station, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
