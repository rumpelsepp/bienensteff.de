import * as echarts from 'echarts';
import type { ECharts } from 'echarts';

import { Land, Regierungsbezirk, Kreis } from './regions.js';

type Record = [Date, number, number, number | null];
type YearlyData = {
    [year: number]: Record[]
}

function normalizeYear(records: Record[]): Record[] {
    return records.map(([date, value, nWaagen, delta]) => {
        let today = new Date();
        let recordDate = new Date(date);
        recordDate.setFullYear(today.getFullYear());
        return [recordDate, value, nWaagen, delta];
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

async function fetchTrachtnetData(years: number | number[], region: string): Promise<YearlyData> {
    if (!isInteger(years) && !isIntegerArray(years)) {
        throw new Error("Year must be an integer or an array of integers.");
    }

    if (isInteger(years)) {
        years = [years];
    } else {
        // Sort and remove duplicates.
        years = [... new Set(years.sort((a, b) => a - b))];
    }

    let out: YearlyData = {};
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
        out[y] = json_data.map(d => {
            let delta = prev === null ? null : d.values - prev;
            if (d.values === null) {
                delta = 0;
            }
            prev = d.values;
            return [new Date(d.dates), d.values, d.n_waagen, delta];
        });
    }

    return out;
}

async function getTrachtnetSeries(year: number | number[], region: string, normalize: boolean = false): Promise<echarts.LineSeriesOption[]> {
    const data = await fetchTrachtnetData(year, region);
    let out: echarts.LineSeriesOption[] = [];

    for (const [year, records] of Object.entries(data)) {
        if (!isInteger(+year)) {
            throw new Error(`Invalid year in data: ${year}`);
        }

        let entry: echarts.LineSeriesOption = {
            name: year.toString(),
            type: "line",
            showSymbol: false,
            data: normalize ? normalizeYear(records) : records,
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

            //     entry.markPoint = {
            //         data: [
            //             { type: 'max', name: 'Maximum' },
            //         ],
            //         label: {
            //             formatter: (params) => {
            //                 const datum = new Date(params.data.coord[0]).toLocaleDateString("de-DE");
            //                 return `📍 ${datum}`;
            //             },
            //             fontSize: 12,
            //             fontWeight: 'bold'
            //         },
            //     }
        }
        out.push(entry);
    }

    return out;

    // NOTE: Zum hervorheben des aktuellen Jahres:
    // const currentYear = new Date().getFullYear();
    //   const isCurrent = yearNum === currentYear;

    //   return {
    //     name: jahr,
    //     type: "line",
    //     showSymbol: false,
    //     data: eintraege,
    //     lineStyle: {
    //       color,
    //       width: isCurrent ? 3 : 1.5
    //     },
    //     areaStyle: {
    //       color: isCurrent ? color + "40" : color + "20"
    //     },
    //     emphasis: {
    //       focus: "series"
    //     },
    //     z: isCurrent ? 10 : 1
    //   };
}

async function getTrachtnetDerivative(year: number, region: string): Promise<echarts.BarSeriesOption> {
    const rawData = await fetchTrachtnetData(year, region);
    let data = rawData[year];

    let entry: echarts.BarSeriesOption = {
        name: year.toString(),
        type: "bar",
        data: data.map(([date, values, nWaagen, delta]) => {
            let color = delta! >= 0 ? QueenColor.Green.toString() : QueenColor.Red.toString();
            return { value: [date, delta, values, nWaagen], itemStyle: { color: color } };
        }),
    };

    return entry;
}

function buildLegendSelected(allYears: number[]): { [key: string]: boolean } {
    const currentYear = new Date().getFullYear();
    const activeYears = [currentYear, currentYear - 1];

    const selected = {};
    for (const year of allYears) {
        selected[year.toString()] = activeYears.includes(year);
    }
    return selected;
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
                selected: buildLegendSelected(this.seriesData.map(s => {
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
                    startValue: new Date(new Date().getFullYear(), 3),
                    endValue: new Date(new Date().getFullYear(), 7),
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
                    startValue: new Date(new Date().getFullYear(), 3),
                    endValue: new Date(new Date().getFullYear(), 7),
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

export { BarChart, LineChart, getTrachtnetSeries, getTrachtnetDerivative };