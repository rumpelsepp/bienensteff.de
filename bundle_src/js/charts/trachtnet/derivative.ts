// The change of weight per day of a year.

import type * as echarts from "echarts";

import { chooseQueenColor, getCurrentYear, getToday, getXWindow, isSeasonOver } from "../helpers";
import { toTitleCase } from "../../helpers";
import { buildBaseOption, buildFormatterDE, chartGrid, headHeight, initEchartsInstance, valueAxis } from "../base";
import { loadYear } from "./data";
import { calendarWeeklyMean, keyFigures, TRACHT_THRESHOLD, trachtPhases } from "./analysis";
import { keyFigureNote, markPoints, MEAN_COLOR, PHASE_NOTE, phaseMarkArea, SERIES_MEAN, shortDate } from "./marks";

// The change of weight per day of "year", as a bar a day and as the mean
// of the week around each day, which is also what decides on the phases
// of a honey flow. Which of the two leads depends on the time: during the
// season it is the bars -- did the hives gain yesterday? --, with the mean
// as a thin line. Once it is over, nobody remembers single days: then the
// mean leads, the bars fade behind it and the best day is marked.
// Other years are looked at by switching the year of the page.
export async function renderDerivativeChart(elementID: string, region: string, year: number) {
    const chart = initEchartsInstance(elementID);
    const formatterDE = buildFormatterDE();
    const seasonOver = isSeasonOver(year);

    const current = await loadYear(region, year);
    const bestDay = seasonOver ? keyFigures(current)?.bestDay : undefined;

    const series: echarts.SeriesOption[] = [{
        name: year.toString(),
        type: "bar",
        markPoint: bestDay ? markPoints([[bestDay, bestDay.delta!]]) : undefined,
        // For the marker in the legend and in the tooltip; the bars have
        // their colours set one by one: a loss is paler than a gain.
        itemStyle: {
            color: chooseQueenColor(year),
        },
        data: current.map(r => ({
            value: [r.date.toString(), r.delta, r.value, r.nWaagen],
            itemStyle: {
                color: chooseQueenColor(year, (r.delta ?? 0) < 0),
                opacity: seasonOver ? 0.4 : 1,
            },
        })),
    }];

    const mean = calendarWeeklyMean(current);
    series.push({
        name: SERIES_MEAN,
        type: "line",
        showSymbol: false,
        smooth: true,
        z: 3,
        lineStyle: {
            color: MEAN_COLOR,
            width: seasonOver ? 3 : 1.5,
        },
        itemStyle: {
            color: MEAN_COLOR,
        },
        // The threshold of a honey flow, see PHASE_NOTE.
        markLine: {
            symbol: "none",
            silent: true,
            label: {
                show: false,
            },
            lineStyle: {
                type: "dashed",
                color: MEAN_COLOR,
            },
            data: [
                { yAxis: TRACHT_THRESHOLD }
            ],
        },
        markArea: phaseMarkArea(trachtPhases(current)),
        data: current.map((r, i) => [r.date.toString(), mean[i]]),
    });

    const tooltipFormatter = (params: any): string => {
        let out = "";
        for (const p of params) {
            const prefix = `${p.marker} <b>${p.seriesName}</b>`;
            if (p.seriesName === SERIES_MEAN) {
                out += `${prefix}: Δ ${formatterDE.format(p.value[1])} kg<br>`;
            } else {
                out += `${prefix}: Δ ${formatterDE.format(p.value[1])} kg (${p.value[3]} Waagen)<br>`;
            }
        }
        return out;
    };

    const notes = ["Gewichtsänderung pro Tag [kg]", PHASE_NOTE];
    if (bestDay) {
        notes.push(keyFigureNote([`Bester Tag +${formatterDE.format(bestDay.delta!)} kg (${shortDate(bestDay.date)})`]));
    }

    const [startDate, endDate] = getXWindow(year);
    chart.setOption({
        ...buildBaseOption(
            `Trachtänderungen ${toTitleCase(region)} ${year}`,
            notes.join("\n"),
            tooltipFormatter,
            year,
        ),
        grid: chartGrid(headHeight(notes.length) + 12),
        yAxis: valueAxis("Gewichtsänderung [kg]", val => Intl.NumberFormat("de-DE", {
            minimumFractionDigits: 1,
            maximumFractionDigits: 1
        }).format(val) + " kg"),
        legend: {
            show: true,
            top: "bottom",
        },
        dataZoom: [
            {
                type: "inside",
                xAxisIndex: 0,
                startValue: startDate.toString(),
                // Nothing to see after today.
                endValue: (year === getCurrentYear() ? getToday() : endDate).toString(),
            }
        ],
        series,
    });
}
