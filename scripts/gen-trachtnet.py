#!/usr/bin/env -S uv run -qs

# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "httpx",
#     "polars",
#     "matplotlib",
# ]
# ///

import argparse
import enum
import locale
import re
import sys
import datetime
from typing import Any, TypedDict

import httpx
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as tck
import polars as pl


class Land(enum.Enum):
    BADEN_WUERTTEMBERG = "08"
    BAYERN = "09"
    BERLIN = "11"
    BRANDENBURG = "12"
    BREMEN = "04"
    DEUTSCHLAND = "49"
    HAMBURG = "02"
    HESSEN = "06"
    MECKLENBURG_VORPOMMERN = "13"
    NIEDERSACHSEN = "03"
    NORDRHEIN_WESTFALEN = "05"
    RHEINLAND_PFALZ = "07"
    SAARLAND = "10"
    SACHSEN = "14"
    SACHSEN_ANHALT = "15"
    SCHLESWIG_HOLSTEIN = "01"
    THUERINGEN = "16"


class Regierungsbezirk(enum.Enum):
    # Baden-Württemberg
    STUTTGART = "081"
    KARLSRUHE = "082"
    FREIBURG = "083"
    TUEBINGEN = "084"

    # Bayern
    OBERBAYERN = "091"
    NIEDERBAYERN = "092"
    OBERPFALZ = "093"
    OBERFRANKEN = "094"
    MITTELFRANKEN = "095"
    UNTERFRANKEN = "096"
    SCHWABEN = "097"

    # Hessen
    DARMSTADT = "064"
    GIESSEN = "065"
    KASSEL = "066"

    # Nordrhein-Westfalen
    DUESSeldorf = "051"
    KOELN = "053"
    MUENSTER = "055"
    DETMOLD = "057"
    ARNSBERG = "059"


