// What is derived from the days of a region (see data.ts): the phases of
// the honey flow and the gaps between them, the key figures of a year and
// the trends over the years. No drawing here, and nothing of the page: the
// charts and the table are built from this.

import { Temporal } from "temporal-polyfill";
import { linearRegression, linearRegressionLine, mean, rSquared } from "simple-statistics";

import { isInSeason, isSeasonOver } from "../helpers";
import { epochDay, loadYear, otherYears, type DayRecord } from "./data";

// Charts lay the years over each other on the calendar of one of them. The
// 29th of February has no place in a year that isn't a leap year.
export function onCalendarOf(records: DayRecord[], year: number): DayRecord[] {
    const leapYear = Temporal.PlainDate.from({ year, month: 1, day: 1 }).inLeapYear;
    return records
        .filter(r => leapYear || !(r.date.month === 2 && r.date.day === 29))
        .map(r => ({ ...r, date: r.date.with({ year }) }));
}

// A honey flow is on while the hives gain this much a day [kg], averaged
// over the week around the day, for at least this many days.
export const TRACHT_THRESHOLD = 0.5;

export const TRACHT_MIN_DAYS = 3;

// Fewer days than this between two flows are no "Trachtlücke": the two
// are one flow, through a few cool days.
export const GAP_MIN_DAYS = 7;

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
        let sum = 0;
        let n = 0;
        const add = (r: DayRecord) => {
            if (r.delta !== null) {
                sum += r.delta;
                n++;
            }
        };
        for (let j = i; j >= 0 && record.day - records[j].day <= 3; j--) {
            add(records[j]);
        }
        for (let j = i + 1; j < records.length && records[j].day - record.day <= 3; j++) {
            add(records[j]);
        }
        return n > 0 ? sum / n : null;
    });
}

// The phases of a year's days, worked out once: every chart and table of
// the page asks for them, of the same arrays (see loadYear()).
export const phaseCache = new WeakMap<DayRecord[], Phase[]>();

export function trachtPhases(records: DayRecord[]): Phase[] {
    let phases = phaseCache.get(records);
    if (!phases) {
        phases = detectPhases(records);
        phaseCache.set(records, phases);
    }
    return phases;
}

// The phases of the season: runs of days whose weekly mean reaches the
// threshold, from March on -- before, the mean over a region's scales has
// spikes (scales being set up) that are no flow. A day missing from the
// dump counts as one without a flow. Runs closer to each other than
// GAP_MIN_DAYS are one phase, through cool days and short holes in the
// data alike; what is left shorter than
// TRACHT_MIN_DAYS, or begins after the season (see isInSeason()), is
// dropped.
export function detectPhases(records: DayRecord[]): Phase[] {
    const mean = calendarWeeklyMean(records);
    type Run = { first: DayRecord, last: DayRecord };
    const runs: Run[] = [];
    records.forEach((r, i) => {
        const m = mean[i];
        if (m === null || m < TRACHT_THRESHOLD || r.date.month < 3) {
            return;
        }
        const run = runs[runs.length - 1];
        if (run && r.day - run.last.day < GAP_MIN_DAYS + 1) {
            run.last = r;
        } else {
            runs.push({ first: r, last: r });
        }
    });
    return runs
        .filter(run => run.last.day - run.first.day + 1 >= TRACHT_MIN_DAYS && isInSeason(run.first.date))
        .map(run => ({ start: run.first.date, end: run.last.date }));
}

export async function loadTrachtPhases(region: string, year: number): Promise<Phase[]> {
    return trachtPhases(await loadYear(region, year));
}

// Whether the days of a year cover the stretch of it from "first" to
// "last" (month, day) in full: data from its first week to its last, for
// at least COVERAGE of its days. A year a region joined TrachtNet in
// counts its weight from the day it joined, not from January; and the
// year still running stops today: neither belongs in a mean over years.
const COVERAGE = 0.9;

