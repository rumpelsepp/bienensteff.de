"""Coordinates of a location from its BayernAtlas link.

The locations in Grist carry links to the BayernAtlas, usually short links
(v.bayern.de/…) that redirect to atlas.bayern.de/?c=EAST,NORTH&…. The
centre `c` is in ETRS89 / UTM zone 32N (EPSG:25832); utm32_to_wgs84()
turns it into latitude/longitude.
"""

import logging
import math
from dataclasses import dataclass
from urllib.parse import parse_qs, urlsplit

from bstools import httpclient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Lage:
    lat: float
    lon: float

    @property
    def koordinaten(self) -> str:
        """ "48.26612, 11.66991" -- decimal degrees, about 1 m."""
        return f"{self.lat:.5f}, {self.lon:.5f}"


def utm32_to_wgs84(east: float, north: float) -> tuple[float, float]:
    """UTM zone 32N (GRS80 = WGS84 to well below a metre here) to
    (latitude, longitude) in degrees -- the usual series expansion, accurate
    to centimetres within the zone."""
    a = 6378137.0
    f = 1 / 298.257222101
    k0 = 0.9996
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)
    x = east - 500000.0
    m = north / k0
    mu = m / (a * (1 - e2 / 4 - 3 * e2**2 / 64 - 5 * e2**3 / 256))
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    phi1 = (
        mu
        + (3 * e1 / 2 - 27 * e1**3 / 32) * math.sin(2 * mu)
        + (21 * e1**2 / 16 - 55 * e1**4 / 32) * math.sin(4 * mu)
        + (151 * e1**3 / 96) * math.sin(6 * mu)
        + (1097 * e1**4 / 512) * math.sin(8 * mu)
    )
    sin1, cos1, tan1 = math.sin(phi1), math.cos(phi1), math.tan(phi1)
    n1 = a / math.sqrt(1 - e2 * sin1**2)
    t1 = tan1**2
    c1 = ep2 * cos1**2
    r1 = a * (1 - e2) / (1 - e2 * sin1**2) ** 1.5
    d = x / (n1 * k0)
    lat = phi1 - (n1 * tan1 / r1) * (
        d**2 / 2
        - (5 + 3 * t1 + 10 * c1 - 4 * c1**2 - 9 * ep2) * d**4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1**2 - 252 * ep2 - 3 * c1**2) * d**6 / 720
    )
    lon = (
        d
        - (1 + 2 * t1 + c1) * d**3 / 6
        + (5 - 2 * c1 + 28 * t1 - 3 * c1**2 + 8 * ep2 + 24 * t1**2) * d**5 / 120
    ) / cos1
    return math.degrees(lat), 9.0 + math.degrees(lon)


def atlas_centre(url: str) -> tuple[float, float] | None:
    """East/north of `c=` in an atlas.bayern.de URL, or None."""
    c = parse_qs(urlsplit(url).query).get("c", [""])[0]
    try:
        east, north = (float(v) for v in c.split(","))
    except ValueError:
        return None
    return east, north


def lage(url: str, client: httpclient.Client | None = None) -> Lage | None:
    """The position a BayernAtlas link points at; a short link is followed
    first. None for an empty link, a link without position, or when the
    short link cannot be resolved (logged as a warning)."""
    if not url:
        return None
    centre = atlas_centre(url)
    if centre is None and urlsplit(url).hostname == "v.bayern.de":
        try:
            own = client is None
            c = client or httpclient.Client()
            try:
                centre = atlas_centre(c.get(url).url)
            finally:
                if own:
                    c.close()
        except httpclient.TransportError as e:
            logger.warning("Could not resolve %s: %s", url, e)
            return None
    if centre is None:
        logger.warning("No position in %s.", url)
        return None
    return Lage(*utm32_to_wgs84(*centre))