class Kreis(enum.Enum):
    AHRWEILER = "07131"
    AICHACH_FRIEDBERG = "09771"
    ALB_DONAU_KREIS = "08425"
    ALTENBURGER_LAND = "16077"
    ALTENKIRCHEN_WESTERWALD = "07132"
    ALTMARKKREIS_SALZWEDEL = "15081"
    ALTOETTING = "09171"
    ALZEY_WORMS = "07331"
    AMBERG = "09361"
    AMBERG_SULZBACH = "09371"
    AMMERLAND = "03451"
    ANHALT_BITTERFELD = "15082"
    KREISFREIE_STADT_ANSBACH = "09561"
    ANSBACH = "09571"
    KREISFREIE_STADT_ASCHAFFENBURG = "09661"
    ASCHAFFENBURG = "09671"
    KREISFREIE_STADT_AUGSBURG = "09761"
    AUGSBURG = "09772"
    AURICH = "03452"
    BADEN_BADEN_STADTKREIS = "08211"
    BAD_DUERKHEIM = "07332"
    BAD_KISSINGEN = "09672"
    BAD_KREUZNACH = "07133"
    BAD_TOELZ_WOLFRATSHAUSEN = "09173"
    KREISFREIE_STADT_BAMBERG = "09461"
    BAMBERG = "09471"
    BARNIM = "12060"
    BAUTZEN = "14625"
    KREISFREIE_STADT_BAYREUTH = "09462"
    BAYREUTH = "09472"
    BERCHTESGADENER_LAND = "09172"
    BERGSTRASSE = "06431"
    BERLIN_STADT = "11000"
    BERNKASTEL_WITTLICH = "07231"
    BIBERACH = "08426"
    BIELEFELD_STADT = "05711"
    BIRKENFELD = "07134"
    BOCHUM_STADT = "05911"
    BODENSEEKREIS = "08435"
    BOEBLINGEN = "08115"
    BOERDE = "15083"
    BONN_STADT = "05314"
    BORKEN = "05554"
    BOTTROP_STADT = "05512"
    BRANDENBURG_AN_DER_HAVEL_STADT = "12051"
    BRAUNSCHWEIG_STADT = "03101"
    BREISGAU_HOCHSCHWARZWALD = "08315"
    BREMEN_STADT = "04011"
    BREMERHAVEN_STADT = "04012"
    BURGENLANDKREIS = "15084"
    CALW = "08235"
    CELLE = "03351"
    CHAM = "09372"
    CHEMNITZ_STADT = "14511"
    CLOPPENBURG = "03453"
    KREISFREIE_STADT_COBURG = "09463"
    COBURG = "09473"
    COCHEM_ZELL = "07135"
    COESFELD = "05558"
    COTTBUS_STADT = "12052"
    CUXHAVEN = "03352"
    DACHAU = "09174"
    DAHME_SPREEWALD = "12061"
    DARMSTADT_DIEBURG = "06432"
    DARMSTADT_WISSENSCHAFTSSTADT = "06411"
    DEGGENDORF = "09271"
    DELMENHORST_STADT = "03401"
    DESSAU_ROSSLAU_STADT = "15001"
    DIEPHOLZ = "03251"
    DILLINGEN_A_D_DONAU = "09773"
    DINGOLFING_LANDAU = "09279"
    DITHMARSCHEN = "01051"
    DONAU_RIES = "09779"
    DONNERSBERGKREIS = "07333"
    DORTMUND_STADT = "05913"
    DRESDEN_STADT = "14612"
    DUEREN = "05358"
    DUESSELDORF_STADT = "05111"
    DUISBURG_STADT = "05112"
    EBERSBERG = "09175"
    EICHSFELD = "16061"
    EICHSTAETT = "09176"
    EIFELKREIS_BITBURG_PRUEM = "07232"
    ELBE_ELSTER = "12062"
    EMDEN_STADT = "03402"
    EMMENDINGEN = "08316"
    EMSLAND = "03454"
    ENNEPE_RUHR_KREIS = "05954"
    ENZKREIS = "08236"
    ERDING = "09177"
    ERFURT_STADT = "16051"
    ERLANGEN = "09562"
    ERLANGEN_HOECHSTADT = "09572"
    ERZGEBIRGSKREIS = "14521"
    ESSEN_STADT = "05113"
    ESSLINGEN = "08116"
    EUSKIRCHEN = "05366"
    FLENSBURG_STADT = "01001"
    FORCHHEIM = "09474"
    FRANKENTHAL_PFALZ_KREISFREIE_STADT = "07311"
    FRANKFURT_AM_MAIN_STADT = "06412"
    FRANKFURT_ODER_STADT = "12053"
    FREIBURG_IM_BREISGAU_STADTKREIS = "08311"
    FREISING = "09178"
    FREUDENSTADT = "08237"
    FREYUNG_GRAFENAU = "09272"
    FRIESLAND = "03455"
    FUERSTENFELDBRUCK = "09179"
    KREISFREIE_STADT_FUERTH = "09563"
    FUERTH = "09573"
    FULDA = "06631"
    GARMISCH_PARTENKIRCHEN = "09180"
    GELSENKIRCHEN_STADT = "05513"
    GERA_STADT = "16052"
    GERMERSHEIM = "07334"
    GIESSEN = "06531"
    GIFHORN = "03151"
    GOEPPINGEN = "08117"
    GOERLITZ = "14626"
    GOETTINGEN = "03159"
    GOSLAR = "03153"
    GOTHA = "16067"
    GRAFSCHAFT_BENTHEIM = "03456"
    GREIZ = "16076"
    GROSS_GERAU = "06433"
    GUENZBURG = "09774"
    GUETERSLOH = "05754"
    HAGEN_STADT_DER_FERNUNIVERSITAET = "05914"
    HALLE_SAALE_STADT = "15002"
    HAMBURG_FREIE_UND_HANSESTADT = "02000"
    HAMELN_PYRMONT = "03252"
    HAMM_STADT = "05915"
    HARBURG = "03353"
    HARZ = "15085"
    HASSBERGE = "09674"
    HAVELLAND = "12063"
    HEIDEKREIS = "03358"
    HEIDELBERG_STADTKREIS = "08221"
    HEIDENHEIM = "08135"
    HEILBRONN = "08125"
    HEILBRONN_STADTKREIS = "08121"
    HEINSBERG = "05370"
    HELMSTEDT = "03154"
    HERFORD = "05758"
    HERNE_STADT = "05916"
    HERSFELD_ROTENBURG = "06632"
    HERZOGTUM_LAUENBURG = "01053"
    HILDBURGHAUSEN = "16069"
    HILDESHEIM = "03254"
    HOCHSAUERLANDKREIS = "05958"
    HOCHTAUNUSKREIS = "06434"
    HOEXTER = "05762"
    KREISFREIE_STADT_HOF = "09464"
    HOF = "09475"
    HOHENLOHEKREIS = "08126"
    HOLZMINDEN = "03255"
    ILM_KREIS = "16070"
    INGOLSTADT = "09161"
    JENA_STADT = "16053"
    JERICHOWER_LAND = "15086"
    KAISERSLAUTERN = "07335"
    KAISERSLAUTERN_KREISFREIE_STADT = "07312"
    KARLSRUHE = "08215"
    KARLSRUHE_STADTKREIS = "08212"
    KASSEL = "06633"
    KASSEL_DOCUMENTA_STADT = "06611"
    KAUFBEUREN = "09762"
    KELHEIM = "09273"
    KEMPTEN_ALLGAEU = "09763"
    KIEL_LANDESHAUPTSTADT = "01002"
    KITZINGEN = "09675"
    KLEVE = "05154"
    KOBLENZ_KREISFREIE_STADT = "07111"
    KOELN_STADT = "05315"
    KONSTANZ = "08335"
    KREFELD_STADT = "05114"
    KRONACH = "09476"
    KULMBACH = "09477"
    KUSEL = "07336"
    KYFFHAEUSERKREIS = "16065"
    LAHN_DILL_KREIS = "06532"
    LANDAU_IN_DER_PFALZ_KREISFREIE_STADT = "07313"
    LANDKREIS_ROSTOCK = "13072"
    LANDSBERG_AM_LECH = "09181"
    KREISFREIE_STADT_LANDSHUT = "09261"
    LANDSHUT = "09274"
    LEER = "03457"
    LEIPZIG = "14729"
    LEIPZIG_STADT = "14713"
    LEVERKUSEN_STADT = "05316"
    LICHTENFELS = "09478"
    LIMBURG_WEILBURG = "06533"
    LINDAU_BODENSEE = "09776"
    LIPPE = "05766"
    LOERRACH = "08336"
    LUDWIGSBURG = "08118"
    LUDWIGSHAFEN_AM_RHEIN_KREISFREIE_STADT = "07314"
    LUDWIGSLUST_PARCHIM = "13076"
    LUEBECK_HANSESTADT = "01003"
    LUECHOW_DANNENBERG = "03354"
    LUENEBURG = "03355"
    MAERKISCHER_KREIS = "05962"
    MAERKISCH_ODERLAND = "12064"
    MAGDEBURG_LANDESHAUPTSTADT = "15003"
    MAINZ_BINGEN = "07339"
    MAINZ_KREISFREIE_STADT = "07315"
    MAIN_KINZIG_KREIS = "06435"
    MAIN_SPESSART = "09677"
    MAIN_TAUBER_KREIS = "08128"
    MAIN_TAUNUS_KREIS = "06436"
    MANNHEIM_STADTKREIS = "08222"
    MANSFELD_SUEDHARZ = "15087"
    MARBURG_BIEDENKOPF = "06534"
    MAYEN_KOBLENZ = "07137"
    MECKLENBURGISCHE_SEENPLATTE = "13071"
    MEISSEN = "14627"
    MEMMINGEN = "09764"
    MERZIG_WADERN = "10042"
    METTMANN = "05158"
    MIESBACH = "09182"
    MILTENBERG = "09676"
    MINDEN_LUEBBECKE = "05770"
    MITTELSACHSEN = "14522"
    MOENCHENGLADBACH_STADT = "05116"
    MUEHLDORF_A_INN = "09183"
    MUELHEIM_AN_DER_RUHR_STADT = "05117"
    MUENCHEN = "09184"
    MUENCHEN_LANDESHAUPTSTADT = "09162"
    MUENSTER_STADT = "05515"
    NECKAR_ODENWALD_KREIS = "08225"
    NEUBURG_SCHROBENHAUSEN = "09185"
    NEUMARKT_I_D_OPF = "09373"
    NEUMUENSTER_STADT = "01004"
    NEUNKIRCHEN = "10043"
    NEUSTADT_AN_DER_WEINSTRASSE_KREISFREIE_STADT = "07316"
    NEUSTADT_A_D_AISCH_BAD_WINDSHEIM = "09575"
    NEUSTADT_A_D_WALDNAAB = "09374"
    NEUWIED = "07138"
    NEU_ULM = "09775"
    NIENBURG_WESER = "03256"
    NORDFRIESLAND = "01054"
    NORDHAUSEN = "16062"
    NORDSACHSEN = "14730"
    NORDWESTMECKLENBURG = "13074"
    NORTHEIM = "03155"
    NUERNBERG = "09564"
    NUERNBERGER_LAND = "09574"
    OBERALLGAEU = "09780"
    OBERBERGISCHER_KREIS = "05374"
    OBERHAUSEN_STADT = "05119"
    OBERHAVEL = "12065"
    OBERSPREEWALD_LAUSITZ = "12066"
    ODENWALDKREIS = "06437"
    ODER_SPREE = "12067"
    OFFENBACH = "06438"
    OFFENBACH_AM_MAIN_STADT = "06413"
    OLDENBURG = "03458"
    OLDENBURG_OLDENBURG_STADT = "03403"
    OLPE = "05966"
    ORTENAUKREIS = "08317"
    OSNABRUECK = "03459"
    OSNABRUECK_STADT = "03404"
    OSTALBKREIS = "08136"
    OSTALLGAEU = "09777"
    OSTERHOLZ = "03356"
    OSTHOLSTEIN = "01055"
    OSTPRIGNITZ_RUPPIN = "12068"
    PADERBORN = "05774"
    KREISFREIE_STADT_PASSAU = "09262"
    PASSAU = "09275"
    PEINE = "03157"
    PFAFFENHOFEN_A_D_ILM = "09186"
    PFORZHEIM_STADTKREIS = "08231"
    PINNEBERG = "01056"
    PIRMASENS_KREISFREIE_STADT = "07317"
    PLOEN = "01057"
    POTSDAM_MITTELMARK = "12069"
    POTSDAM_STADT = "12054"
    PRIGNITZ = "12070"
    RASTATT = "08216"
    RAVENSBURG = "08436"
    RECKLINGHAUSEN = "05562"
    REGEN = "09276"
    KREISFREIE_STADT_REGENSBURG = "09362"
    REGENSBURG = "09375"
    REGIONALVERBAND_SAARBRUECKEN = "10041"
    REGION_HANNOVER = "03241"
    REMSCHEID_STADT = "05120"
    REMS_MURR_KREIS = "08119"
    RENDSBURG_ECKERNFOERDE = "01058"
    REUTLINGEN = "08415"
    RHEINGAU_TAUNUS_KREIS = "06439"
    RHEINISCH_BERGISCHER_KREIS = "05378"
    RHEIN_ERFT_KREIS = "05362"
    RHEIN_HUNSRUECK_KREIS = "07140"
    RHEIN_KREIS_NEUSS = "05162"
    RHEIN_LAHN_KREIS = "07141"
    RHEIN_NECKAR_KREIS = "08226"
    RHEIN_PFALZ_KREIS = "07338"
    RHEIN_SIEG_KREIS = "05382"
    RHOEN_GRABFELD = "09673"
    KREISFREIE_STADT_ROSENHEIM = "09163"
    ROSENHEIM = "09187"
    ROSTOCK = "13003"
    ROTENBURG_WUEMME = "03357"
    ROTH = "09576"
    ROTTAL_INN = "09277"
    ROTTWEIL = "08325"
    SAALEKREIS = "15088"
    SAALE_HOLZLAND_KREIS = "16074"
    SAALE_ORLA_KREIS = "16075"
    SAALFELD_RUDOLSTADT = "16073"
    SAARLOUIS = "10044"
    SAARPFALZ_KREIS = "10045"
    SAECHSISCHE_SCHWEIZ_OSTERZGEBIRGE = "14628"
    SALZGITTER_STADT = "03102"
    SALZLANDKREIS = "15089"
    SCHAUMBURG = "03257"
    SCHLESWIG_FLENSBURG = "01059"
    SCHMALKALDEN_MEININGEN = "16066"
    SCHWABACH = "09565"
    SCHWAEBISCH_HALL = "08127"
    SCHWALM_EDER_KREIS = "06634"
    SCHWANDORF = "09376"
    SCHWARZWALD_BAAR_KREIS = "08326"
    KREISFREIE_STADT_SCHWEINFURT = "09662"
    SCHWEINFURT = "09678"
    SCHWERIN = "13004"
    SEGEBERG = "01060"
    SIEGEN_WITTGENSTEIN = "05970"
    SIGMARINGEN = "08437"
    SOEMMERDA = "16068"
    SOEST = "05974"
    SOLINGEN_KLINGENSTADT = "05122"
    SONNEBERG = "16072"
    SPEYER_KREISFREIE_STADT = "07318"
    SPREE_NEISSE = "12071"
    STADE = "03359"
    STAEDTEREGION_AACHEN = "05334"
    STARNBERG = "09188"
    STEINBURG = "01061"
    STEINFURT = "05566"
    STENDAL = "15090"
    STORMARN = "01062"
    STRAUBING = "09263"
    STRAUBING_BOGEN = "09278"
    STUTTGART_STADTKREIS = "08111"
    ST_WENDEL = "10046"
    SUEDLICHE_WEINSTRASSE = "07337"
    SUEDWESTPFALZ = "07340"
    SUHL_STADT = "16054"
    TELTOW_FLAEMING = "12072"
    TIRSCHENREUTH = "09377"
    TRAUNSTEIN = "09189"
    TRIER_KREISFREIE_STADT = "07211"
    TRIER_SAARBURG = "07235"
    TUEBINGEN = "08416"
    TUTTLINGEN = "08327"
    UCKERMARK = "12073"
    UELZEN = "03360"
    ULM_STADTKREIS = "08421"
    UNNA = "05978"
    UNSTRUT_HAINICH_KREIS = "16064"
    UNTERALLGAEU = "09778"
    VECHTA = "03460"
    VERDEN = "03361"
    VIERSEN = "05166"
    VOGELSBERGKREIS = "06535"
    VOGTLANDKREIS = "14523"
    VORPOMMERN_GREIFSWALD = "13075"
    VORPOMMERN_RUEGEN = "13073"
    VULKANEIFEL = "07233"
    WALDECK_FRANKENBERG = "06635"
    WALDSHUT = "08337"
    WARENDORF = "05570"
    WARTBURGKREIS = "16063"
    WEIDEN_I_D_OPF = "09363"
    WEILHEIM_SCHONGAU = "09190"
    WEIMARER_LAND = "16071"
    WEIMAR_STADT = "16055"
    WEISSENBURG_GUNZENHAUSEN = "09577"
    WERRA_MEISSNER_KREIS = "06636"
    WESEL = "05170"
    WESERMARSCH = "03461"
    WESTERWALDKREIS = "07143"
    WETTERAUKREIS = "06440"
    WIESBADEN_LANDESHAUPTSTADT = "06414"
    WILHELMSHAVEN_STADT = "03405"
    WITTENBERG = "15091"
    WITTMUND = "03462"
    WOLFENBUETTEL = "03158"
    WOLFSBURG_STADT = "03103"
    WORMS_KREISFREIE_STADT = "07319"
    KREISFREIE_STADT_WUERZBURG = "09663"
    WUERZBURG = "09679"
    WUNSIEDEL_I_FICHTELGEBIRGE = "09479"
    WUPPERTAL_STADT = "05124"
    ZOLLERNALBKREIS = "08417"
    ZWEIBRUECKEN_KREISFREIE_STADT = "07320"
    ZWICKAU = "14524"


