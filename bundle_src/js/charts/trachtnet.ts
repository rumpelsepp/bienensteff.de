import { Temporal } from "@js-temporal/polyfill";
import type { ECharts } from 'echarts';
import * as echarts from 'echarts';

import { chooseQueenColor, getCurrentYear, getToday, getXLimits, isInteger, isIntegerArray, isInSeason } from "./helpers";
import { toTitleCase } from '../helpers';
import { buildBaseOption, buildFormatterDE, initEchartsInstance } from "./base";

type Record = {
    date: Temporal.PlainDate,
    value: number,
    nWaagen: number,
    delta: number | null
}
type YearlyData = {
    [year: number]: Record[]
}
type TrachtNetData = {
    [region: string]: YearlyData,
}
// One line of a /trachtnet-dump/<kind>/<id>-<year>.ndjson file, see
// scripts/src/bstools/cli/dump_trachtnet.py. Empty days, junk zeros and the
// still-provisional last two days are already filtered out there.
type TrachtNetRawData = {
    date: string,
    weight: number,
    delta: number | null,
    scales: number,
}
// An entry of /trachtnet-dump/index.json.
type TrachtNetRegion = {
    kind: "bundesland" | "regierungsbezirk" | "landkreis" | "waage",
    id: string,
    name: string,
    slug: string,
    years: number[],
}

function formatRecord(record: Record): string {
    return `date: ${record.date.toLocaleString()}; value: ${record.value}; nWaagen: ${record.nWaagen}; delta: ${record.delta}`;
}

function normalizeYear(records: Record[]): Record[] {
    return records.map(r => {
        let today = Temporal.Now.plainDateISO();
        return {
            date: r.date.with({ "year": today.year }),
            value: r.value,
            nWaagen: r.nWaagen,
            delta: r.delta
        };
    });
}
let regionIndex: Promise<TrachtNetRegion[]> | null = null;

function loadRegionIndex(): Promise<TrachtNetRegion[]> {
    regionIndex ??= fetch("/trachtnet-dump/index.json").then(async response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return (await response.json()).regions as TrachtNetRegion[];
    });
    return regionIndex;
}

// Same lookup order as before the index existed: a number is a scale id,
// otherwise the slug is matched against Bundesländer first, then
// Regierungsbezirke, then Landkreise (e.g. "berlin" is the Bundesland).
async function resolveRegion(region: string): Promise<TrachtNetRegion> {
    const regions = await loadRegionIndex();
    const key = region.toLowerCase();
    let found: TrachtNetRegion | undefined;
    if (isInteger(+key)) {
        const id = key.padStart(4, "0");
        found = regions.find(r => r.kind === "waage" && r.id === id);
    } else {
        for (const kind of ["bundesland", "regierungsbezirk", "landkreis"]) {
            found = regions.find(r => r.kind === kind && r.slug === key);
            if (found) {
                break;
            }
        }
    }
    if (!found) {
        throw new Error(`Unknown region: ${region}`);
    }
    return found;
}

async function fetchRegion(year: number, region: string): Promise<TrachtNetRawData[]> {
    const r = await resolveRegion(region);
    if (!r.years.includes(year)) {
        throw new Error(`No data for ${r.name} in ${year}`);
    }

    const response = await fetch(`/trachtnet-dump/${r.kind}/${r.id}-${year}.ndjson`);
    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }
    return (await response.text())
        .split("\n")
        .filter(line => line.trim() !== "")
        .map(line => JSON.parse(line) as TrachtNetRawData);
}

export async function fetchTrachtnetData(years: number | number[], region: string): Promise<TrachtNetData> {
    if (!isInteger(years) && !isIntegerArray(years)) {
        throw new Error("Year must be an integer or an array of integers.");
    }

    if (isInteger(years)) {
        years = [years];
    } else {
        // Sort and remove duplicates.
        years = [... new Set(years.sort((a, b) => a - b))];
    }

    const currentYear = getCurrentYear();

    let out: TrachtNetData = {};
    let yearlyData: YearlyData = out[region] = {};

    for (const y of years) {
        if (!isInteger(y) || y < 2011 || y > currentYear) {
            throw new Error(`Invalid year: ${y}. Trachtnet only has data from 2011 to the current year.`);
        }

        let rawData: TrachtNetRawData[];
        try {
            rawData = await fetchRegion(y, region);
        } catch (error) {
            // console.error(`Error fetching data for year ${y} and region ${region}:`, error);
            continue;
        }

        yearlyData[y] = rawData.map(d => ({
            date: Temporal.PlainDate.from(d.date),
            value: d.weight,
            nWaagen: d.scales,
            delta: d.delta,
        }));
    }

    return out;
}

