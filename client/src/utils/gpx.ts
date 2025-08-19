import { LatLngTuple } from "leaflet";

export function looksLikeXml(s: string) {
  const head = s.slice(0, 200).trim().replace(/^\uFEFF/, ""); // strip BOM
  return head.startsWith("<?xml") || head.startsWith("<gpx") || head.startsWith("<rte") || head.startsWith("<trk");
}

export function extractGpxCoords(gpxText: string): LatLngTuple[] {
  const parser = new DOMParser();
  const xml = parser.parseFromString(gpxText, "application/xml");

  if (xml.getElementsByTagName("parsererror").length) {
    throw new Error("Invalid GPX XML");
  }

  const trkpts = Array.from(xml.getElementsByTagName("trkpt"));
  if (trkpts.length > 0) {
    return trkpts.map((pt) => {
      const lat = parseFloat(pt.getAttribute("lat") || "0");
      const lon = parseFloat(pt.getAttribute("lon") || "0");
      return [lat, lon] as LatLngTuple;
    });
  }

  const rtepts = Array.from(xml.getElementsByTagName("rtept"));
  if (rtepts.length > 0) {
    return rtepts.map((pt) => {
      const lat = parseFloat(pt.getAttribute("lat") || "0");
      const lon = parseFloat(pt.getAttribute("lon") || "0");
      return [lat, lon] as LatLngTuple;
    });
  }

  throw new Error("No track/route points found in GPX");
}
