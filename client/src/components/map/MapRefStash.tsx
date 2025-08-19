import { useMap } from "react-leaflet";
import { useEffect } from "react";

export default function MapRefStash() {
  const map = useMap();
  useEffect(() => {
    (window as any)._leaflet_map = map;
  }, [map]);
  return null;
}
