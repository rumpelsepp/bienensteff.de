#!/usr/bin/env -S uv run -qs

# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "httpx",
#     "polars",
# ]
# ///

import argparse
import enum
import re
import datetime
import http
import time
from typing import Any, Literal, TypedDict
from pathlib import Path
from urllib.parse import urljoin

import httpx
import polars as pl


@enum.unique
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


@enum.unique
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
    DUESSELDORF = "051"
    KOELN = "053"
    MUENSTER = "055"
    DETMOLD = "057"
    ARNSBERG = "059"


@enum.unique
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

# This list can be found in the HTML source of the Trachtnet page.
waagen_ids = [
    400,
    492,
    517,
    619,
    621,
    625,
    1000,
    1001,
    1003,
    1005,
    1008,
    1010,
    1013,
    1014,
    1016,
    1017,
    1018,
    1021,
    1022,
    1026,
    1027,
    1029,
    1030,
    1033,
    1034,
    1035,
    1036,
    1038,
    1039,
    1040,
    1041,
    1043,
    1045,
    1046,
    1048,
    1049,
    1050,
    1051,
    1052,
    1053,
    1054,
    1055,
    1056,
    1057,
    1059,
    1065,
    1067,
    1068,
    1072,
    1073,
    1074,
    1077,
    1078,
    1079,
    1080,
    1081,
    1082,
    1084,
    1085,
    1086,
    1087,
    1089,
    1090,
    1093,
    1094,
    1095,
    1096,
    1097,
    1100,
    1101,
    1103,
    1105,
    1106,
    1109,
    1111,
    1112,
    1116,
    1117,
    1118,
    1119,
    1121,
    1122,
    1123,
    1126,
    1127,
    1128,
    1131,
    1132,
    1133,
    1134,
    1137,
    1140,
    1141,
    1142,
    1143,
    1144,
    1145,
    1146,
    1147,
    1148,
    1149,
    1150,
    1154,
    1160,
    1161,
    1162,
    1163,
    1164,
    1167,
    1170,
    1171,
    1172,
    1173,
    1174,
    1175,
    1176,
    1177,
    1179,
    1180,
    1181,
    1182,
    1183,
    1184,
    1185,
    1186,
    1187,
    1190,
    1191,
    1192,
    1193,
    1195,
    1196,
    1197,
    1198,
    1199,
    1200,
    1201,
    1202,
    1204,
    1205,
    1206,
    1207,
    1208,
    1209,
    1210,
    1211,
    1212,
    1214,
    1215,
    1216,
    1217,
    1218,
    1219,
    1221,
    1222,
    1223,
    1224,
    1226,
    1227,
    1228,
    1229,
    1230,
    1231,
    1233,
    1235,
    1236,
    1237,
    1240,
    1241,
    1242,
    1243,
    1245,
    1246,
    1247,
    1248,
    1249,
    1250,
    1252,
    1253,
    1254,
    1255,
    1256,
    1257,
    1259,
    1260,
    1261,
    1262,
    1263,
    1264,
    1265,
    1266,
    1267,
    1269,
    1270,
    1271,
    1272,
    1273,
    1274,
    1275,
    1277,
    1278,
    1279,
    1280,
    1281,
    1282,
    1283,
    1284,
    1286,
    1287,
    1288,
    1289,
    1290,
    1291,
    1293,
    1294,
    1295,
    1297,
    1298,
    1299,
    1300,
    1301,
    1302,
    1303,
    1304,
    1305,
    1306,
    1307,
    1309,
    1310,
    1311,
    1312,
    1313,
    1314,
    1315,
    1317,
    1318,
    1319,
    1321,
    1322,
    1323,
    1324,
    1325,
    1327,
    1328,
    1329,
    1331,
    1332,
    1333,
    1334,
    1335,
    1336,
    1337,
    1338,
    1339,
    1340,
    1341,
    1342,
    1343,
    1344,
    1345,
    1346,
    1347,
    1348,
    1349,
    1350,
    1352,
    1353,
    1354,
    1355,
    1356,
    1357,
    1358,
    1359,
    1360,
    1363,
    1364,
    1367,
    1368,
    1369,
    1371,
    1372,
    1373,
    1375,
    1376,
    1381,
    1383,
    1385,
    1386,
    1387,
    1389,
    1390,
    1392,
    1394,
    1395,
    1398,
    1399,
    1402,
    1403,
    1404,
    1407,
    1408,
    1410,
    1411,
    1414,
    1415,
    1416,
    1417,
    1418,
    1419,
    1421,
    1422,
    1423,
    1424,
    1425,
    1427,
    1428,
    1431,
    1434,
    1435,
    1436,
    1437,
    1438,
    1439,
    1443,
    1444,
    1446,
    1448,
    1449,
    1450,
    1451,
    1452,
    1453,
    1454,
    1455,
    1456,
    1457,
    1460,
    1462,
    1464,
    1465,
    1466,
    1467,
    1469,
    1471,
    1472,
    1474,
    1475,
    1476,
    1477,
    1479,
    1480,
    1481,
    1483,
    1484,
    1485,
    1486,
    1487,
    1488,
    1489,
    1490,
    1491,
    1492,
    1493,
    1494,
    1496,
    1497,
    1498,
    1499,
    1500,
    1501,
    1503,
    1505,
    1506,
    1509,
    1510,
    1511,
    1512,
    1513,
    1514,
    1516,
    1517,
    1518,
    1519,
    1520,
    1521,
    1522,
    1524,
    1525,
    1526,
    1527,
    1528,
    1529,
    1530,
    1531,
    1532,
    1533,
    1534,
    1535,
    1536,
    1537,
    1538,
    1540,
    1541,
    1542,
    1543,
    1544,
    1546,
    1547,
    1548,
    1553,
    1555,
    1561,
    1562,
    1563,
    1564,
    1565,
    1566,
    1567,
    1569,
    1570,
    1571,
    1572,
    1573,
    1574,
    1575,
    1576,
    1577,
    1578,
    1579,
    1580,
    1581,
    1582,
    1583,
    1585,
    1587,
    1591,
    1593,
    1594,
    1595,
    1596,
    1598,
    1599,
    1600,
    1601,
    1602,
    1605,
    1606,
    1607,
    1609,
    1610,
    1611,
    1612,
    1613,
    1614,
    1615,
    1616,
    1617,
    1618,
    1619,
    1620,
    1621,
    1622,
    1623,
    1624,
    1625,
    1628,
    1629,
    1630,
    1631,
    1633,
    1634,
    1635,
    1636,
    1637,
    1639,
    1640,
    1641,
    1642,
    1643,
    1644,
    1645,
    1646,
    1647,
    1648,
    1649,
    1650,
    1651,
    1652,
    1653,
    1654,
    1655,
    1656,
    1657,
    1658,
    1659,
    1660,
    1661,
    1662,
    1663,
    1664,
    1681,
    1683,
    1684,
    1686,
    1688,
    1694,
    1697,
    1698,
    1699,
    1700,
    1701,
    1703,
    1704,
    1705,
    1710,
    1712,
    1713,
    1716,
    1718,
    1719,
    1720,
    1721,
    1722,
    1723,
    1725,
    1726,
    1727,
    1728,
    1730,
    1731,
    1732,
    1734,
    1736,
    1737,
    1738,
    1739,
    1741,
    1742,
    1743,
    1744,
    1745,
    1746,
    1747,
    1748,
    1749,
    1750,
    1751,
    1752,
    1753,
    1754,
    1755,
    1756,
    1757,
    1762,
    1764,
    1765,
    1766,
    1767,
    1768,
    1769,
    1770,
    1771,
    1772,
    1773,
    1774,
    1775,
    1779,
    1781,
    1782,
    1783,
    1784,
    1785,
    1786,
    1787,
    1788,
    1789,
    1791,
    1794,
    1795,
    1796,
    1797,
    1798,
    1801,
    1806,
    1807,
    1808,
    1809,
    1810,
    1811,
    1812,
    1814,
    1817,
    1819,
    1821,
    1822,
    1823,
    1824,
    1826,
    1827,
    1828,
    1829,
    1830,
    1831,
    1833,
    1834,
    1835,
    1836,
    1837,
    1838,
    1840,
    1841,
    1844,
    1846,
    1847,
    1848,
    1849,
    1850,
    1851,
    1853,
    1855,
    1857,
    1858,
    1861,
    1863,
    1865,
    1866,
    1867,
    1868,
    1870,
    1871,
    1872,
    1873,
    1874,
    1875,
    1876,
    1877,
    1878,
    1879,
    1880,
    1882,
    1886,
    1887,
    1888,
    1891,
    1892,
    1894,
    1895,
    1896,
    1897,
    1898,
    1899,
    1901,
    1902,
    1903,
    1904,
    1905,
    1906,
    1907,
    1908,
    1909,
    1911,
    1912,
    1913,
    1914,
    1915,
    1916,
    1917,
    1918,
    1919,
    1920,
    1921,
    1922,
    1923,
    1924,
    1925,
    1926,
    1927,
    1928,
    1929,
    1930,
    1931,
    1932,
    1933,
    1934,
    1935,
    1936,
    1937,
    1938,
    1939,
    1940,
    1941,
    1942,
    1943,
    1944,
    1949,
    1952,
    1953,
    1957,
    1958,
    1959,
    1960,
    1963,
    1964,
    1965,
    1966,
    1967,
    1968,
    1969,
    1974,
    1975,
    1976,
    1977,
    1978,
    1979,
    1980,
    1981,
    1982,
    1983,
    1984,
    1985,
    1986,
    1987,
    1988,
    1989,
    1991,
    1992,
    1993,
    1994,
    1995,
    1997,
    1998,
    1999,
    2000,
    2003,
    2006,
    2008,
    2009,
    2010,
    2011,
    2012,
    2013,
    2014,
    2015,
    2022,
    2024,
    2025,
    2026,
    2027,
    2028,
    2029,
    2030,
    2031,
    2032,
    2033,
    2034,
    2036,
    2037,
    2038,
    2039,
    2040,
    2041,
    2042,
    2043,
    2076,
    2077,
    2078,
    2079,
    2080,
    2081,
    2083,
    2085,
    2086,
    2087,
    2088,
    2089,
    2091,
    2093,
    2095,
    2104,
    2105,
    2106,
    2107,
    2108,
    2110,
    2111,
    2112,
    2113,
    2114,
    2115,
    2116,
    2117,
    2118,
    2119,
    2120,
    2121,
    2122,
    2123,
    2124,
    2125,
    2126,
    2127,
    2133,
    2134,
    2135,
    2136,
    2137,
    2138,
    2139,
    2140,
    2142,
    2143,
    2144,
    2148,
    2149,
    2150,
    2151,
    2152,
    2153,
    2155,
    2156,
    2157,
    2158,
    2159,
    2160,
    2162,
    2163,
    2164,
    2165,
    2166,
    2168,
    2169,
    2170,
    2171,
    2178,
    2179,
    2180,
    2181,
    2182,
    2183,
    2184,
    2185,
    2186,
    2187,
    2189,
    2190,
    2191,
    2192,
    2193,
    2194,
    2195,
    2196,
    2197,
    2198,
    2199,
    2200,
    2201,
    2202,
    2203,
    2204,
    2206,
    2207,
    2208,
    2210,
    2212,
    2213,
    2214,
    2215,
    2216,
    2217,
    2219,
    2220,
    2221,
    2222,
    2223,
    2224,
    2225,
    2226,
    2227,
    2228,
    2229,
    2230,
    2231,
    2232,
    2233,
    2234,
    2235,
    2236,
    2237,
    2239,
    2240,
    2241,
    2242,
    2243,
    2245,
    2246,
    2247,
    2248,
    2249,
    2250,
    2251,
    2252,
    2253,
    2254,
    2255,
    2257,
    2258,
    2259,
    2260,
    2261,
    2262,
    2263,
    2264,
    2266,
    2267,
    2268,
    2269,
    2270,
    2271,
    2272,
    2273,
    2274,
    2275,
    2276,
    2277,
    2278,
    2279,
    2280,
    2281,
    2282,
    2283,
    2284,
    2285,
    2286,
    2287,
    2288,
    2289,
    2290,
    2291,
    2292,
    2293,
    2294,
    2295,
    2296,
    2297,
    2298,
    2299,
    2300,
    2301,
    2302,
    2303,
    2304,
    2305,
    2306,
    2307,
    2308,
    2309,
    2310,
    2311,
    2312,
    2313,
    2314,
    2315,
    2316,
    2317,
    2318,
    2319,
    2320,
    2321,
    2322,
    2324,
    2326,
    2327,
    2328,
    2329,
    2330,
    2331,
    2332,
    2333,
    2334,
    2335,
    2336,
    2337,
    2338,
    2339,
    2340,
    2342,
    2343,
    2344,
    2345,
    2346,
    2347,
    2348,
    2350,
    2351,
    2352,
    2354,
    2355,
    2356,
    2358,
    2359,
    2360,
    2361,
    2362,
    2363,
    2364,
    2365,
    2366,
    2367,
    2368,
    2369,
    2370,
    2371,
    2372,
    2373,
    2374,
    2376,
    2377,
    2378,
    2379,
    2380,
    2381,
    2382,
    2383,
    2384,
    2385,
    2386,
    2387,
    2388,
    2389,
    2390,
    2391,
    2392,
    2393,
    2394,
    2395,
    2396,
    2397,
    2398,
]


