import { ALL_CHARTS, CALENDAR_WIDGET } from "./selectors";

// FullCalendar's theme turns dark on data-color-scheme, the page on
// data-bs-theme, which the theme's head.html sets from the system setting
// (params.darkMode): the one is kept in step with the other.
function followColorScheme() {
    const root = document.documentElement;
    const sync = () => {
        root.dataset.colorScheme = root.dataset.bsTheme === "dark" ? "dark" : "light";
    };
    sync();
    new MutationObserver(sync).observe(root, { attributeFilter: ["data-bs-theme"] });
}

// The widget modules (and with them ECharts, FullCalendar and the Temporal
// polyfill) are split into separate chunks by esbuild and only fetched on
// pages that actually contain such a widget -- most pages don't.
async function initCalendars() {
    if (!document.querySelector(CALENDAR_WIDGET)) {
        return;
    }
    followColorScheme();
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
