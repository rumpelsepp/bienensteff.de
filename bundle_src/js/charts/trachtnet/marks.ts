// What the Trachtnet charts share: the shaded phases, the marked days and
// the lines below the titles that say what they are.

import { Temporal } from "temporal-polyfill";
import type * as echarts from "echarts";

import { getToday } from "../helpers";
import { chartColors } from "../base";
import { TRACHT_THRESHOLD, type Phase } from "./analysis";
import type { DayRecord } from "./data";

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

export const SERIES_MEAN = "7-Tage-Mittel";

// The honey of the site's palette, as the phases the mean decides on.
export const MEAN_COLOR = "#b8720c";

export function isYear(name: unknown): boolean {
    return typeof name === "string" && /^\d{4}$/.test(name);
}

export function shortDate(date: Temporal.PlainDate): string {
    return date.toLocaleString("de-DE", { day: "numeric", month: "numeric" });
}

// Dots on days of a series. What they stand for is said below the title
// (keyFigureNote): a text beside a dot lands on the lines around it.
export function markPoints(days: [DayRecord, number][]): echarts.MarkPointComponentOption {
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
export function keyFigureNote(parts: string[]): string {
    return `○ ${parts.join(" · ")}`;
}

export function todayMarkLine(): echarts.MarkLineComponentOption {
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

export function meanLabel(others: number[], year: number): string {
    if (others.length === 0) {
        return "Mittel";
    }
    const first = others[0];
    const last = others[others.length - 1];
    return `Mittel ${first}–${last}` + (year > first && year < last ? ` ohne ${year}` : "");
}

// Days as a signed text: "+2,5 Tage".
export function signedDays(days: number): string {
    return `${days >= 0 ? "+" : "-"}${Math.abs(days).toLocaleString("de-DE", { maximumFractionDigits: 1 })} Tage`;
}
