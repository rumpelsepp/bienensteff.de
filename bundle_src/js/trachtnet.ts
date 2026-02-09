import * as echarts from 'echarts';
import type { ECharts } from 'echarts';

import { Land, Regierungsbezirk, Kreis } from './regions.js';

type Record = {
    date: Date,
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

function normalizeYear(records: Record[]): Record[] {
    return records.map(r => {
        let today = new Date();
        let recordDate = new Date(r.date);
        recordDate.setFullYear(today.getFullYear());
        return {
            date: recordDate,
            value: r.value,
            nWaagen: r.nWaagen,
            delta: r.delta
        };
    });
}

function toTitleCase(text: string): string {
    return text.replace(/\w\S*/g, (wort) =>
        wort.charAt(0).toUpperCase() + wort.slice(1).toLowerCase()
    );
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

async function fetchTrachtnetData(years: number | number[], region: string): Promise<TrachtNetData> {
    if (!isInteger(years) && !isIntegerArray(years)) {
        throw new Error("Year must be an integer or an array of integers.");
    }

    if (isInteger(years)) {
        years = [years];
    } else {
        // Sort and remove duplicates.
        years = [... new Set(years.sort((a, b) => a - b))];
    }

    let out: TrachtNetData = {};
    let yearlyData: YearlyData = out[region] = {};
    for (const y of years) {
        if (!isInteger(y) || y < 2011 || y > new Date().getFullYear()) {
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
                date: new Date(d.dates),
                value: d.values,
                nWaagen: d.n_waagen,
                delta: delta
            };
        });
    }

    return out;
}

