import { Temporal } from "temporal-polyfill";
import type { ECharts } from 'echarts';
import * as echarts from 'echarts';

import de from "./i18n/de.js";
import { isInteger } from "./helpers";

echarts.registerLocale('DE', de);

const localTimeZone = Temporal.Now.timeZoneId();

// Dark mode: the theme's head.html sets data-bs-theme on <html> from the
// system setting (params.darkMode). The charts then take ECharts' own dark
// theme, which turns labels, legend and grid, and for what is coloured
// explicitly here the tokens of the page (bundle_src/css/style.css).
export function isDarkMode(): boolean {
    return document.documentElement.dataset.bsTheme === "dark";
}

export type ChartColors = {
    // Titles, axes, markers: black on a light chart.
    ink: string;
    // Split lines of the grid.
    grid: string;
    // Background of the tooltip.
    surface: string;
};

export function chartColors(): ChartColors {
    if (!isDarkMode()) {
        return { ink: "#000", grid: "#eee", surface: "#fff" };
    }
    const style = getComputedStyle(document.documentElement);
    const token = (name: string, fallback: string) => style.getPropertyValue(name).trim() || fallback;
    return {
        ink: token("--color-ink", "#efe8db"),
        grid: token("--color-border", "rgba(239, 232, 219, 0.14)"),
        surface: token("--color-surface", "#28221a"),
    };
}

// Minor split lines of a value axis. Their colour is left to ECharts on a
// light chart; its dark theme draws them near black, which shows as stripes
// on the card, so there they get a faint light one.
export function minorSplitLine(): { show: boolean, lineStyle?: { color: string } } {
    if (!isDarkMode()) {
        return { show: true };
    }
    return { show: true, lineStyle: { color: "rgba(239, 232, 219, 0.06)" } };
}

export function axisPointerCallback(value: number): string {
    const date = Temporal.Instant.fromEpochMilliseconds(value).toZonedDateTimeISO(localTimeZone).toPlainDate();
    return date.toLocaleString();
}

export function buildFormatterDE(): Intl.NumberFormat {
    return new Intl.NumberFormat("de-DE", {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
}

export function initEchartsInstance(elementID: string): ECharts {
    const chartContainer = document.getElementById(elementID);
    if (!chartContainer) {
        throw new Error(`Element with ID ${elementID} not found.`);
    }

    // Rendered anew when the colour scheme changes, see render.ts.
    echarts.getInstanceByDom(chartContainer)?.dispose();

    const chart = echarts.init(chartContainer, isDarkMode() ? "dark" : null, {
        renderer: "svg",
        locale: "DE",
    });

    window.addEventListener("resize", () => {
        if (!chart.isDisposed()) {
            chart.resize();
        }
    });

    return chart;
}

// The margins around the plot of a chart. The same for all of them, so
// that charts standing one below the other line up day for day: room for
// the labels and the name of a value axis on either side, whether a chart
// has one on the right or not. ECharts' own margins are a share of the
// width, which leaves a wide chart mostly empty at its sides; on a narrow
// screen they are the tighter ones and are kept.
export function chartGrid(top: number): echarts.GridComponentOption {
    if (isNarrow()) {
        return { top };
    }
    return { top, left: 80, right: 80 };
}

// A phone: the charts are as wide as the window there, and what is laid
// out for a wide one doesn't fit.
export function isNarrow(): boolean {
    return window.innerWidth < 576;
}

// How far down the title and the given number of lines below it reach
// [px]: where the legend or the plot of a chart can begin.
export function headHeight(lines: number): number {
    return 36 + lines * 13;
}

// A value axis as all the charts draw it: named along its middle, with a
// line, ticks and minor ticks in the ink of the mode.
export function valueAxis(name: string, labelFormatter: (value: number) => string): echarts.YAXisComponentOption {
    const line = { lineStyle: { color: chartColors().ink } };
    return {
        type: "value",
        name,
        nameLocation: "middle",
        nameGap: 55,
        axisLine: { show: true, ...line },
        axisLabel: { formatter: labelFormatter },
        axisTick: { show: true, ...line },
        minorTick: { show: true, splitNumber: 5, ...line },
        minorSplitLine: minorSplitLine(),
    };
}

// Shared skeleton (title/animation/aria/toolbox/tooltip/xAxis) for the chart
// widgets in klima.ts and trachtnet.ts. Callers add their own yAxis/dataZoom.
// The x axis spans the whole of "year", whatever part of it there is data
// for: charts standing one below the other line up day for day.
export function buildBaseOption(
    title: string,
    subTitle: string,
    tooltipFormatter: (params: any) => string,
    year: number,
): echarts.EChartsOption {
    const colors = chartColors();
    return {
        // The dark theme brings a background of its own; the chart stands
        // on its card in either mode.
        backgroundColor: "transparent",
        title: {
            text: title,
            subtext: subTitle,
            left: "center",
            textStyle: {
                color: colors.ink,
                // The titles are long: "Trachtänderungen Niederbayern 2026".
                fontSize: isNarrow() ? 14 : 18,
            },
            top: 0,
        },
        animation: false,
        aria: {
            enabled: true,
            decal: {
                show: true
            }
        },
        toolbox: {
            // The button to save the chart sits in the top right corner,
            // where on a phone the title ends.
            show: !isNarrow(),
            feature: {
                saveAsImage: {}
            }
        },
        tooltip: {
            trigger: "axis",
            backgroundColor: colors.surface,
            borderColor: colors.ink,
            borderWidth: 1,
            textStyle: {
                color: colors.ink,
                fontSize: 12
            },
            extraCssText: "box-shadow: none; padding: 0.3rem 0.4rem",
            formatter: tooltipFormatter,
        },
        xAxis: {
            type: "time",
            min: `${year}-01-01`,
            max: `${year}-12-31`,
            axisLine: {
                onZero: false,
                lineStyle: {
                    color: colors.ink
                }
            },
            splitLine: {
                show: true,
                lineStyle: {
                    color: colors.grid
                }
            },
            axisPointer: {
                label: {
                    show: true,
                    formatter: params => {
                        const value = params.value;
                        if (!isInteger(value)) {
                            throw new Error("Date axis expected!");
                        }
                        return axisPointerCallback(value);
                    }
                },
            },
        },
    };
}
