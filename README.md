# Munro Scout

**Live site:** https://munroapp.onrender.com/

N.B. It may take up to 30-60 seconds for the backend to reboot when the website is opened. 

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

- **Search pipeline** – Uses a mix of full-text search (SQLite FTS5), fuzzy matching, and tag lookups to find results even when queries are unclear or very specific.  
- **Location handling** – Stores coordinates, calculates distances with haversine formulas, and uses cached lookups (Nominatim/Overpass) to rank results by proximity.  
- **LLM support** – Uses LangChain with OpenAI to understand natural language queries and to add simple tags/keywords to routes.  
- **Data cleaning** – Normalises text, fixes encoding issues, and creates consistent IDs so imports don’t duplicate entries.  
- **Dataset seeding** – Scripts prepare and refresh the Munro dataset, making sure the database and search index stay up to date.  
- **APIs for reuse** – The backend provides JSON APIs that power both the search interface and the chat assistant, so the same logic works across features.  

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

## REST API Snapshot

The same search helpers power both the chat assistant and the REST surface. The `POST /api/search` endpoint accepts JSON payloads with the following optional keys:

- `location` – place name anchoring a nearest-hill lookup.
- `query` – free-text terms for full-text or fallback search.
- `include_tags` / `exclude_tags` – arrays of tag slugs to require or omit.
- `bog_max` / `grade_max` – numeric upper bounds for bog factor and grade.
- `distance_min_km` / `distance_max_km` – lower/upper limits for route length (kilometres).
- `time_min_h` / `time_max_h` – lower/upper limits for estimated time (hours).
- `limit` – maximum number of returned results (defaults to 12).

Responses mirror the structure returned by `search_core` (for text/tag queries) or `search_by_location_core` (for location-first searches), including any applied constraints in the metadata.

