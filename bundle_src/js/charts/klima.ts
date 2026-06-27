import { Temporal } from "@js-temporal/polyfill";
import type { ECharts } from 'echarts';
import * as echarts from 'echarts';

import de from "./i18n/de.js";
import { QueenColor, isInteger, getXLimits, getToday } from "./helpers";

const localTimeZone = Temporal.Now.timeZoneId();
echarts.registerLocale('DE', de);

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
        this.subTitle = "Daten vom Deutschen Wetterdienst";
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
                        out += `${prefix}: ${formatterDE.format(p.value[1])}`;
                        if (p.componentIndex == 0) {
                            out += " °C<br>";
                        } else {
                            out += " mm<br>";
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
                splitLine: {
                    show: true,
                    lineStyle: {
                        color: '#eee'
                    }
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
            },
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

        window.addEventListener("resize", () => {
            this.chart!.resize();
        });
    }

    setData(data: Array<echarts.LineSeriesOption | echarts.BarSeriesOption>) {
        this.chart!.setOption({
            series: data,
        });
    }
}
