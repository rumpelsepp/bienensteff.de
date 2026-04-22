import { toTitleCase } from "../helpers";
import { BarChart, fetchTrachtnetData, getTrachtnetDerivative, getTrachtnetSeries, LineChart, metaDataOfYear, renderMetaData } from "./trachtnet";

async function fetchAndRenderTrachtProgressChart(id: string, region: string, year: number) {
    const chart = new LineChart(`Trachtverlauf ${toTitleCase(region)}`);
    chart.render(id);

    const years = Array.from({ length: 4 }, (_, i) => year - i).reverse();
    const data = await getTrachtnetSeries(years, region, true);

    chart.setData(data);
}

async function fetchAndRenderDerivativeChart(id: string, region: string, year: number) {
    const chart = new BarChart(`Trachtänderungen ${toTitleCase(region)}`);
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

export async function initAllCharts() {
    const renderAll = <T>(selector: string, renderFn: (id: string, region: string, year: number) => Promise<T>) =>
        Array.from(document.querySelectorAll<HTMLElement>(selector))
            .map(c => renderFn(c.dataset.id!, c.dataset.region!, parseInt(c.dataset.year!)));

    const progressPromises = renderAll(".trachtnet-progress-chart-container", fetchAndRenderTrachtProgressChart);
    const derivativePromises = renderAll(".trachtnet-derivative-chart-container", fetchAndRenderDerivativeChart);
    const evaluationPromises = renderAll(".trachtnet-evaluation-table-container", fetchAndRenderEvaluationTable);

    const allPromises = [...progressPromises, ...derivativePromises, ...evaluationPromises];

    await Promise.all(allPromises);
}
