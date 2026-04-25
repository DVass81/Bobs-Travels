from __future__ import annotations

import json
import math
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components


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
CHECKLIST_FILE = DATA_DIR / "departure_checklists.json"
FAVORITES_FILE = DATA_DIR / "favorite_places.json"
RESERVATIONS_FILE = DATA_DIR / "reservations.json"

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

DEPARTURE_ITEMS = [
    "Slides in",
    "Jacks up",
    "Hitch locked",
    "Breakaway cable connected",
    "Safety chains connected",
    "Water disconnected",
    "Sewer disconnected",
    "Power disconnected",
    "Propane checked",
    "Tire pressure checked",
    "Cabinets and fridge secured",
    "Steps up",
    "Lights tested",
    "Site walked for forgotten items",
]

THEME_PRESETS = {
    "Coastal Drive": {
        "sunshine": "#FFE66D",
        "coral": "#FF6B6B",
        "teal": "#00B4D8",
        "deep": "#006D77",
        "sky": "#90E0EF",
        "mint": "#CAF0F8",
        "cream": "#FFF7E6",
        "background": "linear-gradient(180deg, #dff8ff 0%, #fff7e6 54%, #ffffff 100%)",
    },
    "Desert Sunset": {
        "sunshine": "#FFD166",
        "coral": "#EF476F",
        "teal": "#06D6A0",
        "deep": "#26547C",
        "sky": "#8ECAE6",
        "mint": "#E9FFF7",
        "cream": "#FFF2CC",
        "background": "linear-gradient(180deg, #fff0c9 0%, #ffe2d1 48%, #fffdf7 100%)",
    },
    "Mountain Morning": {
        "sunshine": "#F9C74F",
        "coral": "#F9844A",
        "teal": "#43AA8B",
        "deep": "#277DA1",
        "sky": "#A9DEF9",
        "mint": "#E0FBFC",
        "cream": "#FAF3DD",
        "background": "linear-gradient(180deg, #dff5ff 0%, #e9fff7 52%, #fffdf7 100%)",
    },
    "Campfire Night": {
        "sunshine": "#F9C74F",
        "coral": "#F3722C",
        "teal": "#4D908E",
        "deep": "#1D3557",
        "sky": "#457B9D",
        "mint": "#F1FAEE",
        "cream": "#FFF3B0",
        "background": "linear-gradient(180deg, #d8ecff 0%, #fff3b0 58%, #fffdf7 100%)",
    },
}


def ensure_storage() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    PHOTO_DIR.mkdir(exist_ok=True)
    for path in [
        JOURNAL_FILE,
        STOPS_FILE,
        MAINTENANCE_FILE,
        ROADSIDE_FILE,
        CHECKLIST_FILE,
        FAVORITES_FILE,
        RESERVATIONS_FILE,
    ]:
        if not path.exists():
            path.write_text("[]", encoding="utf-8")


def record_type_for_path(path: Path) -> str:
    return path.stem


def get_supabase_client() -> Any | None:
    try:
        url = st.secrets.get("SUPABASE_URL")
        key = st.secrets.get("SUPABASE_ANON_KEY")
    except Exception:
        return None
    if not url or not key:
        return None
    try:
        from supabase import create_client
    except ImportError:
        return None
    return create_client(url, key)


def load_cloud_records(path: Path) -> list[dict[str, Any]] | None:
    client = get_supabase_client()
    if client is None:
        return None
    try:
        response = (
            client.table("app_records")
            .select("payload")
            .eq("record_type", record_type_for_path(path))
            .execute()
        )
        if not response.data:
            return []
        payload = response.data[0].get("payload", [])
        return payload if isinstance(payload, list) else []
    except Exception:
        return None


def save_cloud_records(path: Path, records: list[dict[str, Any]]) -> bool:
    client = get_supabase_client()
    if client is None:
        return False
    try:
        client.table("app_records").upsert(
            {
                "record_type": record_type_for_path(path),
                "payload": records,
                "updated_at": datetime.now().isoformat(),
            },
            on_conflict="record_type",
        ).execute()
        return True
    except Exception:
        return False


