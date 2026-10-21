// The Terminplan shortcode (layouts/shortcodes/terminplan.html): the form
// above the schedule, and the dates of the day X picked there in its
// table and its calendar. Day X stands in the URL (?date=), so a schedule
// can be opened again, or printed later, as it was.

import { TERMINPLAN } from "./selectors";

const DAY_MS = 86_400_000;

// Dates as days since 1970-01-01 in UTC: no time zone or summer time can
// move a day.
function parseDay(value: string | null): number | null {
    const match = value?.match(/^(\d{4})-(\d{2})-(\d{2})$/);
    return match ? Date.UTC(+match[1], +match[2] - 1, +match[3]) / DAY_MS : null;
}

function today(): number {
    const now = new Date();
    return Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()) / DAY_MS;
}

function isoDay(day: number): string {
    return new Date(day * DAY_MS).toISOString().slice(0, 10);
}

const shortDate = new Intl.DateTimeFormat("de-DE", { weekday: "short", day: "numeric", month: "numeric", timeZone: "UTC" });
const longDate = new Intl.DateTimeFormat("de-DE", { weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });
const monthName = new Intl.DateTimeFormat("de-DE", { month: "short", timeZone: "UTC" });
const WEEKDAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];

// A row of the table: a step, counted from day X.
type Step = {
    day: number,
    until: number | null,
    kind: string,
    title: string,
};

function stepsOf(plan: HTMLElement): Step[] {
    return Array.from(plan.querySelectorAll<HTMLTableRowElement>("tbody tr"), row => ({
        day: Number(row.dataset.day),
        until: row.dataset.until ? Number(row.dataset.until) : null,
        kind: row.dataset.kind!,
        title: row.querySelector(".terminplan-title")!.textContent!,
    }));
}

// 0 for a Monday, 6 for a Sunday.
function weekday(day: number): number {
    return (new Date(day * DAY_MS).getUTCDay() + 6) % 7;
}

// The weeks from the one of day X to the one of the last step, Monday
// first: a day with a step carries its title as a chip in the look of its
// kind, a day of a stretch (Step.until) is shaded, day X and today are
// marked at their number, the first of a month names it, and the days
// before X and after the last step are faded.
function renderCalendar(container: HTMLElement, steps: Step[], x: number) {
    const last = x + Math.max(...steps.map(s => s.until ?? s.day));
    const first = x - weekday(x);
    const end = last + 6 - weekday(last);

    const cells: HTMLElement[] = WEEKDAYS.map(name => {
        const head = document.createElement("div");
        head.className = "terminplan-weekday";
        head.textContent = name;
        return head;
    });
    for (let day = first; day <= end; day++) {
        const date = new Date(day * DAY_MS);
        const cell = document.createElement("div");
        cell.className = "terminplan-cell";
        cell.classList.toggle("is-outside", day < x || day > last);
        cell.classList.toggle("is-stretch", steps.some(s => s.until !== null && day >= x + s.day && day <= x + s.until));
        cell.classList.toggle("is-today", day === today());
        cell.classList.toggle("is-day-x", day === x);
        cell.classList.toggle("is-weekend", weekday(day) >= 5);
        cell.classList.toggle("is-month-start", date.getUTCDate() === 1);

        const number = document.createElement("span");
        number.className = "terminplan-cell-day";
        number.textContent = date.getUTCDate() === 1 || day === first
            ? `${date.getUTCDate()}. ${monthName.format(date)}`
            : `${date.getUTCDate()}`;
        if (day === x) {
            number.title = "Tag X";
        }
        cell.append(number);

        for (const step of steps.filter(s => x + s.day === day)) {
            const label = document.createElement("span");
            label.className = `terminplan-cell-step terminplan-${step.kind}`;
            label.textContent = step.title;
            cell.append(label);
        }
        cells.push(cell);
    }
    container.replaceChildren(...cells);
}

function render(plan: HTMLElement, x: number) {
    renderCalendar(plan.querySelector(".terminplan-calendar")!, stepsOf(plan), x);
    for (const row of plan.querySelectorAll<HTMLTableRowElement>("tbody tr")) {
        const from = x + Number(row.dataset.day);
        const cell = row.querySelector<HTMLElement>(".terminplan-date")!;
        cell.textContent = shortDate.format(from * DAY_MS);
        if (row.dataset.until) {
            cell.textContent += ` – ${shortDate.format((x + Number(row.dataset.until)) * DAY_MS)}`;
        }
    }
    plan.querySelector(".terminplan-sheet-day")!.textContent = `Tag X: ${longDate.format(x * DAY_MS)}`;
    plan.classList.add("is-dated");
}

function initPlan(plan: HTMLElement) {
    const form = plan.querySelector<HTMLFormElement>(".terminplan-form")!;
    const dateInput = form.querySelector<HTMLInputElement>("input[name=date]")!;

    const params = new URLSearchParams(window.location.search);
    dateInput.value = isoDay(parseDay(params.get("date")) ?? today());

    const update = () => {
        const x = parseDay(dateInput.value) ?? today();
        render(plan, x);

        const url = new URL(window.location.href);
        url.searchParams.set("date", isoDay(x));
        history.replaceState(null, "", url);
    };

    form.addEventListener("input", update);
    form.addEventListener("submit", event => event.preventDefault());
    form.querySelector(".terminplan-print")!.addEventListener("click", () => window.print());
    // The title of the page names the PDF a browser prints to: the
    // procedure and day X.
    const title = document.title;
    window.addEventListener("beforeprint", () => {
        const heading = plan.querySelector(".terminplan-sheet-head h2")!.textContent;
        document.title = `${heading} – ${dateInput.value}`;
    });
    window.addEventListener("afterprint", () => {
        document.title = title;
    });
    form.hidden = false;
    update();
}

export function initTerminplaene() {
    document.querySelectorAll<HTMLElement>(TERMINPLAN).forEach(initPlan);
}
