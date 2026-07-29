import { Temporal } from "@js-temporal/polyfill";
import type { ECharts } from 'echarts';
import * as echarts from 'echarts';

import { QueenColor, getXLimits, getToday } from "./helpers";
import { buildBaseOption, buildFormatterDE, initEchartsInstance } from "./base";

type DailyRecordRaw = {
    timestamp: string,
    temperature_mean: number,
    temperature_max: number,
    temperature_min: number,
    // dew_point_mean: number,
    precipitation_sum: number,
}

type DailyRecord = {
    timestamp: Temporal.PlainDate,
    temperatureMean: number,
    temperatureMax: number,
    temperatureMin: number,
    // dewPointMean: number,
    precipitationSum: number,
}

async function fetchKlimaDaily(stationID: string): Promise<DailyRecord[]> {
    let data = null;
    const response = await fetch(`/klima/${stationID}_daily.json`);
    if (response.ok) {
        data = (await response.text()).split("\n").filter((line => line.trim() != "")).map((line) => JSON.parse(line) as DailyRecordRaw)
    } else {
        throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    return data.map((d: DailyRecordRaw) => {
        return {
            timestamp: Temporal.PlainDate.from(d.timestamp),
            temperatureMean: d.temperature_mean,
            temperatureMax: d.temperature_max,
            temperatureMin: d.temperature_min,
            // dewPointMean: d.dew_point_mean,
            precipitationSum: d.precipitation_sum,
        };
    });
}

export async function getKlimaDailySeries(stationID: string): Promise<Array<echarts.LineSeriesOption | echarts.BarSeriesOption>> {
    const data = await fetchKlimaDaily(stationID);
    return [
        // {
        //     name: "max. Temperatur",
        //     type: "line",
        //     yAxisIndex: 0,
        //     showSymbol: false,
        //     data: data.map(r => {
        //         return [
        //             r.timestamp.toString(),
        //             r.temperatureMax,
        //         ];
        //     }),
        // },
        // {
        //     name: "min. Temperatur",
        //     type: "line",
        //     showSymbol: false,
        //     data: data.map(r => {
        //         return [
        //             r.timestamp.toString(),
        //             r.temperatureMin,
        //         ];
        //     }),
        // },
        {
            name: "⌀ Temperatur",
            type: "line",
            yAxisIndex: 0,
            showSymbol: false,
            lineStyle: {
                color: QueenColor.Red,
            },
            smooth: true,
            data: data.map(r => {
                return [
                    r.timestamp.toString(),
                    r.temperatureMean,
                ];
            }),
        },
        {
            name: "Niederschlagssumme",
            type: "bar",
            yAxisIndex: 1,
            itemStyle: {
                color: QueenColor.Blue,
            },
            data: data.map(r => {
                return [
                    r.timestamp.toString(),
                    r.precipitationSum,
                ];
            }),
        },
    ];
}

export class LineChart {
    private title: string;
    private subTitle: string;
    private chart?: ECharts;

    constructor(title: string) {
        this.title = title;
        this.subTitle = "Daten vom Deutschen Wetterdienst";
    }

    render(elementID: string) {
        this.chart = initEchartsInstance(elementID);

        const formatterDE = buildFormatterDE();
        const [startDate, _] = getXLimits();

        const tooltipFormatter = (params: any): string => {
            let out = "";
            for (const p of params) {
                const prefix = `${p.marker} <b>${p.seriesName}</b>`;
                out += `${prefix}: ${formatterDE.format(p.value[1])}`;
                if (p.componentIndex == 0) {
                    out += " °C<br>";
                } else {
                    out += " mm<br>";
                }
            }
            return out;
        };

        const option: echarts.EChartsOption = {
            ...buildBaseOption(this.title, this.subTitle, tooltipFormatter),
            yAxis: [{
                type: "value",
                name: "Temperatur [°C]",
                nameLocation: 'middle',
                nameGap: 55,
                axisLine: {
                    show: true,
                    lineStyle: {
                        color: "#000"
                    }
                },
                axisLabel: {
                    formatter: val => Math.trunc(val) + " °C"
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
            {
                type: "value",
                name: "Niederschlagssumme [mm]",
                nameLocation: 'middle',
                nameGap: 55,
                axisLine: {
                    show: true,
                    lineStyle: {
                        color: "#000"
                    }
                },
                axisLabel: {
                    formatter: val => Math.trunc(val) + " mm"
                },
                axisTick: {
                    show: true,
                    lineStyle: {
                        color: "#000"
                    }
                },
                splitLine: {
                    show: false,
                }
            }

            ],
            dataZoom: [
                {
                    type: "slider",
                    show: true,
                    showDetail: false,
                    // xAxisIndex: 0,
                    startValue: startDate.toString(),
                    endValue: getToday().toString(),
                }
            ],
        };

        this.chart.setOption(option);
    }

    setData(data: Array<echarts.LineSeriesOption | echarts.BarSeriesOption>) {
        this.chart!.setOption({
            series: data,
        });
    }
}
