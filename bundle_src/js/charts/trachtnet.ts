import { Temporal } from "temporal-polyfill";
import type * as echarts from 'echarts';

import { centredWeeklyMean, chooseQueenColor, getCurrentYear, getToday, getXWindow, isInteger, isInSeason, isSeasonOver } from "./helpers";
import { toTitleCase } from '../helpers';
import { buildBaseOption, buildFormatterDE, chartColors, chartGrid, headHeight, initEchartsInstance, valueAxis } from "./base";

// --------------------------------------------------------------------
// Data: /trachtnet-dump/, written by scripts/src/bstools/cli/dump_trachtnet.py
// --------------------------------------------------------------------

// A day of a region: the mean of its scales.
export type DayRecord = {
    date: Temporal.PlainDate,
    // Weight gained since the start of the year [kg].
    value: number,
    // Change against the day before [kg].
    delta: number | null,
    nWaagen: number,
}

// One line of a /trachtnet-dump/<kind>/<id>-<year>.ndjson file. Empty days,
// junk zeros and the still-provisional last two days are already filtered
// out by the dump.
type RawRecord = {
    date: string,
    weight: number,
    delta: number | null,
    scales: number,
}

// An entry of /trachtnet-dump/index.json.
type Region = {
    kind: "bundesland" | "regierungsbezirk" | "landkreis" | "waage",
    id: string,
    name: string,
    slug: string,
    years: number[],
}

let regionIndex: Promise<Region[]> | null = null;

function loadRegionIndex(): Promise<Region[]> {
    regionIndex ??= fetch("/trachtnet-dump/index.json").then(async response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return (await response.json()).regions as Region[];
    });
    return regionIndex;
}

// A number is a scale id, otherwise the slug is matched against
// Bundesländer first, then Regierungsbezirke, then Landkreise (e.g. "berlin"
// is the Bundesland).
async function resolveRegion(region: string): Promise<Region> {
    const regions = await loadRegionIndex();
    const key = region.toLowerCase();
    let found: Region | undefined;
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

// Every file is fetched once, however many charts and tables of the page
// show it -- also when they are all built anew for another colour scheme.
const yearCache = new Map<string, Promise<DayRecord[]>>();

// The days of a region in a year, empty if the dump has none.
export function loadYear(region: string, year: number): Promise<DayRecord[]> {
    const key = `${region.toLowerCase()}/${year}`;
    let records = yearCache.get(key);
    if (!records) {
        records = fetchYear(region, year);
        yearCache.set(key, records);
    }
    return records;
}

async function fetchYear(region: string, year: number): Promise<DayRecord[]> {
    const r = await resolveRegion(region);
    if (!r.years.includes(year)) {
        return [];
    }

    const response = await fetch(`/trachtnet-dump/${r.kind}/${r.id}-${year}.ndjson`);
    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }
    return (await response.text())
        .split("\n")
        .filter(line => line.trim() !== "")
        .map(line => {
            const raw = JSON.parse(line) as RawRecord;
            return {
                date: Temporal.PlainDate.from(raw.date),
                value: raw.weight,
                delta: raw.delta,
                nWaagen: raw.scales,
            };
        });
}

async function otherYears(region: string, year: number): Promise<number[]> {
    return (await resolveRegion(region)).years.filter(y => y !== year).sort((a, b) => a - b);
}

// The years any of the regions has data for.
export async function availableYears(regions: string[]): Promise<number[]> {
    const years = new Set<number>();
    for (const region of regions) {
        (await resolveRegion(region)).years.forEach(y => years.add(y));
    }
    return [...years].sort((a, b) => a - b);
}

// --------------------------------------------------------------------
// What is derived from the days
// --------------------------------------------------------------------

// Charts lay the years over each other on the calendar of one of them. The
// 29th of February has no place in a year that isn't a leap year.
function onCalendarOf(records: DayRecord[], year: number): DayRecord[] {
    const leapYear = Temporal.PlainDate.from({ year, month: 1, day: 1 }).inLeapYear;
    return records
        .filter(r => leapYear || !(r.date.month === 2 && r.date.day === 29))
        .map(r => ({ ...r, date: r.date.with({ year }) }));
}

// A honey flow is on while the hives gain this much a day [kg], averaged
// over the week around the day, for at least this many days.
export const TRACHT_THRESHOLD = 0.5;
const TRACHT_MIN_DAYS = 3;

export type Phase = {
    start: Temporal.PlainDate,
    // The last day of the flow.
    end: Temporal.PlainDate,
}

