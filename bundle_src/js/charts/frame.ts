// The frame every chart of the site is drawn in (with d3): a head of plain
// HTML -- title, the lines below it that say what bands and dashed lines
// mean, a legend -- and below it the plot as SVG, with a tooltip of HTML
// over it. Text and lines take the colours of the page by CSS (.chart in
// bundle_src/css/charts.css), so a chart follows the colour scheme without being told.
//
// Two kinds of plot: timeChart() for the days of one year, with zoom and
// a tooltip per day; yearChart() for one value per year.
//
// Each plot can be used without a mouse: it takes the focus by Tab, the
// arrow keys move from day to day (year to year, region to region), + and
// - zoom, 0 goes back, Escape hides the tooltip; and what the tooltip says
// is read out to a screen reader (Tooltip.announce()).

import { select, type Selection } from "d3-selection";
import { scaleBand, scaleLinear, scaleUtc, type ScaleBand, type ScaleLinear, type ScaleTime } from "d3-scale";
import { axisBottom, axisLeft, axisRight } from "d3-axis";
import { zoom, zoomIdentity, zoomTransform, type D3ZoomEvent, type ZoomBehavior } from "d3-zoom";

export type SVG = Selection<SVGSVGElement, unknown, null, undefined>;
export type Layer = Selection<SVGGElement, unknown, null, undefined>;

// --------------------------------------------------------------------
// The frame
// --------------------------------------------------------------------

// An entry of the legend: what a series looks like, and what it is.
export type LegendItem = {
    label: string,
    color: string,
    look: "line" | "thin" | "dashed" | "dotted" | "area" | "hatch" | "bar" | "dot",
};

export type Head = {
    title: string,
    notes: string[],
    legend?: LegendItem[],
    // Buttons and the like below the legend, e.g. to switch what is shown.
    controls?: HTMLElement,
};

// What a chart draws into: the SVG below the head and its size [px].
export type Canvas = {
    svg: SVG,
    width: number,
    height: number,
    tooltip: Tooltip,
    // A prefix for ids within the SVG (clip paths, patterns).
    id: string,
    // The title of the chart, also its name for a screen reader.
    title: string,
};

// A phone: what is laid out for a wide chart doesn't fit there.
export function isNarrow(): boolean {
    return window.innerWidth < 576;
}

// The margins around the plot, the same for all the charts, so that those
// standing one below the other line up day for day: room for the labels
// and the name of a value axis on either side, whether a chart has one on
// the right or not, and some air towards the edge of the card.
export function margins(): { top: number, right: number, bottom: number, left: number } {
    const side = isNarrow() ? 56 : 88;
    return { top: 14, right: side, bottom: 34, left: side };
}

// What draws a chart, kept per container: a change of size draws it anew
// with what it last was given.
const drawings = new WeakMap<HTMLElement, () => void>();

const sizeObserver = new ResizeObserver(entries => {
    for (const entry of entries) {
        drawings.get(entry.target as HTMLElement)?.();
    }
});

