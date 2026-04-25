from __future__ import annotations

import json
import math
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import streamlit as st


APP_TITLE = "Bob's Adventures"
HOME_BASE = {
    "name": "Arizona Home Base",
    "city": "Arizona",
    "state": "AZ",
    "latitude": 34.0489,
    "longitude": -111.0937,
}

DATA_DIR = Path("data")
PHOTO_DIR = DATA_DIR / "photos"
JOURNAL_FILE = DATA_DIR / "journal_entries.json"
STOPS_FILE = DATA_DIR / "trip_stops.json"
MAINTENANCE_FILE = DATA_DIR / "maintenance_log.json"
ROADSIDE_FILE = DATA_DIR / "roadside_finds.json"

US_STATES = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
]

MEMORY_PROMPTS = [
    "Best thing I saw today",
    "Best meal or snack",
    "Funniest moment",
    "Best road view",
    "Something I learned",
    "A place worth coming back to",
    "Best conversation",
]


def ensure_storage() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    PHOTO_DIR.mkdir(exist_ok=True)
    for path in [JOURNAL_FILE, STOPS_FILE, MAINTENANCE_FILE, ROADSIDE_FILE]:
        if not path.exists():
            path.write_text("[]", encoding="utf-8")


def load_records(path: Path) -> list[dict[str, Any]]:
    ensure_storage()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def save_records(path: Path, records: list[dict[str, Any]]) -> None:
    ensure_storage()
    path.write_text(json.dumps(records, indent=2), encoding="utf-8")


def add_record(path: Path, record: dict[str, Any]) -> None:
    records = load_records(path)
    records.insert(0, record)
    save_records(path, records)


def safe_filename(name: str) -> str:
    clean = "".join(char if char.isalnum() or char in ".-_" else "_" for char in name)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{clean}"


def save_uploaded_photos(files: list[Any]) -> list[str]:
    saved_paths = []
    for file in files:
        target = PHOTO_DIR / safe_filename(file.name)
        target.write_bytes(file.getbuffer())
        saved_paths.append(str(target))
    return saved_paths


@st.cache_data(ttl=60 * 60)
def geocode_location(query: str) -> dict[str, Any] | None:
    response = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": query, "count": 1, "language": "en", "format": "json"},
        timeout=10,
    )
    response.raise_for_status()
    results = response.json().get("results", [])
    return results[0] if results else None


@st.cache_data(ttl=30 * 60)
def get_weather(latitude: float, longitude: float) -> dict[str, Any]:
    response = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,wind_speed_10m_max",
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "timezone": "auto",
            "forecast_days": 7,
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def weather_label(code: int) -> str:
    labels = {
        0: "Clear",
        1: "Mostly clear",
        2: "Partly cloudy",
        3: "Cloudy",
        45: "Fog",
        48: "Fog",
        51: "Light drizzle",
        53: "Drizzle",
        55: "Heavy drizzle",
        61: "Light rain",
        63: "Rain",
        65: "Heavy rain",
        71: "Light snow",
        73: "Snow",
        75: "Heavy snow",
        80: "Rain showers",
        81: "Rain showers",
        82: "Heavy showers",
        95: "Thunderstorms",
    }
    return labels.get(code, "Weather changing")


