// When the honey flow began, or ended, in each Landkreis of Bayern in a
// year (see choropleth.ts) -- worked out from the days of each, as the
// trend chart does for a region (see flowOf()).

import { scaleLinear } from "d3-scale";
import { median, quantile } from "simple-statistics";

import { getCurrentYear, isInSeason } from "../helpers";
import { toTitleCase } from "../../helpers";
import { mountChart } from "../frame";
import { drawChoropleth, loadKreise, type MapRegion } from "../choropleth";
import { loadRegionIndex, loadRegionYear } from "./data";
import { dayOfYear, dayOfYearToDate, flowOf, type Flow } from "./analysis";

type Mode = "begin" | "end";

// Early to late, from pale to dark green -- not the honey of the gain map
// above it, which means "more".
const SCALE_COLORS = ["#e9f3df", "#a8d08d", "#4e9a4c", "#1d5631"];

// Which of the two each map shows, kept when it is built anew (another
// year, another colour scheme).
const modes = new Map<string, Mode>();

const shortDate = (doy: number) => dayOfYearToDate(doy).toLocaleString("de-DE", { day: "numeric", month: "numeric" });

// The flow of each Landkreis of Bayern in "year", by its AGS, with the
// median number of scales behind it.
async function flowsOf(year: number): Promise<Map<string, { name: string, flow: Flow, scales: number }>> {
    const kreise = (await loadRegionIndex()).filter(r => r.kind === "landkreis" && r.id.startsWith("09") && r.years.includes(year));
    const records = await Promise.all(kreise.map(r => loadRegionYear(r, year)));
    return new Map(kreise.map((r, i) => {
        const season = records[i].filter(d => isInSeason(d.date));
        return [r.id, {
            name: r.name,
            flow: flowOf(year, records[i]),
            scales: season.length > 0 ? Math.round(median(season.map(d => d.nWaagen))) : 0,
        }];
    }));
}

// The beginning or the end of the honey flow per Landkreis as a
// choropleth, switched by the buttons above it: the darker the later. A
// region without data, without a flow, or whose beginning (end) the data
// doesn't show (see Flow.beginObserved) is grey and hatched.
export async function renderFlowMapChart(elementID: string, region: string, year: number) {
    const [features, flows] = await Promise.all([loadKreise(), flowsOf(year)]);

    const draw = (mode: Mode) => {
        modes.set(elementID, mode);
        const label = mode === "begin" ? "Trachtbeginn" : "Trachtende";

        const regions: MapRegion[] = features.map(feature => {
            const entry = flows.get(feature.properties.ags);
            const name = entry?.name ?? `${feature.properties.gen} (${feature.properties.bez})`;
            let tooltip = `<b>${name}</b><br>`;
            let value: number | null = null;
            if (!entry) {
                tooltip += `keine TrachtNet-Daten für ${year}`;
            } else if (!entry.flow.begin) {
                tooltip += "keine Tracht erkannt";
            } else {
                const { flow } = entry;
                const line = (name: string, date: Flow["begin"], observed: boolean) => date
                    ? `${name}: ${date.toLocaleString("de-DE")}${observed ? "" : " (unsicher: zu wenig Daten davor/danach)"}`
                    : "";
                tooltip += [line("Trachtbeginn", flow.begin, flow.beginObserved), line("Trachtende", flow.end, flow.endObserved)]
                    .filter(l => l).join("<br>");
                tooltip += `<br>${entry.scales} Waage${entry.scales === 1 ? "" : "n"} dahinter`;
                const date = flow[mode];
                if (date && (mode === "begin" ? flow.beginObserved : flow.endObserved)) {
                    value = dayOfYear(date);
                }
            }
            return { feature, value, name, tooltip };
        });

        // The scale spans the 10th to the 90th percentile of the year's
        // days, so that the few early or late regions -- the Alps begin
        // weeks later -- don't wash out the rest; they take the end colours.
        const days = regions.flatMap(r => r.value !== null ? [r.value] : []);
        const [low, high] = days.length > 1
            ? [Math.floor(quantile(days, 0.1)), Math.ceil(quantile(days, 0.9))]
            : [days[0] ?? 100, (days[0] ?? 100) + 1];
        const color = scaleLinear<string>()
            .domain(SCALE_COLORS.map((_, i) => low + (high - low) * i / (SCALE_COLORS.length - 1)))
            .range(SCALE_COLORS)
            .clamp(true);

        const notes = [
            mode === "begin"
                ? "Erster Tag der ersten Trachtphase (ab März) je Landkreis"
                : "Letzter Tag der letzten Trachtphase je Landkreis",
            "grau: keine Daten, keine Tracht oder unsicher · Zahlen im Tooltip",
        ];
        if (year === getCurrentYear()) {
            notes.push("laufendes Jahr bis dato");
        }

        // "Beginn" / "Ende", the one shown pressed.
        const controls = document.createElement("div");
        controls.className = "btn-group btn-group-sm chart-switch";
        controls.setAttribute("role", "group");
        controls.setAttribute("aria-label", "Was die Karte zeigt");
        for (const [key, text] of [["begin", "Beginn"], ["end", "Ende"]] as const) {
            const button = document.createElement("button");
            button.type = "button";
            button.className = `btn btn-outline-primary${key === mode ? " active" : ""}`;
            button.setAttribute("aria-pressed", String(key === mode));
            button.textContent = text;
            button.addEventListener("click", () => {
                if (key !== mode) {
                    draw(key);
                    document.getElementById(elementID)?.querySelector<HTMLButtonElement>(`.chart-switch .btn:nth-child(${key === "begin" ? 1 : 2})`)?.focus();
                }
            });
            controls.append(button);
        }

        mountChart(elementID, { title: `${label} ${toTitleCase(region)} ${year}`, notes, controls }, canvas => drawChoropleth(canvas, {
            regions,
            color,
            legend: { colors: SCALE_COLORS, low: `früh (${shortDate(low)})`, high: `spät (${shortDate(high)})` },
        }));
    };
    draw(modes.get(elementID) ?? "begin");
}