// Sets up the head of a chart in the element with the given id and has
// "draw" fill the space below it -- now, and again whenever the element
// changes its size. Folded away (in a closed <details>) it has none: then
// the drawing waits for it to open.
export function mountChart(elementID: string, head: Head, draw: (canvas: Canvas) => void) {
    const container = document.getElementById(elementID);
    if (!container) {
        throw new Error(`Element with ID ${elementID} not found.`);
    }
    container.classList.add("chart");

    const headElement = document.createElement("div");
    headElement.className = "chart-head";
    const title = document.createElement("div");
    title.className = "chart-title";
    title.textContent = head.title;
    headElement.append(title);
    for (const note of head.notes) {
        const line = document.createElement("div");
        line.className = "chart-note";
        line.textContent = note;
        headElement.append(line);
    }
    if (head.legend && head.legend.length > 0) {
        const legend = document.createElement("ul");
        legend.className = "chart-legend";
        for (const item of head.legend) {
            const entry = document.createElement("li");
            const swatch = document.createElement("span");
            swatch.className = `chart-swatch chart-swatch-${item.look}`;
            swatch.style.setProperty("--swatch", item.color);
            entry.append(swatch, item.label);
            legend.append(entry);
        }
        headElement.append(legend);
    }
    if (head.controls) {
        headElement.append(head.controls);
    }

    const svgElement = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svgElement.setAttribute("role", "group");
    svgElement.setAttribute("aria-label", head.title);
    const tooltipElement = document.createElement("div");
    tooltipElement.className = "chart-tooltip";
    tooltipElement.hidden = true;
    tooltipElement.setAttribute("aria-hidden", "true");
    container.replaceChildren(headElement, svgElement, tooltipElement);

    const svg = select(svgElement);
    const tooltip = new Tooltip(container, tooltipElement);
    const redraw = () => {
        const width = container.clientWidth;
        const height = container.clientHeight - headElement.offsetHeight;
        if (width === 0 || height <= 0) {
            return;
        }
        svg.attr("width", width).attr("height", height).attr("viewBox", `0 0 ${width} ${height}`);
        svg.selectAll("*").remove();
        tooltip.hide();
        draw({ svg, width, height, tooltip, id: elementID, title: head.title });
    };
    drawings.set(container, redraw);
    sizeObserver.observe(container);
    redraw();
}

// The box of HTML that says what is under the pointer.
export class Tooltip {
    constructor(private container: HTMLElement, private element: HTMLElement) {}

    // At a point of the window (the pointer, or what the keyboard has
    // chosen), inside the chart: to the right of it, or to the left where
    // there is no room.
    show(html: string, at: { clientX: number, clientY: number }) {
        this.element.innerHTML = html;
        this.element.hidden = false;
        const box = this.container.getBoundingClientRect();
        const x = at.clientX - box.left;
        const y = at.clientY - box.top;
        const width = this.element.offsetWidth;
        const left = x + 14 + width > box.width ? Math.max(0, x - 14 - width) : x + 14;
        this.element.style.left = `${left}px`;
        this.element.style.top = `${Math.max(0, y - this.element.offsetHeight - 10)}px`;
    }

    // Shows it and has a screen reader read it out: for what the keyboard
    // has chosen.
    announce(html: string, at: { clientX: number, clientY: number }) {
        this.show(html, at);
        // A line of the tooltip is a sentence of what is read out.
        const text = document.createElement("div");
        text.innerHTML = html.replace(/<br\s*\/?>|<\/div>/g, ". ");
        liveRegion().textContent = (text.textContent ?? "").replace(/\s+/g, " ").replace(/(\. )+$/, "").trim();
    }

    hide() {
        this.element.hidden = true;
    }
}

// The one region of the page a screen reader reads out what the keyboard
// has chosen in any chart: made the first time it is needed.
let live: HTMLElement | null = null;

function liveRegion(): HTMLElement {
    if (!live) {
        live = document.createElement("div");
        live.className = "chart-live";
        live.setAttribute("aria-live", "polite");
        document.body.append(live);
    }
    return live;
}

// "Strg + Mausrad zum Zoomen" over a plot for a moment, when the wheel
// alone is turned on it: it scrolls the page, and the reader may have
// wanted to zoom. One hint for the page, made the first time and moved
// into the chart the wheel is turned over.
let hint: HTMLElement | null = null;
let hintTimer: number | undefined;

export function wheelHint(canvas: Canvas, target: Element) {
    const container = canvas.svg.node()!.parentElement!;
    target.addEventListener("wheel", event => {
        if ((event as WheelEvent).ctrlKey) {
            return;
        }
        if (!hint) {
            hint = document.createElement("div");
            hint.className = "chart-hint";
            hint.setAttribute("aria-hidden", "true");
            hint.textContent = "Strg + Mausrad zum Zoomen";
        }
        if (hint.parentElement !== container) {
            container.append(hint);
            // Laid out first, so that it fades in.
            void hint.offsetWidth;
        }
        hint.classList.add("is-shown");
        clearTimeout(hintTimer);
        hintTimer = window.setTimeout(() => hint?.classList.remove("is-shown"), 1200);
    }, { passive: true });
}

