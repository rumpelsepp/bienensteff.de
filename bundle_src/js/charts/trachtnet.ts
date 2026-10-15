import { Temporal } from "temporal-polyfill";
import type * as echarts from 'echarts';

import { QueenColor, chooseQueenColor, getCurrentYear, getToday, getXWindow, isInteger, isInSeason, isSeasonOver } from "./helpers";
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

// The mean of the deltas over the seven calendar days around each day --
// in contrast to centredWeeklyMean() of helpers.ts, whose window is
// positional: where days are missing from the dump -- a scale offline,
// see the dump script -- that mean would reach across the hole, from one
// side of it to the other, and see a flow that isn't there, or miss one
// that is. The weather of klima.ts has no holes; there the positional
// mean stays.
export function calendarWeeklyMean(records: DayRecord[]): (number | null)[] {
    return records.map((record, i) => {
        const window: number[] = [];
        const withinWeek = (j: number) => Math.abs(records[j].date.until(record.date).days) <= 3;
        for (let j = i; j >= 0 && withinWeek(j); j--) {
            if (records[j].delta !== null) {
                window.push(records[j].delta!);
            }
        }
        for (let j = i + 1; j < records.length && withinWeek(j); j++) {
            if (records[j].delta !== null) {
                window.push(records[j].delta!);
            }
        }
        return window.length > 0 ? window.reduce((sum, d) => sum + d, 0) / window.length : null;
    });
}