type RegionType = Land | Regierungsbezirk | Kreis
regions_list = (
    [region.name.lower() for region in Land]
    + [region.name.lower() for region in Regierungsbezirk]
    + [region.name.lower() for region in Kreis]
)


class Record(TypedDict):
    value: float
    date: datetime.date


class Records(TypedDict):
    year: int
    name: str
    data_key: str
    records: list[Record]
    dataframe: pl.DataFrame


class TrachtnetClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        self.user_agent = (
            "Mozilla/5.0 (X11; Linux x86_64; rv:138.0) Gecko/20100101 Firefox/138.0"
        )

    def _request(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        headers = kwargs.pop("headers", {})
        headers["User-Agent"] = self.user_agent
        transport = httpx.HTTPTransport(retries=3)
        with httpx.Client(transport=transport) as client:
            resp = client.request(
                method, f"{self.base_url}/{endpoint}", headers=headers, **kwargs,
            )
        resp.raise_for_status()
        return resp

    def get_raw_data(
        self,
        from_year: int,
        to_year: int,
        regions: list[RegionType | int],
    ) -> dict[str, Any]:
        params = {
            "type": "load_chart",
            "wid": [],
            "blid": [],
            "rbzid": [],
            "lkid": [],
            "from": from_year,
            "to": to_year,
        }
        for region in regions:
            match region:
                case Regierungsbezirk():
                    params["rbzid"].append(region.value)
                case Land():
                    params["blid"].append(region.value)
                case Kreis():
                    params["lkid"].append(region.value)
                case int():
                    params["wid"].append(str(region))
                case _:
                    raise ValueError(f"Invalid region type: {region}")

        resp = self._request(
            "GET",
            self.base_url,
            params=params,
        )
        resp.raise_for_status()
        return resp.json()

    def _parse_german_date(self, date_str: str) -> datetime.date:
        # Map of German month names (abbreviations with and without dots) to month numbers
        month_map = {
            "Jan.": 1,
            "Feb.": 2,
            "Mär.": 3,
            "Apr.": 4,
            "Mai.": 5,
            "Jun.": 6,
            "Jul.": 7,
            "Aug.": 8,
            "Sep.": 9,
            "Okt.": 10,
            "Nov.": 11,
            "Dez.": 12,
            "Jan": 1,
            "Feb": 2,
            "Mär": 3,
            "Apr": 4,
            "Mai": 4,
            "Jun": 6,
            "Jul": 7,
            "Aug": 8,
            "Sep": 9,
            "Okt": 10,
            "Nov": 11,
            "Dez": 12,
        }

        # Remove weekday (e.g., "Donnerstag, ")
        if "," in date_str:
            date_str = date_str.split(",")[1].strip()

        # Extract day, month (as string), and year
        match = re.match(r"(\d{2})\.\s*([A-Za-zäöüÄÖÜß\.]+)\s+(\d{4})", date_str)
        if not match:
            raise ValueError(f"Invalid date format: {date_str}")

        day_str, month_str, year_str = match.groups()

        # Convert German month name to month number
        month = month_map.get(month_str)
        if not month:
            raise ValueError(f"Unknown German month name: {month_str}")

        return datetime.date(int(year_str), month, int(day_str))

    def _lookup_date(self, hashlist: list[dict[str, str]], hash: int) -> datetime.date:
        for item in hashlist:
            date_hash = str(hash)
            if date_hash in item:
                return self._parse_german_date(item[date_hash])
        raise ValueError(f"Date not found for hash: {hash}")

    def get_data(
        self,
        from_year: int,
        to_year: int,
        regions: list[RegionType | int],
    ) -> list[Records]:
        raw_data = self.get_raw_data(from_year, to_year, regions)
        series: list[Records] = []
        for serie in raw_data["chart_data"]["Series"]:
            records: list[Record] = []
            for date_hash, value in serie["data"]:
                date = self._lookup_date(serie["yCurrentDateHash"], date_hash)
                records.append(
                    {
                        "value": value,
                        "date": date,
                    }
                )

            dataframe = pl.DataFrame(
                [
                    pl.Series("dates", [record["date"] for record in records]),
                    pl.Series("values", [record["value"] for record in records]),
                ]
            )
            series.append(
                {
                    "name": serie["name"],
                    "data_key": serie["dataKey"],
                    "year": int(serie["yearId"]),
                    "records": records,
                    "dataframe": dataframe,
                }
            )
        return series


def choose_queen_color(year: int) -> str:
    match year % 10:
        case 0 | 5:
            return "tab:blue"
        case 1 | 6:
            return "tab:black"
        case 2 | 7:
            return "tab:olive"
        case 3 | 8:
            return "tab:red"
        case 4 | 9:
            return "tab:green"
        case _:
            raise ValueError("Invalid year for queen color selection.")


def get_axis_arrays(
    records: list[Record], year: int, min_month: int, max_month: int
) -> tuple[list[float], list[float]]:
    x_data = []
    y_data = []
    for record in records:
        if record["date"].month < min_month or record["date"].month > max_month:
            continue
        try:
            x_data.append(mdates.date2num(record["date"].replace(year=year)))
            y_data.append(record["value"])
        except ValueError:
            continue

    return x_data, y_data


def plot_honey_yield_progress(
    data: list[Records],
    suptitle: str,
    filename: str,
    title: str = "Trachtverlauf im aktuellen Jahr und Vorjahre",
) -> None:
    xlabel = "Monat"
    ylabel = "Kumulierte korrigierte Gewichtänderung [kg]"

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.set_title(title)
    fig.suptitle(suptitle)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid()
    # ax.xaxis.set_major_formatter(mdates.DateFormatter('%b'))
    # ax.xaxis.set_minor_formatter(mdates.DateFormatter('%b'))

    locator = mdates.AutoDateLocator()
    formatter = mdates.ConciseDateFormatter(locator)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)
    ax.xaxis.set_minor_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
    ax.yaxis.set_minor_locator(tck.AutoMinorLocator())

    today = datetime.date.today()

    for records in data:
        year = records["year"]
        x_data, y_data = get_axis_arrays(
            records["records"], year=today.year, min_month=3, max_month=7
        )
        ax.plot(x_data, y_data, label=year, color=choose_queen_color(year))

        df = records["dataframe"]
        min_value = df["values"].min()
        min_date = df["dates"][df["values"].arg_min()]

        ax.annotate(
            # min_date.strftime("%d.%m.%Y"),
            "",
            xy=(mdates.date2num(min_date.replace(year=today.year)), min_value),
            xycoords="data",
            xytext=(-20, 40),
            textcoords="offset points",
            bbox=dict(boxstyle="square", fc="w"),
            # rotation=15,
            arrowprops=dict(
                facecolor="black",
                arrowstyle="->",
                connectionstyle="arc3",
            ),
            size=9,
        )

        # Skip the max value for the current year.
        if records["year"] == today.year:
            continue

        max_value = df["values"].max()
        max_date = df["dates"][df["values"].arg_max()]
        ax.annotate(
            max_date.strftime("%d.%m.%Y"),
            xy=(mdates.date2num(max_date.replace(year=today.year)), max_value),
            xycoords="data",
            xytext=(25, 4),
            textcoords="offset points",
            bbox=dict(boxstyle="square", fc="w"),
            arrowprops=dict(
                facecolor="black",
                arrowstyle="->",
                connectionstyle="arc3",
            ),
            size=9,
        )

    ax.axvline(
        mdates.date2num(today),
        color=choose_queen_color(today.year),
        linestyle="dotted",
        label=today.strftime("heute (%d.%m.%Y)"),
    )

    ax.legend()
    fig.savefig(filename, pad_inches=0, bbox_inches="tight")