// How the charts are used from the keyboard, said once on the page (the
// trachtnet-year-select shortcode): each chart refers to it.
const KEY_HELP_ID = "chart-keys";

// What answers the keys of a plot, per SVG: the SVG stays when the plot
// is drawn anew, its handlers are replaced.
const keyHandlers = new WeakMap<Element, { keydown: (event: Event) => void, blur: () => void }>();

// Lets "element" take the focus by Tab and calls "onKey" with the keys
// pressed on it (those it handles don't scroll the page).
export function keyboard(element: Element, label: string, onKey: (event: KeyboardEvent) => boolean, onBlur: () => void) {
    element.setAttribute("tabindex", "0");
    element.setAttribute("aria-label", label);
    if (document.getElementById(KEY_HELP_ID)) {
        element.setAttribute("aria-describedby", KEY_HELP_ID);
    }
    const previous = keyHandlers.get(element);
    if (previous) {
        element.removeEventListener("keydown", previous.keydown);
        element.removeEventListener("blur", previous.blur);
    }
    const handlers = {
        keydown: (event: Event) => {
            if (onKey(event as KeyboardEvent)) {
                event.preventDefault();
            }
        },
        blur: onBlur,
    };
    element.addEventListener("keydown", handlers.keydown);
    element.addEventListener("blur", handlers.blur);
    keyHandlers.set(element, handlers);
}

// How far a turn of the wheel zooms (as a power of 2). d3 multiplies the
// steps by ten with Ctrl held, taking it for a pinch on a touchpad -- with
// the mouse wheel that makes a factor of 3 to 4 a notch. Here a notch is
// about 1.3 to 1.4 (lines or pixels, as the browser counts it); the small
// steps of a touchpad pinch keep their boost.
export function wheelDelta(event: WheelEvent): number {
    const steps = -event.deltaY * (event.deltaMode === 1 ? 0.05 : event.deltaMode ? 1 : 0.002);
    const pinch = event.deltaMode === 0 && Math.abs(event.deltaY) < 50;
    return steps * (pinch ? 10 : 2.5);
}

// The factor + and - zoom by.
export const KEY_ZOOM = 1.25;

// Zoom and drag of a plot: Ctrl + wheel zooms -- the wheel alone scrolls
// the page, as anywhere, and shows a hint (wheelHint()) --, dragging with
// the mouse moves, two fingers zoom; one finger scrolls the page.
export function zoomFilter(event: Event & { button?: number, touches?: TouchList, ctrlKey?: boolean }): boolean {
    if (event.type === "wheel") {
        return !!event.ctrlKey;
    }
    if (event.type === "touchstart") {
        return (event.touches?.length ?? 0) > 1;
    }
    return !event.button;
}

// A value axis, named along its middle -- on a phone not: there is no
// room beside the labels, which carry the unit anyway.
function valueAxis(layer: Layer, y: ScaleLinear<number, number>, side: "left" | "right", spec: YAxis, plotWidth: number, plotHeight: number) {
    const { name, format } = spec;
    const axis = (side === "left" ? axisLeft(y) : axisRight(y)).tickValues(tickValues(y, spec, plotHeight).major).tickFormat(v => format(+v));
    const g = layer.append("g")
        .attr("class", "chart-axis")
        .attr("transform", side === "left" ? "" : `translate(${plotWidth},0)`)
        .call(axis);
    if (isNarrow()) {
        return;
    }
    g.append("text")
        .attr("class", "chart-axis-name")
        .attr("transform", `translate(${side === "left" ? -margins().left + 24 : margins().right - 24},${plotHeight / 2}) rotate(${side === "left" ? -90 : 90})`)
        .attr("text-anchor", "middle")
        .text(name);
}

