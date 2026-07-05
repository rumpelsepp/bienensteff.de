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

export async function initAllCharts() {
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


    const progressPromises = renderAllTrachtnet(".trachtnet-progress-chart-container", fetchAndRenderTrachtProgressChart);
    const derivativePromises = renderAllTrachtnet(".trachtnet-derivative-chart-container", fetchAndRenderDerivativeChart);
    const evaluationPromises = renderAllTrachtnet(".trachtnet-evaluation-table-container", fetchAndRenderEvaluationTable);
    const klimaPromises = renderAllKlima(".klima-chart-container", fetchAndRenderDailyKlimaChart);

    const allPromises = [...progressPromises, ...derivativePromises, ...evaluationPromises, ...klimaPromises];

    const results = await Promise.allSettled(allPromises);
    for (const result of results) {
        if (result.status === "rejected") {
            console.error("Failed to render chart widget:", result.reason);
        }
    }
}
