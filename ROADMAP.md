# Build Roadmap

## Phase 1: Deployable Streamlit App

- [x] Create the first Streamlit app shell
- [x] Add journal entries
- [x] Add photo uploads
- [x] Add trip stops and campground notes
- [x] Add weather using a no-key API
- [x] Add local event search links
- [x] Add maintenance log
- [x] Add Streamlit Cloud config

## Phase 2: Make Data Persistent Online

Recommended next backend: **Supabase**.

Why:

- Works well with Streamlit
- Stores journal entries, stops, maintenance logs, and user settings
- Can store photo files
- Keeps private travel data out of Git
- Lets the app stay simple while becoming reliable online

Alternative simpler option: **Google Sheets** for journal/stops/maintenance, with photos stored separately.

## Phase 3: Travel Features

- Add route planner with planned stops
- Add arrival and departure checklist
- Add campground favorites
- Add fuel and mileage tracker
- Add trip budget view
- Add printable trip summary

## Phase 4: Better Weather And Events

- Add weather alerts for wind, heat, freezing temperatures, and storms
- Add saved event finds
- Add nearby attractions
- Add low-clearance and RV caution notes

## Phase 5: Polish For Dad

- Add a simple large-button mobile layout
- Add private sign-in
- Add photo gallery by trip
- Add yearly travel recap
- Add export to PDF or CSV
