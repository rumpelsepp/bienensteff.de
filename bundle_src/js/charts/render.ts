import { KLIMA_CHART, TRACHTNET_DERIVATIVE_CHART, TRACHTNET_EVALUATION_TABLE, TRACHTNET_FLOWMAP_CHART, TRACHTNET_GAPS_CHART, TRACHTNET_MAP_CHART, TRACHTNET_PROGRESS_CHART, TRACHTNET_TREND_CHART, TRACHTNET_YEAR_SELECT } from "../selectors";
import { getParam } from "../helpers";
import { getCurrentYear } from "./helpers";
import { availableYears } from "./trachtnet/data";
import { renderDerivativeChart } from "./trachtnet/derivative";
import { renderGapsChart } from "./trachtnet/gaps";
import { renderMapChart } from "./trachtnet/map";
import { renderFlowMapChart } from "./trachtnet/flowmap";
import { renderProgressChart } from "./trachtnet/progress";
import { renderEvaluationTable } from "./trachtnet/table";
import { renderTrendChart } from "./trachtnet/trend";
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
    // The widgets of a folded <details> wait for it to open, see
    // renderAll(). The toggle event doesn't bubble; the capture listener
    // catches it anyway.
    document.addEventListener("toggle", event => {
        const details = event.target as HTMLElement;
        if (details instanceof HTMLDetailsElement && details.open) {
            renderPending(details);
        }
    }, true);
    await initYearSelect();
    await renderAllCharts("all");
    new MutationObserver(() => {
        renderAllCharts("all");
    }).observe(document.documentElement, { attributeFilter: ["data-bs-theme"] });
}

// The button that lets the charts grow beyond the text column and back
// (.charts-wide in bundle_src/css/charts.css). The charts follow the size of their
// containers on their own, see initEchartsInstance().
function initWidthToggle() {
    const button = document.querySelector<HTMLButtonElement>(`${TRACHTNET_YEAR_SELECT} .chart-width-toggle`);
    button?.addEventListener("click", () => {
        const wide = document.body.classList.toggle("charts-wide");
        button.setAttribute("aria-pressed", wide.toString());
        button.classList.toggle("active", wide);
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
        renderAllCharts("year");
    };

    select.addEventListener("change", () => change(parseInt(select.value)));
    for (const button of steps) {
        button.addEventListener("click", () => change(shownYear + parseInt(button.dataset.step!)));
    }
    show(shownYear);
    box.hidden = false;
    // How the charts are used, see the shortcode: only with them.
    document.querySelector<HTMLElement>(".chart-help")?.removeAttribute("hidden");
}

// Widgets inside a folded <details> (the Regierungsbezirke of the
// Trachtnet page), with what builds them once it opens: nobody may ever
// look at them, and a chart built while folded has no size anyway.
const pending = new Map<HTMLElement, () => Promise<void>>();

function renderPending(details: HTMLElement) {
    for (const [container, render] of pending) {
        if (details.contains(container)) {
            pending.delete(container);
            render().catch(reason => console.error("Failed to render chart widget:", reason));
        }
    }
}

// The widgets of a kind on the page, each rendered from the data attributes
// its shortcode in layouts/shortcodes/ gives it.
function renderAll(selector: string, render: (data: DOMStringMap) => Promise<void> | undefined): Promise<void>[] {
    return Array.from(document.querySelectorAll<HTMLElement>(selector)).map(async container => {
        const build = async () => {
            const rendered = render(container.dataset);
            if (!rendered) {
                throw new Error(`Widget is missing required data attributes: ${container.outerHTML.slice(0, 200)}`);
            }
            await rendered;
        };
        if (container.closest("details:not([open])")) {
            pending.set(container, build);
            return;
        }
        await build();
    });
}

// "year": another year was picked, and what doesn't follow it stays as it
// is. "all": everything anew, e.g. for another colour scheme.
async function renderAllCharts(what: "all" | "year") {
    const year = shownYear;
    const chart = (render: (id: string, region: string, year: number) => Promise<void>) =>
        ({ id, region }: DOMStringMap) => id && region ? render(id, region, year) : undefined;

    const results = await Promise.allSettled([
        ...renderAll(KLIMA_CHART, ({ id, stationId, region }) => id && stationId ? renderKlimaChart(id, stationId, year, region || undefined) : undefined),
        ...renderAll(TRACHTNET_DERIVATIVE_CHART, chart(renderDerivativeChart)),
        ...renderAll(TRACHTNET_PROGRESS_CHART, chart(renderProgressChart)),
        ...renderAll(TRACHTNET_MAP_CHART, chart(renderMapChart)),
        ...renderAll(TRACHTNET_FLOWMAP_CHART, chart(renderFlowMapChart)),
        ...(what === "all" ? [
            // The trend and gaps charts span all years: they don't follow
            // the year the page shows.
            ...renderAll(TRACHTNET_TREND_CHART, ({ id, region }) => id && region ? renderTrendChart(id, region) : undefined),
            ...renderAll(TRACHTNET_GAPS_CHART, ({ id, region }) => id && region ? renderGapsChart(id, region) : undefined),
            // A table is of the year its shortcode names: there is one a
            // year, in tabs.
            ...renderAll(TRACHTNET_EVALUATION_TABLE, ({ id, region, year }) => id && region && year ? renderEvaluationTable(id, region, parseInt(year)) : undefined),
        ] : []),
    ]);
    for (const result of results) {
        if (result.status === "rejected") {
            console.error("Failed to render chart widget:", result.reason);
        }
    }
}
