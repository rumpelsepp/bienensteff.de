// When the honey flow began and ended, over the years.

import type * as echarts from "echarts";

import { QueenColor, chooseQueenColor, getCurrentYear } from "../helpers";
import { toTitleCase } from "../../helpers";
import { buildBaseOption, chartColors, chartGrid, headHeight, initEchartsInstance, valueAxis } from "../base";
import { availableYears, loadYear } from "./data";
import { dayOfYear, dayOfYearToDate, flowOf, flowTrend, type Flow, type Trend } from "./analysis";
import { MEAN_COLOR, signedDays } from "./marks";

const SERIES_BEGIN = "Trachtbeginn";

const SERIES_END = "Trachtende";

const SERIES_TREND_BEGIN = "Trend Beginn";

const SERIES_TREND_END = "Trend Ende";

// The dots of a flow series: one per year in its queen colour, the years
// chronological as a thin line in the ink of the mode. A year without a
// flow has no dot, and the line skips it. An unobserved boundary (see
// Flow.beginObserved) is drawn hollow: there is a dot, but it says
// nothing -- the days around it are missing from the dump.
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
        data: flow.map(f => {
            if (!f[key]) {
                return [f.year.toString(), null];
            }
            const observed = key === "begin" ? f.beginObserved : f.endObserved;
            return {
                value: [f.year.toString(), dayOfYear(f[key]!), f[key]!.toLocaleString(), observed ? 1 : 0],
                itemStyle: observed
                    ? { color: chooseQueenColor(f.year) }
                    : {
                        color: "none",
                        borderColor: chooseQueenColor(f.year),
                        borderWidth: 2,
                    },
            };
        }),
    };
}

// The dashed trend line over the years, from a regression (see
// fitTrend()); nothing if there is nothing to fit.
function trendSeries(name: string, flow: Flow[], trend: Trend | null, color: string): echarts.SeriesOption | null {
    if (!trend) {
        return null;
    }
    const at = trend.at;
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
    const flow = years.map((year, i) => flowOf(year, recordsPerYear[i]));

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
                if (!p.value[3]) {
                    out += " (unsicher: zu wenig Daten davor/danach)";
                }
                const trend = p.seriesName === SERIES_BEGIN ? trendBegin : trendEnd;
                if (trend && p.value[3]) {
                    const toTrend = Math.round(p.value[1] - trend.at(+p.name));
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

    const trendNote = (label: string, trend: Trend | null): string | null =>
        trend ? `${label}: ${signedDays(trend.slope)} pro Jahr` : null;
    const notes = [
        `● ${SERIES_BEGIN}, ◆ ${SERIES_END} · ◌ unsicher (Mär–Aug)`,
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
