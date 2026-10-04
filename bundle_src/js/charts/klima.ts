import { Temporal } from "temporal-polyfill";
import type { ECharts } from 'echarts';
import * as echarts from 'echarts';

import { QueenColor, getXLimits, getToday } from "./helpers";
import { buildBaseOption, buildFormatterDE, chartColors, initEchartsInstance, minorSplitLine } from "./base";

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

// Names of the series, also what the legend shows.
const SERIES_TREND = "Temperatur (7-Tage-Mittel)";
const SERIES_RANGE = "Tagesspanne (Min–Max)";
const SERIES_RAIN = "Niederschlag (7-Tage-Summe)";

// From this temperature on the bees fly.
const FLIGHT_TEMPERATURE = 12;
// Carries the band of the daily range and shows nothing itself.
const SERIES_RANGE_BASE = "Tagesminimum";

// Mean of the daily means over the week around each day (three days to
// either side, fewer at the ends of the data): the daily values jump up
// and down too much to see how the weather is developing.
function weeklyMean(data: DailyRecord[]): (number | null)[] {
    return data.map((_, i) => {
        const window = data.slice(Math.max(0, i - 3), i + 4)
            .map(r => r.temperatureMean)
            .filter(v => v !== null && v !== undefined);
        if (window.length === 0) {
            return null;
        }
        return window.reduce((sum, v) => sum + v, 0) / window.length;
    });
}

// Rain of the seven days up to and including each day: a single day's rain
// is a thin spike, the sum shows the wet and the dry spells. Looking back
// only, unlike the mean above -- what has fallen is what the plants have.
function weeklySum(data: DailyRecord[]): (number | null)[] {
    return data.map((_, i) => {
        const window = data.slice(Math.max(0, i - 6), i + 1)
            .map(r => r.precipitationSum)
            .filter(v => v !== null && v !== undefined);
        if (window.length === 0) {
            return null;
        }
        return window.reduce((sum, v) => sum + v, 0);
    });
}

export async function getKlimaDailySeries(stationID: string): Promise<Array<echarts.LineSeriesOption | echarts.BarSeriesOption>> {
    const data = await fetchKlimaDaily(stationID);
    const trend = weeklyMean(data);
    const rain = weeklySum(data);
    return [
        // The range of a day as a band between its minimum and its maximum:
        // an invisible line along the minimum, and stacked on it the
        // difference to the maximum as an area.
        {
            name: SERIES_RANGE_BASE,
            type: "line",
            yAxisIndex: 0,
            stack: "range",
            stackStrategy: "all",
            showSymbol: false,
            silent: true,
            lineStyle: {
                opacity: 0,
            },
            data: data.map(r => {
                return [
                    r.timestamp.toString(),
                    r.temperatureMin,
                ];
            }),
        },
        {
            name: SERIES_RANGE,
            type: "line",
            yAxisIndex: 0,
            stack: "range",
            stackStrategy: "all",
            showSymbol: false,
            silent: true,
            lineStyle: {
                opacity: 0,
            },
            itemStyle: {
                color: QueenColor.Red,
                opacity: 0.35,
            },
            areaStyle: {
                color: QueenColor.Red,
                opacity: 0.18,
            },
            data: data.map(r => {
                // The station has days without values: no band there.
                const known = r.temperatureMin != null && r.temperatureMax != null;
                return [
                    r.timestamp.toString(),
                    known ? r.temperatureMax - r.temperatureMin : null,
                ];
            }),
        },
        {
            name: SERIES_TREND,
            type: "line",
            yAxisIndex: 0,
            showSymbol: false,
            lineStyle: {
                color: QueenColor.Red,
                width: 2.5,
            },
            // The marker in legend and tooltip takes the colour of the item.
            itemStyle: {
                color: QueenColor.Red,
            },
            smooth: true,
            markLine: {
                symbol: "none",
                silent: true,
                label: {
                    formatter: `Flug ab ${FLIGHT_TEMPERATURE} °C`,
                    position: "insideStartTop",
                    fontSize: 10,
                    color: chartColors().ink,
                },
                lineStyle: {
                    type: "dashed",
                    color: chartColors().ink,
                },
                data: [
                    { yAxis: FLIGHT_TEMPERATURE }
                ],
            },
            // Behind the mean of the week the values of the day itself, for
            // the tooltip.
            data: data.map((r, i) => {
                return [
                    r.timestamp.toString(),
                    trend[i],
                    r.temperatureMean,
                    r.temperatureMin,
                    r.temperatureMax,
                ];
            }),
        },
        {
            name: SERIES_RAIN,
            type: "line",
            yAxisIndex: 1,
            // Behind the temperature, which is drawn at the default of 2.
            z: 1,
            showSymbol: false,
            lineStyle: {
                color: QueenColor.Blue,
                width: 1.5,
            },
            itemStyle: {
                color: QueenColor.Blue,
            },
            areaStyle: {
                color: QueenColor.Blue,
                opacity: 0.25,
            },
            // Behind the sum of the week the rain of the day itself, for the
            // tooltip.
            data: data.map((r, i) => {
                return [
                    r.timestamp.toString(),
                    rain[i],
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
                if (p.seriesName === SERIES_TREND) {
                    const [, week, mean, min, max] = p.value;
                    out += `${prefix}: ${formatterDE.format(week)} °C<br>`;
                    if (mean != null && min != null && max != null) {
                        out += `${p.marker} <b>Tag</b>: ⌀ ${formatterDE.format(mean)} °C`
                            + ` (${formatterDE.format(min)} bis ${formatterDE.format(max)} °C)<br>`;
                    }
                } else if (p.seriesName === SERIES_RAIN) {
                    out += `${prefix}: ${formatterDE.format(p.value[1])} mm<br>`;
                    if (p.value[2] != null) {
                        out += `${p.marker} <b>Tag</b>: ${formatterDE.format(p.value[2])} mm<br>`;
                    }
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
                // To the fives around the data: left alone, the axis reaches
                // far below the coldest day, as the stacked band counts in.
                min: value => Math.floor(value.min / 5) * 5,
                max: value => Math.ceil(value.max / 5) * 5,
                axisLine: {
                    show: true,
                    lineStyle: {
                        color: chartColors().ink
                    }
                },
                axisLabel: {
                    formatter: val => Math.trunc(val) + " °C"
                },
                axisTick: {
                    show: true,
                    lineStyle: {
                        color: chartColors().ink
                    }
                },
                minorTick: {
                    show: true,
                    splitNumber: 5,
                    lineStyle: {
                        color: chartColors().ink
                    }
                },
                minorSplitLine: minorSplitLine()
            },
            {
                type: "value",
                name: "Niederschlag, 7 Tage [mm]",
                nameLocation: 'middle',
                nameGap: 55,
                axisLine: {
                    show: true,
                    lineStyle: {
                        color: chartColors().ink
                    }
                },
                axisLabel: {
                    formatter: val => Math.trunc(val) + " mm"
                },
                axisTick: {
                    show: true,
                    lineStyle: {
                        color: chartColors().ink
                    }
                },
                splitLine: {
                    show: false,
                }
            }

            ],
            legend: {
                show: true,
                top: 45,
                data: [SERIES_TREND, SERIES_RANGE, SERIES_RAIN],
            },
            grid: {
                top: 85,
            },
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
