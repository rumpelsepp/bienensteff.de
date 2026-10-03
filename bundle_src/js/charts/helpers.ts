import { Temporal } from "temporal-polyfill";

export function getCurrentYear(): number {
    return Temporal.Now.plainDateISO().year;
}

export function getToday(): Temporal.PlainDate {
    return Temporal.Now.plainDateISO();
}


export enum QueenColor {
    Blue = "#1f77b4",   // tab:blue
    Black = "#000000",  // tab:black
    Olive = "#808000",  // tab:olive
    Red = "#d62728",    // tab:red
    Green = "#2ca02c"   // tab:green
}

// Codes from Gemini.
export enum QueenColorLight {
    Blue = "#7ca0ba",
    Black = "#555555",
    Olive = "#99994d",
    Red = "#cc7a7a",
    Green = "#75a375"
}

// The years of the white queens are drawn in black. On a dark chart black
// can't be seen, there they are drawn in the light ink of the page instead.
const QUEEN_BLACK_ON_DARK = "#efe8db";
const QUEEN_BLACK_LIGHT_ON_DARK = "#a39c8f";

export function chooseQueenColor(year: number, light: boolean = false): string {
    const dark = document.documentElement.dataset.bsTheme === "dark";
    switch (year % 10) {
        case 0:
        case 5:
            return light ? QueenColorLight.Blue : QueenColor.Blue;
        case 1:
        case 6:
            if (dark) {
                return light ? QUEEN_BLACK_LIGHT_ON_DARK : QUEEN_BLACK_ON_DARK;
            }
            return light ? QueenColorLight.Black : QueenColor.Black;
        case 2:
        case 7:
            return light ? QueenColorLight.Olive : QueenColor.Olive;
        case 3:
        case 8:
            return light ? QueenColorLight.Red : QueenColor.Red;
        case 4:
        case 9:
            return light ? QueenColorLight.Green : QueenColor.Green;
        default:
            throw new Error(`Invalid year for queen color selection: ${year}`);
    }
}

export function isInteger(value: unknown): value is number {
    return typeof value === "number" && Number.isInteger(value);
}

export function isIntegerArray(value: unknown): value is number[] {
    return Array.isArray(value) && value.every(v => isInteger(v));
}

export function isInSeason(date: Temporal.PlainDate): boolean {
    if (date.month >= 3 && date.month <= 8) {
        return true;
    }
    return false;
}

export function getXLimits(): [Temporal.PlainDate, Temporal.PlainDate] {
    const today = getToday();
    let startDate: Temporal.PlainDate;
    let endDate: Temporal.PlainDate;
    if ((today.month < 4) || (today.month > 6)) {
        startDate = today.with({ "month": 1, "day": 1 });
        endDate = today.with({ "month": 12, "day": 31 });
    } else {
        startDate = today.with({ "month": 4, "day": 1 });
        endDate = today.add({ "days": 45 });
    }

    return [startDate, endDate];
}
