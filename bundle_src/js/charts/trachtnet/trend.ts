// When the honey flow began and ended, over the years.

import { line, symbol, symbolCircle, symbolDiamond } from "d3-shape";
import type { ScaleBand, ScaleLinear } from "d3-scale";

import { QueenColor, chooseQueenColor } from "../helpers";
import { toTitleCase } from "../../helpers";
import { mountChart, swatch, yearChart, type Layer } from "../frame";
import { availableYears, loadYear } from "./data";
import { datesTicks, dayOfYear, dayOfYearToDate, flowOf, flowTrend, type Flow, type Trend } from "./analysis";
import { MEAN_COLOR, signedDays } from "./marks";

const SERIES_BEGIN = "Trachtbeginn";
const SERIES_END = "Trachtende";
const TREND_BEGIN_COLOR = MEAN_COLOR;
const TREND_END_COLOR = QueenColor.Green;

const dateLabel = (doy: number) => dayOfYearToDate(doy).toLocaleString("de-DE", { day: "numeric", month: "short" });

// The dots of the beginnings or the ends: one per year in its queen
// colour, the years chronological as a thin line. An unobserved boundary
// (see Flow.beginObserved) is drawn hollow: there is a dot, but it says
// nothing -- the days around it are missing from the dump.
function flowDots(layer: Layer, x: ScaleBand<number>, y: ScaleLinear<number, number>, flow: Flow[], key: "begin" | "end") {
    const center = (year: number) => x(year)! + x.bandwidth() / 2;
    const seen = flow.filter(f => f[key]);
    layer.append("path")
        .attr("class", "chart-line chart-ink")
        .attr("opacity", 0.5)
        .attr("d", line<Flow>()
            .defined(f => f[key] !== null)
            .x(f => center(f.year))
            .y(f => y(dayOfYear(f[key]!)))(flow));
    const shape = symbol(key === "begin" ? symbolCircle : symbolDiamond, 70);
    layer.append("g")
        .selectAll("path")
        .data(seen)
        .join("path")
        .attr("d", shape)
        .attr("transform", f => `translate(${center(f.year)},${y(dayOfYear(f[key]!))})`)
        .attr("fill", f => (key === "begin" ? f.beginObserved : f.endObserved) ? chooseQueenColor(f.year) : "none")
        .attr("stroke", f => chooseQueenColor(f.year))
        .attr("stroke-width", 2);
}

// The dashed trend line over the years, from a regression (see
// fitTrend()).
function trendLine(layer: Layer, x: ScaleBand<number>, y: ScaleLinear<number, number>, years: number[], trend: Trend, color: string) {
    const first = years[0];
    const last = years[years.length - 1];
    layer.append("line")
        .attr("class", "chart-dashed")
        .attr("stroke", color)
        .attr("stroke-width", 2)
        .attr("x1", x(first)! + x.bandwidth() / 2)
        .attr("x2", x(last)! + x.bandwidth() / 2)
        .attr("y1", y(trend.at(first)))
        .attr("y2", y(trend.at(last)));
}

// When the flow began and ended each year: a circle for the beginning, a
// diamond for the end, both in the year's queen colour, the years
// chronological as thin lines, and a dashed trend line over each. The
// chart spans all years on its own: it doesn't follow the year the page
// shows. For the year still running, the end is where the flow stands.
export async function renderTrendChart(elementID: string, region: string) {
    const years = await availableYears([region]);
    const recordsPerYear = await Promise.all(years.map(y => loadYear(region, y)));
    const flow = years.map((year, i) => flowOf(year, recordsPerYear[i]));
    const trendBegin = flowTrend(flow, "begin");
    const trendEnd = flowTrend(flow, "end");

    const trendNote = (label: string, trend: Trend | null) => trend ? `${label}: ${signedDays(trend.slope)} pro Jahr` : null;
    const notes = [
        `● ${SERIES_BEGIN}, ◆ ${SERIES_END} · ◌ unsicher (Mär–Aug)`,
        [trendNote("Beginn", trendBegin), trendNote("Ende", trendEnd)].filter(t => t !== null).join(", ")
            || "Zu wenig Jahre für einen Trend",
    ];
    const days = flow.flatMap(f => [f.begin, f.end].flatMap(d => d ? [dayOfYear(d)] : []));

    mountChart(elementID, {
        title: `Trachtbeginn und -ende ${toTitleCase(region)}`,
        notes,
        legend: [
            { label: "Trend Beginn", color: TREND_BEGIN_COLOR, look: "dashed" },
            { label: "Trend Ende", color: TREND_END_COLOR, look: "dashed" },
        ],
    }, canvas => yearChart(canvas, {
        years,
        left: {
            domain: days.length > 0 ? [Math.min(...days) - 5, Math.max(...days) + 5] : [60, 244],
            name: "Tag des Jahres",
            ticks: y => datesTicks(...(y.domain() as [number, number])),
            format: dateLabel,
        },
        draw: (layer, x, y) => {
            flowDots(layer, x, y, flow, "begin");
            flowDots(layer, x, y, flow, "end");
            if (trendBegin) {
                trendLine(layer, x, y, years, trendBegin, TREND_BEGIN_COLOR);
            }
            if (trendEnd) {
                trendLine(layer, x, y, years, trendEnd, TREND_END_COLOR);
            }
        },
        tooltip: year => {
            const f = flow.find(x => x.year === year);
            if (!f || (!f.begin && !f.end)) {
                return null;
            }
            let html = "";
            const row = (name: string, key: "begin" | "end", trend: Trend | null) => {
                const date = f[key];
                if (!date) {
                    return;
                }
                const observed = key === "begin" ? f.beginObserved : f.endObserved;
                html += `${swatch(chooseQueenColor(year))}<b>${name}</b>: ${date.toLocaleString("de-DE")}`;
                if (!observed) {
                    html += " (unsicher: zu wenig Daten davor/danach)";
                } else if (trend) {
                    const toTrend = Math.round(dayOfYear(date) - trend.at(year));
                    if (toTrend !== 0) {
                        html += ` (${toTrend > 0 ? "+" : ""}${toTrend} Tage zum Trend)`;
                    }
                }
                html += "<br>";
            };
            row(SERIES_BEGIN, "begin", trendBegin);
            row(SERIES_END, "end", trendEnd);
            return html;
        },
    }));
}
