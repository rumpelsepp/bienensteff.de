import { KLIMA_CHART, TRACHTNET_DERIVATIVE_CHART, TRACHTNET_EVALUATION_TABLE, TRACHTNET_PROGRESS_CHART, TRACHTNET_YEAR_SELECT } from "../selectors";
import { getParam } from "../helpers";
import { getCurrentYear } from "./helpers";
import { availableYears, renderDerivativeChart, renderEvaluationTable, renderProgressChart } from "./trachtnet";
import { renderKlimaChart } from "./klima";

// The year the charts of the page show: the current one, unless the page is
// called with ?year= or the reader picks another one (trachtnet-year-select
// shortcode).
let shownYear = getCurrentYear();

// The colours of a chart are fixed when it is built (axes, series), so on a
// change of the colour scheme -- the theme's head.html then flips
// data-bs-theme -- all of them are built anew, as they are for another
// year. The Trachtnet data is kept from the first time, see trachtnet.ts.
export async function initAllCharts() {
    const year = parseInt(getParam("year") ?? "");
    if (Number.isInteger(year)) {
        shownYear = year;
    }
    initWidthToggle();
    await initYearSelect();
    await renderAllCharts();
    new MutationObserver(() => {
        renderAllCharts();
    }).observe(document.documentElement, { attributeFilter: ["data-bs-theme"] });
}

// The button that lets the charts grow beyond the text column and back
// (.charts-wide in style.css). The charts take the new width by the resize
// their instances listen for.
function initWidthToggle() {
    const button = document.querySelector<HTMLButtonElement>(`${TRACHTNET_YEAR_SELECT} .chart-width-toggle`);
    button?.addEventListener("click", () => {
        const wide = document.body.classList.toggle("charts-wide");
        button.setAttribute("aria-pressed", wide.toString());
        button.classList.toggle("active", wide);
        window.dispatchEvent(new Event("resize"));
    });
}

// The years to choose from are those the regions on the page have data for.
// The buttons beside the list step through them, to flip between two years
// without opening it.
async function initYearSelect() {
    const box = document.querySelector<HTMLElement>(TRACHTNET_YEAR_SELECT);
    const select = box?.querySelector("select");
    if (!box || !select) {
        return;
    }

    const regions = Array.from(document.querySelectorAll<HTMLElement>(`${TRACHTNET_DERIVATIVE_CHART}, ${TRACHTNET_PROGRESS_CHART}`))
        .map(c => c.dataset.region)
        .filter((region): region is string => !!region);
    const years = await availableYears([...new Set(regions)]);
    if (years.length === 0) {
        return;
    }
    if (!years.includes(shownYear)) {
        shownYear = years[years.length - 1];
    }
    select.replaceChildren(...years.map(y => new Option(y.toString(), y.toString())));

    const steps = Array.from(box.querySelectorAll<HTMLButtonElement>("button[data-step]"));
    const show = (year: number) => {
        shownYear = year;
        select.value = year.toString();
        for (const button of steps) {
            button.disabled = !years.includes(year + parseInt(button.dataset.step!));
        }
    };
    const change = (year: number) => {
        show(year);
        // A link to the page as it is shown.
        const url = new URL(window.location.href);
        if (year === getCurrentYear()) {
            url.searchParams.delete("year");
        } else {
            url.searchParams.set("year", year.toString());
        }
        history.replaceState(null, "", url);
        renderAllCharts();
    };

    select.addEventListener("change", () => change(parseInt(select.value)));
    for (const button of steps) {
        button.addEventListener("click", () => change(shownYear + parseInt(button.dataset.step!)));
    }
    show(shownYear);
    box.hidden = false;
}

// The widgets of a kind on the page, each rendered from the data attributes
// its shortcode in layouts/shortcodes/ gives it.
function renderAll(selector: string, render: (data: DOMStringMap) => Promise<void> | undefined): Promise<void>[] {
    return Array.from(document.querySelectorAll<HTMLElement>(selector)).map(async container => {
        const rendered = render(container.dataset);
        if (!rendered) {
            throw new Error(`Widget is missing required data attributes: ${container.outerHTML.slice(0, 200)}`);
        }
        await rendered;
    });
}

async function renderAllCharts() {
    const year = shownYear;
    const chart = (render: (id: string, region: string, year: number) => Promise<void>) =>
        ({ id, region }: DOMStringMap) => id && region ? render(id, region, year) : undefined;

    const results = await Promise.allSettled([
        ...renderAll(KLIMA_CHART, ({ id, stationId, region }) => id && stationId ? renderKlimaChart(id, stationId, year, region || undefined) : undefined),
        ...renderAll(TRACHTNET_DERIVATIVE_CHART, chart(renderDerivativeChart)),
        ...renderAll(TRACHTNET_PROGRESS_CHART, chart(renderProgressChart)),
        // A table is of the year its shortcode names: there is one a year,
        // in tabs.
        ...renderAll(TRACHTNET_EVALUATION_TABLE, ({ id, region, year }) => id && region && year ? renderEvaluationTable(id, region, parseInt(year)) : undefined),
    ]);
    for (const result of results) {
        if (result.status === "rejected") {
            console.error("Failed to render chart widget:", result.reason);
        }
    }
}
