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
            .map(c => renderFn(c.dataset.id!, c.dataset.region!, parseInt(c.dataset.year!)));
    const renderAllKlima =  <T>(selector: string, renderFn: (id: string, stationID: string) => Promise<T>) =>
        Array.from(document.querySelectorAll<HTMLElement>(selector))
            .map(c => renderFn(c.dataset.id!, c.dataset.stationId!));


    const progressPromises = renderAllTrachtnet(".trachtnet-progress-chart-container", fetchAndRenderTrachtProgressChart);
    const derivativePromises = renderAllTrachtnet(".trachtnet-derivative-chart-container", fetchAndRenderDerivativeChart);
    const evaluationPromises = renderAllTrachtnet(".trachtnet-evaluation-table-container", fetchAndRenderEvaluationTable);
    const klimaPromises = renderAllKlima(".klima-chart-container", fetchAndRenderDailyKlimaChart);
    
    const allPromises = [...progressPromises, ...derivativePromises, ...evaluationPromises, ...klimaPromises];

    await Promise.all(allPromises);
}
