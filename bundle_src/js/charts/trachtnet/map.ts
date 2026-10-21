// The map chart: the season gain of every Landkreis of Bayern (see
// choropleth.ts), from /trachtnet-dump/landkreis-summary.json, written by
// scripts/src/bstools/cli/summarize_trachtnet.py.

import { scaleLinear } from "d3-scale";
import { quantile } from "simple-statistics";

import { getCurrentYear } from "../helpers";
import { toTitleCase } from "../../helpers";
import { formatDE, mountChart } from "../frame";
import { drawChoropleth, loadKreise, type MapRegion } from "../choropleth";

// A region of the summary: what it knows about a Landkreis's year.
type YearSummary = {
    // The sum of the days' positive deltas of the season [kg].
    gain: number,
    // The highest cumulative weight of the season [kg].
    peak: number,
    // The median number of scales that reported on a day -- how
    // trustworthy the average over them is.
    scales: number,
    // The days of the season with data, and how many there were to have.
    days: number,
    season_days: number,
};

// Below this share of the season's days with data, a region's gain falls
// short of what its colonies brought in: the map hatches it.
const MIN_COVERAGE = 0.9;

type Summary = {
    kind: "landkreis",
    years: number[],
    regions: Record<string, {
        name: string,
        slug: string,
        years: Record<string, YearSummary>,
    }>,
};

let summaryPromise: Promise<Summary> | null = null;

function loadSummary(): Promise<Summary> {
    summaryPromise ??= fetch("/trachtnet-dump/landkreis-summary.json").then(async response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json() as Summary;
    });
    return summaryPromise;
}

// The honey of the site's palette, from pale to dark.
const SCALE_COLORS = ["#f6ead0", "#e3bb6d", "#b8720c", "#7d4c05"];

// The season gain per Landkreis as a choropleth: the darker the more the
// colonies brought in during the season. It follows the year the page
// shows; the number of scales behind a region's number -- how much to
// trust it -- and its highest stand are said in the tooltip. Regions
// without data, or with too patchy data (see MIN_COVERAGE), are grey and
// hatched.
export async function renderMapChart(elementID: string, region: string, year: number) {
    const [features, summary] = await Promise.all([loadKreise(), loadSummary()]);

    const regions: MapRegion[] = features.map(feature => {
        const s = summary.regions[feature.properties.ags];
        const y = s?.years[year.toString()];
        const name = s?.name ?? `${feature.properties.gen} (${feature.properties.bez})`;
        const patchy = y && y.days < MIN_COVERAGE * y.season_days;
        let tooltip = `<b>${name}</b><br>`;
        if (!y) {
            tooltip += `keine TrachtNet-Daten für ${year}`;
        } else {
            tooltip += `Saison-Gesamteintrag: <b>${formatDE.format(y.gain)} kg</b>`
                + `<br>${y.scales} Waage${y.scales === 1 ? "" : "n"} dahinter`
                + `<br>Höchststand ${formatDE.format(y.peak)} kg`;
            if (patchy) {
                tooltip += `<br>lückenhaft: nur ${y.days} von ${y.season_days} Tagen mit Daten`;
            }
        }
        return { feature, value: y && !patchy ? y.gain : null, name, tooltip };
    });

    // Where the colour scale ends: the 90th percentile of the year's
    // gains, so a single outstanding region doesn't wash out the rest of
    // the map -- anything above it takes the darkest colour anyway.
    const gains = regions.flatMap(r => r.value !== null ? [r.value] : []);
    const cap = gains.length > 0 ? Math.ceil(quantile(gains, 0.9) / 10) * 10 : 100;
    const color = scaleLinear<string>()
        .domain(SCALE_COLORS.map((_, i) => cap * i / (SCALE_COLORS.length - 1)))
        .range(SCALE_COLORS)
        .clamp(true);

    const notes = [
        "Summe der Tagesgewinne Mär–Aug je Landkreis [kg]",
        "grau: keine oder lückenhafte Daten · Zahlen im Tooltip",
    ];
    if (year === getCurrentYear()) {
        notes.push("laufendes Jahr bis dato");
    }

    mountChart(elementID, { title: `Saison-Gesamteintrag ${toTitleCase(region)} ${year}`, notes }, canvas => drawChoropleth(canvas, {
        regions,
        color,
        legend: { colors: SCALE_COLORS, low: "weniger", high: "mehr" },
    }));
}
