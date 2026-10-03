import { KLIMA_CHART, TRACHTNET_DERIVATIVE_CHART, TRACHTNET_EVALUATION_TABLE, TRACHTNET_PROGRESS_CHART } from "../selectors";
import { toTitleCase } from "../helpers";
import { BarChart as TrachtnetBarChart, fetchTrachtnetData, getTrachtnetDerivative, getTrachtnetSeries, LineChart as TrachtnetLineChart, metaDataOfYear, renderMetaData } from "./trachtnet";
import { getKlimaDailySeries, LineChart as KlimaLineChart } from "./klima";

async function fetchAndRenderTrachtProgressChart(id: string, region: string, year: number) {
    const chart = new TrachtnetLineChart(`Trachtverlauf ${toTitleCase(region)}`);
    chart.render(id);

    const years = Array.from({ length: 4 }, (_, i) => year - i).reverse();
    const data = await getTrachtnetSeries(years, region, true);

    chart.setData(data);
}

async function fetchAndRenderDerivativeChart(id: string, region: string, year: number) {
    const chart = new TrachtnetBarChart(`Trachtänderungen ${toTitleCase(region)}`);
    chart.render(id);

    const years = Array.from({ length: 4 }, (_, i) => year - i).reverse();
    const data = await getTrachtnetDerivative(years, region);

    chart.setData(data);
}

async function fetchAndRenderEvaluationTable(id: string, region: string, year: number) {
    const data = await fetchTrachtnetData([year], region);

    const metaData = metaDataOfYear(year, region, data);
    if (!metaData) {
        return;
    }

    const elem = document.getElementById(id)!;
    elem.innerHTML = renderMetaData(metaData);
}

async function fetchAndRenderDailyKlimaChart(id: string, stationID: string) {
    let chart = new KlimaLineChart(`Klimadaten für Klimastation ${stationID}`);
    chart.render(id);

    const data = await getKlimaDailySeries(stationID);
    chart.setData(data);
}

// The colours of a chart are fixed when it is built (axes, series), so on a
// change of the colour scheme -- the theme's head.html then flips
// data-bs-theme -- all of them are built anew. The data comes out of the
// browser's cache.
export async function initAllCharts() {
    await renderAllCharts();
    new MutationObserver(() => {
        renderAllCharts();
    }).observe(document.documentElement, { attributeFilter: ["data-bs-theme"] });
}

async function renderAllCharts() {
    const renderAllTrachtnet = <T>(selector: string, renderFn: (id: string, region: string, year: number) => Promise<T>) =>
        Array.from(document.querySelectorAll<HTMLElement>(selector))
            .map(c => {
                const { id, region, year } = c.dataset;
                if (!id || !region || !year) {
                    console.error("Trachtnet widget is missing required data attributes:", c);
                    return Promise.resolve();
                }
                return renderFn(id, region, parseInt(year));
            });
    const renderAllKlima = <T>(selector: string, renderFn: (id: string, stationID: string) => Promise<T>) =>
        Array.from(document.querySelectorAll<HTMLElement>(selector))
            .map(c => {
                const { id, stationId } = c.dataset;
                if (!id || !stationId) {
                    console.error("Klima widget is missing required data attributes:", c);
                    return Promise.resolve();
                }
                return renderFn(id, stationId);
            });


    const progressPromises = renderAllTrachtnet(TRACHTNET_PROGRESS_CHART, fetchAndRenderTrachtProgressChart);
    const derivativePromises = renderAllTrachtnet(TRACHTNET_DERIVATIVE_CHART, fetchAndRenderDerivativeChart);
    const evaluationPromises = renderAllTrachtnet(TRACHTNET_EVALUATION_TABLE, fetchAndRenderEvaluationTable);
    const klimaPromises = renderAllKlima(KLIMA_CHART, fetchAndRenderDailyKlimaChart);

    const allPromises = [...progressPromises, ...derivativePromises, ...evaluationPromises, ...klimaPromises];

    const results = await Promise.allSettled(allPromises);
    for (const result of results) {
        if (result.status === "rejected") {
            console.error("Failed to render chart widget:", result.reason);
        }
    }
}
