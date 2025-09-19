# Munro Scout Client

The Munro Scout client is a React single-page application that helps walkers explore Scotland's Munros. The interface combines a data-rich dashboard, conversational assistant, and detailed route views so users can discover summits that match their preferences and constraints.

## Feature Overview

- **Interactive dashboard** – Filter Munros by region, difficulty, bog factor, or curated tags while inspecting stats and charts tailored to the selected hills.
- **Conversational chat assistant** – Ask natural-language questions (e.g. "family-friendly ridge near Aviemore") and receive LLM-backed suggestions sourced from the same search pipeline as the dashboard.
- **Rich details view** – Dive into a single hill to review route notes, terrain context, GPX overlays, and related recommendations.

## Technology Stack

- **React + TypeScript** powered by Create React App.
- **Chakra UI** for accessible, themeable UI components.
- **React Leaflet & Leaflet GPX** to render maps, approach lines, and spatial overlays.
- **Axios** for HTTP requests to the Munro Scout API.