export async function getTrachtnetSeries(year: number | number[], region: string, normalize: boolean = false): Promise<echarts.LineSeriesOption[]> {
    const data = await fetchTrachtnetData(year, region);
    let out: echarts.LineSeriesOption[] = [];

    for (const [year, records] of Object.entries(data[region])) {
        if (!isInteger(+year)) {
            throw new Error(`Invalid year in data: ${year}`);
        }

        let seriesData = (normalize ? normalizeYear(records) : records).map(r => {
            return [
                r.date.toString(),
                r.value,
                r.nWaagen,
                r.delta
            ];
        });

        let entry: echarts.LineSeriesOption = {
            name: year.toString(),
            type: "line",
            showSymbol: false,
            data: seriesData,
            lineStyle: {
                color: chooseQueenColor(+year),
            },
        };

        if (getCurrentYear() === +year) {
            entry.markLine = {
                symbol: "none",
                label: {
                    formatter: getToday().toLocaleString(),
                    fontSize: 10,
                },
                lineStyle: {
                    type: "dashed",
                    color: "#000",
                },
                data: [
                    { xAxis: getToday().toString() }
                ]
            }
        }
        out.push(entry);
    }

    return out;
}

export async function getTrachtnetDerivative(years: number | number[], region: string): Promise<echarts.BarSeriesOption[]> {
    if (!isInteger(years) && !isIntegerArray(years)) {
        throw new Error("Year must be an integer or an array of integers.");
    }

    if (isInteger(years)) {
        years = [years];
    } else {
        // Sort and remove duplicates.
        years = [... new Set(years.sort((a, b) => a - b))];
    }

    const rawData = await fetchTrachtnetData(years, region);

    let entries: echarts.BarSeriesOption[] = [];
    years.forEach(y => {
        let records = rawData[region][y];
        records = normalizeYear(records);
        let lastIndex = records.findLastIndex(r => r.nWaagen !== null);

        // Slice the data to only include entries with valid nWaagen.
        records = lastIndex === -1 ? records : records.slice(0, lastIndex + 1);

        let seriesData = records.map(r => {
            const color = r.delta! >= 0 ? chooseQueenColor(y) : chooseQueenColor(y, true);
            return { value: [r.date.toString(), r.delta, r.value, r.nWaagen], itemStyle: { color: color } };
        });

        let entry: echarts.BarSeriesOption = {
            name: y.toString(),
            type: "bar",
            data: seriesData,
        };

        entries.push(entry);
    });

    return entries;
}

function buildLegendSelectedCurPrev(allYears: number[]): { [key: string]: boolean } {
    const currentYear = getCurrentYear();
    const activeYears = [currentYear, currentYear - 1];

    const selected: { [key: string]: boolean } = {};
    for (const year of allYears) {
        selected[year.toString()] = activeYears.includes(year);
    }
    return selected;
}

function buildLegendSelectedCur(allYears: number[]): { [key: string]: boolean } {
    const currentYear = getCurrentYear();
    const activeYears = [currentYear];

    const selected: { [key: string]: boolean } = {};
    for (const year of allYears) {
        selected[year.toString()] = activeYears.includes(year);
    }
    return selected;
}

type MetaData = {
    year: number;
    region: string;
    globalMax: Record,
    globalMin: Record,
    maxDelta: Record,
};

export function metaDataOfYear(year: number, region: string, rawData: TrachtNetData): MetaData | null {
    const data = rawData[region]?.[year];
    if (!data || data.length === 0) {
        return null;
    }

    const maxData = data.reduce<Record | null>((max, current) => {
        if (isInSeason(current.date)) {
            if (max === null || current.value >= max.value) {
                return current;
            }
        }
        return max;
    }, null);
    const minData = data.reduce<Record | null>((min, current) => {
        if (min === null || current.value < min.value) {
            return current;
        }
        return min;
    }, null);
    const maxDelta = data.reduce<Record | null>((max, current) => {
        if (isInSeason(current.date)) {
            if (max === null || current.delta === null || max.delta === null || current.delta >= max.delta) {
                return current;
            }
        }
        return max;
    }, null);

    if (maxData === null || minData === null || maxDelta === null) {
        return null;
    }

    return {
        year: year,
        // TODO: Capitalize the first letter of the region name.
        // This assumes that the region is a string and not an enum.
        region: toTitleCase(region),
        globalMax: maxData,
        globalMin: minData,
        maxDelta: maxDelta,
    }
}

