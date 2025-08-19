import { useMemo } from "react";
import { FALLBACK_GPX } from "../config/constants";
import { Munro } from "../types/munro";

export function useSelectedGpxUrl(selected: Munro | null): string {
  return useMemo(() => {
    if (!selected) return FALLBACK_GPX;

    const raw = (selected.gpx_file || "").trim();
    if (raw) {
      // Absolute URL?
      if (/^https?:\/\//i.test(raw)) {
        if (/\.(gpx|xml)(\?|#|$)/i.test(raw)) return raw;
        console.warn("[GPX] Absolute URL without .gpx/.xml; falling back:", raw);
        return FALLBACK_GPX;
      }
      // Absolute path from /public
      if (raw.startsWith("/")) {
        if (/\.(gpx|xml)(\?|#|$)/i.test(raw)) return raw;
        console.warn("[GPX] Absolute path without .gpx/.xml; falling back:", raw);
        return FALLBACK_GPX;
      }
      // Relative path like "gpx_files/foo.gpx" or just "foo.gpx"
      let fname = raw.replace(/^\.?\/*/, "");
      if (!/^gpx_files\//i.test(fname)) fname = `gpx_files/${fname}`;
      if (!/\.(gpx|xml)(\?|#|$)/i.test(fname)) fname = `${fname}.gpx`;
      return `/${fname}`;
    }

    const base =
      selected.normalized_name?.trim() ||
      selected.name.toLowerCase().replace(/[^\w]+/g, "-").replace(/(^-|-$)/g, "");
    if (base) return `/gpx_files/${base}.gpx`;

    return FALLBACK_GPX;
  }, [selected]);
}
