// What the Trachtnet charts share: the shaded phases, the marked days and
// the lines below the titles that say what they are.

import { Temporal } from "temporal-polyfill";
import type { ScaleLinear, ScaleTime } from "d3-scale";

import { getToday } from "../helpers";
import { DAY_MS, utcDay, type Layer } from "../frame";
import { TRACHT_THRESHOLD, type Phase } from "./analysis";

// A date of the data as one of the plot, see utcDay().
export function plotDay(date: Temporal.PlainDate): Date {
    return utcDay(date.year, date.month, date.day);
}

// What the shaded bands of phaseMarkArea() are, for the line below the
// title of a chart.
export const PHASE_NOTE = `hinterlegt: Tracht (7-Tage-Mittel ab ${TRACHT_THRESHOLD.toLocaleString("de-DE")} kg pro Tag)`;

// The phases as shaded bands across the plot, from the beginning of their
// first day to the end of their last. What they are is said once, below
// the title of the chart (PHASE_NOTE).
export function phaseBands(layer: Layer, x: ScaleTime<number, number>, phases: Phase[], height: number) {
    layer.append("g")
        .attr("class", "chart-phases")
        .selectAll("rect")
        .data(phases)
        .join("rect")
        .attr("x", p => x(plotDay(p.start)))
        .attr("width", p => x(new Date(plotDay(p.end).getTime() + DAY_MS)) - x(plotDay(p.start)))
        .attr("y", 0)
        .attr("height", height);
}

export const SERIES_MEAN = "7-Tage-Mittel";

// The honey of the site's palette, as the phases the mean decides on.
export const MEAN_COLOR = "#b8720c";

export function shortDate(date: Temporal.PlainDate): string {
    return date.toLocaleString("de-DE", { day: "numeric", month: "numeric" });
}

// Hollow dots on days of a series, in the middle of the day. What they
// stand for is said below the title (keyFigureNote): a text beside a dot
// lands on the lines around it.
export function dayDots(layer: Layer, x: ScaleTime<number, number>, y: ScaleLinear<number, number>, days: [Temporal.PlainDate, number][]) {
    layer.append("g")
        .selectAll("circle")
        .data(days)
        .join("circle")
        .attr("class", "chart-key-dot")
        .attr("cx", ([date]) => x(new Date(plotDay(date).getTime() + DAY_MS / 2)))
        .attr("cy", ([, value]) => y(value))
        .attr("r", 4.5);
}

// The line below the title for the marked days: "○ Maximum 44,36 kg (29.6.)".
export function keyFigureNote(parts: string[]): string {
    return `○ ${parts.join(" · ")}`;
}

// A dashed line at today, in a chart of the year still running.
export function todayLine(layer: Layer, x: ScaleTime<number, number>, height: number) {
    const at = x(plotDay(getToday()));
    layer.append("line")
        .attr("class", "chart-dashed chart-ink")
        .attr("x1", at).attr("x2", at)
        .attr("y1", 0).attr("y2", height);
}

// What the mean over "others" is called: "Mittel 2012–2024", "ohne" the
// year shown where it lies within, and the number of years where some of
// the span are missing (see coversYear()).
export function meanLabel(others: number[], year: number): string {
    if (others.length === 0) {
        return "Mittel";
    }
    const first = others[0];
    const last = others[others.length - 1];
    const within = year > first && year < last;
    const span = last - first + 1 - (within ? 1 : 0);
    return `Mittel ${first}–${last}`
        + (within ? ` ohne ${year}` : "")
        + (others.length < span ? ` (${others.length} Jahre)` : "");
}

// Days as a signed text: "+2,5 Tage".
export function signedDays(days: number): string {
    return `${days >= 0 ? "+" : "-"}${Math.abs(days).toLocaleString("de-DE", { maximumFractionDigits: 1 })} Tage`;
}