def miles_between(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 3958.8
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def event_search_links(city: str, state: str) -> dict[str, str]:
    location = f"{city}, {state}".strip(", ")
    query = location.replace(" ", "+")
    return {
        "Local events": f"https://www.google.com/search?q=events+near+{query}",
        "Festivals": f"https://www.google.com/search?q=festivals+near+{query}",
        "Farmers markets": f"https://www.google.com/search?q=farmers+markets+near+{query}",
        "Live music": f"https://www.google.com/search?q=live+music+near+{query}",
        "Campgrounds": f"https://www.google.com/search?q=campgrounds+near+{query}",
    }


def visited_states(stops: list[dict[str, Any]], journal: list[dict[str, Any]]) -> set[str]:
    states = {HOME_BASE["state"]}
    for stop in stops:
        state = str(stop.get("state", "")).strip().upper()
        if state in US_STATES:
            states.add(state)
    for entry in journal:
        location = str(entry.get("location", "")).upper()
        for state in US_STATES:
            if f", {state}" in location or location.endswith(f" {state}"):
                states.add(state)
    return states


def all_photo_records(journal: list[dict[str, Any]]) -> list[dict[str, str]]:
    photos = []
    for entry in journal:
        for photo_path in entry.get("photos", []):
            if Path(photo_path).exists():
                photos.append(
                    {
                        "path": photo_path,
                        "title": entry.get("title", "Trip photo"),
                        "date": entry.get("entry_date", ""),
                        "location": entry.get("location", ""),
                    }
                )
    return photos


def adventure_badges(
    journal: list[dict[str, Any]],
    stops: list[dict[str, Any]],
    roadside: list[dict[str, Any]],
) -> list[tuple[str, str]]:
    photos = all_photo_records(journal)
    states = visited_states(stops, journal)
    badges = []
    rules = [
        (len(journal) >= 1, "First Logbook Entry", "The adventure has officially started."),
        (len(stops) >= 1, "First Stop Saved", "Bob has a place pinned on the route."),
        (len(photos) >= 1, "Photo Collector", "Trip photos are becoming part of the story."),
        (len(states) >= 2, "State Sticker Starter", "More than one state is on the board."),
        (len(states) >= 5, "Five-State Wanderer", "The map is starting to fill in."),
        (any(entry.get("rating", 0) == 5 for entry in journal), "Five-Star Memory", "A top-rated memory made the log."),
        (any("favorite" in entry.get("tags", []) for entry in journal), "Favorite Found", "Bob marked a keeper."),
        (len(roadside) >= 1, "Roadside Treasure", "A quirky find made the trip notebook."),
        (sum(int(stop.get("nights", 0) or 0) for stop in stops) >= 7, "Week On The Road", "At least seven campground nights are logged."),
    ]
    for earned, name, detail in rules:
        if earned:
            badges.append((name, detail))
    return badges


def trip_stats(journal: list[dict[str, Any]], stops: list[dict[str, Any]]) -> dict[str, Any]:
    photos = all_photo_records(journal)
    states = visited_states(stops, journal)
    nights = sum(int(stop.get("nights", 0) or 0) for stop in stops)
    total_cost = sum(float(stop.get("cost", 0) or 0) * int(stop.get("nights", 0) or 0) for stop in stops)
    favorite_entries = [entry for entry in journal if int(entry.get("rating", 0) or 0) >= 5]
    longest_stop = max(stops, key=lambda stop: int(stop.get("nights", 0) or 0), default={})
    return {
        "states": len(states),
        "nights": nights,
        "photos": len(photos),
        "cost": total_cost,
        "favorite": favorite_entries[0].get("title", "Not picked yet") if favorite_entries else "Not picked yet",
        "longest": longest_stop.get("name", "Not logged yet"),
    }


def render_badge_row(badges: list[tuple[str, str]]) -> None:
    if not badges:
        st.info("Badges will unlock as Bob adds journal entries, stops, photos, favorites, and roadside finds.")
        return
    for index in range(0, len(badges), 3):
        cols = st.columns(3)
        for column, (name, detail) in zip(cols, badges[index : index + 3]):
            column.markdown(
                f"""
                <div class="badge-card">
                    <div class="badge-title">{name}</div>
                    <div class="badge-detail">{detail}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_timeline(stops: list[dict[str, Any]]) -> None:
    st.subheader("Road Timeline")
    if not stops:
        st.info("Saved stops will appear here as a route-style timeline.")
        return
    sorted_stops = sorted(stops, key=lambda stop: stop.get("arrival", "9999-99-99"))
    for stop in sorted_stops:
        st.markdown(
            f"""
            <div class="timeline-item">
                <div class="timeline-date">{stop.get('arrival', '')}</div>
                <div class="timeline-title">{stop.get('name', 'Unnamed stop')}</div>
                <div class="timeline-detail">{stop.get('city', '')}, {stop.get('state', '')} - {stop.get('status', 'Stop')} - {stop.get('nights', 0)} nights</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_state_sticker_board(states: set[str]) -> None:
    st.subheader("State Sticker Board")
    rows = [US_STATES[index : index + 10] for index in range(0, len(US_STATES), 10)]
    for row in rows:
        cols = st.columns(10)
        for column, state in zip(cols, row):
            class_name = "state-sticker earned" if state in states else "state-sticker"
            column.markdown(f'<div class="{class_name}">{state}</div>', unsafe_allow_html=True)


def render_postcard_card(entry: dict[str, Any]) -> None:
    tags = " / ".join(entry.get("tags", [])) or "road note"
    prompt = entry.get("memory_prompt", "Memory")
    memory = entry.get("memory_answer", "")
    st.markdown(
        f"""
        <div class="postcard-card">
            <div class="postcard-stamp">{entry.get('entry_date', '')}</div>
            <h4>{entry.get('title', 'Untitled adventure')}</h4>
            <strong>{entry.get('location', 'Somewhere on the road')}</strong><br>
            <small>{tags} - Rating {entry.get('rating', 0)}/5</small>
            <p>{entry.get('notes', '')}</p>
            <p><strong>{prompt}:</strong> {memory}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_photo_gallery(journal: list[dict[str, Any]]) -> None:
    st.subheader("Photo Gallery")
    photos = all_photo_records(journal)
    if not photos:
        st.info("Uploaded journal photos will show up here in a travel gallery.")
        return

    location_filter = st.selectbox(
        "Filter by location",
        ["All"] + sorted({photo["location"] for photo in photos if photo["location"]}),
    )
    if location_filter != "All":
        photos = [photo for photo in photos if photo["location"] == location_filter]

    for index in range(0, len(photos), 3):
        cols = st.columns(3)
        for column, photo in zip(cols, photos[index : index + 3]):
            column.image(photo["path"], use_column_width=True)
            column.caption(f"{photo['date']} - {photo['location']} - {photo['title']}")


def render_postcard_generator(journal: list[dict[str, Any]]) -> None:
    st.subheader("Postcard Generator")
    if not journal:
        st.info("Add a journal entry first, then this can make a printable postcard-style note.")
        return
    labels = [f"{entry.get('entry_date', '')} - {entry.get('title', 'Untitled')}" for entry in journal]
    selected = st.selectbox("Pick a memory", labels)
    entry = journal[labels.index(selected)]
    render_postcard_card(entry)
    postcard_text = (
        f"Bob's Adventures\n\n"
        f"{entry.get('title', 'Untitled adventure')}\n"
        f"{entry.get('entry_date', '')} - {entry.get('location', '')}\n\n"
        f"{entry.get('notes', '')}\n\n"
        f"{entry.get('memory_prompt', 'Memory')}: {entry.get('memory_answer', '')}\n"
    )
    st.download_button(
        "Download postcard text",
        data=postcard_text,
        file_name=f"bobs_adventure_postcard_{entry.get('entry_date', 'memory')}.txt",
        mime="text/plain",
        use_container_width=True,
    )


def render_trip_awards(journal: list[dict[str, Any]], stops: list[dict[str, Any]]) -> None:
    st.subheader("Best Of The Trip")
    best_memory = max(journal, key=lambda entry: int(entry.get("rating", 0) or 0), default={})
    best_campground = max(stops, key=lambda stop: int(stop.get("stay_again", 0) or 0), default={})
    longest_stop = max(stops, key=lambda stop: int(stop.get("nights", 0) or 0), default={})
    awards = [
        ("Best Memory", best_memory.get("title", "Add journal ratings to pick this")),
        ("Best Campground", best_campground.get("name", "Rate campgrounds to pick this")),
        ("Longest Stay", longest_stop.get("name", "Add stops to pick this")),
    ]
    cols = st.columns(3)
    for column, (title, detail) in zip(cols, awards):
        column.markdown(
            f"""
            <div class="award-card">
                <div class="award-title">{title}</div>
                <div class="award-detail">{detail}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def page_header() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon=":blue_car:", layout="wide")
    st.markdown(
        """
        <style>
        :root {
            --sand: #f7efe1;
            --sunset: #d86f45;
            --campfire: #f2a541;
            --cactus: #2f6f5e;
            --sky: #4f9fcf;
            --ink: #26312d;
        }

        .stApp {
            background:
                linear-gradient(180deg, rgba(247,239,225,0.98) 0%, rgba(255,252,245,1) 42%),
                radial-gradient(circle at top left, rgba(242,165,65,0.18), transparent 28%),
                radial-gradient(circle at top right, rgba(79,159,207,0.16), transparent 30%);
            color: var(--ink);
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #fff7ea 0%, #edf6f1 100%);
            border-right: 1px solid rgba(47, 111, 94, 0.18);
        }

        h1 {
            color: var(--cactus);
            font-weight: 800;
        }

        h2, h3 {
            color: #30483f;
        }

        div[data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.76);
            border: 1px solid rgba(47, 111, 94, 0.14);
            border-radius: 8px;
            padding: 0.85rem;
            box-shadow: 0 6px 18px rgba(56, 42, 22, 0.06);
        }

        .stButton > button,
        .stDownloadButton > button,
        a[data-testid="stLinkButton"] {
            border-radius: 8px;
            border-color: rgba(47, 111, 94, 0.36);
            background: #fffaf1;
            color: var(--cactus);
            font-weight: 650;
        }

        .stButton > button:hover,
        a[data-testid="stLinkButton"]:hover {
            border-color: var(--sunset);
            color: #9c4529;
        }

        [data-testid="stCaptionContainer"] {
            color: #6a5c4c;
        }

        .adventure-hero {
            border-left: 6px solid var(--sunset);
            background: linear-gradient(90deg, rgba(255,250,241,0.94), rgba(237,246,241,0.82));
            padding: 1rem 1.1rem;
            border-radius: 8px;
            margin-bottom: 1rem;
        }

        .adventure-hero strong {
            color: var(--sunset);
        }

        .badge-card,
        .postcard-card,
        .timeline-item,
        .weather-card,
        .award-card {
            background: rgba(255, 250, 241, 0.92);
            border: 1px solid rgba(47, 111, 94, 0.16);
            border-radius: 8px;
            padding: 0.85rem;
            margin-bottom: 0.75rem;
            box-shadow: 0 6px 18px rgba(56, 42, 22, 0.06);
        }

        .badge-title,
        .timeline-title,
        .award-title {
            color: var(--cactus);
            font-weight: 800;
        }

        .badge-detail,
        .timeline-detail,
        .timeline-date,
        .award-detail {
            color: #6a5c4c;
            font-size: 0.9rem;
        }

        .postcard-card {
            border: 2px solid rgba(216, 111, 69, 0.34);
            background:
                linear-gradient(135deg, rgba(255,255,255,0.96), rgba(255,248,236,0.94));
        }

        .postcard-stamp {
            float: right;
            border: 2px dashed rgba(216, 111, 69, 0.62);
            color: var(--sunset);
            padding: 0.35rem 0.5rem;
            border-radius: 6px;
            font-weight: 800;
            font-size: 0.8rem;
        }

        .state-sticker {
            text-align: center;
            border: 1px dashed rgba(47, 111, 94, 0.28);
            border-radius: 8px;
            padding: 0.45rem 0.1rem;
            margin-bottom: 0.35rem;
            color: #8b7b68;
            background: rgba(255, 255, 255, 0.58);
            font-weight: 700;
        }

        .state-sticker.earned {
            background: linear-gradient(135deg, #d86f45, #f2a541);
            color: #ffffff;
            border-color: transparent;
            box-shadow: 0 5px 12px rgba(216, 111, 69, 0.22);
        }

        .weather-card.watch {
            border-left: 6px solid var(--campfire);
        }

        .weather-card.good {
            border-left: 6px solid var(--cactus);
        }

        .quick-actions button {
            min-height: 3rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.title(APP_TITLE)
    st.markdown(
        """
        <div class="adventure-hero">
            <strong>Road notes, weather, photos, and favorite stops from the fifth wheel.</strong><br>
            Built around spring adventures, winter returns to Arizona, and the places worth remembering.
        </div>
        """,
        unsafe_allow_html=True,
    )


def sidebar_location() -> dict[str, Any]:
    st.sidebar.header("Current Stop")
    city = st.sidebar.text_input("City", value="Quartzsite")
    state = st.sidebar.text_input("State", value="AZ")
    location_query = f"{city}, {state}"

    if st.sidebar.button("Update weather location", use_container_width=True):
        st.session_state["location_query"] = location_query

    query = st.session_state.get("location_query", location_query)
    location = None
    try:
        location = geocode_location(query)
    except requests.RequestException:
        st.sidebar.warning("Weather location lookup is offline right now.")

    if not location:
        location = {
            "name": city,
            "admin1": state,
            "latitude": HOME_BASE["latitude"],
            "longitude": HOME_BASE["longitude"],
        }

    st.sidebar.divider()
    st.sidebar.metric("Home Base", HOME_BASE["state"])
    distance = miles_between(
        HOME_BASE["latitude"],
        HOME_BASE["longitude"],
        float(location["latitude"]),
        float(location["longitude"]),
    )
    st.sidebar.metric("Miles from home base", f"{distance:,.0f}")
    return location


def render_dashboard(location: dict[str, Any]) -> None:
    journal = load_records(JOURNAL_FILE)
    stops = load_records(STOPS_FILE)
    maintenance = load_records(MAINTENANCE_FILE)
    roadside = load_records(ROADSIDE_FILE)
    stats = trip_stats(journal, stops)

    st.markdown("### Bob's Travel Stats")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Journal Entries", len(journal))
    col2.metric("States Started", stats["states"])
    col3.metric("Photos Saved", stats["photos"])
    col4.metric("Nights Logged", stats["nights"])

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Trip Stops", len(stops))
    col6.metric("Roadside Finds", len(roadside))
    col7.metric("Maintenance Notes", len(maintenance))
    col8.metric("Current Area", f"{location.get('name', 'Unknown')}, {location.get('admin1', '')}")

    st.subheader("Trip Map")
    map_rows = [
        {
            "stop": HOME_BASE["name"],
            "lat": HOME_BASE["latitude"],
            "lon": HOME_BASE["longitude"],
            "kind": "Home",
        },
        {
            "stop": location.get("name", "Current stop"),
            "lat": float(location["latitude"]),
            "lon": float(location["longitude"]),
            "kind": "Current",
        },
    ]
    for stop in stops:
        if stop.get("latitude") and stop.get("longitude"):
            map_rows.append(
                {
                    "stop": stop["name"],
                    "lat": float(stop["latitude"]),
                    "lon": float(stop["longitude"]),
                    "kind": stop.get("status", "Stop"),
                }
            )
    st.map(pd.DataFrame(map_rows), latitude="lat", longitude="lon", size=120)

    left, right = st.columns([1.2, 1])
    with left:
        st.subheader("Latest Postcards")
        if journal:
            for entry in journal[:3]:
                render_postcard_card(entry)
        else:
            st.info("No journal entries yet. Add the first travel note from the Journal tab.")
    with right:
        st.subheader("Adventure Badges")
        render_badge_row(adventure_badges(journal, stops, roadside))

    render_timeline(stops)


def render_journal() -> None:
    st.subheader("Travel Journal")
    with st.form("journal_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        title = col1.text_input("Entry title")
        entry_date = col2.date_input("Date", value=date.today())
        location = st.text_input("Location")
        tags = st.multiselect(
            "Tags",
            [
                "campground",
                "family",
                "food",
                "scenic",
                "maintenance",
                "weather",
                "road conditions",
                "favorite",
                "campfire story",
                "roadside find",
                "good eats",
            ],
        )
        rating = st.slider("Would he come back?", 1, 5, 4)
        prompt = st.selectbox("Memory of the day", MEMORY_PROMPTS)
        memory_answer = st.text_input("Answer")
        notes = st.text_area("Notes", height=170)
        photos = st.file_uploader("Attach photos", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
        submitted = st.form_submit_button("Save journal entry", use_container_width=True)

    if submitted:
        if not title or not notes:
            st.warning("Add a title and notes before saving.")
        else:
            photo_paths = save_uploaded_photos(photos)
            add_record(
                JOURNAL_FILE,
                {
                    "id": datetime.now().isoformat(),
                    "title": title,
                    "entry_date": str(entry_date),
                    "location": location,
                    "tags": tags,
                    "rating": rating,
                    "memory_prompt": prompt,
                    "memory_answer": memory_answer,
                    "notes": notes,
                    "photos": photo_paths,
                },
            )
            st.success("Journal entry saved.")

    entries = load_records(JOURNAL_FILE)
    search = st.text_input("Search entries")
    if search:
        needle = search.lower()
        entries = [
            entry
            for entry in entries
            if needle in json.dumps(entry, default=str).lower()
        ]

    for entry in entries:
        with st.expander(f"{entry['entry_date']} - {entry['title']}", expanded=False):
            render_postcard_card(entry)
            photo_paths = entry.get("photos", [])
            if photo_paths:
                st.image(photo_paths, width=220)


def render_stops() -> None:
    st.subheader("Stops and Campgrounds")
    with st.form("stop_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        name = col1.text_input("Stop or campground name")
        city = col2.text_input("City")
        state = col3.text_input("State")
        status = st.radio("Status", ["Planned", "Current", "Visited"], horizontal=True)
        col4, col5, col6 = st.columns(3)
        arrival = col4.date_input("Arrival", value=date.today())
        nights = col5.number_input("Nights", min_value=0, max_value=365, value=1)
        cost = col6.number_input("Nightly cost", min_value=0.0, value=0.0, step=5.0)
        hookups = st.multiselect("Hookups", ["Water", "Electric", "Sewer", "Dump station", "Laundry", "Showers", "Wi-Fi"])
        cell_signal = st.select_slider("Cell signal", options=["None", "Weak", "Good", "Great"], value="Good")
        col7, col8, col9 = st.columns(3)
        noise_level = col7.slider("Quiet score", 1, 5, 4)
        parking_ease = col8.slider("Parking ease", 1, 5, 4)
        stay_again = col9.slider("Stay again score", 1, 5, 4)
        notes = st.text_area("Campground notes", height=120)
        submitted = st.form_submit_button("Save stop", use_container_width=True)

    if submitted:
        if not name:
            st.warning("Add a stop or campground name before saving.")
        else:
            latitude = None
            longitude = None
            try:
                lookup = geocode_location(f"{city}, {state}") if city or state else None
                if lookup:
                    latitude = lookup["latitude"]
                    longitude = lookup["longitude"]
            except requests.RequestException:
                pass
            add_record(
                STOPS_FILE,
                {
                    "id": datetime.now().isoformat(),
                    "name": name,
                    "city": city,
                    "state": state,
                    "status": status,
                    "arrival": str(arrival),
                    "nights": nights,
                    "cost": cost,
                    "hookups": hookups,
                    "cell_signal": cell_signal,
                    "noise_level": noise_level,
                    "parking_ease": parking_ease,
                    "stay_again": stay_again,
                    "notes": notes,
                    "latitude": latitude,
                    "longitude": longitude,
                },
            )
            st.success("Stop saved.")

    stops = load_records(STOPS_FILE)
    if stops:
        stop_table = pd.DataFrame(stops)
        for column in ["noise_level", "parking_ease", "stay_again"]:
            if column not in stop_table:
                stop_table[column] = ""
        st.dataframe(
            stop_table[
                [
                    "arrival",
                    "name",
                    "city",
                    "state",
                    "status",
                    "nights",
                    "cost",
                    "cell_signal",
                    "noise_level",
                    "parking_ease",
                    "stay_again",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )
        st.subheader("Campground Score Cards")
        for stop in stops[:4]:
            cols = st.columns(4)
            cols[0].metric(stop.get("name", "Stop"), f"{stop.get('stay_again', 'N/A')}/5", "stay again")
            cols[1].metric("Quiet", f"{stop.get('noise_level', 'N/A')}/5")
            cols[2].metric("Parking", f"{stop.get('parking_ease', 'N/A')}/5")
            cols[3].metric("Cell", stop.get("cell_signal", "N/A"))
    else:
        st.info("No stops saved yet.")


def render_weather(location: dict[str, Any]) -> None:
    st.subheader("Weather Watch")
    try:
        weather = get_weather(float(location["latitude"]), float(location["longitude"]))
    except requests.RequestException:
        st.error("Weather is unavailable right now. Check internet connection or try again later.")
        return

    current = weather["current"]
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Temperature", f"{current['temperature_2m']:.0f} F")
    col2.metric("Condition", weather_label(int(current["weather_code"])))
    col3.metric("Wind", f"{current['wind_speed_10m']:.0f} mph")
    col4.metric("Humidity", f"{current['relative_humidity_2m']:.0f}%")

    daily = pd.DataFrame(weather["daily"])
    daily = daily.rename(
        columns={
            "time": "Date",
            "temperature_2m_max": "High F",
            "temperature_2m_min": "Low F",
            "precipitation_probability_max": "Rain %",
            "wind_speed_10m_max": "Wind mph",
        }
    )
    st.dataframe(daily, use_container_width=True, hide_index=True)

    alerts = []
    for row in daily.to_dict("records"):
        if row["Wind mph"] >= 25:
            alerts.append(("Wind Watch", f"{row['Date']}: high wind could matter for towing."))
        if row["Low F"] <= 32:
            alerts.append(("Freeze Watch", f"{row['Date']}: freezing temperatures possible."))
        if row["High F"] >= 95:
            alerts.append(("Heat Watch", f"{row['Date']}: extreme heat day."))
    if alerts:
        for title, detail in alerts:
            st.markdown(
                f"""
                <div class="weather-card watch">
                    <strong>{title}</strong><br>
                    {detail}
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            """
            <div class="weather-card good">
                <strong>Good Travel Window</strong><br>
                No major wind, freeze, or heat flags in the 7-day forecast.
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_events(location: dict[str, Any]) -> None:
    st.subheader("Things Nearby")
    city = location.get("name", "")
    state = location.get("admin1", "")
    st.write(f"Quick searches for **{city}, {state}**.")
    links = event_search_links(city, state)
    cols = st.columns(len(links))
    for column, (label, url) in zip(cols, links.items()):
        column.link_button(label, url, use_container_width=True)

    st.divider()
    st.markdown("**Good RV-day ideas to check in each area**")
    st.write(
        "Visitor center, county fairgrounds, farmers market, local music calendar, national/state parks, "
        "RV supply stores, scenic drives, diners, and fuel stops with easy trailer access."
    )


def render_maintenance() -> None:
    st.subheader("RV Maintenance Log")
    with st.form("maintenance_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        item_date = col1.date_input("Date", value=date.today())
        category = col2.selectbox(
            "Category",
            ["Tires", "Generator", "Propane", "Batteries", "Truck", "Fifth wheel", "Repairs", "Other"],
        )
        odometer = st.number_input("Truck odometer", min_value=0, value=0, step=100)
        notes = st.text_area("Maintenance notes", height=130)
        submitted = st.form_submit_button("Save maintenance note", use_container_width=True)

    if submitted:
        if not notes:
            st.warning("Add notes before saving.")
        else:
            add_record(
                MAINTENANCE_FILE,
                {
                    "id": datetime.now().isoformat(),
                    "date": str(item_date),
                    "category": category,
                    "odometer": odometer,
                    "notes": notes,
                },
            )
            st.success("Maintenance note saved.")

    records = load_records(MAINTENANCE_FILE)
    if records:
        st.dataframe(pd.DataFrame(records), use_container_width=True, hide_index=True)
    else:
        st.info("No maintenance notes yet.")


def render_fun_stuff() -> None:
    journal = load_records(JOURNAL_FILE)
    stops = load_records(STOPS_FILE)
    roadside = load_records(ROADSIDE_FILE)

    st.subheader("Adventure Wheel")
    activities = [
        "Find a local diner",
        "Take a sunset photo",
        "Visit a scenic overlook",
        "Ask a local for one recommendation",
        "Find a farmers market",
        "Take the slow road",
        "Look for a quirky roadside stop",
        "Make it a rest day",
    ]
    seed = len(journal) + len(stops) + date.today().toordinal()
    st.markdown(
        f"""
        <div class="award-card">
            <div class="award-title">Today's Pick</div>
            <div class="award-detail">{activities[seed % len(activities)]}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("Roadside Finds")
    with st.form("roadside_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        name = col1.text_input("Find name")
        place = col2.text_input("Where was it?")
        category = st.selectbox("Type", ["Diner", "Scenic view", "Odd museum", "Cool sign", "Antique store", "Local shop", "Other"])
        notes = st.text_area("What made it memorable?", height=100)
        submitted = st.form_submit_button("Save roadside find", use_container_width=True)
    if submitted:
        if not name:
            st.warning("Add a name before saving the find.")
        else:
            add_record(
                ROADSIDE_FILE,
                {
                    "id": datetime.now().isoformat(),
                    "date": str(date.today()),
                    "name": name,
                    "place": place,
                    "category": category,
                    "notes": notes,
                },
            )
            st.success("Roadside find saved.")

    if roadside:
        for find in roadside:
            with st.container(border=True):
                st.markdown(f"**{find.get('name', 'Roadside find')}**")
                st.caption(f"{find.get('date', '')} - {find.get('place', '')} - {find.get('category', '')}")
                st.write(find.get("notes", ""))
    else:
        st.info("No roadside finds yet.")

    st.divider()
    render_badge_row(adventure_badges(journal, stops, roadside))
    render_postcard_generator(journal)


def render_recap() -> None:
    journal = load_records(JOURNAL_FILE)
    stops = load_records(STOPS_FILE)
    roadside = load_records(ROADSIDE_FILE)
    stats = trip_stats(journal, stops)
    states = visited_states(stops, journal)

    st.subheader("Season Recap")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("States", stats["states"])
    col2.metric("Nights", stats["nights"])
    col3.metric("Photos", stats["photos"])
    col4.metric("Campground Spend", f"${stats['cost']:,.0f}")

    render_trip_awards(journal, stops)
    render_state_sticker_board(states)
    render_photo_gallery(journal)

    recap_text = (
        "Bob's Adventures Season Recap\n\n"
        f"States started: {stats['states']}\n"
        f"Nights logged: {stats['nights']}\n"
        f"Photos saved: {stats['photos']}\n"
        f"Favorite memory: {stats['favorite']}\n"
        f"Longest stay: {stats['longest']}\n"
        f"Roadside finds: {len(roadside)}\n"
    )
    st.download_button(
        "Download recap",
        data=recap_text,
        file_name="bobs_adventures_recap.txt",
        mime="text/plain",
        use_container_width=True,
    )


def main() -> None:
    ensure_storage()
    page_header()
    location = sidebar_location()

    tabs = st.tabs(["Basecamp", "Journal", "Gallery", "Stops", "Weather", "Events", "Fun Stuff", "Recap", "Maintenance"])
    with tabs[0]:
        render_dashboard(location)
    with tabs[1]:
        render_journal()
    with tabs[2]:
        render_photo_gallery(load_records(JOURNAL_FILE))
    with tabs[3]:
        render_stops()
    with tabs[4]:
        render_weather(location)
    with tabs[5]:
        render_events(location)
    with tabs[6]:
        render_fun_stuff()
    with tabs[7]:
        render_recap()
    with tabs[8]:
        render_maintenance()


if __name__ == "__main__":
    main()
