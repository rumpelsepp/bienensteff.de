// The weight gained over a year, against the years before.

import type * as echarts from "echarts";

import { chooseQueenColor, getCurrentYear, getXWindow, isSeasonOver } from "../helpers";
import { toTitleCase } from "../../helpers";
import { buildBaseOption, buildFormatterDE, chartColors, chartGrid, headHeight, initEchartsInstance, valueAxis } from "../base";
import { loadYear, otherYears, type DayRecord } from "./data";
import { keyFigures, meanPerDay, onCalendarOf, trachtPhases } from "./analysis";
import { isYear, keyFigureNote, markPoints, meanLabel, PHASE_NOTE, phaseMarkArea, shortDate, todayMarkLine } from "./marks";

// The weight gained over the year: "year" as a bold line, the year before
// as a thin one, and as a dashed line the mean of all the other years.
// Once the season is over the lowest and the highest stand are marked;
// before that they are only the lowest and highest so far.
export async function renderProgressChart(elementID: string, region: string, year: number) {
    const chart = initEchartsInstance(elementID);
    const formatterDE = buildFormatterDE();
    const colors = chartColors();
    const isCurrent = year === getCurrentYear();

    const others = await otherYears(region, year);
    const [current, ...otherRecords] = await Promise.all([
        loadYear(region, year),
        ...others.map(y => loadYear(region, y)),
    ]);
    const means = meanPerDay(otherRecords, year);
    const seriesMean = meanLabel(others, year);

    const yearSeries = (y: number, records: DayRecord[], bold: boolean): echarts.LineSeriesOption => ({
        name: y.toString(),
        type: "line",
        showSymbol: false,
        z: bold ? 4 : 3,
        lineStyle: {
            color: chooseQueenColor(y),
            width: bold ? 3 : 1.5,
        },
        // The marker in the legend and in the tooltip takes the colour of
        // the item, not that of the line.
        itemStyle: {
            color: chooseQueenColor(y),
        },
        data: onCalendarOf(records, year).map(r => [r.date.toString(), r.value, r.nWaagen, r.delta]),
    });

    const series: echarts.SeriesOption[] = [];
    if (means.length > 0) {
        series.push({
            name: seriesMean,
            type: "line",
            showSymbol: false,
            z: 2,
            lineStyle: { color: colors.ink, width: 1.5, type: "dashed", opacity: 0.7 },
            itemStyle: { color: colors.ink, opacity: 0.7 },
            data: means.map(([date, mean]) => [date.toString(), mean]),
        });
    }
    if (others.includes(year - 1)) {
        series.push(yearSeries(year - 1, otherRecords[others.indexOf(year - 1)], false));
    }
    const figures = isSeasonOver(year) ? keyFigures(current) : null;
    series.push({
        ...yearSeries(year, current, true),
        markLine: isCurrent ? todayMarkLine() : undefined,
        markArea: phaseMarkArea(trachtPhases(current)),
        markPoint: figures ? markPoints([
            [figures.max, figures.max.value],
            [figures.min, figures.min.value],
        ]) : undefined,
    });
    const notes = ["Aufsummierte Gewichtsänderung pro Tag [kg]", PHASE_NOTE];
    if (figures) {
        notes.push(keyFigureNote([
            `Maximum ${formatterDE.format(figures.max.value)} kg (${shortDate(figures.max.date)})`,
            `Minimum ${formatterDE.format(figures.min.value)} kg (${shortDate(figures.min.date)})`,
        ]));
    }

    const tooltipFormatter = (params: any): string => {
        let out = "";
        for (const p of params) {
            const prefix = `${p.marker} <b>${p.seriesName}</b>`;
            if (isYear(p.seriesName)) {
                const [, value, waagen, delta] = p.value;
                const change = delta !== null ? `Δ ${formatterDE.format(delta)} kg, ` : "";
                out += `${prefix}: ${formatterDE.format(value)} kg (${change}${waagen} Waagen)<br>`;
            } else if (p.seriesName === seriesMean) {
                out += `${prefix}: ${formatterDE.format(p.value[1])} kg<br>`;
            }
        }
        return out;
    };

    const [startDate, endDate] = getXWindow(year);
    chart.setOption({
        ...buildBaseOption(
            `Trachtverlauf ${toTitleCase(region)} ${year}`,
            notes.join("\n"),
            tooltipFormatter,
            year,
        ),
        grid: chartGrid(headHeight(notes.length) + 12),
        yAxis: valueAxis("Gewicht [kg]", val => Math.trunc(val) + " kg"),
        legend: {
            show: true,
            top: "bottom",
            // The year first.
            data: series.map(s => s.name as string).reverse(),
        },
        dataZoom: [
            {
                type: "inside",
                xAxisIndex: 0,
                startValue: startDate.toString(),
                endValue: endDate.toString(),
            }
        ],
        series,
    });
}
