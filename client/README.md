# Munro Scout Client

The Munro Scout client is a React single-page application that helps walkers explore Scotland's Munros. The interface combines a data-rich dashboard, conversational assistant, and detailed hill views so users can discover summits that match their preferences and constraints.

## Feature Overview

- **Interactive dashboard** – Filter Munros by region, difficulty, bog factor, or curated tags while inspecting stats and charts tailored to the selected hills.
- **Conversational chat assistant** – Ask natural-language questions (e.g. "family-friendly ridge near Aviemore") and receive LLM-backed suggestions sourced from the same search pipeline as the dashboard.
- **Rich details view** – Dive into a single hill to review route notes, terrain context, GPX overlays, and related recommendations.

## Technology Stack

- **React + TypeScript** powered by Create React App.
- **Chakra UI** for accessible, themeable UI components.
- **React Leaflet & Leaflet GPX** to render maps, approach lines, and spatial overlays.
- **Axios** for HTTP requests to the Munro Scout API.

## Getting Started Locally

1. Install dependencies:
   ```bash
   npm install
   ```
2. Start the development server (defaults to http://localhost:3000):
   ```bash
   npm start
   ```
3. The app proxies API calls using the configuration described below. Update the settings if you are running the Flask API on a non-default host.

Hot module reloading is enabled, so component changes appear instantly in the browser.

## API Base Configuration

The client resolves the API base URL in the following order:

1. `window.__MUNRO_API_BASE__` – injected at runtime by the hosting template.
2. `REACT_APP_API_BASE` – compile-time environment variable consumed by Create React App.
3. Fallback to the Render-hosted production API (`https://munro-scout.onrender.com`).

When developing locally against the Flask server, export an environment variable before starting the client:

```bash
export REACT_APP_API_BASE="http://localhost:5000"
npm start
```

Alternatively, inject `window.__MUNRO_API_BASE__` on the static host that serves the built assets if you need to retarget without rebuilding.

## Available Scripts

| Command | Description |
| ------- | ----------- |
| `npm start` | Launches the development server with hot reloading. |
| `npm test` | Runs the Jest + Testing Library suite in watch mode (press `q` to quit). |
| `npm run build` | Produces an optimized production bundle in `build/`. |
| `npm run eject` | Exposes CRA configuration files—irreversible, not generally required. |

## Testing

- Unit and integration tests live alongside components and hooks.
- Execute the suite with `npm test`. For CI-friendly output, use `CI=true npm test -- --watch=false`.
- Testing Library and Jest DOM assertions cover UI interactions and API state management.

## Linting & Code Quality

- The project inherits Create React App's ESLint configuration (`react-app` + `react-app/jest`).
- No explicit `npm run lint` script is defined; lint warnings surface automatically in the terminal and browser during `npm start`.
- TypeScript type-checking runs as part of the build to catch structural issues early.

## Production Builds & Deployment Tips

1. Build the static assets:
   ```bash
   npm run build
   ```
2. Serve the generated `build/` directory with any static host (Render, Netlify, S3 + CloudFront, etc.). Ensure your hosting stack injects or proxies API requests to the correct backend.
3. If your deployment environment needs a different API origin, either set `REACT_APP_API_BASE` during the build step or inject `window.__MUNRO_API_BASE__` in the hosting template (e.g. via an inline script) before loading `index.html`.
4. Consider enabling HTTPS and configuring CORS on the API to match your chosen domain.

## Additional Notes

- Coordinate `npm install` versions with the server's expected API contract to avoid mismatches in request/response payloads.
- Keep `.env` files out of version control; prefer `.env.local` for machine-specific configuration.
- The front end is often paired with the Flask API located in `../server`; ensure both services run simultaneously for full functionality.