def load_records(path: Path) -> list[dict[str, Any]]:
    ensure_storage()
    cloud_records = load_cloud_records(path)
    if cloud_records is not None:
        return cloud_records
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def save_records(path: Path, records: list[dict[str, Any]]) -> None:
    ensure_storage()
    if save_cloud_records(path, records):
        return
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


def radar_links(latitude: float, longitude: float) -> dict[str, str]:
    return {
        "NWS Radar": "https://radar.weather.gov/",
        "NWS Forecast": f"https://forecast.weather.gov/MapClick.php?lat={latitude:.4f}&lon={longitude:.4f}",
        "Weather Map": f"https://www.google.com/maps/search/weather/@{latitude:.4f},{longitude:.4f},10z",
    }


def food_search_links(city: str, state: str) -> dict[str, str]:
    location = f"{city}, {state}".strip(", ")
    query = location.replace(" ", "+")
    return {
        "Diners": f"https://www.google.com/search?q=best+diners+near+{query}",
        "Breakfast": f"https://www.google.com/search?q=best+breakfast+near+{query}",
        "BBQ": f"https://www.google.com/search?q=best+bbq+near+{query}",
        "Coffee": f"https://www.google.com/search?q=coffee+near+{query}",
        "Ice Cream": f"https://www.google.com/search?q=ice+cream+near+{query}",
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
    card_html = f"""
    <div class="postcard-card">
        <div class="postcard-stamp">{entry.get('entry_date', '')}</div>
        <h4>{entry.get('title', 'Untitled adventure')}</h4>
        <strong>{entry.get('location', 'Somewhere on the road')}</strong><br>
        <small>{tags} - Rating {entry.get('rating', 0)}/5</small>
        <p>{entry.get('notes', '')}</p>
        <p><strong>{prompt}:</strong> {memory}</p>
    </div>
    """
    photos = [photo for photo in entry.get("photos", []) if Path(photo).exists()]
    if photos:
        image_col, text_col = st.columns([0.42, 1])
        image_col.image(photos[0], use_column_width=True)
        text_col.markdown(card_html, unsafe_allow_html=True)
    else:
        st.markdown(card_html, unsafe_allow_html=True)


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
    selected_theme = st.sidebar.selectbox("Visual theme", list(THEME_PRESETS), index=0)
    st.markdown(
        """
        <style>
        :root {
            --sunshine: #ffcf4a;
            --coral: #ff6f61;
            --teal: #00a6a6;
            --deep-teal: #087f8c;
            --sky: #43b5e8;
            --mint: #d9fff5;
            --cream: #fff7df;
            --ink: #22313f;
        }

        .stApp {
            background:
                radial-gradient(circle at 12% 8%, rgba(255, 207, 74, 0.42), transparent 24%),
                radial-gradient(circle at 88% 12%, rgba(67, 181, 232, 0.34), transparent 26%),
                linear-gradient(180deg, #e8fbff 0%, #fff7df 48%, #fffdf7 100%);
            color: var(--ink);
        }

        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #d9fff5 0%, #fff7df 100%);
            border-right: 1px solid rgba(0, 166, 166, 0.28);
        }

        h1 {
            color: var(--deep-teal);
            font-weight: 800;
        }

        h2, h3 {
            color: #22545d;
        }

        div[data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.88);
            border: 1px solid rgba(0, 166, 166, 0.18);
            border-radius: 8px;
            padding: 0.85rem;
            box-shadow: 0 8px 22px rgba(34, 49, 63, 0.08);
        }

        .stButton > button,
        .stDownloadButton > button,
        a[data-testid="stLinkButton"] {
            border-radius: 8px;
            border-color: rgba(8, 127, 140, 0.42);
            background: #ffffff;
            color: var(--deep-teal);
            font-weight: 650;
        }

        .stButton > button:hover,
        a[data-testid="stLinkButton"]:hover {
            border-color: var(--coral);
            color: var(--coral);
        }

        [data-testid="stCaptionContainer"] {
            color: #6a5c4c;
        }

        .adventure-hero {
            background:
                linear-gradient(180deg, rgba(255,255,255,0.16), rgba(255,255,255,0.02)),
                linear-gradient(135deg, rgba(255, 111, 97, 0.96), rgba(255, 207, 74, 0.94) 48%, rgba(0, 166, 166, 0.94)),
                linear-gradient(90deg, #ff6f61, #ffcf4a);
            padding: 1.3rem 1.4rem;
            border-radius: 8px;
            margin-bottom: 1.1rem;
            color: white;
            box-shadow: 0 14px 34px rgba(34, 49, 63, 0.18);
            position: relative;
            overflow: hidden;
        }

        .adventure-hero:after {
            content: "";
            position: absolute;
            left: -6%;
            right: -6%;
            bottom: -3.8rem;
            height: 7rem;
            background:
                linear-gradient(90deg, transparent 0 48%, rgba(255,255,255,0.8) 48% 52%, transparent 52% 100%),
                #22313f;
            transform: rotate(-2deg);
            opacity: 0.18;
        }

        .adventure-hero-inner {
            position: relative;
            z-index: 2;
            display: grid;
            grid-template-columns: minmax(0, 1fr) auto;
            gap: 1rem;
            align-items: center;
        }

        .brand-badge {
            width: 108px;
            height: 108px;
            border-radius: 50%;
            background:
                radial-gradient(circle at 50% 34%, var(--sunshine) 0 27%, transparent 28%),
                linear-gradient(180deg, rgba(255,255,255,0.24), rgba(255,255,255,0.08));
            border: 3px solid rgba(255,255,255,0.78);
            display: grid;
            place-items: center;
            box-shadow: 0 10px 24px rgba(34,49,63,0.22);
        }

        .brand-badge span {
            background: rgba(34, 49, 63, 0.9);
            color: white;
            border-radius: 8px;
            padding: 0.28rem 0.46rem;
            font-size: 1.7rem;
            font-weight: 900;
            letter-spacing: 0;
        }

        .adventure-kicker {
            font-weight: 800;
            letter-spacing: 0;
            text-transform: uppercase;
            font-size: 0.86rem;
            opacity: 0.92;
        }

        .adventure-name {
            font-size: 3rem;
            line-height: 1;
            font-weight: 900;
            margin: 0.2rem 0 0.45rem 0;
            color: white;
        }

        .adventure-route {
            font-size: 1.02rem;
            max-width: 760px;
            font-weight: 650;
        }

        .adventure-chips {
            display: flex;
            flex-wrap: wrap;
            gap: 0.5rem;
            margin-top: 0.9rem;
        }

        .adventure-chip {
            background: rgba(255, 255, 255, 0.24);
            border: 1px solid rgba(255, 255, 255, 0.42);
            border-radius: 999px;
            padding: 0.28rem 0.62rem;
            font-weight: 800;
            color: white;
        }

        @media (max-width: 720px) {
            .adventure-hero-inner {
                grid-template-columns: 1fr;
            }

            .brand-badge {
                width: 84px;
                height: 84px;
            }

            .adventure-name {
                font-size: 2.2rem;
            }
        }

        .badge-card,
        .postcard-card,
        .timeline-item,
        .weather-card,
        .award-card {
            background: rgba(255, 255, 255, 0.9);
            border: 1px solid rgba(0, 166, 166, 0.18);
            border-radius: 8px;
            padding: 0.85rem;
            margin-bottom: 0.75rem;
            box-shadow: 0 8px 22px rgba(34, 49, 63, 0.08);
        }

        .badge-title,
        .timeline-title,
        .award-title {
            color: var(--deep-teal);
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
            border: 2px solid rgba(255, 111, 97, 0.34);
            background:
                linear-gradient(135deg, rgba(255,255,255,0.98), rgba(217,255,245,0.86));
        }

        .postcard-stamp {
            float: right;
            border: 2px dashed rgba(255, 111, 97, 0.72);
            color: var(--coral);
            padding: 0.35rem 0.5rem;
            border-radius: 6px;
            font-weight: 800;
            font-size: 0.8rem;
        }

        .state-sticker {
            text-align: center;
            border: 2px dashed rgba(8, 127, 140, 0.32);
            border-radius: 8px;
            padding: 0.45rem 0.1rem;
            margin-bottom: 0.35rem;
            color: #8b7b68;
            background: rgba(255, 255, 255, 0.58);
            font-weight: 700;
            box-shadow: 0 4px 10px rgba(34,49,63,0.06);
            transform: rotate(-1deg);
        }

        .state-sticker.earned {
            background: linear-gradient(135deg, var(--coral), var(--sunshine));
            color: #ffffff;
            border-color: transparent;
            box-shadow: 0 5px 12px rgba(255, 111, 97, 0.24);
            text-shadow: 0 1px 1px rgba(34,49,63,0.18);
        }

        .stColumn:nth-child(even) .state-sticker {
            transform: rotate(1deg);
        }

        .weather-card.watch {
            border-left: 6px solid var(--sunshine);
        }

        .weather-card.good {
            border-left: 6px solid var(--teal);
        }

        .quick-actions button {
            min-height: 3rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    theme = THEME_PRESETS[selected_theme]
    st.markdown(
        f"""
        <style>
        :root {{
            --sunshine: {theme["sunshine"]};
            --coral: {theme["coral"]};
            --teal: {theme["teal"]};
            --deep-teal: {theme["deep"]};
            --sky: {theme["sky"]};
            --mint: {theme["mint"]};
            --cream: {theme["cream"]};
        }}

        .stApp {{
            background:
                radial-gradient(circle at 12% 8%, {theme["sunshine"]}66, transparent 24%),
                radial-gradient(circle at 88% 12%, {theme["sky"]}66, transparent 26%),
                {theme["background"]};
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        <div class="adventure-hero">
            <div class="adventure-hero-inner">
                <div>
                    <div class="adventure-kicker">Welcome to the open-road logbook</div>
                    <div class="adventure-name">Bob's Adventures</div>
                    <div class="adventure-route">
                        Road notes, photos, weather, favorite stops, and all the little moments worth remembering from the fifth wheel.
                    </div>
                    <div class="adventure-chips">
                        <span class="adventure-chip">Arizona Basecamp</span>
                        <span class="adventure-chip">Spring Routes</span>
                        <span class="adventure-chip">Photo Memories</span>
                        <span class="adventure-chip">Campground Finds</span>
                    </div>
                </div>
                <div class="brand-badge"><span>BA</span></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def sidebar_location() -> dict[str, Any]:
    st.sidebar.header("Current Stop")
    city = st.sidebar.text_input("City", value="Quartzsite")
    state = st.sidebar.text_input("State", value="AZ")
    with st.sidebar.expander("Use precise location"):
        components.html(
            """
            <button style="width:100%;padding:10px;border-radius:8px;border:1px solid #087f8c;background:#ffffff;color:#087f8c;font-weight:700;cursor:pointer;"
                onclick="
                    navigator.geolocation.getCurrentPosition(
                        function(pos) {
                            const url = new URL(window.parent.location.href);
                            url.searchParams.set('gps_lat', pos.coords.latitude.toFixed(5));
                            url.searchParams.set('gps_lon', pos.coords.longitude.toFixed(5));
                            window.parent.location.href = url.toString();
                        },
                        function() { alert('Location was blocked or unavailable. You can type coordinates below.'); }
                    );
                ">
                Use my device location
            </button>
            """,
            height=48,
        )
        manual_lat = st.number_input("Latitude", value=0.0, format="%.5f")
        manual_lon = st.number_input("Longitude", value=0.0, format="%.5f")
        use_manual = st.button("Use typed coordinates", use_container_width=True)
        st.caption("GPS works best on a phone or laptop browser that allows location access.")
    location_query = f"{city}, {state}"

    if st.sidebar.button("Update weather location", use_container_width=True):
        st.session_state["location_query"] = location_query

    gps_lat = st.query_params.get("gps_lat")
    gps_lon = st.query_params.get("gps_lon")
    if gps_lat and gps_lon:
        location = {
            "name": "Device Location",
            "admin1": "GPS",
            "latitude": float(gps_lat),
            "longitude": float(gps_lon),
        }
    elif use_manual and manual_lat and manual_lon:
        location = {
            "name": "Typed Coordinates",
            "admin1": "GPS",
            "latitude": float(manual_lat),
            "longitude": float(manual_lon),
        }
    else:
        location = None

    query = st.session_state.get("location_query", location_query)
    if location is None:
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
    reservations = load_records(RESERVATIONS_FILE)
    checklists = load_records(CHECKLIST_FILE)
    stats = trip_stats(journal, stops)

    st.markdown("### Trip Command Center")
    planned_stops = [stop for stop in stops if stop.get("status") == "Planned"]
    next_reservation = sorted(reservations, key=lambda item: item.get("check_in", "9999-99-99"))[0] if reservations else {}
    latest_checklist = checklists[0] if checklists else {}
    try:
        weather = get_weather(float(location["latitude"]), float(location["longitude"]))
        current = weather["current"]
        weather_summary = f"{current['temperature_2m']:.0f} F, {weather_label(int(current['weather_code']))}"
    except requests.RequestException:
        weather_summary = "Weather offline"
    command_cols = st.columns(4)
    command_cols[0].metric("Current Stop", location.get("name", "Current area"))
    command_cols[1].metric("Today's Weather", weather_summary)
    command_cols[2].metric("Next Stop", planned_stops[0].get("name", "Add a planned stop") if planned_stops else "Add a planned stop")
    command_cols[3].metric("Next Reservation", next_reservation.get("campground", "None saved"))
    if latest_checklist:
        done = len(latest_checklist.get("completed", []))
        total = latest_checklist.get("total_items", len(DEPARTURE_ITEMS))
        st.progress(done / total if total else 0)
        st.caption(f"Latest departure checklist: {done}/{total} complete")

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

    st.subheader("Route Board")
    visited_stops = [stop for stop in stops if stop.get("status") == "Visited"]
    current_stops = [stop for stop in stops if stop.get("status") == "Current"]
    route1, route2, route3, route4 = st.columns(4)
    route1.metric("Current Pin", current_stops[0].get("name", location.get("name", "Current stop")) if current_stops else location.get("name", "Current stop"))
    route2.metric("Next Planned", planned_stops[0].get("name", "Add a planned stop") if planned_stops else "Add a planned stop")
    route3.metric("Visited Stops", len(visited_stops))
    route4.metric("Favorite Memory", stats["favorite"])

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
    st.caption("Home base, current area, and saved stops appear together so Bob can see where the route is filling in.")

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
    lat = float(location["latitude"])
    lon = float(location["longitude"])
    st.caption(f"Forecast location: {location.get('name', 'Selected location')} ({lat:.4f}, {lon:.4f})")
    radar_cols = st.columns(3)
    for column, (label, url) in zip(radar_cols, radar_links(lat, lon).items()):
        column.link_button(label, url, use_container_width=True)

    try:
        weather = get_weather(lat, lon)
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
    st.subheader("Local Food Finder")
    food_links = food_search_links(city, state)
    food_cols = st.columns(len(food_links))
    for column, (label, url) in zip(food_cols, food_links.items()):
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


def render_departure_checklist() -> None:
    st.subheader("Departure Checklist")
    st.caption("A quick leave-the-site check before Bob pulls out.")
    checklist_name = st.text_input("Checklist name", value=f"Departure - {date.today()}")
    completed = []
    for index, item in enumerate(DEPARTURE_ITEMS):
        if st.checkbox(item, key=f"departure_{index}"):
            completed.append(item)

    progress = len(completed) / len(DEPARTURE_ITEMS)
    st.progress(progress)
    st.caption(f"{len(completed)} of {len(DEPARTURE_ITEMS)} checked")

    if st.button("Save checklist", use_container_width=True):
        add_record(
            CHECKLIST_FILE,
            {
                "id": datetime.now().isoformat(),
                "date": str(date.today()),
                "name": checklist_name,
                "completed": completed,
                "total_items": len(DEPARTURE_ITEMS),
            },
        )
        st.success("Departure checklist saved.")

    saved = load_records(CHECKLIST_FILE)
    if saved:
        st.subheader("Saved Checklists")
        for item in saved[:5]:
            count = len(item.get("completed", []))
            total = item.get("total_items", len(DEPARTURE_ITEMS))
            with st.container(border=True):
                st.markdown(f"**{item.get('name', 'Departure checklist')}**")
                st.caption(f"{item.get('date', '')} - {count}/{total} complete")


def render_favorites() -> None:
    st.subheader("Favorite Places")
    with st.form("favorite_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        name = col1.text_input("Place name")
        city = col2.text_input("City")
        state = col3.text_input("State")
        category = st.selectbox(
            "Category",
            ["Campground", "Restaurant", "Scenic view", "Small town", "Attraction", "RV store", "Fuel stop", "Other"],
        )
        rating = st.slider("Favorite score", 1, 5, 5)
        notes = st.text_area("Why it is a favorite", height=120)
        submitted = st.form_submit_button("Save favorite", use_container_width=True)

    if submitted:
        if not name:
            st.warning("Add a place name before saving.")
        else:
            add_record(
                FAVORITES_FILE,
                {
                    "id": datetime.now().isoformat(),
                    "date": str(date.today()),
                    "name": name,
                    "city": city,
                    "state": state.upper(),
                    "category": category,
                    "rating": rating,
                    "notes": notes,
                },
            )
            st.success("Favorite saved.")

    favorites = load_records(FAVORITES_FILE)
    if favorites:
        category_filter = st.selectbox("Show category", ["All"] + sorted({favorite.get("category", "Other") for favorite in favorites}))
        shown = favorites if category_filter == "All" else [favorite for favorite in favorites if favorite.get("category") == category_filter]
        for index in range(0, len(shown), 3):
            cols = st.columns(3)
            for column, favorite in zip(cols, shown[index : index + 3]):
                column.markdown(
                    f"""
                    <div class="award-card">
                        <div class="award-title">{favorite.get('name', 'Favorite place')}</div>
                        <div class="award-detail">
                            {favorite.get('category', '')} - {favorite.get('city', '')}, {favorite.get('state', '')}<br>
                            Score: {favorite.get('rating', 0)}/5<br>
                            {favorite.get('notes', '')}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
    else:
        st.info("Favorites will show here once Bob saves places worth revisiting.")


def render_cloud_storage_status() -> None:
    st.subheader("Cloud Storage")
    client = get_supabase_client()
    if client is None:
        st.info(
            "Cloud storage is ready in the code but not connected yet. Add SUPABASE_URL and "
            "SUPABASE_ANON_KEY in Streamlit secrets, then create an app_records table."
        )
        st.code(
            """
create table app_records (
  record_type text primary key,
  payload jsonb not null default '[]'::jsonb,
  updated_at timestamp with time zone default now()
);
            """.strip(),
            language="sql",
        )
    else:
        st.success("Supabase credentials found. App records will use cloud storage with local fallback.")


def render_reservations() -> None:
    st.subheader("Reservation Tracker")
    with st.form("reservation_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        campground = col1.text_input("Campground")
        site = col2.text_input("Site number")
        confirmation = col3.text_input("Confirmation number")
        col4, col5, col6 = st.columns(3)
        check_in = col4.date_input("Check-in", value=date.today())
        check_out = col5.date_input("Check-out", value=date.today())
        balance_due = col6.number_input("Balance due", min_value=0.0, value=0.0, step=10.0)
        phone = st.text_input("Campground phone")
        notes = st.text_area("Reservation notes", height=110)
        submitted = st.form_submit_button("Save reservation", use_container_width=True)

    if submitted:
        if not campground:
            st.warning("Add the campground name before saving.")
        else:
            add_record(
                RESERVATIONS_FILE,
                {
                    "id": datetime.now().isoformat(),
                    "campground": campground,
                    "site": site,
                    "confirmation": confirmation,
                    "check_in": str(check_in),
                    "check_out": str(check_out),
                    "balance_due": balance_due,
                    "phone": phone,
                    "notes": notes,
                },
            )
            st.success("Reservation saved.")

    reservations = sorted(load_records(RESERVATIONS_FILE), key=lambda item: item.get("check_in", "9999-99-99"))
    if reservations:
        st.dataframe(
            pd.DataFrame(reservations)[
                ["check_in", "check_out", "campground", "site", "confirmation", "balance_due", "phone"]
            ],
            use_container_width=True,
            hide_index=True,
        )
        for reservation in reservations[:4]:
            with st.container(border=True):
                st.markdown(f"**{reservation.get('campground', 'Campground')}**")
                st.caption(
                    f"{reservation.get('check_in', '')} to {reservation.get('check_out', '')} - "
                    f"Site {reservation.get('site', '')} - Confirmation {reservation.get('confirmation', '')}"
                )
                st.write(reservation.get("notes", ""))
    else:
        st.info("No reservations saved yet.")


def render_family_view(location: dict[str, Any]) -> None:
    st.subheader("Family View")
    st.caption("A simple read-only snapshot for family to see where Bob is and what he has been enjoying.")
    journal = load_records(JOURNAL_FILE)
    stops = load_records(STOPS_FILE)
    favorites = load_records(FAVORITES_FILE)
    stats = trip_stats(journal, stops)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Current Area", f"{location.get('name', 'Unknown')}, {location.get('admin1', '')}")
    col2.metric("States", stats["states"])
    col3.metric("Stops", len(stops))
    col4.metric("Photos", stats["photos"])

    latest_photos = all_photo_records(journal)[:6]
    if latest_photos:
        st.subheader("Latest Photos")
        for index in range(0, len(latest_photos), 3):
            cols = st.columns(3)
            for column, photo in zip(cols, latest_photos[index : index + 3]):
                column.image(photo["path"], use_column_width=True)
                column.caption(f"{photo['location']} - {photo['date']}")

    st.subheader("Latest Notes")
    if journal:
        for entry in journal[:3]:
            render_postcard_card(entry)
    else:
        st.info("No journal notes yet.")

    st.subheader("Favorite Places")
    if favorites:
        for favorite in favorites[:5]:
            st.markdown(f"**{favorite.get('name', 'Favorite')}** - {favorite.get('city', '')}, {favorite.get('state', '')}")
            st.caption(f"{favorite.get('category', '')} - {favorite.get('rating', 0)}/5")
    else:
        st.info("No favorite places saved yet.")


def main() -> None:
    ensure_storage()
    page_header()
    location = sidebar_location()

    tabs = st.tabs(
        [
            "Basecamp",
            "Journal",
            "Gallery",
            "Stops",
            "Weather",
            "Events",
            "Prep",
            "Reservations",
            "Favorites",
            "Family View",
            "Fun Stuff",
            "Recap",
            "Maintenance",
            "Storage",
        ]
    )
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
        render_departure_checklist()
    with tabs[7]:
        render_reservations()
    with tabs[8]:
        render_favorites()
    with tabs[9]:
        render_family_view(location)
    with tabs[10]:
        render_fun_stuff()
    with tabs[11]:
        render_recap()
    with tabs[12]:
        render_maintenance()
    with tabs[13]:
        render_cloud_storage_status()


if __name__ == "__main__":
    main()
