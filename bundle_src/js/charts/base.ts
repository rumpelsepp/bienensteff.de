import { Temporal } from "@js-temporal/polyfill";
import type { ECharts } from 'echarts';
import * as echarts from 'echarts';

import de from "./i18n/de.js";
import { isInteger } from "./helpers";

echarts.registerLocale('DE', de);

const localTimeZone = Temporal.Now.timeZoneId();

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

    const chart = echarts.init(chartContainer, null, {
        renderer: "svg",
        locale: "DE",
    });

    window.addEventListener("resize", () => {
        chart.resize();
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
    return {
        title: {
            text: title,
            subtext: subTitle,
            left: "center",
            textStyle: {
                color: "#000",
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
            backgroundColor: "#fff",
            borderColor: "#000",
            borderWidth: 1,
            textStyle: {
                color: "#000",
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
                    color: "#000"
                }
            },
            splitLine: {
                show: true,
                lineStyle: {
                    color: '#eee'
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
