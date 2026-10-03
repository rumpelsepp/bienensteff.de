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

// Shared skeleton (title/animation/aria/toolbox/tooltip/xAxis) for the chart
// widgets in klima.ts and trachtnet.ts. Callers add their own yAxis/dataZoom.
export function buildBaseOption(
    title: string,
    subTitle: string,
    tooltipFormatter: (params: any) => string
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
            show: true,
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
