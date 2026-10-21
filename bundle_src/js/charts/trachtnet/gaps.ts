import type * as echarts from "echarts";
import { median } from "simple-statistics";

import { chooseQueenColor, getCurrentYear } from "../helpers";
import { toTitleCase } from "../../helpers";
import { buildBaseOption, chartColors, chartGrid, headHeight, initEchartsInstance, valueAxis } from "../base";
import { availableYears, loadYear } from "./data";
import { dayOfYear, dayOfYearToDate, fitTrend, GAP_MIN_DAYS, trachtGaps } from "./analysis";
import { signedDays } from "./marks";

// The gaps chart: the days without a honey flow between a season's
// phases (see trachtGaps()), one vertical segment per gap and year --
// for the question when in the year there is time to harvest, how much
// that timing moves around and whether it has drifted over the years.

export async function renderGapsChart(elementID: string, region: string) {
    const chart = initEchartsInstance(elementID);
    const colors = chartColors();

    const years = await availableYears([region]);
    const recordsPerYear = await Promise.all(years.map(y => loadYear(region, y)));
    const gapsPerYear = recordsPerYear.map(records => trachtGaps(records));
    const longestPerYear = gapsPerYear.map(gaps => gaps.find(g => g.longest) ?? null);

    // The rule of thumb to take away: the median of when the longest gaps
    // begin and of how long they last over the years -- only over the
    // ones that rest on data, see Gap.reliable. (A median of their ends
    // could come out before the median of their beginnings.)
    const solid = longestPerYear.flatMap(g => g ? [g] : []);
    const medianStart = solid.length > 0 ? median(solid.map(g => dayOfYear(g.start))) : 0;
    const typical = solid.length > 0 ? {
        start: medianStart,
        end: medianStart + median(solid.map(g => g.days)) - 1,
    } : null;
    const medianText = (doy: number) =>
        dayOfYearToDate(doy).toLocaleString("de-DE", { day: "numeric", month: "numeric" });

    // Whether the gaps have drifted over the years: the trend of the
    // centers of the longest ones.
    const centers: [number, number][] = longestPerYear.flatMap((g, i) => g
        ? [[years[i], (dayOfYear(g.start) + dayOfYear(g.end)) / 2] as [number, number]]
        : []);
    const trend = fitTrend(centers);

    // One vertical segment per gap, at its year. The segments are what is
    // read here, so they carry their tooltip themselves; what they stand
    // for is in the notes below the title.
    const segments: echarts.SeriesOption = {
        type: "custom",
        name: "Trachtlücken",
        z: 3,
        renderItem: (_params: any, api: any) => {
            const x = api.coord([api.value(0), api.value(1)])[0];
            const yTop = api.coord([api.value(0), api.value(2)])[1];
            const yBottom = api.coord([api.value(0), api.value(1)])[1];
            const width = api.value(3) ? 16 : 7;
            const height = Math.max(yBottom - yTop, 2);
            // An unreliable gap (see Gap.reliable) is only outlined: a
            // hole in the data, not a window to harvest in.
            const style = api.value(8)
                ? {
                    fill: chooseQueenColor(api.value(5), !api.value(3)),
                }
                : {
                    fill: "none",
                    stroke: chartColors().ink,
                    lineWidth: 1.5,
                    lineDash: [4, 3],
                    opacity: 0.7,
                };
            return {
                type: "rect",
                shape: { x: x - width / 2, y: yTop, width, height, r: width / 2 },
                style,
            };
        },
        data: gapsPerYear.flatMap((gaps, i) => gaps.map(g => ({
            value: [
                i,                                   // 0: the year's index on the x axis
                dayOfYear(g.start),                  // 1: where the gap begins
                dayOfYear(g.end),                    // 2: where it ends
                g.longest ? 1 : 0,                    // 3: the season's longest?
                g.days,                              // 4
                years[i],                            // 5: for the queen colour
                g.start.toLocaleString("de-DE", { day: "numeric", month: "numeric" }),
                g.end.toLocaleString("de-DE", { day: "numeric", month: "numeric" }),
                g.reliable ? 1 : 0,                   // 8: rest on data?
                g.covered,                            // 9
            ],
        }))),
    };

    // The rule of thumb as a band: the typical window of the longest gap,
    // across all the years.
    let band: echarts.SeriesOption | null = null;
    if (typical) {
        band = {
            type: "custom",
            name: "Median",
            z: 1,
            silent: true,
            renderItem: (params: any, api: any) => {
                const sys = params.coordSys;
                const yTop = api.coord([0, typical.end])[1];
                const yBottom = api.coord([0, typical.start])[1];
                return {
                    type: "rect",
                    shape: { x: sys.x, y: yTop, width: sys.width, height: yBottom - yTop },
                    style: {
                        fill: colors.ink,
                        opacity: 0.07,
                    },
                };
            },
            data: [[0, typical.start, typical.end]],
        };
    }

    let trendLine: echarts.SeriesOption | null = null;
    if (trend) {
        const at = trend.at;
        trendLine = {
            type: "line",
            name: "Trend der Mitten",
            showSymbol: false,
            z: 4,
            lineStyle: { color: chartColors().ink, width: 1.5, type: "dashed", opacity: 0.8 },
            itemStyle: { color: chartColors().ink, opacity: 0.8 },
            silent: true,
            data: [
                [0, at(years[0])],
                [years.length - 1, at(years[years.length - 1])],
            ],
        };
    }

    const tooltipFormatter = (params: any): string => {
        const parts = Array.isArray(params) ? params : [params];
        let out = "";
        for (const p of parts) {
            if (p.seriesName === "Trachtlücken") {
                const v = p.value as number[];
                if (v[8]) {
                    out += `${p.marker} <b>${v[5]}</b>: ${v[4]} Tage ohne Tracht (${v[6]} – ${v[7]})`
                        + (v[3] ? " – längste Lücke" : "") + "<br>";
                } else {
                    out += `${p.marker} <b>${v[5]}</b>: Datenlücke, nur ${v[9]} von ${v[4]} Tagen mit Daten<br>`;
                }
            }
        }
        return out;
    };

    const notes = [
        `Trachtlücken ab ${GAP_MIN_DAYS} Tagen zwischen den Trachtphasen (ab März)`,
        "dick: längste Lücke · gestrichelt: Datenlücke",
        typical
            ? `hinterlegt: Median ${medianText(typical.start)}–${medianText(typical.end)}`
            : "Zu wenig verlässliche Jahre für einen Median",
        trend
            ? `Trend: ${signedDays(trend.slope * 10)}/Jahrzehnt · R² ${trend.rSquared.toLocaleString("de-DE", { maximumFractionDigits: 2 })}${trend.rSquared < 0.25 ? " – eher zufällig" : ""}`
            : "Zu wenig Jahre für einen Trend",
    ];

    chart.setOption({
        ...buildBaseOption(
            `Trachtlücken ${toTitleCase(region)}`,
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
        series: ([band, segments, trendLine] as (echarts.SeriesOption | null)[])
            .filter((s): s is echarts.SeriesOption => s !== null),
    });
}
