import { ALL_CHARTS, CALENDAR_WIDGET } from "./selectors";

// The widget modules (and with them ECharts, FullCalendar and the Temporal
// polyfill) are split into separate chunks by esbuild and only fetched on
// pages that actually contain such a widget -- most pages don't.
async function initCalendars() {
    if (!document.querySelector(CALENDAR_WIDGET)) {
        return;
    }
    const { initAllCalendarWidgets } = await import("./calendars/render");
    initAllCalendarWidgets();
}

async function initCharts() {
    if (!document.querySelector(ALL_CHARTS)) {
        return;
    }
    const { initAllCharts } = await import("./charts/render");
    await initAllCharts();
}

const [calendars, charts] = await Promise.allSettled([initCalendars(), initCharts()]);
if (calendars.status === "rejected") {
    console.error("Failed to initialize calendar widgets:", calendars.reason);
}
if (charts.status === "rejected") {
    console.error("Failed to initialize charts:", charts.reason);
}
