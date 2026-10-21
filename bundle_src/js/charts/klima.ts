import { Temporal } from "temporal-polyfill";
import { area, line, curveMonotoneX } from "d3-shape";
import { sum } from "simple-statistics";

import { QueenColor, centredWeeklyMean, getCurrentYear, getXWindow, getToday } from "./helpers";
import { DAY_MS, emptyNote, formatDE, hatch, hLine, isNarrow, mountChart, swatch, timeChart } from "./frame";
import { loadTrachtPhases } from "./trachtnet/analysis";
import { phaseBands, plotDay } from "./trachtnet/marks";
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
        return sum(window);
    });
}

// A day of "year" with what the chart shows of it. The weekly values are
// worked out over all the days there are, so the first week of the year
// has a past, too.
type Day = {
    record: DailyRecord,
    date: Date,
    trend: number | null,
    rain: number | null,
};

function daysOf(all: DailyRecord[], year: number): Day[] {
    // The daily means jump up and down too much to see how the weather is
    // developing: the line is their mean over the week around each day.
    const trend = centredWeeklyMean(all.map(r => r.temperatureMean));
    const rain = weeklySum(all);
    return all.flatMap((record, i) => record.timestamp.year === year
        ? [{ record, date: plotDay(record.timestamp), trend: trend[i], rain: rain[i] }]
        : []);
}

// Weather of a DWD station in "year". With a "region" the phases of that
// year's honey flow there are shaded, as in the Trachtnet charts the chart
// stands above.
export async function renderKlimaChart(elementID: string, stationID: string, year: number, region?: string) {
    const [all, station, phases] = await Promise.all([
        fetchKlimaDaily(stationID),
        fetchStation(stationID),
        region ? loadTrachtPhases(region, year) : Promise.resolve([]),
    ]);
    const days = daysOf(all, year);
    const byDay = new Map(days.map(d => [d.date.getTime(), d]));
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
        if (days[0].record.timestamp.dayOfYear > 7) {
            notes.push(`Wetterdaten erst ab ${days[0].record.timestamp.toLocaleString("de-DE", { day: "numeric", month: "numeric" })}`);
        }
    }

    const temperatures = days.flatMap(d => [d.record.temperatureMin, d.record.temperatureMax]).filter(v => v != null);
    const rains = days.flatMap(d => d.rain !== null ? [d.rain] : []);
    const [start, end] = getXWindow(year);
    const middle = (x: (d: Date) => number, date: Date) => x(new Date(date.getTime() + DAY_MS / 2));

    mountChart(elementID, {
        title: station ? `Wetter ${station.name} ${year}` : `Klimadaten für Klimastation ${stationID} ${year}`,
        notes,
        legend: hasData ? [
            { label: SERIES_TREND, color: QueenColor.Red, look: "line" },
            { label: SERIES_RANGE, color: QueenColor.Red, look: "area" },
            { label: SERIES_RAIN, color: QueenColor.Blue, look: "hatch" },
        ] : [],
    }, canvas => {
        timeChart(canvas, {
            year,
            // Nothing to see after today.
            window: [plotDay(start), plotDay(year === getCurrentYear() ? getToday() : end)],
            left: {
                // To the fives around the data.
                domain: temperatures.length > 0
                    ? [Math.floor(Math.min(...temperatures) / 5) * 5, Math.ceil(Math.max(...temperatures) / 5) * 5]
                    : [-10, 30],
                name: "Temperatur [°C]",
                format: v => Math.trunc(v) + " °C",
            },
            right: {
                domain: [0, Math.max(10, ...rains)],
                name: "Niederschlag, 7 Tage [mm]",
                format: v => Math.trunc(v) + " mm",
            },
            draw: (layer, x, temperature, rainScale) => {
                const height = temperature.range()[0];
                phaseBands(layer, x, phases, height);
                // Behind the temperature: the rain of the week, hatched --
                // it lies under the band of the temperature.
                layer.append("path")
                    .style("fill", hatch("rain"))
                    .attr("stroke", QueenColor.Blue)
                    .attr("stroke-width", 1.5)
                    .attr("d", area<Day>()
                        .defined(d => d.rain !== null)
                        .x(d => middle(x, d.date))
                        .y0(rainScale!(0))
                        .y1(d => rainScale!(d.rain!))(days));
                // The range of a day, as a band from its minimum to its
                // maximum; the station has days without values.
                layer.append("path")
                    .attr("fill", QueenColor.Red)
                    .attr("fill-opacity", 0.18)
                    .attr("d", area<Day>()
                        .defined(d => d.record.temperatureMin != null && d.record.temperatureMax != null)
                        .x(d => middle(x, d.date))
                        .y0(d => temperature(d.record.temperatureMin))
                        .y1(d => temperature(d.record.temperatureMax))(days));
                hLine(layer, temperature(FLIGHT_TEMPERATURE), x.range()[1], "var(--color-ink)");
                layer.append("path")
                    .attr("class", "chart-line")
                    .attr("stroke", QueenColor.Red)
                    .attr("stroke-width", 2.5)
                    .attr("d", line<Day>()
                        .defined(d => d.trend !== null)
                        .x(d => middle(x, d.date))
                        .y(d => temperature(d.trend!))
                        .curve(curveMonotoneX)(days));
            },
            tooltip: day => {
                const d = byDay.get(day.getTime());
                if (!d) {
                    return null;
                }
                const r = d.record;
                let html = "";
                if (d.trend !== null) {
                    html += `${swatch(QueenColor.Red)}<b>${SERIES_TREND}</b>: ${formatDE.format(d.trend)} °C<br>`;
                }
                if (r.temperatureMean != null && r.temperatureMin != null && r.temperatureMax != null) {
                    html += `${swatch(QueenColor.Red)}<b>Tag</b>: ⌀ ${formatDE.format(r.temperatureMean)} °C (${formatDE.format(r.temperatureMin)} bis ${formatDE.format(r.temperatureMax)} °C)<br>`;
                }
                if (d.rain !== null) {
                    html += `${swatch(QueenColor.Blue)}<b>${SERIES_RAIN}</b>: ${formatDE.format(d.rain)} mm<br>`;
                }
                if (r.precipitationSum != null) {
                    html += `${swatch(QueenColor.Blue)}<b>Tag</b>: ${formatDE.format(r.precipitationSum)} mm`;
                }
                return html || null;
            },
        });
        // Without data the empty frame stays, so the charts below keep
        // their place, with a note across it saying why it is empty.
        if (!hasData) {
            emptyNote(canvas, `Für ${year} liegen keine Wetterdaten des Deutschen Wetterdienstes vor.`);
        }
    });
}
