# Bob's Adventures

A private Streamlit travel companion for Bob's RV trips from an Arizona home base.

## What It Does

- Travel journal with daily notes, tags, ratings, and photo uploads
- Memory-of-the-day prompts and postcard-style journal cards
- Photo gallery with location filtering
- Stops and campground log with hookups, nights, cost, and cell signal
- Campground score cards for quiet, parking ease, and stay-again rating
- Dashboard with current location, Arizona home base distance, map, stats, badges, and recent postcards
- Trip command center with current stop, today's weather, next stop, reservation, and checklist progress
- Full travel-poster hero, custom BA logo mark, theme presets, route board, and upgraded state sticker board
- Weather watch using Open-Meteo, with no API key required
- RV-friendly weather alert cards for wind, heat, and freezing temperatures
- Browser GPS/manual coordinate helper and radar/forecast links
- Local event search links for festivals, farmers markets, live music, and campgrounds
- Local food finder for diners, breakfast, BBQ, coffee, and ice cream
- Departure checklist and favorite places tracker
- Reservation tracker with campground, site, confirmation number, dates, phone, balance, and notes
- Family View tab with a read-only travel snapshot
- Adventure badges, trip awards, road timeline, state sticker board, and season recap
- Fun Stuff tab with an adventure prompt wheel, roadside finds, and postcard generator
- RV maintenance log for tires, generator, propane, batteries, truck, repairs, and more
- Optional Supabase cloud storage with local JSON fallback

## Run Locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy On Streamlit Community Cloud

1. Push this repository to GitHub.
2. Go to [Streamlit Community Cloud](https://share.streamlit.io/).
3. Choose **New app**.
4. Select the GitHub repository.
5. Set the main file path to `app.py`.
6. Deploy.

## Data Storage

The app currently saves journal entries, trip stops, maintenance notes, and uploaded photos in the local `data/` folder. That folder is intentionally ignored by Git so private travel notes and photos do not get committed.

For a hosted Streamlit app, the next build step should be moving persistent data to a cloud-friendly backend such as Google Sheets, Supabase, Airtable, or a private GitHub-backed storage workflow.

## Optional Supabase Storage

Add these values to Streamlit secrets:

```toml
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_ANON_KEY = "your-anon-key"
```

Create this table in Supabase:

```sql
create table app_records (
  record_type text primary key,
  payload jsonb not null default '[]'::jsonb,
  updated_at timestamp with time zone default now()
);
```

When those secrets exist, the app saves records to Supabase. Without them, it keeps using local files.