export function renderMetaData(data: MetaData): string {
    const formatterDE = new Intl.NumberFormat("de-DE", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
    let out = `<table class="table table-bordered table-striped table-sm">
  <caption>Auswertung von ${data.region} (${data.year})</caption>
  <tbody>
    <tr><th scope="row">Jahresminimum</th><td>${data.globalMin.date.toLocaleString()} (${formatterDE.format(data.globalMin.value)} kg)</td></tr>
    <tr><th scope="row">Jahresmaximum</th><td>${data.globalMax.date.toLocaleString()} (${formatterDE.format(data.globalMax.value)} kg)</td></tr>
    <tr><th scope="row">Bester Tag</th><td>${data.maxDelta.date.toLocaleString()} (Δ ${formatterDE.format(data.maxDelta.delta!)} kg)</td></tr>
  </tbody>
</table>`;
    return out;
}

export class LineChart {
    private title: string;
    private subTitle: string;
    private chart?: ECharts;

    constructor(title: string) {
        this.title = title;
        this.subTitle = "Aufsummierte Gewichtsänderung pro Tag [kg]";
    }

    render(elementID: string) {
        this.chart = initEchartsInstance(elementID);

        const formatterDE = buildFormatterDE();
        const [startDate, endDate] = getXLimits();

        const tooltipFormatter = (params: any): string => {
            let out = "";
            for (const p of params) {
                const prefix = `${p.marker} <b>${p.seriesName}</b>`;
                const waagen = p.value[2];
                if (waagen === null) {
                    continue;
                }
                const delta = p.value[3];
                if (delta !== null) {
                    out += `${prefix}: ${formatterDE.format(p.value[1])} kg (Δ ${formatterDE.format(delta)} kg, ${p.value[2]} Waagen)<br>`;
                } else {
                    out += `${prefix}: ${formatterDE.format(p.value[1])} kg (${p.value[2]} Waagen)<br>`;
                }
            }
            return out;
        };

        const option: echarts.EChartsOption = {
            ...buildBaseOption(this.title, this.subTitle, tooltipFormatter),
            yAxis: {
                type: "value",
                name: "Gewicht [kg]",
                nameLocation: 'middle',
                nameGap: 55,
                axisLine: {
                    show: true,
                    lineStyle: {
                        color: "#000"
                    }
                },
                axisLabel: {
                    formatter: val => Math.trunc(val) + " kg"
                },
                axisTick: {
                    show: true,
                    lineStyle: {
                        color: "#000"
                    }
                },
                minorTick: {
                    show: true,
                    splitNumber: 5,
                    lineStyle: {
                        color: "#000"
                    }
                },
                minorSplitLine: {
                    show: true
                }
            },
            dataZoom: [
                {
                    type: "inside",
                    xAxisIndex: 0,
                    startValue: startDate.toString(),
                    endValue: endDate.toString(),
                }
            ],
        };

        this.chart.setOption(option);
    }

    setData(data: echarts.LineSeriesOption[]) {
        this.chart!.setOption({
            series: data,
            legend: {
                show: true,
                top: "bottom",
                selected: buildLegendSelectedCurPrev(data.map(s => {
                    return parseInt(typeof s.name === "string" ? s.name : "");
                })),
            },
        });
    }
}

export class BarChart {
    private title: string;
    private subTitle: string;
    private chart?: ECharts;

    constructor(title: string) {
        this.title = title;
        this.subTitle = "Gewichtsänderung pro Tag [kg]";
    }

    render(elementID: string) {
        this.chart = initEchartsInstance(elementID);

        const formatterDE = buildFormatterDE();
        const [startDate, _] = getXLimits();

        const tooltipFormatter = (params: any): string => {
            let out = "";
            for (const p of params) {
                const nWaagen = p.value[3];
                const prefix = `${p.marker} <b>${p.seriesName}</b>`;
                out += `${prefix}: Δ ${formatterDE.format(p.value[1])} kg (${nWaagen} Waagen)<br>`;
            }
            return out;
        };

        const option: echarts.EChartsOption = {
            ...buildBaseOption(this.title, this.subTitle, tooltipFormatter),
            yAxis: {
                type: "value",
                name: "Gewichtsänderung [kg]",
                nameLocation: 'middle',
                nameGap: 55,
                axisLine: {
                    show: true,
                    lineStyle: {
                        color: "#000"
                    }
                },
                axisLabel: {
                    formatter: val => Intl.NumberFormat("de-DE", {
                        minimumFractionDigits: 1,
                        maximumFractionDigits: 1
                    }).format(val) + " kg"
                },
                axisTick: {
                    show: true,
                    lineStyle: {
                        color: "#000"
                    }
                },
                minorTick: {
                    show: true,
                    splitNumber: 5,
                    lineStyle: {
                        color: "#000"
                    }
                },
                minorSplitLine: {
                    show: true
                }
            },
            dataZoom: [
                {
                    type: "inside",
                    xAxisIndex: 0,
                    startValue: startDate.toString(),
                    endValue: getToday().toString(),
                }
            ],
        };

        this.chart!.setOption(option);
    }

    setData(data: echarts.BarSeriesOption[]) {
        this.chart!.setOption({
            series: data,
            legend: {
                show: true,
                top: "bottom",
                selected: buildLegendSelectedCur(data.map(s => {
                    return parseInt(typeof s.name === "string" ? s.name : "");
                }))
            },
        });
    }
}