// The grid of a value axis: a faint line at each of its ticks, and fainter
// ones between them.
function grid(layer: Layer, y: ScaleLinear<number, number>, axis: YAxis, plotWidth: number, plotHeight: number) {
    const { major, minor } = tickValues(y, axis, plotHeight);
    for (const [values, className] of [[minor, "chart-grid chart-grid-minor"], [major, "chart-grid"]] as const) {
        layer.append("g")
            .attr("class", className)
            .selectAll("line")
            .data(values)
            .join("line")
            .attr("x1", 0)
            .attr("x2", plotWidth)
            .attr("y1", v => y(v))
            .attr("y2", v => y(v));
    }
}

// A value scale over "domain" with a little room above and below, so that
// a dot on the highest value isn't cut in half, then rounded to ticks. An
// axis from 0 (rain) keeps 0 at its foot.
function valueScale(domain: [number, number], height: number): ScaleLinear<number, number> {
    const room = (domain[1] - domain[0]) * 0.04;
    const low = domain[0] === 0 ? 0 : domain[0] - room;
    return scaleLinear().domain([low, domain[1] + room]).range([height, 0]).nice();
}

export type YAxis = {
    domain: [number, number],
    name: string,
    format: (value: number) => string,
    // Where the labelled lines and the faint ones between them go, if not
    // where d3 puts them (e.g. at dates, see datesTicks()).
    ticks?: (y: ScaleLinear<number, number>) => { major: number[], minor: number[] },
};

// The lines of a value axis: where "axis" says, or d3's ticks with five
// minor steps to each.
function tickValues(y: ScaleLinear<number, number>, axis: YAxis, plotHeight: number): { major: number[], minor: number[] } {
    if (axis.ticks) {
        return axis.ticks(y);
    }
    const count = Math.max(3, Math.round(plotHeight / 50));
    const major = y.ticks(count);
    return { major, minor: y.ticks(count * 5).filter(v => !major.includes(v)) };
}

// --------------------------------------------------------------------
// The days of a year
// --------------------------------------------------------------------

export const DAY_MS = 86_400_000;

// A date of the plot: midnight UTC, so that no summer time moves a day.
export function utcDay(year: number, month: number, day: number): Date {
    return new Date(Date.UTC(year, month - 1, day));
}

const monthLabel = new Intl.DateTimeFormat("de-DE", { month: "short", timeZone: "UTC" });

function dayLabel(date: Date): string {
    return date.getUTCDate() === 1
        ? monthLabel.format(date)
        : `${date.getUTCDate()}.${date.getUTCMonth() + 1}.`;
}

export type TimeChartSpec = {
    year: number,
    // What the chart opens with, see getXWindow().
    window: [Date, Date],
    left: YAxis,
    right?: YAxis,
    // Draws the series into "layer", which is clipped to the plot; again
    // on every zoom, with the x scale of it.
    draw: (layer: Layer, x: ScaleTime<number, number>, left: ScaleLinear<number, number>, right: ScaleLinear<number, number> | null) => void,
    // What the tooltip says for a day; null for nothing.
    tooltip: (day: Date) => string | null,
};