async function getTrachtnetSeries(year: number | number[], region: string, normalize: boolean = false): Promise<echarts.LineSeriesOption[]> {
    const data = await fetchTrachtnetData(year, region);
    let out: echarts.LineSeriesOption[] = [];

    for (const [year, records] of Object.entries(data[region])) {
        if (!isInteger(+year)) {
            throw new Error(`Invalid year in data: ${year}`);
        }

        let seriesData = (normalize ? normalizeYear(records) : records).map(r => {
            return [
                r.date,
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

        if (new Date().getFullYear() !== +year) {
            entry.markLine = {
                symbol: "none",
                label: {
                    formatter: `heute (${new Date().toLocaleDateString("de-DE")})`,
                    fontSize: 10,
                },
                lineStyle: {
                    type: "dashed",

                },
                data: [
                    { xAxis: new Date().toISOString() }
                ]
            }
        }
        out.push(entry);
    }

    return out;
}

async function getTrachtnetDerivative(years: number | number[], region: string): Promise<echarts.BarSeriesOption[]> {
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
            return { value: [r.date, r.delta, r.value, r.nWaagen], itemStyle: { color: color } };
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
    const currentYear = new Date().getFullYear();
    const activeYears = [currentYear, currentYear - 1];

    const selected: { [key: string]: boolean } = {};
    for (const year of allYears) {
        selected[year.toString()] = activeYears.includes(year);
    }
    return selected;
}

function buildLegendSelectedCur(allYears: number[]): { [key: string]: boolean } {
    const currentYear = new Date().getFullYear();
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
    globalMax: { value: number, date: Date };
    globalMin: { value: number, date: Date };
    maxDelta: { value: number; dates: Date[] };
    bestDays: Date[];
};

function metaDataOfYear(year: number, region: string, rawData: TrachtNetData): MetaData | null {
    let data = rawData[region][year];
    const maxDelta = Math.max(...data.filter(r => r.delta !== null).map(r => r.delta!));
    const bestDays = data
        .filter(r => r.delta === maxDelta)
        .map(r => r.date);

    const minValue = Math.min(...data.map(r => r.value));
    const minDate = data.find(r => r.value === minValue)?.date ?? null;

    const maxValue = Math.max(...data.map(d => d.value));
    const maxDate = data.find(r => r.value === maxValue)?.date ?? null;

    if (!minDate || !maxDate) {
        return null; // No valid data for min or max
    }

    return {
        year: year,
        // TODO: Capitalize the first letter of the region name.
        // This assumes that the region is a string and not an enum.
        region: toTitleCase(region),
        globalMax: { value: maxValue, date: maxDate },
        globalMin: { value: minValue, date: minDate },
        maxDelta: { value: maxDelta, dates: bestDays },
        bestDays: bestDays,
    }
}

function renderMetaData(data: MetaData): string {
    const formatterDE = new Intl.NumberFormat("de-DE", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
    let out = `<table class="table table-bordered table-striped table-sm">
  <caption>Auswertung von ${data.region} (${data.year})</caption>
  <tbody>
    <tr><th scope="row">Jahresminimum</th><td>${data.globalMin.date.toLocaleDateString("de-DE")} (${formatterDE.format(data.globalMin.value)} kg)</td></tr>
    <tr><th scope="row">Jahresmaximum</th><td>${data.globalMax.date.toLocaleDateString("de-DE")} (${formatterDE.format(data.globalMax.value)} kg)</td></tr>
    <tr><th scope="row">Bester Tag</th><td>${data.maxDelta.dates.map(d => d.toLocaleDateString("de-DE")).join(", ")} (Δ ${formatterDE.format(data.maxDelta.value)} kg)</td></tr>
  </tbody>
</table>`;
    return out;
}

function getXLimits(): [Date, Date] {
    const currentDate = new Date();
    let startDate: Date;
    let endDate: Date;
    if ((currentDate.getMonth() < 3) || (currentDate.getMonth() > 6)) {
        startDate = new Date(new Date().getFullYear(), 0);
        endDate = new Date(new Date().getFullYear(), 11);
    } else {
        startDate = new Date(new Date().getFullYear(), 3);
        endDate = new Date(new Date().getFullYear(), 7);
    }

    return [startDate, endDate];
}

class LineChart {
    private seriesData: echarts.LineSeriesOption[];
    private title: string;
    private subTitle: string;
    private chart?: ECharts;

    constructor(rawData: echarts.LineSeriesOption[], title: string) {
        this.seriesData = rawData;
        this.title = title;
        this.subTitle = "Datenquelle: TrachtNet";
    }

    render(elementID: string) {
        const chartContainer = document.getElementById(elementID);
        if (!chartContainer) {
            throw new Error(`Element with ID ${elementID} not found.`);
        }

        this.chart = echarts.init(chartContainer, null, {
            renderer: "svg"
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
                }
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
            legend: {
                show: true,
                top: "bottom",
                selected: buildLegendSelectedCurPrev(this.seriesData.map(s => {
                    return parseInt(typeof s.name === "string" ? s.name : "");
                })),
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
                            const date = new Date(typeof value === "number" ? value : String(value));
                            return date.toLocaleDateString("de-DE", {
                                year: 'numeric', month: 'long', day: 'numeric'
                            });
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
                name: "Korrigierte Gewichtänderung [kg]",
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
                    filterMode: 'none',
                    startValue: startDate,
                    endValue: endDate,
                }
            ],
            series: this.seriesData
        };

        this.chart.setOption(option);

        window.addEventListener("resize", () => {
            this.chart!.resize();
        });
    }
}

class BarChart {
    private seriesData: echarts.BarSeriesOption[];
    private title: string;
    private subTitle: string;
    private chart?: ECharts;

    constructor(rawData: echarts.BarSeriesOption[], title: string) {
        this.seriesData = rawData;
        this.title = title;
        this.subTitle = "Datenquelle: TrachtNet";
    }

    render(elementID: string) {
        const chartContainer = document.getElementById(elementID);
        if (!chartContainer) {
            throw new Error(`Element with ID ${elementID} not found.`);
        }

        this.chart = echarts.init(chartContainer, null, {
            renderer: "svg"
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
                }
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
            legend: {
                show: true,
                top: "bottom",
                selected: buildLegendSelectedCur(this.seriesData.map(s => {
                    return parseInt(typeof s.name === "string" ? s.name : "");
                }))
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
                    for (const p of params) {
                        const date = new Date(p.value[0]);
                        const nWaagen = p.value[3];
                        const prefix = `<b>${date.toLocaleDateString("de-DE")}</b>`;
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
                    // TODO: https://echarts.apache.org/en/option.html#xAxis.axisLabel.formatter
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
                name: "Gewichtänderung [kg]",
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
                    filterMode: 'none',
                    startValue: startDate,
                    endValue: endDate,
                }
            ],
            series: this.seriesData
        };

        this.chart.setOption(option);

        window.addEventListener("resize", () => {
            this.chart!.resize();
        });
    }
}

export { BarChart, LineChart, fetchTrachtnetData, getTrachtnetSeries, getTrachtnetDerivative, metaDataOfYear, renderMetaData, toTitleCase };