export function trachtPhases(records: DayRecord[]): Phase[] {
    const mean = centredWeeklyMean(records.map(r => r.delta));
    const phases: Phase[] = [];
    let current: Phase | null = null;
    const close = () => {
        if (current && current.start.until(current.end).days + 1 >= TRACHT_MIN_DAYS) {
            phases.push(current);
        }
        current = null;
    };
    records.forEach((r, i) => {
        const m = mean[i];
        if (m !== null && m >= TRACHT_THRESHOLD) {
            current = { start: current?.start ?? r.date, end: r.date };
        } else {
            close();
        }
    });
    close();
    return phases;
}

export async function loadTrachtPhases(region: string, year: number): Promise<Phase[]> {
    return trachtPhases(await loadYear(region, year));
}

// What the shaded bands of phaseMarkArea() are, for the line below the
// title of a chart.
export const PHASE_NOTE = `hinterlegt: Tracht (7-Tage-Mittel ab ${TRACHT_THRESHOLD.toLocaleString("de-DE")} kg pro Tag)`;

// The phases as shaded bands, to hang on a series of any chart over time.
export function phaseMarkArea(phases: Phase[]): echarts.MarkAreaComponentOption {
    return {
        silent: true,
        itemStyle: {
            // The honey of the site's palette.
            color: "rgba(184, 114, 12, 0.16)",
        },
        // What the bands are is said once, below the title of the chart
        // (PHASE_NOTE): a label on each of them gets in the way of the
        // rest.
        label: {
            show: false,
        },
        data: phases.map(p => [
            { xAxis: p.start.toString() },
            // To the end of the last day, not its beginning.
            { xAxis: p.end.add({ days: 1 }).toString() },
        ]),
    };
}

// For every day of the calendar of "year": the mean of where the given
// years stood on that day.
function meanPerDay(years: DayRecord[][], year: number): [Temporal.PlainDate, number][] {
    const perDay = new Map<string, number[]>();
    for (const records of years) {
        for (const r of records) {
            const key = r.date.toPlainMonthDay().toString();
            let values = perDay.get(key);
            if (!values) {
                values = [];
                perDay.set(key, values);
            }
            values.push(r.value);
        }
    }

    const means: [Temporal.PlainDate, number][] = [];
    const first = Temporal.PlainDate.from({ year, month: 1, day: 1 });
    for (let date = first; date.year === year; date = date.add({ days: 1 })) {
        const values = perDay.get(date.toPlainMonthDay().toString());
        if (values && values.length > 0) {
            means.push([date, values.reduce((sum, v) => sum + v, 0) / values.length]);
        }
    }
    return means;
}

// The key figures of a year. The highest stand and the best day are looked
// for in the season only, see isInSeason(); of equals the later day counts.
type KeyFigures = {
    min: DayRecord,
    max: DayRecord,
    bestDay: DayRecord,
}

function keyFigures(records: DayRecord[]): KeyFigures | null {
    const inSeason = records.filter(r => isInSeason(r.date));
    if (inSeason.length === 0) {
        return null;
    }
    const latest = (best: DayRecord, r: DayRecord, key: (r: DayRecord) => number) => key(r) >= key(best) ? r : best;
    return {
        min: records.reduce((best, r) => r.value < best.value ? r : best),
        max: inSeason.reduce((best, r) => latest(best, r, x => x.value)),
        bestDay: inSeason.reduce((best, r) => latest(best, r, x => x.delta ?? -Infinity)),
    };
}

// --------------------------------------------------------------------
// Charts
//
// Each shows one year, on the calendar of that year. Text in a chart is
// kept to what can't be said elsewhere, so that it doesn't end up on top
// of other text: what bands and dashed lines mean stands below the title.
// --------------------------------------------------------------------

const SERIES_MEAN = "7-Tage-Mittel";
// The honey of the site's palette, as the phases the mean decides on.
const MEAN_COLOR = "#b8720c";

function isYear(name: unknown): boolean {
    return typeof name === "string" && /^\d{4}$/.test(name);
}

function shortDate(date: Temporal.PlainDate): string {
    return date.toLocaleString("de-DE", { day: "numeric", month: "numeric" });
}

// Dots on days of a series. What they stand for is said below the title
// (keyFigureNote): a text beside a dot lands on the lines around it.
function markPoints(days: [DayRecord, number][]): echarts.MarkPointComponentOption {
    return {
        symbol: "circle",
        symbolSize: 9,
        silent: true,
        itemStyle: {
            color: chartColors().surface,
            borderColor: chartColors().ink,
            borderWidth: 2,
        },
        label: {
            show: false,
        },
        data: days.map(([record, value]) => ({
            name: record.date.toString(),
            coord: [record.date.toString(), value],
        })),
    };
}

// The line below the title for the marked days: "○ Maximum 44,36 kg (29.6.)".
function keyFigureNote(parts: string[]): string {
    return `○ ${parts.join(" · ")}`;
}

function todayMarkLine(): echarts.MarkLineComponentOption {
    return {
        symbol: "none",
        silent: true,
        // The line speaks for itself in a chart that ends with today.
        label: {
            show: false,
        },
        lineStyle: {
            type: "dashed",
            color: chartColors().ink,
        },
        data: [
            { xAxis: getToday().toString() }
        ],
    };
}