function covers(records: DayRecord[], first: [number, number], last: [number, number]): boolean {
    if (records.length === 0) {
        return false;
    }
    const year = records[0].date.year;
    const from = Date.UTC(year, first[0] - 1, first[1]) / 86_400_000;
    const to = Date.UTC(year, last[0] - 1, last[1]) / 86_400_000;
    const inside = records.filter(r => r.day >= from && r.day <= to);
    return inside.length >= COVERAGE * (to - from + 1)
        && inside[0].day <= from + 6
        && inside[inside.length - 1].day >= to - 6;
}

// The whole year, January to December.
export function coversYear(records: DayRecord[]): boolean {
    return covers(records, [1, 1], [12, 31]);
}

// The season (see isInSeason()), March to August.
export function coversSeason(records: DayRecord[]): boolean {
    return covers(records, [3, 1], [8, 31]);
}

// For every day of the calendar of "year": the mean of where the given
// years stood on that day.
export function meanPerDay(years: DayRecord[][], year: number): [Temporal.PlainDate, number][] {
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
            means.push([date, mean(values)]);
        }
    }
    return means;
}

// The key figures of a year. The highest stand and the best day are looked
// for in the season only, see isInSeason(); of equals the later day counts.
export type KeyFigures = {
    min: DayRecord,
    max: DayRecord,
    bestDay: DayRecord,
}

