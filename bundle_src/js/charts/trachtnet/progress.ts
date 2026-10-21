// The weight gained over a year, against the years before.

import { line } from "d3-shape";

import { chooseQueenColor, getCurrentYear, getXWindow, isSeasonOver } from "../helpers";
import { toTitleCase } from "../../helpers";
import { DAY_MS, formatDE, mountChart, swatch, timeChart, type LegendItem } from "../frame";
import { loadYear, otherYears, type DayRecord } from "./data";
import { coversYear, keyFigures, meanPerDay, onCalendarOf, trachtPhases } from "./analysis";
import { dayDots, keyFigureNote, meanLabel, PHASE_NOTE, phaseBands, plotDay, shortDate, todayLine } from "./marks";

// The ink of the page, for the mean of the other years.
const INK = "var(--color-ink)";

// The weight gained over the year: "year" as a bold line, the years before
// and after it as thin ones -- the one after dotted --, where there is data
// for them, and as a dashed line the mean of the other complete years.
// Once the season is over the lowest and the highest stand are marked;
// before that they are only the lowest and highest so far.
export async function renderProgressChart(elementID: string, region: string, year: number) {
    const others = await otherYears(region, year);
    const [current, ...otherRecords] = await Promise.all([
        loadYear(region, year),
        ...others.map(y => loadYear(region, y)),
    ]);
    // The mean is over the other years with data for all of them (see
    // coversYear()).
    const complete = others.filter((_, i) => coversYear(otherRecords[i]));
    const means = meanPerDay(otherRecords.filter((_, i) => coversYear(otherRecords[i])), year);
    const neighbour = (y: number) => others.includes(y) ? onCalendarOf(otherRecords[others.indexOf(y)], year) : null;
    const previous = neighbour(year - 1);
    const next = neighbour(year + 1);
    const figures = isSeasonOver(year) ? keyFigures(current) : null;
    const phases = trachtPhases(current);
    const meanName = meanLabel(complete, year);

    const notes = ["Aufsummierte Gewichtsänderung pro Tag [kg]", PHASE_NOTE];
    if (figures) {
        notes.push(keyFigureNote([
            `Maximum ${formatDE.format(figures.max.value)} kg (${shortDate(figures.max.date)})`,
            `Minimum ${formatDE.format(figures.min.value)} kg (${shortDate(figures.min.date)})`,
        ]));
    }
    const legend: LegendItem[] = [{ label: year.toString(), color: chooseQueenColor(year), look: "line" }];
    if (previous) {
        legend.push({ label: (year - 1).toString(), color: chooseQueenColor(year - 1), look: "thin" });
    }
    if (next) {
        legend.push({ label: (year + 1).toString(), color: chooseQueenColor(year + 1), look: "dotted" });
    }
    if (means.length > 0) {
        legend.push({ label: meanName, color: INK, look: "dashed" });
    }

    const byDay = <T>(rows: [Date, T][]) => new Map(rows.map(([d, v]) => [d.getTime(), v]));
    const currentByDay = byDay(current.map(r => [plotDay(r.date), r]));
    const previousByDay = byDay((previous ?? []).map(r => [plotDay(r.date), r]));
    const nextByDay = byDay((next ?? []).map(r => [plotDay(r.date), r]));
    const meanByDay = byDay(means.map(([d, v]) => [plotDay(d), v]));
    const values = [...current, ...(previous ?? []), ...(next ?? [])].map(r => r.value).concat(means.map(([, v]) => v));
    const [start, end] = getXWindow(year);

    mountChart(elementID, { title: `Trachtverlauf ${toTitleCase(region)} ${year}`, notes, legend }, canvas => timeChart(canvas, {
        year,
        window: [plotDay(start), plotDay(end)],
        left: {
            domain: [Math.min(0, ...values), Math.max(1, ...values)],
            name: "Gewicht [kg]",
            format: v => Math.trunc(v) + " kg",
        },
        draw: (layer, x, y) => {
            const height = y.range()[0];
            phaseBands(layer, x, phases, height);
            const middle = (date: Date) => x(new Date(date.getTime() + DAY_MS / 2));
            const path = (rows: DayRecord[]) => line<DayRecord>()
                .x(r => middle(plotDay(r.date)))
                .y(r => y(r.value))(rows);
            if (means.length > 0) {
                layer.append("path")
                    .attr("class", "chart-line chart-dashed")
                    .style("stroke", INK)
                    .attr("stroke-width", 1.5)
                    .attr("opacity", 0.7)
                    .attr("d", line<[Date, number]>().x(([d]) => middle(d)).y(([, v]) => y(v))(means.map(([d, v]) => [plotDay(d), v])));
            }
            if (previous) {
                layer.append("path")
                    .attr("class", "chart-line")
                    .attr("stroke", chooseQueenColor(year - 1))
                    .attr("stroke-width", 1.5)
                    .attr("d", path(previous));
            }
            if (next) {
                layer.append("path")
                    .attr("class", "chart-line chart-dotted")
                    .attr("stroke", chooseQueenColor(year + 1))
                    .attr("stroke-width", 1.75)
                    .attr("d", path(next));
            }
            layer.append("path")
                .attr("class", "chart-line")
                .attr("stroke", chooseQueenColor(year))
                .attr("stroke-width", 3)
                .attr("d", path(current));
            if (year === getCurrentYear()) {
                todayLine(layer, x, height);
            }
            if (figures) {
                dayDots(layer, x, y, [[figures.max.date, figures.max.value], [figures.min.date, figures.min.value]]);
            }
        },
        tooltip: day => {
            const key = day.getTime();
            let html = "";
            const row = (r: DayRecord | undefined, y: number) => {
                if (r) {
                    const change = r.delta !== null ? `Δ ${formatDE.format(r.delta)} kg, ` : "";
                    html += `${swatch(chooseQueenColor(y))}<b>${y}</b>: ${formatDE.format(r.value)} kg (${change}${r.nWaagen} Waagen)<br>`;
                }
            };
            row(currentByDay.get(key), year);
            row(previousByDay.get(key), year - 1);
            row(nextByDay.get(key), year + 1);
            const m = meanByDay.get(key);
            if (m !== undefined) {
                html += `${swatch(INK)}<b>${meanName}</b>: ${formatDE.format(m)} kg`;
            }
            return html || null;
        },
    }));
}
