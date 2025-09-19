# Munro Scout

**Live site:** https://munroapp.onrender.com/

Munro Scout is an exploration assistant for Scotland’s Munros. It began with a systematic web-scrape of Walkhighlands, transforming scattered route descriptions into a structured dataset of distances, times, grades, and terrain. Layered with geospatial lookups, this dataset became the foundation for insights and recommendations, whether finding a quiet ridge near Fort William or a quick summit close to a bus stop. An LLM-backed conversation interface then ties it all together, letting walkers discover routes that fit their style, constraints, and location.

## Project Structure

```
munro-scout/
├── client/                     # React front-end for the interactive explorer
│   ├── src/                    # Components, state hooks, and view-level logic
│   └── public/                 # Static assets served by the SPA shell
├── server/                     # Flask API surface and background utilities
│   ├── app.py                  # Application build
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
- **Normalisation utilities** – Data cleaning helpers repair and standardise unicode, and derive deterministic keys to keep imports idempotent.
- **Progressive enhancement** – The back end exposes JSON APIs that power both the search UI and the chat assistant, allowing the same retrieval primitives to be reused across touchpoints.

## How to Use

1. Visit **https://munroapp.onrender.com/** to open the web app.
2. Browse the map or filter list to inspect Munros by difficulty, bog factor, and descriptive tags.
3. Use the conversational assistant to describe the outing you want (e.g. "quiet ridge near Glencoe accessible by bus"). The system parses your intent, retrieves matching hills, and summarises why they fit.

## Potential Features

- Weather and conditions integration to tailor recommendations to upcoming forecasts.
- Public transport API integration with real-time train and bus schedules for route accessibility.
- Multi-day route planning linking Munros, huts, and bothies into tailored itineraries.
- Personal logbook support with completion tracking and trip notes.

## Development Notes

- Run the Flask API locally with `python server/app.py` (or via a WSGI server) after setting the necessary environment variables (database path, OpenAI API key, etc.).
- The front end is a TypeScript React SPA; use `npm install` followed by `npm run dev` within the `client` directory for local development.
- Background scripts like `server/tag_munros.py` and `server/seed.py` help keep the dataset and search index up to date. Check the docstrings in each file for how to run them.

