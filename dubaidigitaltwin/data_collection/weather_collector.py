"""
Fetches REAL historical weather data for Dubai using Open-Meteo API.

DATA SOURCE   : Open-Meteo (https://open-meteo.com/)
DATA IS REAL  : Genuine ERA5 reanalysis data for Dubai
API KEY       : Not required
LICENSE       : CC BY 4.0 — free to use with attribution
COST          : Free

What is ERA5?
    ERA5 is a global atmospheric dataset produced by the European Centre
    for Medium-Range Weather Forecasts (ECMWF). It combines weather model
    data with billions of real observations worldwide. It is the gold
    standard dataset used by climate scientists and meteorologists.

Dubai Climate Context (important for ML):
    - Desert climate (Köppen: BWh)
    - Summer (Jun–Sep): 38–45°C, extremely humid near coast, almost zero rain
    - Winter (Dec–Feb): 15–25°C, occasional light rain
    - UAE Weekend: Friday + Saturday (NOT Saturday + Sunday)
    - Timezone: Asia/Dubai (UTC+4), NO daylight saving time ever

Variables we collect:
    temperature_2m         → Air temp at 2m height (°C)
    relative_humidity_2m   → Humidity (%)
    precipitation          → Rainfall (mm)
    wind_speed_10m         → Wind speed (km/h)
    wind_direction_10m     → Wind direction (degrees 0–360)
    surface_pressure       → Atmospheric pressure (hPa)
    cloud_cover            → Total cloud cover (%)
    uv_index               → UV index (0–11+)
    apparent_temperature   → "Feels like" temperature (°C)
    dew_point_2m           → Dew point (°C) — key for humidity forecasting
"""

from datetime import date, timedelta
from typing import Optional

import httpx
import pandas as pd
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
)

from dubaidigitaltwin.config import settings
from dubaidigitaltwin.data_collection.base_collector import BaseCollector


