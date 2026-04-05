import { BaseCalendar, BeeStatesCalendar, TUBCalendar, ZuchtCalendar } from "./calendars";
import { getDateParam, toTitleCase } from "./helpers";
import { BarChart, fetchTrachtnetData, getTrachtnetDerivative, getTrachtnetSeries, LineChart, metaDataOfYear, renderMetaData } from "./trachtnet";

const CALENDAR_REGISTRY: Record<string, new (id: string) => BaseCalendar> = {
    "zucht": ZuchtCalendar,
    "beestate": BeeStatesCalendar,
    "tub": TUBCalendar,
};

function renderCalendarWidget(
    containerId: string,
    CalendarClass: new (id: string) => BaseCalendar
) {
    const selector = `#${containerId} #date-input`;
    const input = document.querySelector<HTMLInputElement>(selector)!;
    input.value = getDateParam().toString();

    const cal = new CalendarClass(containerId);
    cal.render();
    cal.registerSubmitHandler();
}

export function initAllCalendarWidgets() {
    const widgets = document.querySelectorAll<HTMLElement>('.calendar-widget-container');

    widgets.forEach(container => {
        const type = container.dataset.widgetType!;
        const calendarClass = CALENDAR_REGISTRY[type]!;

        renderCalendarWidget(container.id, calendarClass);
    });
}

async function fetchAndRenderTrachtProgressChart(id: string, region: string, year: number) {
    const years = Array.from({ length: 4 }, (_, i) => year - i).reverse();
    const data = await getTrachtnetSeries(years, region, true);

    const chart = new LineChart(data, `Trachtverlauf ${toTitleCase(region)}`);
    chart.render(id);
}

async function fetchAndRenderDerivativeChart(id: string, region: string, year: number) {
    const years = Array.from({ length: 4 }, (_, i) => year - i).reverse();
    const data = await getTrachtnetDerivative(years, region);

    const chart = new BarChart(data, `Trachtänderungen ${toTitleCase(region)}`);
    chart.render(id);
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
    const progressCharts = Array.from(document.querySelectorAll<HTMLElement>('.trachtnet-progress-chart-container'));
    const derivativeCharts = Array.from(document.querySelectorAll<HTMLElement>('.trachtnet-derivative-chart-container'));
    const evaluationTables = Array.from(document.querySelectorAll<HTMLElement>('.trachtnet-evaluation-table-container'));

    const progressPromises = progressCharts.map(c =>
        fetchAndRenderTrachtProgressChart(
            c.dataset.id!,
            c.dataset.region!,
            parseInt(c.dataset.year!)
        )
    );

    const derivativePromises = derivativeCharts.map(c =>
        fetchAndRenderDerivativeChart(
            c.dataset.id!,
            c.dataset.region!,
            parseInt(c.dataset.year!)
        )
    );

    const evaluationPromises = evaluationTables.map(c =>
        fetchAndRenderEvaluationTable(
            c.dataset.id!,
            c.dataset.region!,
            parseInt(c.dataset.year!)
        )
    );

    const allPromises = [...progressPromises, ...derivativePromises, ...evaluationPromises];

    await Promise.all(allPromises);
}
