import * as echarts from "echarts";

import { getCurrentYear } from "./helpers";
import { toTitleCase } from "../helpers";
import { buildFormatterDE, chartColors, initEchartsInstance } from "./base";

// The map chart: the season gain of every Landkreis of Bayern, drawn over
// the county boundaries of /trachtnet-dump/bayern-kreise.geojson (AGS as
// the join key, see the feature's "name") and the numbers of
// /trachtnet-dump/landkreis-summary.json -- both written by the scripts of
// this site, the GeoJSON once from BKG VG250 data (dl-de/by-2.0), the
// summary by scripts/src/bstools/cli/summarize_trachtnet.py.

// A region of the summary: what it knows about a Landkreis's year.
type YearSummary = {
    // The sum of the days' positive deltas of the season [kg].
    gain: number,
    // The highest cumulative weight of the season [kg].
    peak: number,
    // The median number of scales that reported on a day -- how
    // trustworthy the average over them is.
    scales: number,
};

type Summary = {
    kind: "landkreis",
    years: number[],
    regions: Record<string, {
        name: string,
        slug: string,
        years: Record<string, YearSummary>,
    }>,
};

// A feature of the map's GeoJSON, see the comment at the top.
type GeoFeature = {
    properties: {
        // ECharts matches the series data by this -- the AGS.
        name: string,
        ags: string,
        gen: string,
        bez: string,
    },
};

const MAP_NAME = "bayern-kreise";

// Both files are fetched once, however often the chart is built anew --
// also when that happens for another colour scheme.
let geoPromise: Promise<GeoFeature[]> | null = null;

function loadMap(): Promise<GeoFeature[]> {
    geoPromise ??= fetch("/trachtnet-dump/bayern-kreise.geojson").then(async response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const geojson = await response.json() as object & { features: GeoFeature[] };
        echarts.registerMap(MAP_NAME, geojson as unknown as Parameters<typeof echarts.registerMap>[1]);
        return geojson.features;
    });
    return geoPromise;
}

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

type RegionData = {
    // The AGS, as the geojson feature's "name".
    name: string,
    // The season gain of the year [kg], null where there is none.
    value: number | null,
    peak: number | null,
    scales: number | null,
    // How the region is called in the tooltip: TrachtNet's name, or the
    // one of the geojson where it has none there (e.g. the kreisfreie
    // Städte without a scale).
    displayName: string,
};

// The season gain per Landkreis as a choropleth: the darker the more the
// colonies brought in during the season. It follows the year the page
// shows; the number of scales behind a region's number -- how much to
// trust it -- and its highest stand are said in the tooltip, where there
// is room for them.
export async function renderMapChart(elementID: string, region: string, year: number) {
    const chart = initEchartsInstance(elementID);
    const colors = chartColors();
    const formatterDE = buildFormatterDE();
    const [features, summary] = await Promise.all([loadMap(), loadSummary()]);

    const data: RegionData[] = features.map(f => {
        const s = summary.regions[f.properties.ags];
        const yearSummary = s?.years[year.toString()];
        return {
            name: f.properties.name,
            value: yearSummary?.gain ?? null,
            peak: yearSummary?.peak ?? null,
            scales: yearSummary?.scales ?? null,
            displayName: s?.name ?? `${f.properties.gen} (${f.properties.bez})`,
        };
    });

    // Where the colour scale ends: the 90th percentile of the year's
    // gains, so a single outstanding region doesn't wash out the rest of
    // the map -- anything above it takes the darkest colour anyway.
    const gains = data.map(d => d.value)
        .filter((v): v is number => v !== null)
        .sort((a, b) => a - b);
    const cap = gains.length > 0
        ? Math.ceil(gains[Math.floor(gains.length * 0.9)] / 10) * 10
        : 100;

    const tooltipFormatter = (params: any): string => {
        const d = data.find(x => x.name === params.name);
        if (!d || d.value === null) {
            const name = d?.displayName ?? params.name;
            return `${name}<br>keine TrachtNet-Daten für ${year}`;
        }
        const waagen = d.scales !== null
            ? `<br>${d.scales} Waage${d.scales === 1 ? "" : "n"} dahinter`
            : "";
        const peak = d.peak !== null
            ? `<br>Höchststand ${formatterDE.format(d.peak)} kg`
            : "";
        return `${d.displayName}<br>Saison-Gesamteintrag: <b>${formatterDE.format(d.value)} kg</b>${waagen}${peak}`;
    };

    const notes = [
        "Summe der Tagesgewinne Mär–Aug je Landkreis [kg], dunkler = mehr",
        "grau: keine Daten · Höchststand und Waagenzahl im Tooltip"
            + (year === getCurrentYear() ? " · laufendes Jahr bis dato" : ""),
    ];

    const option: echarts.EChartsOption = {
        title: {
            text: `Saison-Gesamteintrag ${toTitleCase(region)} ${year}`,
            subtext: notes.join("\n"),
            left: "center",
            textStyle: { color: colors.ink, fontSize: 18 },
            top: 0,
        },
        animation: false,
        aria: {
            enabled: true,
            decal: {
                show: true,
            },
        },
        toolbox: {
            show: true,
            feature: {
                saveAsImage: {},
            },
        },
        tooltip: {
            trigger: "item",
            backgroundColor: colors.surface,
            borderColor: colors.ink,
            borderWidth: 1,
            textStyle: {
                color: colors.ink,
                fontSize: 12,
            },
            extraCssText: "box-shadow: none; padding: 0.3rem 0.4rem",
            formatter: tooltipFormatter,
        },
        visualMap: {
            type: "continuous",
            min: 0,
            max: cap,
            dimension: 0,
            orient: "horizontal",
            left: "center",
            bottom: 0,
            text: ["mehr", "weniger"],
            textStyle: { color: colors.ink },
            // The honey of the site's palette, from pale to dark.
            inRange: {
                color: ["#f6ead0", "#e3bb6d", "#b8720c", "#7d4c05"],
            },
        },
        series: [{
            type: "map",
            map: MAP_NAME,
            roam: true,
            scaleLimit: { min: 1, max: 8 },
            data: data.map(d => ({ name: d.name, value: d.value ?? undefined })),
            // Regions without data stay this colour; the ones with one
            // are coloured by the visualMap.
            itemStyle: {
                areaColor: colors.grid,
                borderColor: colors.ink,
                borderWidth: 0.5,
            },
        }],
    };
    chart.setOption(option);
}