function meanLabel(others: number[], year: number): string {
    if (others.length === 0) {
        return "Mittel";
    }
    const first = others[0];
    const last = others[others.length - 1];
    return `Mittel ${first}–${last}` + (year > first && year < last ? ` ohne ${year}` : "");
}

// The weight gained over the year: "year" as a bold line, the year before
// as a thin one, and as a dashed line the mean of all the other years.
// Once the season is over the lowest and the highest stand are marked;
// before that they are only the lowest and highest so far.
export async function renderProgressChart(elementID: string, region: string, year: number) {
    const chart = initEchartsInstance(elementID);
    const formatterDE = buildFormatterDE();
    const colors = chartColors();
    const isCurrent = year === getCurrentYear();

    const others = await otherYears(region, year);
    const [current, ...otherRecords] = await Promise.all([
        loadYear(region, year),
        ...others.map(y => loadYear(region, y)),
    ]);
    const means = meanPerDay(otherRecords, year);
    const seriesMean = meanLabel(others, year);

    const yearSeries = (y: number, records: DayRecord[], bold: boolean): echarts.LineSeriesOption => ({
        name: y.toString(),
        type: "line",
        showSymbol: false,
        z: bold ? 4 : 3,
        lineStyle: {
            color: chooseQueenColor(y),
            width: bold ? 3 : 1.5,
        },
        // The marker in the legend and in the tooltip takes the colour of
        // the item, not that of the line.
        itemStyle: {
            color: chooseQueenColor(y),
        },
        data: onCalendarOf(records, year).map(r => [r.date.toString(), r.value, r.nWaagen, r.delta]),
    });

    const series: echarts.SeriesOption[] = [];
    if (means.length > 0) {
        series.push({
            name: seriesMean,
            type: "line",
            showSymbol: false,
            z: 2,
            lineStyle: { color: colors.ink, width: 1.5, type: "dashed", opacity: 0.7 },
            itemStyle: { color: colors.ink, opacity: 0.7 },
            data: means.map(([date, mean]) => [date.toString(), mean]),
        });
    }
    if (others.includes(year - 1)) {
        series.push(yearSeries(year - 1, otherRecords[others.indexOf(year - 1)], false));
    }
    const figures = isSeasonOver(year) ? keyFigures(current) : null;
    series.push({
        ...yearSeries(year, current, true),
        markLine: isCurrent ? todayMarkLine() : undefined,
        markArea: phaseMarkArea(trachtPhases(current)),
        markPoint: figures ? markPoints([
            [figures.max, figures.max.value],
            [figures.min, figures.min.value],
        ]) : undefined,
    });
    const notes = ["Aufsummierte Gewichtsänderung pro Tag [kg]", PHASE_NOTE];
    if (figures) {
        notes.push(keyFigureNote([
            `Maximum ${formatterDE.format(figures.max.value)} kg (${shortDate(figures.max.date)})`,
            `Minimum ${formatterDE.format(figures.min.value)} kg (${shortDate(figures.min.date)})`,
        ]));
    }

    const tooltipFormatter = (params: any): string => {
        let out = "";
        for (const p of params) {
            const prefix = `${p.marker} <b>${p.seriesName}</b>`;
            if (isYear(p.seriesName)) {
                const [, value, waagen, delta] = p.value;
                const change = delta !== null ? `Δ ${formatterDE.format(delta)} kg, ` : "";
                out += `${prefix}: ${formatterDE.format(value)} kg (${change}${waagen} Waagen)<br>`;
            } else if (p.seriesName === seriesMean) {
                out += `${prefix}: ${formatterDE.format(p.value[1])} kg<br>`;
            }
        }
        return out;
    };

    const [startDate, endDate] = getXWindow(year);
    chart.setOption({
        ...buildBaseOption(
            `Trachtverlauf ${toTitleCase(region)} ${year}`,
            notes.join("\n"),
            tooltipFormatter,
            year,
        ),
        grid: chartGrid(headHeight(notes.length) + 12),
        yAxis: valueAxis("Gewicht [kg]", val => Math.trunc(val) + " kg"),
        legend: {
            show: true,
            top: "bottom",
            // The year first.
            data: series.map(s => s.name as string).reverse(),
        },
        dataZoom: [
            {
                type: "inside",
                xAxisIndex: 0,
                startValue: startDate.toString(),
                endValue: endDate.toString(),
            }
        ],
        series,
    });
}

