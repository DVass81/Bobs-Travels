from __future__ import annotations

import json
import math
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import streamlit as st


APP_TITLE = "Dad's RV Travel Companion"
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


def ensure_storage() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    PHOTO_DIR.mkdir(exist_ok=True)
    for path in [JOURNAL_FILE, STOPS_FILE, MAINTENANCE_FILE]:
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


def page_header() -> None:
    st.set_page_config(page_title=APP_TITLE, page_icon=":blue_car:", layout="wide")
    st.title(APP_TITLE)
    st.caption("A private travel log for spring trips, winter returns to Arizona, photos, weather, stops, and RV notes.")


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

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Journal Entries", len(journal))
    col2.metric("Trip Stops", len(stops))
    col3.metric("Maintenance Notes", len(maintenance))
    col4.metric("Current Area", f"{location.get('name', 'Unknown')}, {location.get('admin1', '')}")

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

    st.subheader("Latest Notes")
    if journal:
        for entry in journal[:3]:
            with st.container(border=True):
                st.markdown(f"**{entry['title']}**")
                st.caption(f"{entry['entry_date']} - {entry['location']} - {entry['rating']}/5")
                st.write(entry["notes"])
    else:
        st.info("No journal entries yet. Add the first travel note from the Journal tab.")


def render_journal() -> None:
    st.subheader("Travel Journal")
    with st.form("journal_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        title = col1.text_input("Entry title")
        entry_date = col2.date_input("Date", value=date.today())
        location = st.text_input("Location")
        tags = st.multiselect(
            "Tags",
            ["campground", "family", "food", "scenic", "maintenance", "weather", "road conditions", "favorite"],
        )
        rating = st.slider("Would he come back?", 1, 5, 4)
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
            st.caption(f"{entry['location']} - Rating {entry['rating']}/5 - {', '.join(entry.get('tags', []))}")
            st.write(entry["notes"])
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
                    "notes": notes,
                    "latitude": latitude,
                    "longitude": longitude,
                },
            )
            st.success("Stop saved.")

    stops = load_records(STOPS_FILE)
    if stops:
        st.dataframe(
            pd.DataFrame(stops)[["arrival", "name", "city", "state", "status", "nights", "cost", "cell_signal"]],
            use_container_width=True,
            hide_index=True,
        )
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
            alerts.append(f"{row['Date']}: high wind could matter for towing.")
        if row["Low F"] <= 32:
            alerts.append(f"{row['Date']}: freezing temperatures possible.")
        if row["High F"] >= 95:
            alerts.append(f"{row['Date']}: extreme heat day.")
    if alerts:
        st.warning("\n".join(alerts))
    else:
        st.success("No major wind, freeze, or heat flags in the 7-day forecast.")


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


def main() -> None:
    ensure_storage()
    page_header()
    location = sidebar_location()

    tabs = st.tabs(["Dashboard", "Journal", "Stops", "Weather", "Events", "Maintenance"])
    with tabs[0]:
        render_dashboard(location)
    with tabs[1]:
        render_journal()
    with tabs[2]:
        render_stops()
    with tabs[3]:
        render_weather(location)
    with tabs[4]:
        render_events(location)
    with tabs[5]:
        render_maintenance()


if __name__ == "__main__":
    main()
