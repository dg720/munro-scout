# Munro Scout

**Live site:** https://munroapp.onrender.com/

Munro Scout is a full-stack exploration tool for Scotland's Munros. A Vite-powered React client partners with a Flask API to surface curated hill data, coordinate lookups, and LLM-assisted chat guidance for planning ascents.

## How to use

1. Visit the live site to browse Scotland's Munros with searchable listings and rich detail panels.
2. Apply filters or free-text queries to narrow results by height, region, or descriptive tags.
3. Open the chat assistant to get personalised suggestions, itinerary tips, and tag clarifications.
4. Drill into individual Munro pages for coordinates, summaries, and related peaks to plan your day on the hill.

## Repository layout

```
munro-scout/
├── client/           # React front-end (TypeScript + Vite)
├── server/           # Flask API, data services, and background scripts
├── requirements.txt  # Python dependencies for the API and tooling
├── package.json      # Root Node dependencies (linting, shared tooling)
└── README.md
```

### API service (`server/`)

- `app.py` bootstraps the Flask application, configures CORS, and registers feature blueprints.
- `routes/` exposes REST endpoints for health checks, Munro listings, free-text search, tag summaries, and the LLM chat surface.
- `services/` encapsulate search orchestration, geo lookups, and enrichment logic shared across routes.
- `utils/` normalise user input, parse numeric filters, and compose SQL fragments for ranking.
- `extensions/llm.py` lazily initialises the configured LLM provider for tagging and chat.
- `munro_coords.py`, `seed.py`, and `tag_munros.py` build and maintain the SQLite dataset and coordinate cache.

### Client (`client/`)

- Vite + React front end written in TypeScript.
- Consumes the Flask API for search results, detail panels, and conversational assistance.
- Leans on component-level state and hooks to orchestrate filters and API requests.

## Stack highlights

| Layer        | Technologies |
|--------------|--------------|
| Front end    | React, TypeScript, Vite, CSS Modules |
| API          | Flask, SQLite, SQLAlchemy-style query helpers |
| Intelligence | OpenAI-powered chat + tagging workflows |
| Tooling      | Python virtualenv, npm scripts, dataset maintenance CLIs |

## Techniques in play

- **Structured search parsing** to normalise free-text, range filters, and tag selectors into SQL-ready conditions.
- **Hybrid ranking** that blends text relevance, numeric heuristics, and optional distance calculations for nearby hill discovery.
- **LLM-assisted workflows** for both user-facing chat recommendations and back-office tag generation.
- **Data curation scripts** to geocode missing coordinates, standardise names, and keep the SQLite database in sync.
- **Blueprint-driven Flask architecture** isolating HTTP concerns from domain services.
- **Client-side filter orchestration** with React hooks managing query state and optimistic UI feedback.

## Data & automation flow

1. **Seed scripts** ingest CSV datasets, clean descriptions, and populate the SQLite store.
2. **Coordinate builders** call external geocoding services and cache lat/long pairs for each Munro.
3. **Tag generation** leverages LLM prompts to classify routes, with review loops to keep taxonomy consistent.
4. **Search endpoints** stitch the curated data, filters, and scoring strategy together for responsive results.

## Potential features

- Offline-first caching so hill details remain available when signal drops on the hill.
- Progressive Web App shell for quick-add of favourite Munros and itinerary planning.
- User accounts to track completed peaks, wishlists, and shared trip reports.
- Weather and avalanche condition overlays sourced from third-party APIs.
- Live map visualisations with clustering and gradient difficulty layers.

## Development notes

- Run `python server/munro_coords.py --build` to refresh coordinate caches before recalculating distances.
- Regenerate descriptive tags with `python server/tag_munros.py --build` once the LLM credentials are set.
- Adjust default model identifiers via environment variables such as `MUNRO_CHAT_MODEL` to experiment with providers.

Happy exploring!