// A plot over the days of a year, the whole year on the x axis -- charts
// standing one below the other line up day for day. Dragging moves it,
// Ctrl + wheel or two fingers zoom in and out, a double click goes back to
// the window it opened with; one finger scrolls the page, as anywhere.
export function timeChart(canvas: Canvas, spec: TimeChartSpec) {
    const m = margins();
    const width = canvas.width - m.left - m.right;
    const height = canvas.height - m.top - m.bottom;
    const plot = canvas.svg.append("g").attr("transform", `translate(${m.left},${m.top})`);

    const x0 = scaleUtc()
        .domain([utcDay(spec.year, 1, 1), utcDay(spec.year + 1, 1, 1)])
        .range([0, width]);
    const left = valueScale(spec.left.domain, height);
    const right = spec.right ? valueScale(spec.right.domain, height) : null;

    grid(plot, left, spec.left, width, height);
    valueAxis(plot, left, "left", spec.left, width, height);
    if (right && spec.right) {
        valueAxis(plot, right, "right", spec.right, width, height);
    }

    const clipID = `${canvas.id}-clip`;
    canvas.svg.append("clipPath").attr("id", clipID)
        .append("rect").attr("width", width).attr("height", height);
    const xAxis = plot.append("g").attr("class", "chart-axis").attr("transform", `translate(0,${height})`);
    // A line up the plot at each tick of the time axis, behind the series.
    const xGrid = plot.append("g").attr("class", "chart-grid").attr("clip-path", `url(#${clipID})`);
    const content = plot.append("g").attr("clip-path", `url(#${clipID})`);
    const guide = plot.append("line").attr("class", "chart-guide").attr("y1", 0).attr("y2", height).style("display", "none");
    const overlay = plot.append("rect")
        .attr("class", "chart-overlay")
        .attr("width", width)
        .attr("height", height);

    let x = x0;
    const render = () => {
        const ticks = x.ticks(Math.max(2, Math.round(width / 80)));
        xAxis.call(axisBottom(x).tickValues(ticks).tickFormat(d => dayLabel(d as Date)));
        xGrid.selectAll("line")
            .data(ticks)
            .join("line")
            .attr("x1", d => x(d))
            .attr("x2", d => x(d))
            .attr("y1", 0)
            .attr("y2", height);
        content.selectAll("*").remove();
        spec.draw(content, x, left, right);
    };

    const opening = () => {
        const [from, to] = spec.window.map(d => x0(d));
        const k = width / Math.max(1, to - from);
        return zoomIdentity.scale(k).translate(-from, 0);
    };
    const behaviour: ZoomBehavior<SVGRectElement, unknown> = zoom<SVGRectElement, unknown>()
        .scaleExtent([1, 40])
        .extent([[0, 0], [width, height]])
        .translateExtent([[0, 0], [width, height]])
        .filter(zoomFilter)
        .wheelDelta(wheelDelta)
        .on("zoom", (event: D3ZoomEvent<SVGRectElement, unknown>) => {
            x = event.transform.rescaleX(x0);
            render();
            if (cursor) {
                showDay(cursor, true);
            }
        });
    overlay.call(behaviour).on("dblclick.zoom", null);
    overlay.on("dblclick", () => overlay.call(behaviour.transform, opening()));
    wheelHint(canvas, overlay.node()!);

    // The day the tooltip is about: under the pointer, or chosen by the
    // keyboard (then it stays when the plot zooms, and is read out).
    let cursor: Date | null = null;
    const toDay = (date: Date) => utcDay(date.getUTCFullYear(), date.getUTCMonth() + 1, date.getUTCDate());
    const middleOf = (day: Date) => x(new Date(day.getTime() + DAY_MS / 2));
    const showDay = (day: Date, byKeyboard: boolean, event?: PointerEvent) => {
        const html = day.getUTCFullYear() === spec.year ? spec.tooltip(day) : null;
        const middle = middleOf(day);
        guide.attr("x1", middle).attr("x2", middle).style("display", middle >= 0 && middle <= width ? "" : "none");
        const text = `<div class="chart-tooltip-head">${day.toLocaleDateString("de-DE", { timeZone: "UTC" })}</div>${html ?? "keine Daten"}`;
        if (byKeyboard) {
            const box = overlay.node()!.getBoundingClientRect();
            canvas.tooltip.announce(text, { clientX: box.left + middle, clientY: box.top + 24 });
        } else if (html && event) {
            canvas.tooltip.show(text, event);
        } else {
            hide();
        }
    };
    const hide = () => {
        cursor = null;
        guide.style("display", "none");
        canvas.tooltip.hide();
    };
    overlay.on("pointermove", (event: PointerEvent) => {
        cursor = null;
        const [px] = pointerIn(overlay.node()!, event);
        showDay(toDay(x.invert(px)), false, event);
    });
    overlay.on("pointerleave", hide);

    // The keyboard: a day at a time (a week with Shift, a month with Page
    // Up/Down), into view if it isn't.
    const first = utcDay(spec.year, 1, 1).getTime();
    const last = utcDay(spec.year, 12, 31).getTime();
    keyboard(canvas.svg.node()!, canvas.title, event => {
        const step = (days: number) => {
            const [from, to] = x.domain();
            const start = cursor ?? toDay(new Date((from.getTime() + to.getTime()) / 2));
            const next = new Date(Math.min(last, Math.max(first, start.getTime() + days * DAY_MS)));
            cursor = next;
            const at = middleOf(next);
            if (at < 0 || at > width) {
                overlay.call(behaviour.translateBy, (width / 2 - at) / zoomTransform(overlay.node()!).k, 0);
            }
            showDay(next, true);
        };
        switch (event.key) {
            case "ArrowRight": step(event.shiftKey ? 7 : 1); return true;
            case "ArrowLeft": step(event.shiftKey ? -7 : -1); return true;
            case "PageDown": step(30); return true;
            case "PageUp": step(-30); return true;
            case "+": case "=": overlay.call(behaviour.scaleBy, KEY_ZOOM, cursor ? [middleOf(cursor), 0] : undefined); return true;
            case "-": overlay.call(behaviour.scaleBy, 1 / KEY_ZOOM, cursor ? [middleOf(cursor), 0] : undefined); return true;
            case "0": overlay.call(behaviour.transform, opening()); return true;
            case "Escape": hide(); return true;
        }
        return false;
    }, hide);

    // The window the chart opens with; this draws it the first time.
    overlay.call(behaviour.transform, opening());
}

