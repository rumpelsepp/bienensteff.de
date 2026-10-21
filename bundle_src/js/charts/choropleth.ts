// Maps of the Landkreise of Bayern, coloured by a value each: the county
// boundaries of /trachtnet-dump/bayern-kreise.geojson (AGS as the join
// key, BKG VG250 data, dl-de/by-2.0) and what the maps share -- regions
// without a value grey and hatched, a tooltip, zoom, the keyboard and the
// colour scale below.

import { geoArea, geoMercator, geoPath, type GeoPermissibleObjects } from "d3-geo";
import { select } from "d3-selection";
import { zoom, zoomIdentity, type D3ZoomEvent } from "d3-zoom";

import { KEY_ZOOM, keyboard, wheelDelta, wheelHint, zoomFilter, type Canvas } from "./frame";

// A feature of the GeoJSON.
export type GeoFeature = {
    type: "Feature",
    geometry: { type: "Polygon" | "MultiPolygon", coordinates: number[][][] | number[][][][] },
    properties: {
        ags: string,
        gen: string,
        bez: string,
    },
};

// d3-geo draws on the sphere: a ring that runs counter-clockwise -- as
// GeoJSON has them -- encloses all of the earth but the county. Such a
// feature is turned round.
function rewound(feature: GeoFeature): GeoFeature {
    if (geoArea(feature as GeoPermissibleObjects) <= 2 * Math.PI) {
        return feature;
    }
    const reverse = (rings: number[][][]) => rings.map(ring => [...ring].reverse());
    const coordinates = feature.geometry.type === "Polygon"
        ? reverse(feature.geometry.coordinates as number[][][])
        : (feature.geometry.coordinates as number[][][][]).map(reverse);
    return { ...feature, geometry: { ...feature.geometry, coordinates } as GeoFeature["geometry"] };
}

// Fetched once, however often a map is built anew.
let geoPromise: Promise<GeoFeature[]> | null = null;

export function loadKreise(): Promise<GeoFeature[]> {
    geoPromise ??= fetch("/trachtnet-dump/bayern-kreise.geojson").then(async response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const geojson = await response.json() as { features: GeoFeature[] };
        return geojson.features.map(rewound);
    });
    return geoPromise;
}

// What a map shows of a region.
export type MapRegion = {
    feature: GeoFeature,
    // Coloured by; null for grey and hatched.
    value: number | null,
    // What it is called -- also the order the keyboard goes through them.
    name: string,
    // What the tooltip says.
    tooltip: string,
};

export type MapSpec = {
    regions: MapRegion[],
    color: (value: number) => string,
    // The colour scale below the map: its colours, and what its ends say.
    legend: { colors: string[], low: string, high: string },
};

// Draws the map into the canvas. Dragging moves it, Ctrl + wheel or two
// fingers zoom, a double click goes back; from the keyboard the arrow keys
// go from region to region, in the order of their names.
export function drawChoropleth(canvas: Canvas, spec: MapSpec) {
    const legendHeight = 34;
    const width = canvas.width;
    const height = canvas.height - legendHeight;
    const collection = { type: "FeatureCollection", features: spec.regions.map(r => r.feature) } as GeoPermissibleObjects;
    const projection = geoMercator().fitExtent([[8, 8], [width - 8, height - 8]], collection);
    const path = geoPath(projection);

    const defs = canvas.svg.append("defs");
    const hatchID = `${canvas.id}-hatch`;
    const hatch = defs.append("pattern")
        .attr("id", hatchID)
        .attr("patternUnits", "userSpaceOnUse")
        .attr("width", 6)
        .attr("height", 6);
    hatch.append("rect").attr("class", "chart-nodata").attr("width", 6).attr("height", 6);
    hatch.append("path").attr("class", "chart-hatch").attr("d", "M-1,1 l2,-2 M0,6 l6,-6 M5,7 l2,-2");

    const map = canvas.svg.append("g");
    const regions = map.selectAll<SVGPathElement, MapRegion>("path")
        .data(spec.regions)
        .join("path")
        .attr("class", "chart-region")
        .attr("d", d => path(d.feature as GeoPermissibleObjects))
        .style("fill", d => d.value !== null ? spec.color(d.value) : `url(#${hatchID})`);
    regions
        .on("pointerenter", function () {
            select(this).raise().classed("is-hover", true);
        })
        .on("pointermove", (event: PointerEvent, d) => canvas.tooltip.show(d.tooltip, event))
        .on("pointerleave", function () {
            select(this).classed("is-hover", false);
            canvas.tooltip.hide();
        });

    const behaviour = zoom<SVGSVGElement, unknown>()
        .scaleExtent([1, 8])
        .translateExtent([[0, 0], [width, height]])
        .extent([[0, 0], [width, height]])
        .filter(zoomFilter)
        .wheelDelta(wheelDelta)
        .on("zoom", (event: D3ZoomEvent<SVGSVGElement, unknown>) => map.attr("transform", event.transform.toString()));
    canvas.svg.call(behaviour).on("dblclick.zoom", null);
    canvas.svg.on("dblclick", () => canvas.svg.call(behaviour.transform, zoomIdentity));
    wheelHint(canvas, map.node()!);

    // The keyboard: from region to region, by name.
    const order = regions.nodes()
        .map(node => ({ node, d: select<SVGPathElement, MapRegion>(node).datum() }))
        .sort((a, b) => a.d.name.localeCompare(b.d.name, "de"));
    let index: number | null = null;
    const unmark = () => regions.classed("is-hover", false);
    keyboard(canvas.svg.node()!, canvas.title, event => {
        const go = (i: number) => {
            index = (i + order.length) % order.length;
            const { node, d } = order[index];
            unmark();
            select(node).raise().classed("is-hover", true);
            const box = node.getBoundingClientRect();
            canvas.tooltip.announce(d.tooltip, { clientX: box.left + box.width / 2, clientY: box.top + box.height / 2 });
        };
        switch (event.key) {
            case "ArrowRight": case "ArrowDown": go(index === null ? 0 : index + 1); return true;
            case "ArrowLeft": case "ArrowUp": go(index === null ? order.length - 1 : index - 1); return true;
            case "+": case "=": canvas.svg.call(behaviour.scaleBy, KEY_ZOOM); return true;
            case "-": canvas.svg.call(behaviour.scaleBy, 1 / KEY_ZOOM); return true;
            case "0": canvas.svg.call(behaviour.transform, zoomIdentity); return true;
            case "Escape": index = null; unmark(); canvas.tooltip.hide(); return true;
        }
        return false;
    }, () => {
        index = null;
        unmark();
        canvas.tooltip.hide();
    });

    // The colour scale below the map: low end -- gradient -- high end.
    const { colors, low, high } = spec.legend;
    const gradientID = `${canvas.id}-gradient`;
    const gradient = defs.append("linearGradient").attr("id", gradientID);
    colors.forEach((c, i) => gradient.append("stop").attr("offset", `${100 * i / (colors.length - 1)}%`).attr("stop-color", c));
    const legend = canvas.svg.append("g").attr("transform", `translate(${width / 2},${height + 10})`);
    legend.append("rect").attr("x", -70).attr("width", 140).attr("height", 14).attr("rx", 2).style("fill", `url(#${gradientID})`);
    legend.append("text").attr("class", "chart-label").attr("x", -78).attr("y", 11).attr("text-anchor", "end").text(low);
    legend.append("text").attr("class", "chart-label").attr("x", 78).attr("y", 11).text(high);
}
