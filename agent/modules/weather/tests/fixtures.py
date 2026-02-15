"""Test fixtures and mock data for weather module tests."""

from __future__ import annotations

GEOCODING_RESPONSE = {
    "results": [
        {
            "name": "London",
            "latitude": 51.5074,
            "longitude": -0.1278,
            "country": "United Kingdom",
            "admin1": "England",
        }
    ]
}

GEOCODING_RESPONSE_EMPTY = {}

CURRENT_WEATHER_RESPONSE = {
    "current": {
        "time": "2026-02-15T12:00",
        "temperature_2m": 8.5,
        "relative_humidity_2m": 72,
        "apparent_temperature": 5.3,
        "weather_code": 3,
        "wind_speed_10m": 15.2,
        "wind_direction_10m": 230,
        "wind_gusts_10m": 28.0,
        "pressure_msl": 1013.2,
        "cloud_cover": 85,
        "uv_index": 1.5,
    }
}

FORECAST_RESPONSE = {
    "daily": {
        "time": ["2026-02-15", "2026-02-16", "2026-02-17"],
        "weather_code": [3, 61, 1],
        "temperature_2m_max": [10.2, 8.5, 11.0],
        "temperature_2m_min": [4.1, 3.2, 5.5],
        "apparent_temperature_max": [7.5, 5.8, 8.2],
        "apparent_temperature_min": [1.2, 0.5, 2.8],
        "precipitation_sum": [0.0, 5.2, 0.1],
        "precipitation_probability_max": [10, 85, 15],
        "wind_speed_10m_max": [20.5, 35.2, 15.0],
        "wind_gusts_10m_max": [35.0, 55.0, 25.0],
        "uv_index_max": [2.0, 1.5, 3.0],
        "sunrise": ["2026-02-15T07:15", "2026-02-16T07:13", "2026-02-17T07:11"],
        "sunset": ["2026-02-15T17:05", "2026-02-16T17:07", "2026-02-17T17:09"],
    }
}

HOURLY_RESPONSE = {
    "hourly": {
        "time": [
            "2026-02-15T00:00",
            "2026-02-15T01:00",
            "2026-02-15T02:00",
        ],
        "temperature_2m": [6.5, 6.2, 5.8],
        "relative_humidity_2m": [78, 80, 82],
        "apparent_temperature": [3.5, 3.1, 2.8],
        "weather_code": [2, 3, 3],
        "wind_speed_10m": [12.5, 13.0, 11.8],
        "wind_direction_10m": [220, 225, 230],
        "precipitation_probability": [5, 10, 15],
        "precipitation": [0.0, 0.0, 0.1],
        "visibility": [10000, 9500, 8000],
        "cloud_cover": [60, 75, 80],
        "uv_index": [0, 0, 0],
    }
}

ALERTS_RESPONSE = {
    "current": {
        "time": "2026-02-15T12:00",
        "temperature_2m": 8.5,
        "weather_code": 95,
        "wind_speed_10m": 45.0,
        "wind_gusts_10m": 95.0,
    },
    "hourly": {
        "time": [
            "2026-02-15T12:00",
            "2026-02-15T13:00",
        ],
        "temperature_2m": [8.5, 8.0],
        "weather_code": [95, 65],
        "wind_speed_10m": [45.0, 40.0],
        "wind_gusts_10m": [95.0, 80.0],
        "precipitation": [5.0, 10.0],
        "precipitation_probability": [90, 95],
        "visibility": [500, 800],
    },
    "daily": {
        "time": ["2026-02-15", "2026-02-16"],
        "weather_code": [95, 63],
        "temperature_2m_max": [10.0, 8.0],
        "temperature_2m_min": [5.0, 3.0],
        "precipitation_sum": [15.0, 8.0],
        "wind_speed_10m_max": [45.0, 30.0],
        "wind_gusts_10m_max": [95.0, 50.0],
        "uv_index_max": [2.0, 1.5],
    },
}

ALERTS_RESPONSE_CLEAR = {
    "current": {
        "time": "2026-02-15T12:00",
        "temperature_2m": 22.0,
        "weather_code": 0,
        "wind_speed_10m": 10.0,
        "wind_gusts_10m": 15.0,
    },
    "hourly": {
        "time": ["2026-02-15T12:00", "2026-02-15T13:00"],
        "temperature_2m": [22.0, 23.0],
        "weather_code": [0, 1],
        "wind_speed_10m": [10.0, 12.0],
        "wind_gusts_10m": [15.0, 18.0],
        "precipitation": [0.0, 0.0],
        "precipitation_probability": [0, 5],
        "visibility": [20000, 20000],
    },
    "daily": {
        "time": ["2026-02-15", "2026-02-16"],
        "weather_code": [0, 1],
        "temperature_2m_max": [25.0, 26.0],
        "temperature_2m_min": [15.0, 16.0],
        "precipitation_sum": [0.0, 0.0],
        "wind_speed_10m_max": [15.0, 12.0],
        "wind_gusts_10m_max": [25.0, 20.0],
        "uv_index_max": [5.0, 4.0],
    },
}
