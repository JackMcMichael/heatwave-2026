/* map.js — MapLibre choropleth. No basemap: pure region fills on a neutral
 * background (PLAN.md §2.8), which keeps first load tiny and scrubbing cheap.
 * Timeline steps only touch feature-state — the GeoJSON is parsed once and
 * the GPU restyles fills, so a step costs well under a frame. */

// Diverging, anomaly-centred, colour-blind-safe (ColorBrewer RdBu, extended
// to +20 °C for this event's extremes). Keep in sync with the legend in
// index.html.
export const ANOMALY_STOPS = [
  [-5, "#2166ac"], [-2, "#67a9cf"], [0, "#f7f7f7"],
  [4, "#fddbc7"], [8, "#ef8a62"], [12, "#d6604d"],
  [16, "#b2182b"], [20, "#67001f"],
];

const EUROPE_BOUNDS = [[-11, 35], [25, 62]]; // same bbox as the pipeline

export function createMap({ container, regionsUrl, onRegionClick }) {
  const map = new maplibregl.Map({
    container,
    style: {
      version: 8,
      sources: {},
      layers: [{ id: "bg", type: "background",
                 paint: { "background-color": "#12141c" } }],
    },
    bounds: EUROPE_BOUNDS,
    fitBoundsOptions: { padding: 20 },
    attributionControl: false, // rendered in our own footer instead
    dragRotate: false,
    touchPitch: false,
  });

  const ramp = ANOMALY_STOPS.flat();
  let hoveredId = null;

  const ready = new Promise((resolve) => {
    map.on("load", () => {
      map.addSource("regions", {
        type: "geojson",
        data: regionsUrl,
        promoteId: "id", // feature-state keyed by NUTS_ID
      });

      map.addLayer({
        id: "region-fill",
        type: "fill",
        source: "regions",
        paint: {
          // coalesce: regions render neutral until the first setDate().
          "fill-color": [
            "interpolate", ["linear"],
            ["coalesce", ["feature-state", "anomaly"], 0],
            ...ramp,
          ],
          "fill-opacity": [
            "case", ["boolean", ["feature-state", "hover"], false], 1.0, 0.88,
          ],
        },
      });

      map.addLayer({
        id: "region-line",
        type: "line",
        source: "regions",
        paint: { "line-color": "#12141c", "line-width": 0.6 },
      });

      map.on("mousemove", "region-fill", (e) => {
        map.getCanvas().style.cursor = "pointer";
        const id = e.features[0]?.id;
        if (id === hoveredId) return;
        setHover(hoveredId, false);
        setHover((hoveredId = id), true);
      });
      map.on("mouseleave", "region-fill", () => {
        map.getCanvas().style.cursor = "";
        setHover(hoveredId, false);
        hoveredId = null;
      });
      map.on("click", "region-fill", (e) => {
        const f = e.features[0];
        if (f) onRegionClick(f.properties);
      });

      resolve();
    });
  });

  function setHover(id, hover) {
    if (id == null) return;
    map.setFeatureState({ source: "regions", id }, { hover });
  }

  /* Push one timeline step's anomalies into feature-state. */
  function setDate(dateIndex, regions) {
    for (const [id, r] of Object.entries(regions)) {
      map.setFeatureState(
        { source: "regions", id },
        { anomaly: r.anomaly[dateIndex] },
      );
    }
  }

  return { map, ready, setDate };
}
