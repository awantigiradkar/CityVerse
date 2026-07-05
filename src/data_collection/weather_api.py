import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional

class WeatherAPIClient:
    """
    Client for fetching weather data for Dubai using the free Open-Meteo API.
    Does not require an API key.
    """
    def __init__(self):
        # Coordinates for Dubai
        self.latitude = 25.2048
        self.longitude = 55.2708
        self.base_url = "https://api.open-meteo.com/v1/forecast"

    def _map_wmo_code_to_condition(self, code: int, wind_speed: float, humidity: float) -> str:
        """
        Maps WMO Weather Codes to descriptive weather strings.
        Also simulates 'Sandstorm' for high winds in low-humidity environments.
        """
        # Dubai specific: High wind + low humidity = Sandstorm
        if wind_speed > 35.0 and humidity < 35.0:
            return "Sandstorm"
            
        mapping = {
            0: "Sunny",
            1: "Mainly Sunny",
            2: "Partly Cloudy",
            3: "Cloudy",
            45: "Foggy",
            48: "Depositing Rime Fog",
            51: "Light Drizzle",
            53: "Moderate Drizzle",
            55: "Dense Drizzle",
            61: "Slight Rain",
            63: "Moderate Rain",
            65: "Heavy Rain",
            80: "Slight Rain Showers",
            81: "Moderate Rain Showers",
            82: "Violent Rain Showers",
            95: "Thunderstorm",
            96: "Thunderstorm with Slight Hail",
            99: "Thunderstorm with Heavy Hail"
        }
        return mapping.get(code, "Sunny")  # Default to Sunny

    def fetch_hourly_weather(self, days_back: int = 30) -> Optional[pd.DataFrame]:
        """
        Fetches hourly weather data for Dubai for the last N days.
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days_back)
        
        # Format dates for API query
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        
        params = {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "start_date": start_str,
            "end_date": end_str,
            "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation,weather_code",
            "timezone": "Asia/Dubai"
        }
        
        print(f"Requesting Dubai weather from {start_str} to {end_str}...")
        
        try:
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            hourly_data = data.get("hourly", {})
            if not hourly_data:
                print("No hourly data returned from Open-Meteo API.")
                return None
                
            # Parse into a Pandas DataFrame
            df = pd.DataFrame({
                "timestamp": pd.to_datetime(hourly_data["time"]),
                "temperature": hourly_data["temperature_2m"],
                "humidity": hourly_data["relative_humidity_2m"],
                "wind_speed": hourly_data["wind_speed_10m"],
                "precipitation": hourly_data["precipitation"],
                "weather_code": hourly_data["weather_code"]
            })
            
            # Map weather conditions
            df["condition"] = df.apply(
                lambda row: self._map_wmo_code_to_condition(
                    int(row["weather_code"]), row["wind_speed"], row["humidity"]
                ),
                axis=1
            )
            
            # Drop the raw weather code
            df = df.drop(columns=["weather_code"])
            print(f"Successfully fetched {len(df)} hourly weather records.")
            return df
            
        except Exception as e:
            print(f"Failed to fetch weather data: {e}")
            return None

if __name__ == "__main__":
    client = WeatherAPIClient()
    df = client.fetch_hourly_weather(days_back=3)
    if df is not None:
        print(df.head())