def plot_2024_bayern(data: Records) -> None:
    xlabel = "Monat"
    ylabel = "Kumulierte korrigierte Gewichtänderung [kg]"

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.set_title("Bayern 2024")
    # fig.suptitle(suptitle)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid()

    locator = mdates.AutoDateLocator()
    formatter = mdates.ConciseDateFormatter(locator)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)
    ax.xaxis.set_minor_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
    ax.yaxis.set_minor_locator(tck.AutoMinorLocator())

    df = data["dataframe"]
    year = data["year"]
    min_value = df["values"].min()
    min_date = df["dates"][df["values"].arg_min()]
    max_value = df["values"].min()
    max_date = df["dates"][df["values"].arg_max()]

    # NOTE: Peaks were found using the following code:
    # peaks = df.select(pl.col("values").peak_min())["values"].to_list()
    #
    # for index, is_peak in enumerate(peaks):
    #     if is_peak:
    #         print(f"index {index}  {df["dates"][index]}")
    #         print(f"index {index}  {df["values"][index]}")

    x_data, y_data = get_axis_arrays(
        data["records"], year=year, min_month=3, max_month=8,
    )
    ax.plot(
        x_data, y_data, label=f"Trachtverlauf {year}", color=choose_queen_color(year),
    )

    ax.annotate(
        f"Kälteeinbruch ({df['dates'][104].strftime('%d.%m.%Y')})",
        xy=(mdates.date2num(df["dates"][104]), df["values"][104]),
        xycoords="data",
        xytext=(-80, 20),
        textcoords="offset points",
        bbox=dict(boxstyle="square", fc="w"),
        arrowprops=dict(
            facecolor="black",
            arrowstyle="->",
            connectionstyle="arc3",
        ),
        size=9,
    )
    ax.annotate(
        f"Beginn Melizitosetracht ({df['dates'][162].strftime('%d.%m.%Y')})",
        xy=(mdates.date2num(df["dates"][162]), df["values"][162]),
        xycoords="data",
        xytext=(50, 10),
        textcoords="offset points",
        bbox=dict(boxstyle="square", fc="w"),
        arrowprops=dict(
            facecolor="black",
            arrowstyle="->",
            connectionstyle="arc3",
        ),
        size=9,
    )

    ax.annotate(
        min_date.strftime("Trachtbeginn (%d.%m.%Y)"),
        xy=(mdates.date2num(min_date), min_value),
        xycoords="data",
        xytext=(-110, 30),
        textcoords="offset points",
        bbox=dict(boxstyle="square", fc="w"),
        # rotation=15,
        arrowprops=dict(
            facecolor="black",
            arrowstyle="->",
            connectionstyle="arc3",
        ),
        size=9,
    )

    max_value = df["values"].max()
    max_date = df["dates"][df["values"].arg_max()]
    ax.annotate(
        max_date.strftime("Trachtende (%d.%m.%Y)"),
        xy=(mdates.date2num(max_date), max_value),
        xycoords="data",
        xytext=(25, 4),
        textcoords="offset points",
        bbox=dict(boxstyle="square", fc="w"),
        arrowprops=dict(
            facecolor="black",
            arrowstyle="->",
            connectionstyle="arc3",
        ),
        size=9,
    )

    ax.axvline(
        mdates.date2num(datetime.date(2024, 6, 2)),
        color="black",
        linestyle="dotted",
        label="Schleuderung 01",
    )
    ax.annotate(
        "Schleuderung 01",
        xy=(mdates.date2num(datetime.date(2024, 6, 2)), -4),
        xycoords="data",
        xytext=(-15, 0),
        color="black",
        textcoords="offset points",
        bbox=dict(boxstyle="square", fc="w"),
        rotation=90,
        size=9,
    )
    ax.axvline(
        mdates.date2num(datetime.date(2024, 6, 17)),
        color="black",
        linestyle="dotted",
        label="Schleuderung 02",
    )
    ax.annotate(
        "Schleuderung 02",
        xy=(mdates.date2num(datetime.date(2024, 6, 17)), -4),
        xycoords="data",
        xytext=(-15, 0),
        color="black",
        textcoords="offset points",
        bbox=dict(boxstyle="square", fc="w"),
        rotation=90,
        size=9,
    )
    ax.axvline(
        mdates.date2num(datetime.date(2024, 8, 3)),
        color="black",
        linestyle="dotted",
        label="Schleuderung 03",
    )
    ax.annotate(
        "Schleuderung 03",
        xy=(mdates.date2num(datetime.date(2024, 8, 3)), -4),
        xycoords="data",
        xytext=(-15, 0),
        color="black",
        textcoords="offset points",
        bbox=dict(boxstyle="square", fc="w"),
        rotation=90,
        size=9,
    )

    ax.axvspan(mdates.date2num(min_date), mdates.date2num(max_date), color="0.95")
    ax.axvspan(
        mdates.date2num(df["dates"][162]),
        mdates.date2num(df["dates"][172]),
        color="0.9",
    )

    fig.savefig(
        "trachtnet-bayern-2024-auswertung.svg", pad_inches=0, bbox_inches="tight"
    )