function pointerIn(element: SVGGraphicsElement, event: PointerEvent): [number, number] {
    const box = element.getBoundingClientRect();
    return [event.clientX - box.left, event.clientY - box.top];
}

// --------------------------------------------------------------------
// One value per year
// --------------------------------------------------------------------

export type YearChartSpec = {
    years: number[],
    left: YAxis,
    draw: (layer: Layer, x: ScaleBand<number>, y: ScaleLinear<number, number>) => void,
    tooltip: (year: number) => string | null,
};

// A plot with a slot per year along the x axis; the tooltip says what
// there is in the slot under the pointer.
export function yearChart(canvas: Canvas, spec: YearChartSpec) {
    const m = margins();
    const width = canvas.width - m.left - m.right;
    const height = canvas.height - m.top - m.bottom;
    const plot = canvas.svg.append("g").attr("transform", `translate(${m.left},${m.top})`);

    const x = scaleBand<number>().domain(spec.years).range([0, width]).padding(0.1);
    const y = valueScale(spec.left.domain, height);

    grid(plot, y, spec.left, width, height);
    plot.append("g")
        .attr("class", "chart-grid")
        .selectAll("line")
        .data(spec.years)
        .join("line")
        .attr("x1", year => x(year)! + x.bandwidth() / 2)
        .attr("x2", year => x(year)! + x.bandwidth() / 2)
        .attr("y1", 0)
        .attr("y2", height);
    valueAxis(plot, y, "left", spec.left, width, height);
    const every = Math.ceil(spec.years.length / Math.max(1, Math.floor(width / 44)));
    plot.append("g")
        .attr("class", "chart-axis")
        .attr("transform", `translate(0,${height})`)
        .call(axisBottom(x).tickValues(spec.years.filter((_, i) => i % every === 0)).tickFormat(String));

    const content = plot.append("g");
    spec.draw(content, x, y);

    const overlay = plot.append("rect").attr("class", "chart-overlay").attr("width", width).attr("height", height);
    const text = (year: number) => `<div class="chart-tooltip-head">${year}</div>${spec.tooltip(year) ?? "keine Daten"}`;
    overlay.on("pointermove", (event: PointerEvent) => {
        const [px] = pointerIn(overlay.node()!, event);
        const year = spec.years[Math.min(spec.years.length - 1, Math.max(0, Math.floor((px - x.range()[0]) / x.step())))];
        if (year !== undefined && spec.tooltip(year)) {
            canvas.tooltip.show(text(year), event);
        } else {
            canvas.tooltip.hide();
        }
    });
    overlay.on("pointerleave", () => canvas.tooltip.hide());

    // The keyboard: a year at a time.
    let index: number | null = null;
    keyboard(canvas.svg.node()!, canvas.title, event => {
        const go = (i: number) => {
            index = Math.min(spec.years.length - 1, Math.max(0, i));
            const year = spec.years[index];
            const box = overlay.node()!.getBoundingClientRect();
            canvas.tooltip.announce(text(year), { clientX: box.left + x(year)! + x.bandwidth() / 2, clientY: box.top + 24 });
        };
        switch (event.key) {
            case "ArrowRight": go(index === null ? 0 : index + 1); return true;
            case "ArrowLeft": go(index === null ? spec.years.length - 1 : index - 1); return true;
            case "Home": go(0); return true;
            case "End": go(spec.years.length - 1); return true;
            case "Escape": index = null; canvas.tooltip.hide(); return true;
        }
        return false;
    }, () => {
        index = null;
        canvas.tooltip.hide();
    });
}