// The change of weight per day of "year", as a bar a day and as the mean
// of the week around each day, which is also what decides on the phases
// of a honey flow. Which of the two leads depends on the time: during the
// season it is the bars -- did the hives gain yesterday? --, with the mean
// as a thin line. Once it is over, nobody remembers single days: then the
// mean leads, the bars fade behind it and the best day is marked.
// Other years are looked at by switching the year of the page.
export async function renderDerivativeChart(elementID: string, region: string, year: number) {
    const chart = initEchartsInstance(elementID);
    const formatterDE = buildFormatterDE();
    const seasonOver = isSeasonOver(year);

    const current = await loadYear(region, year);
    const bestDay = seasonOver ? keyFigures(current)?.bestDay : undefined;

    const series: echarts.SeriesOption[] = [{
        name: year.toString(),
        type: "bar",
        markPoint: bestDay ? markPoints([[bestDay, bestDay.delta!]]) : undefined,
        // For the marker in the legend and in the tooltip; the bars have
        // their colours set one by one: a loss is paler than a gain.
        itemStyle: {
            color: chooseQueenColor(year),
        },
        data: current.map(r => ({
            value: [r.date.toString(), r.delta, r.value, r.nWaagen],
            itemStyle: {
                color: chooseQueenColor(year, (r.delta ?? 0) < 0),
                opacity: seasonOver ? 0.4 : 1,
            },
        })),
    }];

    const mean = centredWeeklyMean(current.map(r => r.delta));
    series.push({
        name: SERIES_MEAN,
        type: "line",
        showSymbol: false,
        smooth: true,
        z: 3,
        lineStyle: {
            color: MEAN_COLOR,
            width: seasonOver ? 3 : 1.5,
        },
        itemStyle: {
            color: MEAN_COLOR,
        },
        // The threshold of a honey flow, see PHASE_NOTE.
        markLine: {
            symbol: "none",
            silent: true,
            label: {
                show: false,
            },
            lineStyle: {
                type: "dashed",
                color: MEAN_COLOR,
            },
            data: [
                { yAxis: TRACHT_THRESHOLD }
            ],
        },
        markArea: phaseMarkArea(trachtPhases(current)),
        data: current.map((r, i) => [r.date.toString(), mean[i]]),
    });

    const tooltipFormatter = (params: any): string => {
        let out = "";
        for (const p of params) {
            const prefix = `${p.marker} <b>${p.seriesName}</b>`;
            if (p.seriesName === SERIES_MEAN) {
                out += `${prefix}: Δ ${formatterDE.format(p.value[1])} kg<br>`;
            } else {
                out += `${prefix}: Δ ${formatterDE.format(p.value[1])} kg (${p.value[3]} Waagen)<br>`;
            }
        }
        return out;
    };

    const notes = ["Gewichtsänderung pro Tag [kg]", PHASE_NOTE];
    if (bestDay) {
        notes.push(keyFigureNote([`Bester Tag +${formatterDE.format(bestDay.delta!)} kg (${shortDate(bestDay.date)})`]));
    }

    const [startDate, endDate] = getXWindow(year);
    chart.setOption({
        ...buildBaseOption(
            `Trachtänderungen ${toTitleCase(region)} ${year}`,
            notes.join("\n"),
            tooltipFormatter,
            year,
        ),
        grid: chartGrid(headHeight(notes.length) + 12),
        yAxis: valueAxis("Gewichtsänderung [kg]", val => Intl.NumberFormat("de-DE", {
            minimumFractionDigits: 1,
            maximumFractionDigits: 1
        }).format(val) + " kg"),
        legend: {
            show: true,
            top: "bottom",
        },
        dataZoom: [
            {
                type: "inside",
                xAxisIndex: 0,
                startValue: startDate.toString(),
                // Nothing to see after today.
                endValue: (year === getCurrentYear() ? getToday() : endDate).toString(),
            }
        ],
        series,
    });
}

// --------------------------------------------------------------------
// Table of a year's key figures
// --------------------------------------------------------------------

export async function renderEvaluationTable(elementID: string, region: string, year: number) {
    const records = await loadYear(region, year);
    if (records.length === 0) {
        return;
    }

    const figures = keyFigures(records);
    if (!figures) {
        return;
    }
    const { min, max, bestDay } = figures;

    const formatterDE = buildFormatterDE();
    document.getElementById(elementID)!.innerHTML = `<table class="table table-bordered table-striped table-sm">
  <caption>Auswertung von ${toTitleCase(region)} (${year})</caption>
  <tbody>
    <tr><th scope="row">Jahresminimum</th><td>${min.date.toLocaleString()} (${formatterDE.format(min.value)} kg)</td></tr>
    <tr><th scope="row">Jahresmaximum</th><td>${max.date.toLocaleString()} (${formatterDE.format(max.value)} kg)</td></tr>
    <tr><th scope="row">Bester Tag</th><td>${bestDay.date.toLocaleString()} (Δ ${formatterDE.format(bestDay.delta!)} kg)</td></tr>
  </tbody>
</table>`;
}