type RegionType = Land | Regierungsbezirk | Kreis
regions_list = (
    [region.name.lower() for region in Land]
    + [region.name.lower() for region in Regierungsbezirk]
    + [region.name.lower() for region in Kreis]
)


class Record(TypedDict):
    value: float
    date: datetime.date
    n_waagen: int


class Records(TypedDict):
    year: int
    name: str
    data_key: str
    records: list[Record]
    dataframe: pl.DataFrame


TrachtnetParams = TypedDict(
    "TrachtnetParams",
    {
        "type": Literal["load_chart"],
        "wid": list[str],
        "blid": list[str],
        "rbzid": list[str],
        "lkid": list[str],
        "from": int,
        "to": int,
    },
)


class TrachtnetClient:
    def __init__(self) -> None:
        self.base_url = "https://dlr-web-daten1.aspdienste.de"
        self.user_agent = (
            "Mozilla/5.0 (X11; Linux x86_64; rv:138.0) Gecko/20100101 Firefox/138.0"
        )
        transport = httpx.HTTPTransport(retries=3)
        self.client = httpx.Client(transport=transport)

    def _request(self, method: str, endpoint: str, **kwargs) -> httpx.Response:
        headers = kwargs.pop("headers", {})
        headers["User-Agent"] = self.user_agent
        resp = self.client.request(
            method,
            urljoin(self.base_url, endpoint),
            headers=headers,
            **kwargs,
        )
        resp.raise_for_status()
        return resp

    def get_raw_data(
        self,
        from_year: int,
        to_year: int,
        regions: list[RegionType | int],
    ) -> dict[str, Any]:
        params: TrachtnetParams = {
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
                    params["wid"].append(format(region, "04d"))
                case _:
                    raise ValueError(f"Invalid region type: {region}")

        max_retries = 5
        for _ in range(max_retries):
            try:
                resp = self._request(
                    http.HTTPMethod.GET,
                    "cgi-bin/tdsa/tdsa_client.pl",
                    params=params,
                )
                return resp.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code == http.HTTPStatus.INTERNAL_SERVER_ERROR:
                    print(f"Internal server error for {regions}. Returning empty data.")
                    return {}
                else:
                    raise e
            except httpx.ReadTimeout:
                print("ReadTimeout, trying again…")
                time.sleep(2)
                continue

        print("unknown problem, no data gathered")
        return {}

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

    def _lookup_waagen(self, hashlist: list[dict[str, int]], hash: int) -> int:
        for item in hashlist:
            date_hash = str(hash)
            if date_hash in item:
                return item[date_hash]
        raise ValueError(f"Waagen not found for hash: {hash}")

    def get_data(
        self,
        from_year: int,
        to_year: int,
        regions: list[RegionType | int],
    ) -> list[Records]:
        raw_data = self.get_raw_data(from_year, to_year, regions)
        series: list[Records] = []

        chart_data = raw_data.get("chart_data")
        if not chart_data or not isinstance(chart_data, dict):
            return series

        raw_series = chart_data.get("Series")
        if not raw_series or not isinstance(raw_series, list):
            return series

        for serie in raw_series:
            records: list[Record] = []
            for date_hash, value in serie["data"]:
                date = self._lookup_date(serie["yCurrentDateHash"], date_hash)
                n_waagen = self._lookup_waagen(serie["yAmountWaageHash"], date_hash)
                records.append(
                    {
                        "value": value,
                        "date": date,
                        "n_waagen": n_waagen,
                    }
                )

            dataframe = pl.DataFrame(
                [
                    pl.Series("dates", [record["date"] for record in records]),
                    pl.Series(
                        "values",
                        [
                            float(record["value"])
                            if record["value"] is not None
                            else None
                            for record in records
                        ],
                    ),
                    pl.Series(
                        "n_waagen",
                        [
                            int(record["n_waagen"])
                            if record["n_waagen"] is not None
                            else None
                            for record in records
                        ],
                    ),
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

    def dump_data(self, year: int, region: RegionType | int, outdir: Path) -> None:
        raw_data = self.get_data(year, year, regions=[region])
        name = region.name if isinstance(region, enum.Enum) else str(region)
        if not raw_data:
            print(f"No data found for {name} in {year}")
            return

        match region:
            case Land():
                folder = "bundesland"
            case Regierungsbezirk():
                folder = "regierungsbezirk"
            case Kreis():
                folder = "landkreis"
            case int():
                folder = "waage"
            case _:
                raise ValueError(f"invalid region: {region}")

        outfile = outdir.joinpath(folder).joinpath(f"{name.lower()}-{year}.json")
        outfile.parent.mkdir(parents=True, exist_ok=True)
        outfile.write_text(raw_data[0]["dataframe"].write_json())


def parse_args() -> tuple[argparse.ArgumentParser, argparse.Namespace]:
    parser = argparse.ArgumentParser(
        description="Dump Trachtnet data for a given year and region."
    )
    parser.add_argument(
        "--year",
        type=int,
        nargs="+",
        help="Year to dump data for",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("./trachtnet-dump"),
        help="Output directory for the dumped data",
    )
    return parser, parser.parse_args()


def main() -> None:
    _, args = parse_args()

    year_list = (
        args.year if args.year else list(range(2011, datetime.datetime.today().year))
    )

    client = TrachtnetClient()

    for year in year_list:
        for state in Land:
            print(f"Dumping {year} {state.name}")
            client.dump_data(year, state, args.outdir)
        for county in Regierungsbezirk:
            print(f"Dumping {year} {county.name}")
            client.dump_data(year, county, args.outdir)
        for landkreis in Kreis:
            print(f"Dumping {year} {landkreis.name}")
            client.dump_data(year, landkreis, args.outdir)
        for wid in waagen_ids:
            print(f"Dumping {year} wid {wid}")
            client.dump_data(year, wid, args.outdir)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
