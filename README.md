# Dad's RV Travel Companion

A private Streamlit travel companion for RV trips from an Arizona home base.

## What It Does

- Travel journal with daily notes, tags, ratings, and photo uploads
- Stops and campground log with hookups, nights, cost, and cell signal
- Dashboard with current location, Arizona home base distance, map, and recent notes
- Weather watch using Open-Meteo, with no API key required
- Local event search links for festivals, farmers markets, live music, and campgrounds
- RV maintenance log for tires, generator, propane, batteries, truck, repairs, and more

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