class WeatherCollector(BaseCollector):
    """
    Collects real historical weather data for Dubai from Open-Meteo.

    Usage:
        # Collect 1 year of hourly weather data
        collector = WeatherCollector(days_back=365)
        df = collector.run()   # fetches → validates → saves → returns

    The DataFrame returned has one row per hour.
    """

    # ── Variables to request from the API ────────────────────────────────────
    # These are Open-Meteo's exact internal parameter names.
    # Adding or removing a name here changes what we download.
    HOURLY_VARIABLES = [
        "temperature_2m",
        "relative_humidity_2m",
        "precipitation",
        "wind_speed_10m",
        "wind_direction_10m",
        "surface_pressure",
        "cloud_cover",
        "uv_index",
        "apparent_temperature",
        "dew_point_2m",
    ]

    def __init__(self, days_back: int = 365):
        """
        Args:
            days_back : How many days of history to download.
                        365  = 1 year  (8,760 hourly rows)
                        1825 = 5 years (43,800 hourly rows) — good for ML
                        Default: 365
        """
        # Call the parent class constructor first
        # is_synthetic=False → this is REAL data
        super().__init__(name="weather", is_synthetic=False)

        self.days_back = days_back

        # ── Date range ────────────────────────────────────────────────────────
        # End = yesterday (today's data may be incomplete)
        # Start = days_back days before end
        self.end_date = date.today() - timedelta(days=1)
        self.start_date = self.end_date - timedelta(days=days_back)

        self.logger.info(
            f"Date range: {self.start_date} → {self.end_date} "
            f"({self.days_back} days)"
        )

    @retry(
        # Retry up to 3 times if the API call fails
        stop=stop_after_attempt(3),
        # Exponential backoff: wait 2s → 4s → 8s between retries
        # This is polite — don't hammer a struggling server
        wait=wait_exponential(multiplier=1, min=2, max=10),
    )
    def _call_api(self, url: str, params: dict) -> dict:
        """
        Make the HTTP GET request with automatic retry.

        We separate the API call from data parsing so that:
        - The @retry decorator only wraps the network call
        - Parsing errors (bugs in our code) don't get retried

        Args:
            url    : Full API endpoint URL
            params : Query parameters dict

        Returns:
            dict: Parsed JSON response from the API
        """
        self.logger.debug(f"Calling API: {url}")

        # httpx.get() makes an HTTP GET request
        # timeout=60 → give up after 60 seconds (don't hang forever)
        response = httpx.get(url, params=params, timeout=60)

        # raise_for_status() → if server returns 4xx or 5xx error,
        # raise an exception → triggers the @retry decorator
        response.raise_for_status()

        return response.json()

    def fetch(self) -> pd.DataFrame:
        """
        Download historical weather data from Open-Meteo API.

        API docs: https://open-meteo.com/en/docs/historical-weather-api

        Returns:
            pd.DataFrame: One row per hour.
            Columns: timestamp, temperature_2m, relative_humidity_2m,
                     precipitation, wind_speed_10m, wind_direction_10m,
                     surface_pressure, cloud_cover, uv_index,
                     apparent_temperature, dew_point_2m,
                     hour, day_of_week, month, year, is_weekend,
                     season, source, data_type, location,
                     latitude, longitude
        """
        self.logger.info(
            f"Fetching weather data from Open-Meteo: "
            f"{self.start_date} → {self.end_date}"
        )

        # ── Build API request ─────────────────────────────────────────────────
        # Open-Meteo historical archive endpoint
        url = f"{settings.openmeteo_archive_url}/archive"

        params = {
            "latitude": settings.dubai_lat,       # 25.2048
            "longitude": settings.dubai_lon,       # 55.2708
            "start_date": str(self.start_date),    # "2024-01-01"
            "end_date": str(self.end_date),         # "2024-12-31"
            # Join list into comma-separated string: "temperature_2m,humidity_2m,..."
            "hourly": ",".join(self.HOURLY_VARIABLES),
            "timezone": "Asia/Dubai",              # UTC+4, no daylight saving
            "wind_speed_unit": "kmh",
            "temperature_unit": "celsius",
            "precipitation_unit": "mm",
        }

        # ── Call the API ──────────────────────────────────────────────────────
        data = self._call_api(url, params)

        # ── Parse the response ────────────────────────────────────────────────
        # Open-Meteo returns this structure:
        # {
        #   "hourly": {
        #     "time": ["2024-01-01T00:00", "2024-01-01T01:00", ...],
        #     "temperature_2m": [18.5, 17.9, ...],
        #     "relative_humidity_2m": [65, 67, ...],
        #     ...
        #   }
        # }
        hourly_data = data.get("hourly", {})

        if not hourly_data:
            raise ValueError(
                "Open-Meteo returned empty data. "
                "Check the date range and coordinates."
            )

        # pd.DataFrame() turns the dict into a table.
        # Each key becomes a column, each list becomes column values.
        df = pd.DataFrame(hourly_data)

        # ── Rename 'time' → 'timestamp' ───────────────────────────────────────
        # We use 'timestamp' as our standard column name across ALL collectors.
        # This makes joins and merges predictable later.
        df = df.rename(columns={"time": "timestamp"})

        # ── Convert to datetime ───────────────────────────────────────────────
        # Raw API gives strings like "2024-01-01T00:00"
        # pd.to_datetime() converts to proper Python datetime objects
        df["timestamp"] = pd.to_datetime(df["timestamp"])

        # ── Add metadata columns ──────────────────────────────────────────────
        # These columns help us track where data came from
        df["source"] = "open-meteo-archive"
        df["data_type"] = "REAL"          # Not synthetic — very important flag
        df["location"] = "Dubai, UAE"
        df["latitude"] = settings.dubai_lat
        df["longitude"] = settings.dubai_lon

        # ── Add time-based features ───────────────────────────────────────────
        # Extract useful time components — ML models love these as features
        df["hour"] = df["timestamp"].dt.hour
        df["day_of_week"] = df["timestamp"].dt.dayofweek  # 0=Mon, 6=Sun
        df["month"] = df["timestamp"].dt.month
        df["year"] = df["timestamp"].dt.year
        df["day_of_year"] = df["timestamp"].dt.dayofyear

        # UAE weekend = Friday (4) + Saturday (5)
        # Not Western Sat+Sun — domain knowledge matters in data science!
        df["is_weekend"] = df["day_of_week"].isin([4, 5]).astype(int)

        # ── Dubai season flag ─────────────────────────────────────────────────
        # Dubai seasons are temperature-based, not calendar-based
        # Hot: May–Sep | Cool: Nov–Mar | Transitional: Apr, Oct
        season_map = {
            1: "cool", 2: "cool",  3: "cool",
            4: "transitional",
            5: "hot",  6: "hot",   7: "hot",  8: "hot",  9: "hot",
            10: "transitional",
            11: "cool", 12: "cool",
        }
        df["season"] = df["month"].map(season_map)

        # ── Heat index category ───────────────────────────────────────────────
        # Useful categorical feature for ML — how extreme is the heat?
        def heat_category(temp):
            if temp < 20:
                return "mild"
            elif temp < 30:
                return "warm"
            elif temp < 38:
                return "hot"
            else:
                return "extreme"

        df["heat_category"] = df["temperature_2m"].apply(heat_category)

        self.logger.info(
            f"Weather fetch complete: {len(df):,} hourly records | "
            f"Temp range: {df['temperature_2m'].min():.1f}°C "
            f"to {df['temperature_2m'].max():.1f}°C"
        )

        return df

    def fetch_forecast(self, days_ahead: int = 7) -> pd.DataFrame:
        """
        Fetch upcoming weather FORECAST (not historical).
        Used for real-time dashboard and scenario simulation.

        Args:
            days_ahead: Number of future days (max 16 on free tier)

        Returns:
            pd.DataFrame: Hourly forecast data
        """
        self.logger.info(f"Fetching {days_ahead}-day weather forecast...")

        url = f"{settings.openmeteo_base_url}/forecast"
        params = {
            "latitude": settings.dubai_lat,
            "longitude": settings.dubai_lon,
            "hourly": ",".join(self.HOURLY_VARIABLES),
            "forecast_days": min(days_ahead, 16),
            "timezone": "Asia/Dubai",
            "wind_speed_unit": "kmh",
            "temperature_unit": "celsius",
        }

        data = self._call_api(url, params)
        df = pd.DataFrame(data["hourly"])
        df = df.rename(columns={"time": "timestamp"})
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["source"] = "open-meteo-forecast"
        df["data_type"] = "REAL_FORECAST"
        df["location"] = "Dubai, UAE"
        df["latitude"] = settings.dubai_lat
        df["longitude"] = settings.dubai_lon
        df["hour"] = df["timestamp"].dt.hour
        df["month"] = df["timestamp"].dt.month
        df["day_of_week"] = df["timestamp"].dt.dayofweek
        df["is_weekend"] = df["day_of_week"].isin([4, 5]).astype(int)

        self.save(df, filename=f"weather_forecast_{days_ahead}day.csv")
        self.logger.success(f"Forecast saved: {len(df)} rows")
        return df