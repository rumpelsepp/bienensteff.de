// The change of weight per day of a year.

import { line, curveMonotoneX } from "d3-shape";

import { chooseQueenColor, getCurrentYear, getToday, getXWindow, isSeasonOver } from "../helpers";
import { toTitleCase } from "../../helpers";
import { DAY_MS, formatDE, hLine, mountChart, swatch, timeChart } from "../frame";
import { loadYear } from "./data";
import { calendarWeeklyMean, keyFigures, TRACHT_THRESHOLD, trachtPhases } from "./analysis";
import { dayDots, keyFigureNote, MEAN_COLOR, PHASE_NOTE, phaseBands, plotDay, SERIES_MEAN, shortDate } from "./marks";

// The change of weight per day of "year", as a bar a day and as the mean
// of the week around each day, which is also what decides on the phases
// of a honey flow. Which of the two leads depends on the time: during the
// season it is the bars -- did the hives gain yesterday? --, with the mean
// as a thin line. Once it is over, nobody remembers single days: then the
// mean leads, the bars fade behind it and the best day is marked.
// Other years are looked at by switching the year of the page.
export async function renderDerivativeChart(elementID: string, region: string, year: number) {
    const seasonOver = isSeasonOver(year);
    const records = await loadYear(region, year);
    const bestDay = seasonOver ? keyFigures(records)?.bestDay : undefined;
    const mean = calendarWeeklyMean(records);
    const phases = trachtPhases(records);
    const byDay = new Map(records.map((r, i) => [plotDay(r.date).getTime(), { record: r, mean: mean[i] }]));

    const notes = ["Gewichtsänderung pro Tag [kg]", PHASE_NOTE];
    if (bestDay) {
        notes.push(keyFigureNote([`Bester Tag +${formatDE.format(bestDay.delta!)} kg (${shortDate(bestDay.date)})`]));
    }
    const color = chooseQueenColor(year);
    const deltas = records.flatMap(r => r.delta !== null ? [r.delta] : []);
    const [start, end] = getXWindow(year);

    mountChart(elementID, {
        title: `Trachtänderungen ${toTitleCase(region)} ${year}`,
        notes,
        legend: [
            { label: year.toString(), color, look: "bar" },
            { label: SERIES_MEAN, color: MEAN_COLOR, look: "line" },
        ],
    }, canvas => timeChart(canvas, {
        year,
        // Nothing to see after today.
        window: [plotDay(start), plotDay(year === getCurrentYear() ? getToday() : end)],
        left: {
            domain: [Math.min(0, ...deltas), Math.max(TRACHT_THRESHOLD, ...deltas)],
            name: "Gewichtsänderung [kg]",
            format: v => v.toLocaleString("de-DE", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + " kg",
        },
        draw: (layer, x, y) => {
            const height = y.range()[0];
            phaseBands(layer, x, phases, height);
            // A bar a day, a loss paler than a gain.
            const dayWidth = x(new Date(DAY_MS)) - x(new Date(0));
            const barWidth = Math.max(1, dayWidth * 0.8);
            layer.append("g")
                .attr("opacity", seasonOver ? 0.4 : 1)
                .selectAll("rect")
                .data(records.filter(r => r.delta !== null))
                .join("rect")
                .attr("x", r => x(plotDay(r.date)) + (dayWidth - barWidth) / 2)
                .attr("width", barWidth)
                .attr("y", r => y(Math.max(0, r.delta!)))
                .attr("height", r => Math.abs(y(r.delta!) - y(0)))
                .attr("fill", r => chooseQueenColor(year, r.delta! < 0));
            // The threshold of a honey flow, see PHASE_NOTE.
            hLine(layer, y(TRACHT_THRESHOLD), x.range()[1], MEAN_COLOR);
            layer.append("path")
                .attr("class", "chart-line")
                .attr("stroke", MEAN_COLOR)
                .attr("stroke-width", seasonOver ? 3 : 1.5)
                .attr("d", line<number>()
                    .defined(i => mean[i] !== null)
                    .x(i => x(new Date(plotDay(records[i].date).getTime() + DAY_MS / 2)))
                    .y(i => y(mean[i]!))
                    .curve(curveMonotoneX)(records.map((_, i) => i)));
            if (bestDay) {
                dayDots(layer, x, y, [[bestDay.date, bestDay.delta!]]);
            }
        },
        tooltip: day => {
            const entry = byDay.get(day.getTime());
            if (!entry) {
                return null;
            }
            const { record, mean } = entry;
            let html = "";
            if (record.delta !== null) {
                html += `${swatch(color)}<b>${year}</b>: Δ ${formatDE.format(record.delta)} kg (${record.nWaagen} Waagen)<br>`;
            }
            if (mean !== null) {
                html += `${swatch(MEAN_COLOR)}<b>${SERIES_MEAN}</b>: Δ ${formatDE.format(mean)} kg`;
            }
            return html;
        },
    }));
}