// --------------------------------------------------------------------
// Bits the charts share
// --------------------------------------------------------------------

// Hatchings for areas, so that they are told apart by more than a tint:
// the rain under the band of the temperature ("rain", a tint and lines);
// and stripes to lay over an area of any colour ("stripes", lines in the
// background colour of the page only). Defined once for the page, in an
// SVG of their own, and filled in by fill: url(#chart-hatch-...); their
// lines take the colours of the page by CSS (.chart-hatch-*).
export type Hatch = "rain" | "stripes";

let hatches: SVGSVGElement | null = null;

export function hatch(name: Hatch): string {
    if (!hatches) {
        hatches = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        hatches.setAttribute("class", "chart-hatches");
        hatches.setAttribute("aria-hidden", "true");
        const defs = select(hatches).append("defs");
        const pattern = (name: Hatch, size: number, lines: string, tint: boolean) => {
            const p = defs.append("pattern")
                .attr("id", `chart-hatch-${name}`)
                .attr("patternUnits", "userSpaceOnUse")
                .attr("width", size)
                .attr("height", size);
            if (tint) {
                p.append("rect").attr("class", `chart-hatch-${name}-tint`).attr("width", size).attr("height", size);
            }
            p.append("path").attr("class", `chart-hatch-${name}-line`).attr("d", lines);
        };
        pattern("rain", 7, "M-2,5 l4,4 M0,0 l7,7 M5,-2 l4,4", true);
        pattern("stripes", 6, "M-2,2 l4,-4 M0,6 l6,-6 M4,8 l4,-4", false);
        document.body.append(hatches);
    }
    return `url(#chart-hatch-${name})`;
}

export const formatDE = new Intl.NumberFormat("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

// A coloured dot for a line of the tooltip.
export function swatch(color: string): string {
    return `<span class="chart-tooltip-swatch" style="background:${color}"></span>`;
}

// A horizontal dashed line across the plot, e.g. a threshold.
export function hLine(layer: Layer, y: number, width: number, color: string) {
    layer.append("line")
        .attr("class", "chart-dashed")
        .attr("x1", 0).attr("x2", width)
        .attr("y1", y).attr("y2", y)
        .attr("stroke", color);
}

// "No data" across an empty plot, which keeps its place on the page.
export function emptyNote(canvas: Canvas, text: string) {
    canvas.svg.append("text")
        .attr("class", "chart-empty")
        .attr("x", canvas.width / 2)
        .attr("y", canvas.height / 2)
        .attr("text-anchor", "middle")
        .text(text);
}
