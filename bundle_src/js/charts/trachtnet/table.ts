// The table of a year's key figures.

import { Temporal } from "temporal-polyfill";

import { isSeasonOver } from "../helpers";
import { toTitleCase } from "../../helpers";
import { formatDE } from "../frame";
import { loadYear } from "./data";
import { keyFigures, meanSeasonGain, seasonTotals, trachtGaps, trachtPhases } from "./analysis";

export async function renderEvaluationTable(elementID: string, region: string, year: number) {
    const records = await loadYear(region, year);
    if (records.length === 0) {
        return;
    }

    const figures = keyFigures(records);
    if (!figures) {
        return;
    }
    const { min, max, bestDay } = figures;

    const date = (d: Temporal.PlainDate) => d.toLocaleString();
    const row = (label: string, value: string) => `<tr><th scope="row">${label}</th><td>${value}</td></tr>`;
    const rows = [
        row("Jahresminimum", `${date(min.date)} (${formatDE.format(min.value)} kg)`),
        row("Jahresmaximum", `${date(max.date)} (${formatDE.format(max.value)} kg)`),
        row("Bester Tag", `${date(bestDay.date)} (Δ ${formatDE.format(bestDay.delta!)} kg)`),
    ];

    // When the flow began and ended, how many phases it came in, and the
    // longest stretch without it in between.
    const phases = trachtPhases(records);
    if (phases.length > 0) {
        const phaseDays = phases.reduce((sum, p) => sum + p.start.until(p.end).days + 1, 0);
        rows.push(
            row("Trachtbeginn", date(phases[0].start)),
            row("Trachtende", date(phases[phases.length - 1].end)),
            row("Trachtphasen", `${phases.length} (${phaseDays} Tage)`),
        );
        const gap = trachtGaps(records).find(g => g.longest);
        if (gap) {
            rows.push(row("Längste Trachtlücke", `${gap.days} Tage (${date(gap.start)} – ${date(gap.end)})`));
        }
    }

    // What the season added up to, and how that stands against the years
    // around it.
    const totals = seasonTotals(records);
    rows.push(
        row("Gesamteintrag (Mär–Aug)", `${formatDE.format(totals.gain)} kg`),
        row("Gesamtverlust (Mär–Aug)", `${formatDE.format(totals.loss)} kg`),
    );
    const comparison = await meanSeasonGain(region, year, records);
    if (comparison) {
        const years = comparison.from === comparison.to
            ? `${comparison.from}`
            : `${comparison.from}–${comparison.to}`;
        let against = `Mittel ${years}: ${formatDE.format(comparison.mean)} kg`;
        if (comparison.mean > 0) {
            const percent = Math.round((totals.gain / comparison.mean - 1) * 100);
            against = `${percent >= 0 ? "+" : ""}${percent} % (${against})`;
        }
        rows.push(row("Gesamteintrag ggü. Mittel", against));
    }

    document.getElementById(elementID)!.innerHTML = `<table class="table table-bordered table-striped table-sm">
  <caption>Auswertung von ${toTitleCase(region)} (${year}${isSeasonOver(year) ? "" : ", bis dato"})</caption>
  <tbody>
    ${rows.join("\n    ")}
  </tbody>
</table>`;
}
