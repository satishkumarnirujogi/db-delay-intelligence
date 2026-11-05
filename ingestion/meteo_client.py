"""One Open-Meteo call for all stations (free, no key). Credit: Weather data by Open-Meteo.com"""
import requests

HOURLY = "temperature_2m,precipitation,snowfall,wind_gusts_10m"


def fetch(stations: list[dict]) -> bytes:
    """Last 6 h (refreshes earlier forecasts with observations) + next 3 h (for scoring)."""
    resp = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": ",".join(str(s["lat"]) for s in stations),
            "longitude": ",".join(str(s["lon"]) for s in stations),
            "hourly": HOURLY,
            "past_hours": 6,
            "forecast_hours": 3,
            "timezone": "UTC",
            "wind_speed_unit": "kmh",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.content