export function keyFigures(records: DayRecord[]): KeyFigures | null {
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
export function ordinalMonthDay(date: Temporal.PlainDate): number {
    return date.month * 100 + date.day;
}

// The gross sums of the season (see isInSeason()): what the colonies
// brought in on the days they gained, what they used up (or lost, e.g. to
// robbing) on the others. For the year still running, "until" cuts records
// back to the same day of the year, so that it can be compared with a year
// that is over.
export function seasonTotals(records: DayRecord[], until?: number): { gain: number, loss: number } {
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

// A "Trachtlücke": the days between two consecutive phases, at least
// GAP_MIN_DAYS of them (see detectPhases()). A gap is only a gap if its
// days were actually seen: days missing from the dump (a scale offline,
// see the dump script) are no proof of a flow ending. Up to
// GAP_TOLERATED missing days are lived with; more make the gap what it
// is -- a hole in the data, drawn as an outline and left out of the
// statistics.
export type Gap = {
    start: Temporal.PlainDate,
    end: Temporal.PlainDate,
    days: number,
    // Days of the gap that have data.
    covered: number,
    reliable: boolean,
    // The year's longest reliable one -- the window an imker waits for.
    longest: boolean,
};

export const GAP_TOLERATED = 2;

export const gapCache = new WeakMap<DayRecord[], Gap[]>();

export function trachtGaps(records: DayRecord[]): Gap[] {
    let gaps = gapCache.get(records);
    if (gaps) {
        return gaps;
    }
    const phases = trachtPhases(records);
    gaps = phases.slice(1).map((phase, i) => {
        const first = epochDay(phases[i].end) + 1;
        const last = epochDay(phase.start) - 1;
        const days = last - first + 1;
        const covered = records.filter(r => r.day >= first && r.day <= last).length;
        return {
            start: phases[i].end.add({ days: 1 }),
            end: phase.start.add({ days: -1 }),
            days,
            covered,
            reliable: days - covered <= GAP_TOLERATED,
            longest: false,
        };
    });
    const longest = gaps.filter(g => g.reliable).reduce<Gap | null>((best, g) => !best || g.days > best.days ? g : best, null);
    if (longest) {
        longest.longest = true;
    }
    gapCache.set(records, gaps);
    return gaps;
}

// --------------------------------------------------------------------
// Charts
//
// Each shows one year, on the calendar of that year. Text in a chart is
// kept to what can't be said elsewhere, so that it doesn't end up on top
// of other text: what bands and dashed lines mean stands below the title.

// The mean of the season gain (see seasonTotals()) of the other years
// with a full season (see coversSeason()), to put that of "year" against
// -- cut back to the same day of the year for one that is still running.
// Null if there is nothing to compare with.
export async function meanSeasonGain(
    region: string,
    year: number,
    records: DayRecord[],
): Promise<{ mean: number, from: number, to: number } | null> {
    const until = isSeasonOver(year) ? undefined : ordinalMonthDay(records[records.length - 1].date);
    const gains: [year: number, gain: number][] = [];
    for (const other of await otherYears(region, year)) {
        const otherRecords = await loadYear(region, other);
        if (coversSeason(otherRecords)) {
            gains.push([other, seasonTotals(otherRecords, until).gain]);
        }
    }
    if (gains.length === 0) {
        return null;
    }
    return {
        mean: mean(gains.map(([, gain]) => gain)),
        from: gains[0][0],
        to: gains[gains.length - 1][0],
    };
}

// The y axis counts the days of the year on the calendar of a leap year,
// in which every month/day fits: the 1st of March is day 61 in every
// year, and the labels show the date the dot stands for.
export const LABEL_YEAR = 2024;

export function dayOfYear(date: Temporal.PlainDate): number {
    return (Date.UTC(LABEL_YEAR, date.month - 1, date.day) - Date.UTC(LABEL_YEAR, 0, 1)) / 86_400_000 + 1;
}

// Lines for an axis of days of the year (see dayOfYear()) between "from"
// and "to": labelled on the 1st and the 15th of each month, faint on the
// 8th and the 22nd.
export function datesTicks(from: number, to: number): { major: number[], minor: number[] } {
    const major: number[] = [];
    const minor: number[] = [];
    for (let month = 1; month <= 12; month++) {
        for (const [day, into] of [[1, major], [8, minor], [15, major], [22, minor]] as const) {
            const doy = dayOfYear(Temporal.PlainDate.from({ year: LABEL_YEAR, month, day }));
            if (doy >= from && doy <= to) {
                into.push(doy);
            }
        }
    }
    return { major, minor };
}

export function dayOfYearToDate(doy: number): Temporal.PlainDate {
    return Temporal.PlainDate.from({ year: LABEL_YEAR, month: 1, day: 1 }).add({ days: Math.round(doy) - 1 });
}

// A straight line through points of (year, day), by least squares: its
// slope [days per year], the line itself, and how much of the points'
// spread it explains (R²). Null with fewer than two years to fit it to.
export type Trend = {
    slope: number,
    at: (x: number) => number,
    rSquared: number,
};

export function fitTrend(points: [number, number][]): Trend | null {
    if (points.length < 2) {
        return null;
    }
    const line = linearRegression(points);
    const at = linearRegressionLine(line);
    return { slope: line.m, at, rSquared: rSquared(points, at) };
}

// A year's flow: the first day of its first phase of the season and the
// last day of its last (see detectPhases()), null where there was none.
// Whether the beginning and the ending were observed -- whether the days
// around them have data: where the dump has a hole there (a scale
// offline, see the dump script), the flow may well have gone on before
// or after, and the dot says nothing. See boundaryObserved().
export type Flow = {
    year: number,
    begin: Temporal.PlainDate | null,
    end: Temporal.PlainDate | null,
    beginObserved: boolean,
    endObserved: boolean,
};

// Whether a phase boundary was seen: at least half of the fortnight
// outside of it must have data.
export function boundaryObserved(records: DayRecord[], date: Temporal.PlainDate, before: boolean): boolean {
    const boundary = epochDay(date);
    const seen = records.filter(r => before
        ? r.day < boundary && r.day >= boundary - 14
        : r.day > boundary && r.day <= boundary + 14).length;
    return seen >= 7;
}

export function flowOf(year: number, records: DayRecord[]): Flow {
    const phases = trachtPhases(records);
    const begin = phases[0]?.start ?? null;
    const end = phases.length > 0 ? phases[phases.length - 1].end : null;
    return {
        year,
        begin,
        end,
        beginObserved: begin !== null && boundaryObserved(records, begin, true),
        endObserved: end !== null && boundaryObserved(records, end, false),
    };
}

export function flowTrend(flow: Flow[], key: "begin" | "end"): Trend | null {
    const observed = (f: Flow) => key === "begin" ? f.beginObserved : f.endObserved;
    return fitTrend(flow.flatMap(
        f => f[key] && observed(f)
            ? [[f.year, dayOfYear(f[key]!)] as [number, number]]
            : [],
    ));
}
