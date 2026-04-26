import { Temporal } from "@js-temporal/polyfill";
import type { ECharts } from 'echarts';
import * as echarts from 'echarts';

import { toTitleCase } from '../helpers.js';
import { Kreis, Land, Regierungsbezirk } from '../calendars/regions.js';
import de from "./i18n/de.js";

const localTimeZone = Temporal.Now.timeZoneId();
echarts.registerLocale('DE', de);

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
type TrachtNetRawData = {
    dates: string,
    values: number | null,
    n_waagen: number | null,
}

function formatRecord(record: Record): string {
    return `date: ${record.date.toLocaleString()}; value: ${record.value}; nWaagen: ${record.nWaagen}; delta: ${record.delta}`;
}

function getCurrentYear(): number {
    return Temporal.Now.plainDateISO().year;
}

function getToday(): Temporal.PlainDate {
    return Temporal.Now.plainDateISO();
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

enum QueenColor {
    Blue = "#1f77b4",   // tab:blue
    Black = "#000000",  // tab:black
    Olive = "#808000",  // tab:olive
    Red = "#d62728",    // tab:red
    Green = "#2ca02c"   // tab:green
}

function chooseQueenColor(year: number): QueenColor {
    switch (year % 10) {
        case 0:
        case 5:
            return QueenColor.Blue;
        case 1:
        case 6:
            return QueenColor.Black;
        case 2:
        case 7:
            return QueenColor.Olive;
        case 3:
        case 8:
            return QueenColor.Red;
        case 4:
        case 9:
            return QueenColor.Green;
        default:
            throw new Error(`Invalid year for queen color selection: ${year}`);
    }
}

function isInteger(value: unknown): value is number {
    return typeof value === "number" && Number.isInteger(value);
}

function isIntegerArray(value: unknown): value is number[] {
    return Array.isArray(value) && value.every(v => isInteger(v));
}

async function fetchRegion(year: number, region: string): Promise<any> {
    let rawRegion = region.toUpperCase();

    let endpoint = "";
    if (rawRegion in Land) {
        endpoint = `/trachtnet-dump/bundesland/${region.toLowerCase()}-${year}.json`;
    } else if (rawRegion in Regierungsbezirk) {
        endpoint = `/trachtnet-dump/regierungsbezirk/${region.toLowerCase()}-${year}.json`;
    } else if (rawRegion in Kreis) {
        endpoint = `/trachtnet-dump/landkreis/${region.toLowerCase()}-${year}.json`;
    } else if (isInteger(+region)) {
        endpoint = `/trachtnet-dump/waage/${region}-${year}.json`;
    } else {
        throw new Error(`Unknown region: ${region}`);
    }

    let response = await fetch(endpoint);
    if (response.ok) {
        return await response.json();
    } else {
        throw new Error(`HTTP error! status: ${response.status}`);
    }
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
    const today = getToday();
    const yesterday = today.subtract({ "days": 1 })

    let out: TrachtNetData = {};
    let yearlyData: YearlyData = out[region] = {};

    for (const y of years) {
        if (!isInteger(y) || y < 2011 || y > currentYear) {
            throw new Error(`Invalid year: ${y}. Trachtnet only has data from 2011 to the current year.`);
        }

        let json_data: any;
        try {
            json_data = await fetchRegion(y, region);
        } catch (error) {
            // console.error(`Error fetching data for year ${y} and region ${region}:`, error);
            continue;
        }

        let prev: number | null = null;
        yearlyData[y] = json_data.map((d: TrachtNetRawData) => {
            let delta = prev === null ? null : d.values! - prev;
            if (d.values === null) {
                delta = 0;
            }
            prev = d.values;
            return {
                date: Temporal.PlainDate.from(d.dates),
                value: d.values,
                nWaagen: d.n_waagen,
                delta: delta
            };
        }).filter((r: Record) => {
            if (r.value === null || r.nWaagen == 0) {
                return false;
            }
            return true;
        })
        .filter((r: Record) => {
            if (r.date.equals(today) || r.date.equals(yesterday)) {
                return false;
            }
            return true;
        });
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
        let data = rawData[region][y];
        let lastIndex = data.findLastIndex(r => r.nWaagen !== null);

        // Slice the data to only include entries with valid nWaagen.
        data = lastIndex === -1 ? data : data.slice(0, lastIndex + 1);

        let seriesData = data.map(r => {
            let color = r.delta! >= 0 ? QueenColor.Green.toString() : QueenColor.Red.toString();
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

function isInSeason(date: Temporal.PlainDate): boolean {
    if (date.month >= 3 && date.month <= 8) {
        return true;
    }
    return false;
}

export function metaDataOfYear(year: number, region: string, rawData: TrachtNetData): MetaData | null {
    const data = rawData[region][year];
    
    const maxData = data.reduce((max, current) => {
        if (isInSeason(current.date)) {
            if (max === null || current.value >= max.value) {
                return current;
            }
        }
        return max;
    });
    const minData = data.reduce((min, current) => {
        if (min === null || current.value < min.value) {
            return current;
        }
        return min;
    });
    const maxDelta = data.reduce((max, current) => {
        if (isInSeason(current.date)) {
            if (max === null || current.delta === null || max.delta === null || current.delta >= max.delta) {
                return current;
            }
        }
        return max;
    });
    
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

function getXLimits(): [Temporal.PlainDate, Temporal.PlainDate] {
    const today = getToday();
    let startDate: Temporal.PlainDate;
    let endDate: Temporal.PlainDate;
    if ((today.month < 4) || (today.month > 6)) {
        startDate = today.with({ "month": 1, "day": 1 });
        endDate = today.with({ "month": 12, "day": 31 });
    } else {
        startDate = today.with({ "month": 4, "day": 1 });
        endDate = today.add({ "days": 45 });
    }

    return [startDate, endDate];
}

function axisPointerCallback(value: number): string {
    const date = Temporal.Instant.fromEpochMilliseconds(value).toZonedDateTimeISO(localTimeZone).toPlainDate();
    return date.toLocaleString();
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
        const chartContainer = document.getElementById(elementID);
        if (!chartContainer) {
            throw new Error(`Element with ID ${elementID} not found.`);
        }

        this.chart = echarts.init(chartContainer, null, {
            renderer: "svg",
            locale: "DE",
        });

        const formatterDE = new Intl.NumberFormat("de-DE", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });

        const [startDate, endDate] = getXLimits();

        const option: echarts.EChartsOption = {
            title: {
                text: this.title,
                subtext: this.subTitle,
                left: "center",
                textStyle: {
                    color: "#000",
                },
                top: 0,
            },
            animation: false,
            aria: {
                enabled: true,
                decal: {
                    show: true
                }
            },
            toolbox: {
                show: true,
                feature: {
                    saveAsImage: {}
                }
            },
            tooltip: {
                trigger: "axis",
                backgroundColor: "#fff",
                borderColor: "#000",
                borderWidth: 1,
                textStyle: {
                    color: "#000",
                    fontSize: 12
                },
                extraCssText: "box-shadow: none; padding: 0.3rem 0.4rem",
                formatter: params => {
                    let out = "";
                    // @ts-expect-error
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
                }
            },
            xAxis: {
                type: "time",
                axisLine: {
                    onZero: false,
                    lineStyle: {
                        color: "#000"
                    }
                    // TODO: https://echarts.apache.org/en/option.html#xAxis.axisLabel.formatter
                },
                axisPointer: {
                    label: {
                        show: true,
                        formatter: params => {
                            const value = params.value;
                            if (!isInteger(value)) {
                                throw new Error("Date axis expected!");
                            }
                            return axisPointerCallback(value);
                        }
                    },
                },
                splitLine: {
                    show: true,
                    lineStyle: {
                        color: '#eee'
                    }
                }
            },
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

        window.addEventListener("resize", () => {
            this.chart!.resize();
        });
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
        const chartContainer = document.getElementById(elementID);
        if (!chartContainer) {
            throw new Error(`Element with ID ${elementID} not found.`);
        }

        this.chart = echarts.init(chartContainer, null, {
            renderer: "svg",
            locale: "DE",
        });

        const formatterDE = new Intl.NumberFormat("de-DE", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });

        const [startDate, _] = getXLimits();

        const option: echarts.EChartsOption = {
            title: {
                text: this.title,
                subtext: this.subTitle,
                left: "center",
                textStyle: {
                    color: "#000",
                },
                top: 0,
            },
            animation: false,
            aria: {
                enabled: true,
                decal: {
                    show: true
                }
            },
            toolbox: {
                show: true,
                feature: {
                    saveAsImage: {}
                }
            },
            tooltip: {
                trigger: "axis",
                backgroundColor: "#fff",
                borderColor: "#000",
                borderWidth: 1,
                // borderRadius: 0,
                textStyle: {
                    color: "#000",
                    fontSize: 12
                },
                extraCssText: "box-shadow: none; padding: 0.3rem 0.4rem",
                formatter: params => {
                    let out = "";
                    // @ts-expect-error
                    for (const p of params) {
                        const date = Temporal.PlainDate.from(p.value[0])
                        const nWaagen = p.value[3];
                        const prefix = `<b>${date.toLocaleString()}</b>`;
                        out += `${prefix}: Δ ${formatterDE.format(p.value[1])} kg (${nWaagen} Waagen)<br>`;
                    }
                    return out;
                }
            },
            xAxis: {
                type: "time",
                axisLine: {
                    onZero: false,
                    lineStyle: {
                        color: "#000"
                    }
                },
                splitLine: {
                    show: true,
                    lineStyle: {
                        color: '#eee'
                    }
                }
            },
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

        window.addEventListener("resize", () => {
            this.chart!.resize();
        });
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
