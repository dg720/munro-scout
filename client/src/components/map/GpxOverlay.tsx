import { useEffect } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";
import { extractGpxCoords, looksLikeXml } from "../../utils/gpx";

export default function GpxOverlay({ url, onError }: { url: string; onError?: (msg: string) => void }) {
  const map = useMap();

  useEffect(() => {
    let poly: L.Polyline | null = null;
    let startMarker: L.Marker | null = null;
    let endMarker: L.Marker | null = null;
    let cancelled = false;

    (async () => {
      try {
        const res = await fetch(url, { cache: "no-store" });
        if (!res.ok) throw new Error(`GPX fetch failed (${res.status})`);

        const ct = res.headers.get("content-type") || "";
        const isXmlCT = /(application|text)\/(gpx\+xml|xml)/i.test(ct) || ct === "";
        const text = await res.text();

        if (!isXmlCT && !looksLikeXml(text)) {
          const head = text.slice(0, 160).replace(/\s+/g, " ");
          throw new Error(
            `Response is not GPX/XML (content-type: ${ct || "n/a"}; head: ${JSON.stringify(head)} ...)`
          );
        }

        const coords = extractGpxCoords(text);
        if (coords.length < 2) throw new Error("Not enough points in GPX");

        if (cancelled) return;

        poly = L.polyline(coords, { color: "#e11d48", weight: 3 }).addTo(map);
        startMarker = L.marker(coords[0]).addTo(map).bindTooltip("Start");
        endMarker = L.marker(coords[coords.length - 1]).addTo(map).bindTooltip("Finish");
        map.fitBounds(poly.getBounds(), { padding: [16, 16] });
      } catch (err: any) {
        console.error("GPX overlay error:", err);
        onError?.(err?.message || "Failed to load GPX");
      }
    })();

    return () => {
      cancelled = true;
      if (poly) map.removeLayer(poly);
      if (startMarker) map.removeLayer(startMarker);
      if (endMarker) map.removeLayer(endMarker);
    };
  }, [map, url, onError]);

  return null;
}
