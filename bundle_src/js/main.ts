import { ALL_CHARTS, TERMINPLAN } from "./selectors";

// The widget modules (and with them ECharts and the Temporal polyfill)
// are split into separate chunks by esbuild and only fetched on pages that
// actually contain such a widget -- most pages don't.
async function initTerminplaene() {
    if (!document.querySelector(TERMINPLAN)) {
        return;
    }
    const { initTerminplaene } = await import("./terminplan");
    initTerminplaene();
}

async function initCharts() {
    if (!document.querySelector(ALL_CHARTS)) {
        return;
    }
    const { initAllCharts } = await import("./charts/render");
    await initAllCharts();
}

const [terminplaene, charts] = await Promise.allSettled([initTerminplaene(), initCharts()]);
if (terminplaene.status === "rejected") {
    console.error("Failed to initialize the Terminplan:", terminplaene.reason);
}
if (charts.status === "rejected") {
    console.error("Failed to initialize charts:", charts.reason);
}
