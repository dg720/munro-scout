# Munro Scout

**Live site:** https://munroapp.onrender.com/

Munro Scout is an exploration assistant for Scotland's Munros. It blends curated hill data, geospatial lookups, and an LLM-backed conversation interface so walkers can discover routes that suit their style, constraints, and location.

## Project Structure

```
munro-scout/
├── client/                     # React + Vite front-end for the interactive explorer
│   ├── src/                    # Components, state hooks, and view-level logic
│   └── public/                 # Static assets served by the SPA shell
├── server/                     # Flask API surface and background utilities
│   ├── app.py                  # Application factory and CORS setup
│   ├── config.py               # Environment-driven settings
│   ├── routes/                 # HTTP blueprints (health, search, chat, etc.)
│   ├── services/               # Search, geo, and data orchestration layers
│   ├── utils/                  # Shared parsing helpers (query/token filters)
│   ├── extensions/             # Lazy-initialised integrations (LLM client)
│   ├── munro_coords.py         # Coordinate builder + nearest-hill maths
│   ├── tag_munros.py           # Ontology-based auto-tagging workflow
│   └── seed.py                 # Dataset normalisation & ingestion tooling
├── requirements.txt            # Python dependencies for the API toolchain
├── package.json                # Front-end tooling dependencies
└── README.md                   # Project documentation (this file)
```

## Techniques & Key Components

- **Layered search pipeline** – Full-text search (SQLite FTS5), fuzzy LIKE fallbacks, and tag-only rescues allow robust retrieval even when queries are noisy or highly specific.
- **Geospatial reasoning** – A dedicated coordinates module caches Nominatim/Overpass results, implements haversine distance calculations, and powers location-first ranking.
- **LLM-assisted flows** – LangChain's OpenAI bindings drive two specialised tasks: structured intent extraction for conversational queries and conservative route tagging/keywording.
- **Normalisation utilities** – Data cleaning helpers repair mojibake, standardise unicode, snake-case fields, and derive deterministic keys to keep imports idempotent.
- **Progressive enhancement** – The back end exposes JSON APIs that power both the search UI and the chat assistant, allowing the same retrieval primitives to be reused across touchpoints.

## How to Use

1. Visit **https://munroapp.onrender.com/** to open the web app.
2. Browse the map or filter list to inspect Munros by difficulty, bog factor, and descriptive tags.
3. Use the conversational assistant to describe the outing you want (e.g. "quiet ridge near Glencoe under 6 hours"). The system parses your intent, retrieves matching hills, and summarises why they fit.

The site is designed to surface both well-known classics and lesser-travelled options based on the factors that matter most to you.

## Potential Features

- Offline-first caching so hikers can review saved routes in low-connectivity areas.
- Personal logbook support with completion tracking and trip notes.
- Weather and conditions integration to tailor recommendations to upcoming forecasts.
- Export utilities for GPX/geojson bundles tailored to the suggested outings.
- Multi-lingual support for overseas visitors planning Munro rounds.

## Development Notes

- Run the Flask API locally with `python server/app.py` (or via a WSGI server) after setting the necessary environment variables (database path, OpenAI API key, etc.).
- The front end is a TypeScript React SPA bootstrapped with Vite; use `npm install` followed by `npm run dev` within the `client` directory for local development.
- Background scripts such as `server/tag_munros.py` and `server/seed.py` keep the dataset and search indices consistent—consult their docstrings for invocation details.