def plot_2023_bayern_wetter() -> None:
    # TODO: Maybe this instead: https://meteostat.net There is a json api.
    df = pl.read_csv("scripts/data/wetter-oberpfaffenhofen-saison-2023.csv").with_columns(
        pl.col("date").str.strptime(pl.Date, "%Y-%m-%d %H:%M:%S"),
        pl.col("tavg").ewm_mean(span=8).alias('tavg_ema'),
        pl.col("prcp").ewm_mean(span=4).alias('prcp_ema')
    )

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(
        list(map(lambda x: mdates.date2num(x), df["date"].to_list())),
        df["tavg_ema"].to_list(),
        color="tab:red",
        label="Temperatur [°C]",
    )
    ax2 = ax.twinx()
    ax2.plot(
        list(map(lambda x: mdates.date2num(x), df["date"].to_list())),
        df["prcp_ema"].to_list(),
        color="tab:blue",
        label="Niederschlag [mm]",
    )
    ax2.set_ylabel("Niederschlag [mm]")
    ax2.set_ylim(top=150)
    
    ax.set_title("Bayern 2023 Wetter")
    ax.set_xlabel("Monat")
    ax.set_ylabel("Temperatur [°C]")
    ax.grid()

    locator = mdates.AutoDateLocator()
    formatter = mdates.ConciseDateFormatter(locator)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)
    ax.xaxis.set_minor_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
    ax.yaxis.set_minor_locator(tck.AutoMinorLocator())
    fig.legend()

    fig.savefig("bayern-2023-wetter.svg", pad_inches=0, bbox_inches="tight")


