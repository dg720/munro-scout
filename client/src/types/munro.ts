export interface Munro {
  id: number;
  name: string;
  summary: string;
  distance: number;
  time: number;
  grade: number;
  bog: number; // 0–5
  start: string;
  title?: string;
  terrain?: string;
  public_transport?: string;
  description?: string;
  gpx_file?: string;   // "a.gpx" | "gpx_files/a.gpx" | "/gpx_files/a.gpx" | full URL
  url?: string;
  route_url?: string;
  normalized_name?: string;
  [key: string]: any;
}