export function trachtPhases(records: DayRecord[]): Phase[] {
    const mean = calendarWeeklyMean(records);
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

// A day of the year to sort "up to the same day of the year" by, as a
// plain number: month, then day. (Temporal.PlainMonthDay.compare() is
// beyond the polyfill's version 1.)
function ordinalMonthDay(date: Temporal.PlainDate): number {
    return date.month * 100 + date.day;
}

// The gross sums of the season (see isInSeason()): what the colonies
// brought in on the days they gained, what they used up (or lost, e.g. to
// robbing) on the others. For the year still running, "until" cuts records
// back to the same day of the year, so that it can be compared with a year
// that is over.
function seasonTotals(records: DayRecord[], until?: number): { gain: number, loss: number } {
    const totals = { gain: 0, loss: 0 };
    for (const r of records) {
        if (r.delta === null || !isInSeason(r.date)) {
            continue;
        }
        if (until !== undefined && ordinalMonthDay(r.date) > until) {
            continue;
        }
        if (r.delta >= 0) {
            totals.gain += r.delta;
        } else {
            totals.loss -= r.delta;
        }
    }
    return totals;
}

// The phases that begin in the season (see isInSeason()): before March
// there is no flow to speak of, and the mean over a region's scales has
// spikes in January -- scales being set up -- that the phase detection
// would count.
export function seasonPhases(records: DayRecord[]): Phase[] {
    return trachtPhases(records).filter(p => isInSeason(p.start));
}

// The flow-free days between two of the phases, the longest run first --
// the "Trachtlücke" an imker watches out for.
function longestGap(phases: Phase[]): { days: number, from: Temporal.PlainDate, to: Temporal.PlainDate } | null {
    let longest: { days: number, from: Temporal.PlainDate, to: Temporal.PlainDate } | null = null;
    for (let i = 1; i < phases.length; i++) {
        const from = phases[i - 1].end.add({ days: 1 });
        const to = phases[i].start.add({ days: -1 });
        const days = from.until(to).days + 1;
        if (days > 0 && (!longest || days > longest.days)) {
            longest = { days, from, to };
        }
    }
    return longest;
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

    const mean = calendarWeeklyMean(current);
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

// The mean of the season gain (see seasonTotals()) of the years around
// "year", to put its own against -- cut back to the same day of the year
// for one that is still running. Null if there is nothing to compare
// with.
async function meanSeasonGain(
    region: string,
    year: number,
    records: DayRecord[],
): Promise<{ mean: number, from: number, to: number } | null> {
    const until = isSeasonOver(year) ? undefined : ordinalMonthDay(records[records.length - 1].date);
    const gains: [year: number, gain: number][] = [];
    for (const other of await otherYears(region, year)) {
        const otherRecords = await loadYear(region, other);
        if (!otherRecords.some(r => isInSeason(r.date))) {
            continue;  // the region wasn't in TrachtNet yet that year
        }
        const gain = seasonTotals(otherRecords, until).gain;
        if (until !== undefined && gain === 0 && !otherRecords.some(r => isInSeason(r.date) && ordinalMonthDay(r.date) <= until)) {
            continue;  // it joined TrachtNet after "until": nothing of the season yet
        }
        gains.push([other, gain]);
    }
    if (gains.length === 0) {
        return null;
    }
    return {
        mean: gains.reduce((sum, [, gain]) => sum + gain, 0) / gains.length,
        from: gains[0][0],
        to: gains[gains.length - 1][0],
    };
}

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
    const date = (d: Temporal.PlainDate) => d.toLocaleString();
    const row = (label: string, value: string) => `<tr><th scope="row">${label}</th><td>${value}</td></tr>`;
    const rows = [
        row("Jahresminimum", `${date(min.date)} (${formatterDE.format(min.value)} kg)`),
        row("Jahresmaximum", `${date(max.date)} (${formatterDE.format(max.value)} kg)`),
        row("Bester Tag", `${date(bestDay.date)} (Δ ${formatterDE.format(bestDay.delta!)} kg)`),
    ];

    // When the flow began and ended, how many phases it came in, and the
    // longest stretch without it in between.
    const phases = seasonPhases(records);
    if (phases.length > 0) {
        const phaseDays = phases.reduce((sum, p) => sum + p.start.until(p.end).days + 1, 0);
        rows.push(
            row("Trachtbeginn", date(phases[0].start)),
            row("Trachtende", date(phases[phases.length - 1].end)),
            row("Trachtphasen", `${phases.length} (${phaseDays} Tage)`),
        );
        const gap = longestGap(phases);
        if (gap) {
            rows.push(row("Längste Trachtlücke", `${gap.days} Tage (${date(gap.from)} – ${date(gap.to)})`));
        }
    }

    // What the season added up to, and how that stands against the years
    // around it.
    const totals = seasonTotals(records);
    rows.push(
        row("Gesamteintrag (Mär–Aug)", `${formatterDE.format(totals.gain)} kg`),
        row("Gesamtverlust (Mär–Aug)", `${formatterDE.format(totals.loss)} kg`),
    );
    const comparison = await meanSeasonGain(region, year, records);
    if (comparison) {
        const years = comparison.from === comparison.to
            ? `${comparison.from}`
            : `${comparison.from}–${comparison.to}`;
        let against = `Mittel ${years}: ${formatterDE.format(comparison.mean)} kg`;
        if (comparison.mean > 0) {
            const percent = Math.round((totals.gain / comparison.mean - 1) * 100);
            against = `${percent >= 0 ? "+" : ""}${percent} % (${against})`;
        }
        rows.push(row("Gesamteintrag ggü. Mittel", against));
    }

    document.getElementById(elementID)!.innerHTML = `<table class="table table-bordered table-striped table-sm">
  <caption>Auswertung von ${toTitleCase(region)} (${year}${isSeasonOver(year) ? "" : ", bis dato"})</caption>
  <tbody>
    ${rows.join("\n    ")}
  </tbody>
</table>`;
}

// --------------------------------------------------------------------
// Chart: when the honey flow began and ended, over the years
// --------------------------------------------------------------------

const SERIES_BEGIN = "Trachtbeginn";
const SERIES_END = "Trachtende";
const SERIES_TREND_BEGIN = "Trend Beginn";
const SERIES_TREND_END = "Trend Ende";
// The y axis counts the days of the year; its labels show them as dates of
// a leap year, in which every month/day fits.
const LABEL_YEAR = 2024;

// A year's flow: the first day of its first phase of the season and the
// last day of its last (see seasonPhases()), null where there was none.
// Whether the beginning and the ending were observed -- whether the days
// around them have data: where the dump has a hole there (a scale
// offline, see the dump script), the flow may well have gone on before
// or after, and the dot says nothing. See boundaryObserved().
type Flow = {
    year: number,
    begin: Temporal.PlainDate | null,
    end: Temporal.PlainDate | null,
};

export function dayOfYear(date: Temporal.PlainDate): number {
    return Temporal.PlainDate.from({ year: date.year, month: 1, day: 1 }).until(date).days + 1;
}

export function dayOfYearToDate(doy: number): Temporal.PlainDate {
    return Temporal.PlainDate.from({ year: LABEL_YEAR, month: 1, day: 1 }).add({ days: Math.round(doy) - 1 });
}

// Least squares over the given points: y = slope * x + intercept. Null if
// there is nothing to fit.
export function linearRegression(points: [number, number][]): { slope: number, intercept: number } | null {
    if (points.length < 2) {
        return null;
    }
    const meanX = points.reduce((sum, [x]) => sum + x, 0) / points.length;
    const meanY = points.reduce((sum, [, y]) => sum + y, 0) / points.length;
    let sxy = 0;
    let sxx = 0;
    for (const [x, y] of points) {
        sxy += (x - meanX) * (y - meanY);
        sxx += (x - meanX) ** 2;
    }
    return sxx === 0 ? null : { slope: sxy / sxx, intercept: meanY - (sxy / sxx) * meanX };
}

function flowTrend(flow: Flow[], key: "begin" | "end"): { slope: number, intercept: number } | null {
    return linearRegression(flow.flatMap(
        f => f[key] ? [[f.year, dayOfYear(f[key]!)] as [number, number]] : [],
    ));
}

// Days as a signed text: "+2,5 Tage".
export function signedDays(days: number): string {
    return `${days >= 0 ? "+" : "-"}${Math.abs(days).toLocaleString("de-DE", { maximumFractionDigits: 1 })} Tage`;
}

// The dots of a flow series: one per year in its queen colour, the years
// chronological as a thin line in the ink of the mode. A year without a
// flow has no dot, and the line skips it.
function flowSeries(name: string, flow: Flow[], key: "begin" | "end", symbol: string): echarts.LineSeriesOption {
    return {
        name,
        type: "line",
        symbol,
        symbolSize: 9,
        connectNulls: false,
        z: 3,
        lineStyle: { color: chartColors().ink, width: 1, opacity: 0.5 },
        itemStyle: { color: chartColors().ink },
        data: flow.map(f => f[key]
            ? {
                value: [f.year.toString(), dayOfYear(f[key]!), f[key]!.toLocaleString()],
                itemStyle: { color: chooseQueenColor(f.year) },
            }
            : [f.year.toString(), null]),
    };
}

// The dashed trend line over the years, from a regression (see
// linearRegression()); nothing if there is nothing to fit.
function trendSeries(name: string, flow: Flow[], trend: { slope: number, intercept: number } | null, color: string): echarts.SeriesOption | null {
    if (!trend) {
        return null;
    }
    const at = (year: number) => trend.slope * year + trend.intercept;
    const first = flow[0].year;
    const last = flow[flow.length - 1].year;
    return {
        name,
        type: "line",
        showSymbol: false,
        z: 4,
        lineStyle: { color, width: 2, type: "dashed" },
        itemStyle: { color },
        data: [
            [first.toString(), at(first)],
            [last.toString(), at(last)],
        ],
    };
}

// When the flow began and ended each year: a circle for the beginning, a
// diamond for the end, both in the year's queen colour, the years
// chronological as thin lines, and a dashed trend line over each. The
// chart spans all years on its own: it doesn't follow the year the page
// shows. For the year still running, the end is where the flow stands.
export async function renderTrendChart(elementID: string, region: string) {
    const chart = initEchartsInstance(elementID);
    const colors = chartColors();

    const years = await availableYears([region]);
    const recordsPerYear = await Promise.all(years.map(y => loadYear(region, y)));
    const flow: Flow[] = years.map((year, i) => {
        const phases = seasonPhases(recordsPerYear[i]);
        return {
            year,
            begin: phases[0]?.start ?? null,
            end: phases.length > 0 ? phases[phases.length - 1].end : null,
        };
    });

    const trendBegin = flowTrend(flow, "begin");
    const trendEnd = flowTrend(flow, "end");
    const series = [
        flowSeries(SERIES_BEGIN, flow, "begin", "circle"),
        flowSeries(SERIES_END, flow, "end", "diamond"),
        trendSeries(SERIES_TREND_BEGIN, flow, trendBegin, MEAN_COLOR),
        trendSeries(SERIES_TREND_END, flow, trendEnd, QueenColor.Green),
    ].filter((s): s is echarts.SeriesOption => s !== null);

    const tooltipFormatter = (params: any): string => {
        let out = "";
        for (const p of params) {
            const prefix = `${p.marker} <b>${p.seriesName}</b> ${p.name}`;
            if ((p.seriesName === SERIES_BEGIN || p.seriesName === SERIES_END) && p.value[1] !== null) {
                out += `${prefix}: ${p.value[2]}`;
                const trend = p.seriesName === SERIES_BEGIN ? trendBegin : trendEnd;
                if (trend) {
                    const toTrend = Math.round(p.value[1] - (trend.slope * +p.name + trend.intercept));
                    if (toTrend !== 0) {
                        out += ` (${toTrend > 0 ? "+" : ""}${toTrend} Tage zum Trend)`;
                    }
                }
                out += "<br>";
            } else if (p.seriesName === SERIES_TREND_BEGIN || p.seriesName === SERIES_TREND_END) {
                out += `${prefix}: ${dayOfYearToDate(p.value[1]).toLocaleString("de-DE", { day: "numeric", month: "long" })}<br>`;
            }
        }
        return out;
    };

    const trendNote = (label: string, trend: { slope: number, intercept: number } | null): string | null =>
        trend ? `${label}: ${signedDays(trend.slope)} pro Jahr` : null;
    const notes = [
        `● ${SERIES_BEGIN}, ◆ ${SERIES_END} (Mär–Aug)`,
        [trendNote("Beginn", trendBegin), trendNote("Ende", trendEnd)].filter(t => t !== null).join(", ")
            || "Zu wenig Jahre für einen Trend",
    ];

    chart.setOption({
        // The trend chart is not of a single year: buildBaseOption()'s time
        // axis of one is replaced by the years below.
        ...buildBaseOption(
            `Trachtbeginn und -ende ${toTitleCase(region)}`,
            notes.join("\n"),
            tooltipFormatter,
            getCurrentYear(),
        ),
        grid: chartGrid(headHeight(notes.length) + 12),
        xAxis: {
            type: "category",
            data: years.map(y => y.toString()),
            boundaryGap: true,
            axisLine: { lineStyle: { color: colors.ink } },
            axisTick: { show: true, lineStyle: { color: colors.ink } },
            splitLine: { show: true, lineStyle: { color: colors.grid } },
        },
        yAxis: valueAxis("Tag des Jahres", v => dayOfYearToDate(v).toLocaleString("de-DE", { day: "numeric", month: "short" })),
        series,
    });
}
