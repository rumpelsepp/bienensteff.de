import { median } from "simple-statistics";

import { chooseQueenColor } from "../helpers";
import { toTitleCase } from "../../helpers";
import { hatch, mountChart, swatch, yearChart } from "../frame";
import { availableYears, loadYear } from "./data";
import { datesTicks, dayOfYear, dayOfYearToDate, fitTrend, GAP_MIN_DAYS, trachtGaps, type Gap } from "./analysis";
import { signedDays } from "./marks";

// The gaps chart: the days without a honey flow between a season's
// phases (see trachtGaps()), one vertical segment per gap and year --
// for the question when in the year there is time to harvest, how much
// that timing moves around and whether it has drifted over the years.

const shortDate = (doy: number) => dayOfYearToDate(doy).toLocaleString("de-DE", { day: "numeric", month: "numeric" });

export async function renderGapsChart(elementID: string, region: string) {
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

    // Whether the gaps have drifted over the years: the trend of the
    // centers of the longest ones.
    const centers: [number, number][] = longestPerYear.flatMap((g, i) => g
        ? [[years[i], (dayOfYear(g.start) + dayOfYear(g.end)) / 2] as [number, number]]
        : []);
    const trend = fitTrend(centers);

    const notes = [
        `Trachtlücken ab ${GAP_MIN_DAYS} Tagen zwischen den Trachtphasen (ab März)`,
        "dick: längste Lücke · gestrichelt: Datenlücke",
        typical
            ? `hinterlegt: Median ${shortDate(typical.start)}–${shortDate(typical.end)}`
            : "Zu wenig verlässliche Jahre für einen Median",
        trend
            ? `Trend: ${signedDays(trend.slope * 10)}/Jahrzehnt · R² ${trend.rSquared.toLocaleString("de-DE", { maximumFractionDigits: 2 })}${trend.rSquared < 0.25 ? " – eher zufällig" : ""}`
            : "Zu wenig Jahre für einen Trend",
    ];
    const all = gapsPerYear.flat();
    const days = all.flatMap(g => [dayOfYear(g.start), dayOfYear(g.end)]);

    mountChart(elementID, { title: `Trachtlücken ${toTitleCase(region)}`, notes }, canvas => yearChart(canvas, {
        years,
        left: {
            domain: days.length > 0 ? [Math.min(...days) - 5, Math.max(...days) + 5] : [60, 244],
            name: "Tag des Jahres",
            ticks: y => datesTicks(...(y.domain() as [number, number])),
            format: doy => dayOfYearToDate(doy).toLocaleString("de-DE", { day: "numeric", month: "short" }),
        },
        draw: (layer, x, y) => {
            const width = x.range()[1];
            // The rule of thumb as a band: the typical window of the
            // longest gap, across all the years.
            if (typical) {
                layer.append("rect")
                    .attr("class", "chart-typical")
                    .attr("x", 0)
                    .attr("width", width)
                    .attr("y", y(typical.end + 1))
                    .attr("height", y(typical.start) - y(typical.end + 1));
            }
            // One vertical segment per gap, at its year: the longest wide,
            // a hole in the data (see Gap.reliable) only outlined.
            const segments = gapsPerYear.flatMap((gaps, i) => gaps.map(g => ({ gap: g, year: years[i] })));
            layer.append("g")
                .selectAll("rect")
                .data(segments)
                .join("rect")
                .attr("class", ({ gap }) => gap.reliable ? "" : "chart-gap-hole")
                .attr("x", ({ gap, year }) => x(year)! + x.bandwidth() / 2 - (gap.longest ? 8 : 3.5))
                .attr("width", ({ gap }) => gap.longest ? 16 : 7)
                .attr("rx", ({ gap }) => gap.longest ? 8 : 3.5)
                .attr("y", ({ gap }) => y(dayOfYear(gap.end) + 1))
                .attr("height", ({ gap }) => Math.max(2, y(dayOfYear(gap.start)) - y(dayOfYear(gap.end) + 1)))
                .attr("fill", ({ gap, year }) => gap.reliable ? chooseQueenColor(year, !gap.longest) : "none");
            // Stripes over the gaps that rest on data, so that they read
            // without their colour, too.
            layer.append("g")
                .attr("pointer-events", "none")
                .selectAll("rect")
                .data(segments.filter(({ gap }) => gap.reliable))
                .join("rect")
                .attr("x", ({ gap, year }) => x(year)! + x.bandwidth() / 2 - (gap.longest ? 8 : 3.5))
                .attr("width", ({ gap }) => gap.longest ? 16 : 7)
                .attr("rx", ({ gap }) => gap.longest ? 8 : 3.5)
                .attr("y", ({ gap }) => y(dayOfYear(gap.end) + 1))
                .attr("height", ({ gap }) => Math.max(2, y(dayOfYear(gap.start)) - y(dayOfYear(gap.end) + 1)))
                .style("fill", hatch("stripes"));
            if (trend) {
                layer.append("line")
                    .attr("class", "chart-dashed chart-ink")
                    .attr("stroke-width", 1.5)
                    .attr("opacity", 0.8)
                    .attr("x1", x(years[0])! + x.bandwidth() / 2)
                    .attr("x2", x(years[years.length - 1])! + x.bandwidth() / 2)
                    .attr("y1", y(trend.at(years[0]) + 0.5))
                    .attr("y2", y(trend.at(years[years.length - 1]) + 0.5));
            }
        },
        tooltip: year => {
            const gaps = gapsPerYear[years.indexOf(year)];
            if (!gaps || gaps.length === 0) {
                return null;
            }
            const date = (d: Gap["start"]) => d.toLocaleString("de-DE", { day: "numeric", month: "numeric" });
            return gaps.map(g => g.reliable
                ? `${swatch(chooseQueenColor(year, !g.longest))}${g.days} Tage ohne Tracht (${date(g.start)} – ${date(g.end)})${g.longest ? " – längste Lücke" : ""}`
                : `${swatch("transparent")}Datenlücke, nur ${g.covered} von ${g.days} Tagen mit Daten`).join("<br>");
        },
    }));
}
