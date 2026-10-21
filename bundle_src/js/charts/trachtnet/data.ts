// The Trachtnet data: /trachtnet-dump/, written by
// scripts/src/bstools/cli/dump_trachtnet.py -- the days of a region in a
// year, and which regions and years there are.

import { Temporal } from "temporal-polyfill";

import { isInteger } from "../helpers";

// A day of a region: the mean of its scales.
export type DayRecord = {
    date: Temporal.PlainDate,
    // The date as days since 1970-01-01 (see epochDay()), for the
    // arithmetic on dates the phase detection does day by day.
    day: number,
    // Weight gained since the start of the year [kg].
    value: number,
    // Change against the day before [kg].
    delta: number | null,
    nWaagen: number,
}

// One line of a /trachtnet-dump/<kind>/<id>-<year>.ndjson file. Empty days,
// junk zeros and the still-provisional last two days are already filtered
// out by the dump.
export type RawRecord = {
    date: string,
    weight: number,
    delta: number | null,
    scales: number,
}

// An entry of /trachtnet-dump/index.json.
export type Region = {
    kind: "bundesland" | "regierungsbezirk" | "landkreis" | "waage",
    id: string,
    name: string,
    slug: string,
    years: number[],
}

export let regionIndex: Promise<Region[]> | null = null;

export function loadRegionIndex(): Promise<Region[]> {
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
export async function resolveRegion(region: string): Promise<Region> {
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
// The same array, too: what is worked out of it is kept along with it
// (see analysis.ts).
export const yearCache = new Map<string, Promise<DayRecord[]>>();

// The days of a region in a year, empty if the dump has none -- the region
// by its name, see resolveRegion().
export async function loadYear(region: string, year: number): Promise<DayRecord[]> {
    return loadRegionYear(await resolveRegion(region), year);
}

// The same for a region of the index, e.g. each Landkreis of a map.
export function loadRegionYear(r: Region, year: number): Promise<DayRecord[]> {
    const key = `${r.kind}/${r.id}/${year}`;
    let records = yearCache.get(key);
    if (!records) {
        records = fetchYear(r, year);
        yearCache.set(key, records);
    }
    return records;
}

export async function fetchYear(r: Region, year: number): Promise<DayRecord[]> {
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
            const date = Temporal.PlainDate.from(raw.date);
            return {
                date,
                day: epochDay(date),
                value: raw.weight,
                delta: raw.delta,
                nWaagen: raw.scales,
            };
        });
}

// Days since 1970-01-01. Comparing and counting days is what the phase
// detection does most; Temporal's polyfill takes milliseconds for what
// is a subtraction of two numbers here.
export function epochDay(date: Temporal.PlainDate): number {
    return Date.UTC(date.year, date.month - 1, date.day) / 86_400_000;
}

export async function otherYears(region: string, year: number): Promise<number[]> {
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
