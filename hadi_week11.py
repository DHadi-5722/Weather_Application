"""
============================================
; Title: Assignment 11.1
; Author: Dawood Hadi
; Date: 19 November 2025
; Modified By: Dawood Hadi
; Description: For my final project I crafted an application that interacts with a webservice to fetch information
on the weather in any part of the United States, and translates the temperatures into Fahrenheit, Celsius, and Kelvin.
;===========================================
"""

from __future__ import annotations

from typing import Dict, Tuple
import sys

import requests
from requests.exceptions import HTTPError, Timeout, ConnectionError, RequestException
import os
from dotenv import load_dotenv

load_dotenv()
# -----------------------------
# Constants / Endpoints
# -----------------------------

GEO_DIRECT_URL = "https://api.openweathermap.org/geo/1.0/direct"
GEO_ZIP_URL = "https://api.openweathermap.org/geo/1.0/zip"
CURRENT_WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"

DEFAULT_COUNTRY = "US"
TIMEOUT_SECS = 12

ALLOWED_CITY_SEPARATORS = {" ", "-", "'", "."}


# -----------------------------
# Input / Validation Utilities
# -----------------------------

def prompt_yes_no(message: str) -> bool:
    """Prompt the user for a yes/no answer (case-insensitive)."""
    while True:
        ans = input(message).strip().lower()
        if ans in {"y", "yes"}:
            return True
        if ans in {"n", "no"}:
            return False
        print("Please enter Y/Yes or N/No.")


def prompt_menu_choice(prompt: str, options: Dict[str, str]) -> str:
    """Generic menu prompt that enforces valid choice keys.

    Parameters
    ----------
    prompt : str
        Prompt shown to the user.
    options : Dict[str, str]
        Map of option key -> description

    Returns
    -------
    str
        The chosen key from options.
    """
    keys = set(options.keys())
    while True:
        print(prompt)
        for key, desc in options.items():
            print(f"  {key}) {desc}")
        choice = input("Select an option: ").strip()
        if choice in keys:
            return choice
        print("Invalid selection. Please try again.\n")


def prompt_units() -> str:
    """Ask for units: imperial (F) default, metric (C), or optional Kelvin.

    Returns
    -------
    str
        One of {'imperial', 'metric', 'standard'} for OpenWeather API.
    """
    print("\nTemperature Units:")
    options = {
        "1": "Fahrenheit (imperial)",   # default
        "2": "Celsius (metric)",
        "3": "Kelvin (standard)"       # optional
    }
    choice = prompt_menu_choice("Choose units (default is 1):", options)
    if choice == "2":
        return "metric"
    if choice == "3":
        return "standard"
    return "imperial"  # default


def prompt_location_mode() -> str:
    """Ask whether to search by ZIP or City + State.

    Returns
    -------
    str
        'zip' or 'city'
    """
    print("\nLookup Mode:")
    options = {"1": "ZIP Code (US)", "2": "City + State (US)"}
    choice = prompt_menu_choice("How would you like to search?", options)
    return "zip" if choice == "1" else "city"


def prompt_zip_code() -> str:
    """Prompt for a US ZIP code (basic validation: 5 digits)."""
    while True:
        raw = input("Enter a 5-digit US ZIP code: ").strip()
        if raw.isdigit() and len(raw) == 5:
            return raw
        print("ZIP must be exactly 5 digits. Please try again.\n")


def prompt_city_state() -> Tuple[str, str]:
    """Prompt for city and 2-letter state (US)."""
    while True:
        city = input("Enter city name (e.g., Omaha): ").strip()
        if not city:
            print("City cannot be empty.\n")
            continue
        if city.isdigit():
            print("City cannot be numeric.\n")
            continue
        if not city[0].isalpha() or not city[-1].isalpha():
            print("City must start and end with a letter.\n")
            continue
        if any(char not in ALLOWED_CITY_SEPARATORS and not char.isalpha() for char in city):
            print("City contains invalid characters.\n")
            continue
        state = input("Enter 2-letter state code (e.g., NE): ").strip().upper()
        if len(state) == 2 and state.isalpha():
            return city, state
        if len(state) != 2:
            print("State code must be exactly 2 letters.\n")
            continue
        if state.isdigit():
            print("State code cannot be numeric.\n")
            continue
        print("State must be a 2-letter code (e.g., NE).\n")


# -----------------------------
# API Calls
# -----------------------------

def geocode_zip(zip_code: str, api_key: str) -> Dict[str, str]:
    """Geo lookup by ZIP -> returns dict with name, lat, lon, state, country.

    Parameters
    ----------
    zip_code : str
        US ZIP code (5 digits).
    api_key : str
        OpenWeather API key.

    Returns
    -------
    Dict[str, str]
        A mapping including keys: 'name', 'lat', 'lon', 'state', 'country'.
    """
    params = {"zip": f"{zip_code},{DEFAULT_COUNTRY}", "appid": api_key}
    resp = requests.get(GEO_ZIP_URL, params=params, timeout=12)
    resp.raise_for_status()
    data = resp.json()

    # Expected fields: name, lat, lon, country (and optionally state)
    if not all(k in data for k in ("name", "lat", "lon", "country")):
        raise ValueError("Unexpected ZIP geocode payload.")

    result = {
        "name": str(data.get("name", "")),
        "lat": float(data["lat"]),
        "lon": float(data["lon"]),
        "state": str(data.get("state", "")),
        "country": str(data.get("country", "")),
    }
    return result