def plot_2024_bayern_wetter() -> None:
    # TODO: Maybe this instead: https://meteostat.net There is a json api.
    df = pl.read_csv("scripts/data/wetter-oberpfaffenhofen-saison-2024.csv").with_columns(
        pl.col("date").str.strptime(pl.Date, "%Y-%m-%d %H:%M:%S"),
        pl.col("tavg").ewm_mean(span=8).alias('tavg_ema'),
        pl.col("prcp").ewm_mean(span=4).alias('prcp_ema')
    )

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(
        list(map(lambda x: mdates.date2num(x), df["date"].to_list())),
        df["tavg_ema"].to_list(),
        color="tab:red",
        label="Temperatur [°C]",
    )
    ax2 = ax.twinx()
    ax2.plot(
        list(map(lambda x: mdates.date2num(x), df["date"].to_list())),
        df["prcp_ema"].to_list(),
        color="tab:blue",
        label="Niederschlag [mm]",
    )
    ax2.set_ylabel("Niederschlag [mm]")
    ax2.set_ylim(top=150)
    
    ax.set_title("Bayern 2024 Wetter")
    ax.set_xlabel("Monat")
    ax.set_ylabel("Temperatur [°C]")
    ax.grid()

    locator = mdates.AutoDateLocator()
    formatter = mdates.ConciseDateFormatter(locator)
    ax.xaxis.set_major_locator(locator)
    ax.xaxis.set_major_formatter(formatter)
    ax.xaxis.set_minor_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
    ax.yaxis.set_minor_locator(tck.AutoMinorLocator())
    fig.legend()

    ax.axvspan(mdates.date2num(datetime.date(2024, 4, 2)), mdates.date2num(datetime.date(2024, 6, 29)), color="0.95")
    ax.axvspan(
        mdates.date2num(datetime.date(2024, 6, 11)),
        mdates.date2num(datetime.date(2024, 6, 21)),
        color="0.9",
    )

    fig.savefig("bayern-2024-wetter.svg", pad_inches=0, bbox_inches="tight")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch and plot Trachtnet data for a given region.",
    )
    parser.add_argument(
        "--from-year",
        type=int,
        default=2022,
        help="Start year for fetching data (default: 2022)",
    )
    parser.add_argument(
        "--to-year",
        type=int,
        default=datetime.date.today().year,
        help="End year for fetching data (default: current year)",
    )

    parser.add_argument(
        "--region",
        type=str,
        nargs="+",
        choices=regions_list,
        metavar="REGION",
        help="Regions to fetch data for",
    )
    parser.add_argument(
        "--station-id",
        type=int,
        nargs="+",
        help="Individual station ID",
    )
    parser.add_argument(
        "--name",
        type=str,
        help="Super title for the plot",
    )
    parser.add_argument(
        "--show-regions",
        action="store_true",
        help="Show all available regions and exit",
    )
    parser.add_argument(
        "--chosen-evaluations",
        action="store_true",
        help="Do chosen evaluations",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    locale.setlocale(locale.LC_ALL, "de_DE.UTF-8")

    client = TrachtnetClient(
        "https://dlr-web-daten1.aspdienste.de/cgi-bin/tdsa/tdsa_client.pl"
    )

    if args.chosen_evaluations:
        data = client.get_data(
            from_year=2024,
            to_year=2024,
            regions=[Land.BAYERN],
        )

        plot_2024_bayern(data[0])
        plot_2023_bayern_wetter()
        plot_2024_bayern_wetter()

        sys.exit(0)

    if args.show_regions:
        for region in regions_list:
            print(region)
        sys.exit(0)

    regions: list[RegionType | int] = []
    if args.region:
        for region in args.region:
            try:
                regions.append(Land[region.upper()])
                continue
            except KeyError:
                pass
            try:
                regions.append(Regierungsbezirk[region.upper()])
                continue
            except KeyError:
                pass

            regions.append(Kreis[region.upper()])

    if args.station_id:
        regions.extend(args.station_id)

    if not regions:
        print("No regions specified. Use --region or --station-id to specify regions.")
        sys.exit(1)

    data = client.get_data(
        from_year=args.from_year,
        to_year=args.to_year,
        regions=regions,
    )
    plot_honey_yield_progress(
        data=data,
        suptitle=args.name,
        filename=f"trachtnet-{args.name.lower().replace(' ', '-').replace('(', '').replace(')', '').replace('.', '')}.svg",
    )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
