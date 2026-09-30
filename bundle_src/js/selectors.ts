// Container selectors of the widgets rendered by the shortcodes in
// layouts/shortcodes/. Kept in this dependency-free module so main.ts can
// check for them without pulling in the (code-split) widget modules.
export const CALENDAR_WIDGET = ".calendar-widget-container";
export const TRACHTNET_PROGRESS_CHART = ".trachtnet-progress-chart-container";
export const TRACHTNET_DERIVATIVE_CHART = ".trachtnet-derivative-chart-container";
export const TRACHTNET_EVALUATION_TABLE = ".trachtnet-evaluation-table-container";
export const KLIMA_CHART = ".klima-chart-container";

export const ALL_CHARTS = [
    TRACHTNET_PROGRESS_CHART,
    TRACHTNET_DERIVATIVE_CHART,
    TRACHTNET_EVALUATION_TABLE,
    KLIMA_CHART,
].join(", ");
