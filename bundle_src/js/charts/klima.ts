import { Temporal } from "temporal-polyfill";
import type * as echarts from 'echarts';

import { QueenColor, centredWeeklyMean, getCurrentYear, getXWindow, getToday } from "./helpers";
import { buildBaseOption, buildFormatterDE, chartColors, chartGrid, headHeight, initEchartsInstance, isNarrow, valueAxis } from "./base";
import { loadTrachtPhases, phaseMarkArea, type Phase } from "./trachtnet";
import { toTitleCase } from "../helpers";

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

// What a station is: /klima/<id>_meta.json, written along with its data by
// scripts/src/bstools/cli/dump_dwd.py.
type Station = {
    id: string,
    name: string,
    latitude: number,
    longitude: number,
    // Above sea level [m].
    height: number,
}

// Null where a station has no such file yet: the chart then names it by
// its number.
async function fetchStation(stationID: string): Promise<Station | null> {
    const response = await fetch(`/klima/${stationID}_meta.json`);
    if (!response.ok) {
        return null;
    }
    return await response.json() as Station;
}

// "48,16° N, 11,54° O"
function formatPosition(station: Station): string {
    const degrees = (value: number) => Math.abs(value).toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    return `${degrees(station.latitude)}° ${station.latitude >= 0 ? "N" : "S"}, `
        + `${degrees(station.longitude)}° ${station.longitude >= 0 ? "O" : "W"}`;
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

// The series for the days of "year". The weekly values are worked out over
// all the days there are, so the first week of the year has a past, too.
function buildSeries(all: DailyRecord[], year: number, phases: Phase[]): echarts.LineSeriesOption[] {
    // The daily means jump up and down too much to see how the weather is
    // developing: the line is their mean over the week around each day.
    const allTrend = centredWeeklyMean(all.map(r => r.temperatureMean));
    const allRain = weeklySum(all);
    const inYear = all.map((_, i) => i).filter(i => all[i].timestamp.year === year);
    const data = inYear.map(i => all[i]);
    const trend = inYear.map(i => allTrend[i]);
    const rain = inYear.map(i => allRain[i]);
    if (data.length === 0) {
        return [];
    }
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
                // Said below the title instead, where it is in nobody's way.
                label: {
                    show: false,
                },
                lineStyle: {
                    type: "dashed",
                    color: chartColors().ink,
                },
                data: [
                    { yAxis: FLIGHT_TEMPERATURE }
                ],
            },
            // When the honey flow of the region was on, see trachtnet.ts.
            markArea: phaseMarkArea(phases),
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

// Weather of a DWD station in "year". With a "region" the phases of that
// year's honey flow there are shaded, as in the Trachtnet charts the chart
// stands above.
export async function renderKlimaChart(elementID: string, stationID: string, year: number, region?: string) {
    const chart = initEchartsInstance(elementID);
    const formatterDE = buildFormatterDE();

    const [data, station, phases] = await Promise.all([
        fetchKlimaDaily(stationID),
        fetchStation(stationID),
        region ? loadTrachtPhases(region, year) : Promise.resolve([]),
    ]);
    const series = buildSeries(data, year, phases);

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

    // The station doesn't have every year, and not every year in full.
    const days = data.filter(r => r.timestamp.year === year);
    const hasData = days.length > 0;

    // The lines below the title: what the dashed line and the bands mean,
    // instead of labels on them -- side by side where there is room.
    // Where the weather is from, the number of the station behind its name.
    const notes = ["Daten vom Deutschen Wetterdienst"];
    if (station) {
        const source = [`Deutscher Wetterdienst, Station ${stationID}`, `${formatPosition(station)}, ${Math.round(station.height)} m`];
        // On a phone the position has a line of its own.
        notes.splice(0, 1, ...(isNarrow() ? source : [`${source[0]} (${source[1]})`]));
    }
    if (hasData) {
        const marks = [`gestrichelt: ${FLIGHT_TEMPERATURE} °C, ab da fliegen die Bienen`];
        if (region) {
            marks.push(`hinterlegt: Tracht in ${toTitleCase(region)}`);
        }
        notes.push(...(isNarrow() ? marks : [marks.join(" · ")]));
        if (days[0].timestamp.dayOfYear > 7) {
            notes.push(`Wetterdaten erst ab ${days[0].timestamp.toLocaleString("de-DE", { day: "numeric", month: "numeric" })}`);
        }
    }
    // The legend follows them: its three entries in a row, on a phone one
    // below the other.
    const legendTop = headHeight(notes.length) + 4;
    const legendHeight = isNarrow() ? 70 : 26;

    const [startDate, endDate] = getXWindow(year);
    chart.setOption({
        ...buildBaseOption(
            station ? `Wetter ${station.name} ${year}` : `Klimadaten für Klimastation ${stationID} ${year}`,
            notes.join("\n"),
            tooltipFormatter,
            year,
        ),
        // Without data the empty frame stays, so the charts below keep
        // their place, with a note across it saying why it is empty.
        graphic: hasData ? [] : [
            {
                type: "text",
                left: "center",
                top: "middle",
                // Above the grid lines of the frame.
                z: 100,
                style: {
                    lineHeight: 22,
                    text: `Für ${year} liegen keine Wetterdaten\ndes Deutschen Wetterdienstes vor.`,
                    align: "center",
                    font: "600 15px sans-serif",
                    fill: chartColors().ink,
                    backgroundColor: chartColors().surface,
                    borderColor: chartColors().ink,
                    borderWidth: 1,
                    borderRadius: 6,
                    padding: [12, 18],
                },
            },
        ],
        yAxis: [
            {
                ...valueAxis("Temperatur [°C]", val => Math.trunc(val) + " °C"),
                // To the fives around the data: left alone, the axis reaches
                // far below the coldest day, as the stacked band counts in.
                min: (value: { min: number }) => Math.floor(value.min / 5) * 5,
                max: (value: { max: number }) => Math.ceil(value.max / 5) * 5,
            },
            {
                ...valueAxis("Niederschlag, 7 Tage [mm]", val => Math.trunc(val) + " mm"),
                // The grid belongs to the temperature.
                minorTick: { show: false },
                minorSplitLine: { show: false },
                splitLine: { show: false },
            },
        ],
        legend: {
            show: hasData,
            top: legendTop,
            data: [SERIES_TREND, SERIES_RANGE, SERIES_RAIN],
        },
        grid: chartGrid(legendTop + legendHeight + 8),
        dataZoom: [
            {
                type: "slider",
                show: hasData,
                showDetail: false,
                startValue: startDate.toString(),
                // Nothing to see after today.
                endValue: (year === getCurrentYear() ? getToday() : endDate).toString(),
            }
        ],
        series,
    });
}