def geocode_city_state(city: str, state: str, api_key: str) -> Dict[str, str]:
    """Geo lookup by City + State (US) -> returns first match dict.

    Parameters
    ----------
    city : str
        City name (e.g., Omaha).
    state : str
        2-letter state code (e.g., NE).
    api_key : str
        OpenWeather API key.

    Returns
    -------
    Dict[str, str]
        A mapping including keys: 'name', 'lat', 'lon', 'state', 'country'.
    """
    q = f"{city},{state},{DEFAULT_COUNTRY}"
    params = {"q": q, "limit": 1, "appid": api_key}
    resp = requests.get(GEO_DIRECT_URL, params=params, timeout=12)
    resp.raise_for_status()
    arr = resp.json()

    if not isinstance(arr, list) or not arr:
        raise ValueError("No results found for the provided city/state.")

    item = arr[0]
    if not all(k in item for k in ("name", "lat", "lon", "country")):
        raise ValueError("Unexpected city/state geocode payload.")

    result = {
        "name": str(item.get("name", "")),
        "lat": float(item["lat"]),
        "lon": float(item["lon"]),
        "state": str(item.get("state", state)),
        "country": str(item.get("country", "")),
    }
    return result


def fetch_current_weather(lat: float, lon: float, units: str, api_key: str) -> Dict:
    """Fetch current weather using lat/lon and OpenWeather 'units' parameter.

    Parameters
    ----------
    lat : float
    lon : float
    units : str
        One of {'imperial', 'metric', 'standard'}.
    api_key : str

    Returns
    -------
    Dict
        Parsed JSON dict from the weather endpoint.
    """
    params = {"lat": lat, "lon": lon, "units": units, "appid": api_key}
    resp = requests.get(CURRENT_WEATHER_URL, params=params, timeout=12)
    resp.raise_for_status()
    return resp.json()


# -----------------------------
# Presentation / Formatting
# -----------------------------

def unit_symbols(units: str):
    """Return (temp_symbol, speed_symbol) for chosen units."""
    if units == "metric":
        return "°C", "m/s"
    if units == "imperial":
        return "°F", "mph"
    return "K", "m/s"  # standard


def format_weather_report(location: Dict[str, str], weather: Dict, units: str) -> str:
    """Build a readable multi-line report string for the current weather."""
    temp_sym, speed_sym = unit_symbols(units)

    name = location.get("name", "")
    state = location.get("state", "")
    country = location.get("country", "")
    where = ", ".join([p for p in (name, state, country) if p])

    main = weather.get("main", {})
    wind = weather.get("wind", {})
    clouds = weather.get("clouds", {})
    weather_list = weather.get("weather", [])
    desc = (weather_list[0].get("description", "").title()
            if weather_list else "N/A")

    temp = main.get("temp", "N/A")
    t_min = main.get("temp_min", "N/A")
    t_max = main.get("temp_max", "N/A")
    pressure = main.get("pressure", "N/A")
    humidity = main.get("humidity", "N/A")
    cloud_pct = clouds.get("all", "N/A")
    wind_speed = wind.get("speed", "N/A")

    lines = [
        "",
        "=" * 70,
        f"Weather for: {where}",
        "-" * 70,
        f"Conditions : {desc}",
        f"Temperature: {temp} {temp_sym}",
        f"  High/Low : {t_max} {temp_sym} / {t_min} {temp_sym}",
        f"Humidity   : {humidity}%",
        f"Pressure   : {pressure} hPa",
        f"Clouds     : {cloud_pct}% coverage",
        f"Wind Speed : {wind_speed} {speed_sym}",
        "=" * 70,
        ""
    ]
    return "\n".join(lines)


# -----------------------------
# Main Orchestration
# -----------------------------

def main() -> None:
    """Program entry point."""
    print("Welcome to the OpenWeather Lookup!\n"
          "This tool lets you search U.S. weather by ZIP or City + State.\n"
          "We will geo-locate your input first, then fetch current conditions.\n")

    try:
        api_key = os.getenv("OPENWEATHER_API_KEY")
        if not api_key:
            raise RuntimeError("OPENWEATHER_API_KEY environment variable not set.")
    except RuntimeError as exc:
        print(f"Configuration error: {exc}")
        sys.exit(1)

    while True:
        units = prompt_units()  # 'imperial' (default), 'metric', or 'standard'
        mode = prompt_location_mode()  # 'zip' or 'city'

        try:
            if mode == "zip":
                zip_code = prompt_zip_code()
                loc = geocode_zip(zip_code, api_key)
            else:
                city, state = prompt_city_state()
                loc = geocode_city_state(city, state, api_key)

            weather = fetch_current_weather(loc["lat"], loc["lon"], units, api_key)
            report = format_weather_report(loc, weather, units)
            print(report)

        except Timeout:
            print("\nRequest timed out. Please check your connection and try again.\n")
        except HTTPError as exc:
            # Surface useful HTTP messages (e.g., 401 if key wrong; 404 for bad request)
            print(f"\nHTTP error: {exc}\n")
        except ConnectionError:
            print("\nNetwork connection error. Please verify internet access.\n")
        except ValueError as exc:
            print(f"\nData error: {exc}\n")
        except RequestException as exc:
            print(f"\nNetwork/Request error: {exc}\n")
        except Exception as exc:
            print(f"\nUnexpected error: {exc}\n")

        if not prompt_yes_no("Look up another location? (y/n): "):
            break

    print("\nThanks for using the OpenWeather Lookup. Goodbye!")


if __name__ == "__main__":
    main()
