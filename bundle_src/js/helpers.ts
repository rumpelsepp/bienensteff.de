import { Temporal } from "@js-temporal/polyfill";

export function getParam(name: string): string | null {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get(name);
}

export function getDateParam(): Temporal.PlainDate {
    const dateParam = getParam("date");

    if (dateParam === null) {
        return Temporal.Now.plainDateISO();
    }
    return Temporal.PlainDate.from(dateParam);
}

export function toTitleCase(text: string): string {
    return text.replace(/\w\S*/g, (word) =>
        word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
    );
}
