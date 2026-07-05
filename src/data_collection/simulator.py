import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any

class CityDataSimulator:
    """
    High-fidelity mathematical simulator for Dubai Cityverse digital twin.
    Generates realistic, correlated indicators for multiple city domains.
    """
    def __init__(self, locations: List[Dict[str, Any]]):
        self.locations = locations

    def simulate_hour(self, timestamp: datetime, location: Dict[str, Any], weather: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simulates interconnected indicators for a single hour, location, and weather condition.
        """
        hour = timestamp.hour
        weekday = timestamp.weekday()  # Monday=0, Sunday=6
        month = timestamp.month
        
        # 1. Determine if it's a weekday or weekend (UAE weekend: Saturday/Sunday)
        is_weekend = weekday in [5, 6]
        
        # 2. Extract weather features
        temp = weather["temperature"]
        wind = weather["wind_speed"]
        rain = weather["precipitation"]
        
        # 3. Location-specific scale modifiers
        loc_name = location["name"]
        loc_scale = {
            "Downtown Dubai": {"traffic": 1.4, "tourists": 1.5, "energy": 1.3, "transport": 1.4},
            "Dubai Marina": {"traffic": 1.3, "tourists": 1.4, "energy": 1.2, "transport": 1.3},
            "Deira": {"traffic": 1.2, "tourists": 0.8, "energy": 0.9, "transport": 1.1},
            "Palm Jumeirah": {"traffic": 0.9, "tourists": 1.6, "energy": 1.4, "transport": 0.7},
            "Jumeirah": {"traffic": 0.7, "tourists": 1.0, "energy": 0.8, "transport": 0.6},
            "Business Bay": {"traffic": 1.5, "tourists": 0.6, "energy": 1.2, "transport": 1.2},
            "Al Barsha": {"traffic": 1.1, "tourists": 1.0, "energy": 1.0, "transport": 1.0},
            "Dubai International Airport (DXB)": {"traffic": 1.6, "tourists": 1.8, "energy": 2.5, "transport": 1.8}
        }.get(loc_name, {"traffic": 1.0, "tourists": 1.0, "energy": 1.0, "transport": 1.0})

        # --- DOMAIN SIMULATIONS ---
        
        # 1. Traffic Congestion (0.0 to 10.0 scale)
        if not is_weekend:
            # Weekday rush hour peaks (8-10 AM, 5-7 PM)
            time_factor = 2.0 + 4.5 * np.exp(-((hour - 8.5) / 1.2) ** 2) + 5.0 * np.exp(-((hour - 18.0) / 1.5) ** 2)
        else:
            # Weekend mid-day activity peak
            time_factor = 2.5 + 3.0 * np.exp(-((hour - 15.0) / 3.0) ** 2)
            
        # Night drop-off
        if hour < 5:
            time_factor *= 0.3
            
        # Traffic rises in rain or sandstorms
        weather_traffic_mult = 1.0
        if rain > 0.5:
            weather_traffic_mult = 1.25
        if wind > 35.0:
            weather_traffic_mult = 1.20
            
        congestion = np.clip(time_factor * loc_scale["traffic"] * weather_traffic_mult + np.random.normal(0, 0.3), 0.0, 10.0)
        
        # Average Speed in km/h (negatively correlated with congestion)
        max_speed = 80.0 if loc_name != "Dubai International Airport (DXB)" else 60.0
        avg_speed = np.clip(max_speed * (1.0 - (congestion / 11.0)) + np.random.normal(0, 2.0), 10.0, max_speed)
        vehicle_count = int(congestion * 280 + np.random.randint(50, 150))
        
        # 2. Tourism Demand
        # Highly seasonal (Winter: Nov-March is peak; Summer: June-Aug is hot and low)
        seasonal_factors = {1: 1.5, 2: 1.4, 3: 1.3, 4: 1.0, 5: 0.7, 6: 0.4, 7: 0.3, 8: 0.3, 9: 0.6, 10: 0.9, 11: 1.3, 12: 1.6}
        season_mult = seasonal_factors.get(month, 1.0)
        
        # Weekend bump for tourists
        weekend_mult = 1.30 if is_weekend else 1.0
        
        # Event modifier (Dubai Shopping Festival in January)
        event_mult = 1.40 if month == 1 else 1.0
        
        base_visitors = 1200 * loc_scale["tourists"]
        visitor_count = int(base_visitors * season_mult * weekend_mult * event_mult + np.random.normal(0, 50))
        visitor_count = max(50, visitor_count)
        
        # Hotel occupancy (capped between 20% and 98%)
        hotel_occupancy = np.clip(35.0 * season_mult * event_mult + (15.0 if is_weekend else 5.0) + np.random.normal(0, 2.0), 20.0, 98.0)
        
        # 3. Energy Consumption (kWh)
        # Base load depends on size/type of location
        base_energy = 2500.0 * loc_scale["energy"]
        # Temperature AC Load: AC demand surges exponentially when temp goes above 25C
        cooling_mult = 1.0
        if temp > 25.0:
            cooling_mult = 1.0 + 0.05 * (temp - 25.0) + 0.001 * ((temp - 25.0) ** 2)
            
        # Daily cycle: peak energy demand during afternoon working hours
        day_mult = 0.7 + 0.5 * np.exp(-((hour - 14.0) / 4.0) ** 2)
        
        consumption_kwh = base_energy * cooling_mult * day_mult + np.random.normal(0, 100)
        peak_load_kw = (consumption_kwh / 0.85) * (1.0 + np.random.uniform(0.05, 0.15))
        
        # 4. Water Consumption (m3)
        # Deeply correlated with cooling load (AC chillers) and visitor density
        base_water = 120.0 * loc_scale["energy"]
        water_consumption_m3 = base_water * cooling_mult * (0.8 + 0.2 * (visitor_count / 1500.0)) + np.random.normal(0, 5)
        water_consumption_m3 = max(10.0, water_consumption_m3)
        
        # 5. Air Quality (AQI)
        # Baseline = 45 (Good)
        # Traffic increments, high heat increases ozone, wind disperses unless wind is extremely high (sandstorms)
        aqi_base = 40.0
        traffic_impact = congestion * 12.0
        temp_impact = max(0.0, (temp - 30.0) * 1.5)
        
        if wind > 35.0 and humidity < 35.0:
            wind_impact = 90.0  # Spikes due to sand and dust particles
        elif wind > 15.0:
            wind_impact = -15.0  # Air dispersion improves quality
        else:
            wind_impact = 5.0   # Stagnant air accumulates pollutants
            
        aqi = int(np.clip(aqi_base + traffic_impact + temp_impact + wind_impact + np.random.normal(0, 5), 15, 300))
        
        # Derive air pollutants using linear proxy equations from AQI
        pm25 = np.clip(aqi * 0.35 + np.random.normal(0, 1), 2.0, 150.0)
        pm10 = np.clip(aqi * 0.75 + (50.0 if wind > 35.0 else 0.0) + np.random.normal(0, 3), 5.0, 250.0)
        no2 = np.clip(aqi * 0.22 + np.random.normal(0, 0.8), 1.0, 80.0)
        co = np.clip(aqi * 0.008 + np.random.normal(0, 0.05), 0.1, 4.0)
        
        # 6. Public Transport Ridership
        # Heavy rush peaks on weekdays
        if not is_weekend:
            transit_time_factor = 3000 * np.exp(-((hour - 8.0) / 1.0) ** 2) + 3500 * np.exp(-((hour - 17.5) / 1.2) ** 2) + 500
        else:
            transit_time_factor = 1200 * np.exp(-((hour - 16.0) / 3.0) ** 2) + 300
            
        # Metro and Bus scales with tourists and traffic congestion (high traffic makes driving annoying, shifting to metro)
        metro_ridership = int(transit_time_factor * loc_scale["transport"] * (1.0 + (congestion / 20.0)) + np.random.normal(0, 50))
        bus_ridership = int((transit_time_factor * 0.5) * loc_scale["transport"] * (1.0 + (congestion / 30.0)) + np.random.normal(0, 30))
        taxi_ridership = int((transit_time_factor * 0.4) * loc_scale["transport"] * (1.0 + (visitor_count / 3000.0)) + np.random.normal(0, 20))
        
        metro_ridership = max(10, metro_ridership)
        bus_ridership = max(10, bus_ridership)
        taxi_ridership = max(5, taxi_ridership)
        
        # 7. Carbon Emissions (Metric Tons of CO2 per Hour)
        # Vehicles: CO2 proportional to vehicle count and congestion (low speeds increase emissions per km)
        vehicle_emissions = vehicle_count * 0.00015 * (1.0 + (congestion / 8.0))
        # Electricity: UAE grid carbon intensity proxy (approx 0.38 kg CO2 per kWh = 0.00038 MT)
        grid_emissions = consumption_kwh * 0.00038
        
        emissions_mt_co2 = vehicle_emissions + grid_emissions + (loc_scale["energy"] * 0.1) + np.random.normal(0, 0.02)
        emissions_mt_co2 = max(0.01, emissions_mt_co2)
        
        return {
            "traffic": {
                "congestion_index": round(congestion, 2),
                "avg_speed": round(avg_speed, 1),
                "vehicle_count": vehicle_count
            },
            "tourism": {
                "visitor_count": visitor_count,
                "hotel_occupancy": round(hotel_occupancy, 1)
            },
            "energy": {
                "consumption_kwh": round(consumption_kwh, 1),
                "peak_load_kw": round(peak_load_kw, 1)
            },
            "water": {
                "consumption_m3": round(water_consumption_m3, 1)
            },
            "air_quality": {
                "aqi": aqi,
                "pm25": round(pm25, 1),
                "pm10": round(pm10, 1),
                "no2": round(no2, 1),
                "co": round(co, 2)
            },
            "transport": {
                "metro_ridership": metro_ridership,
                "bus_ridership": bus_ridership,
                "taxi_ridership": taxi_ridership
            },
            "carbon": {
                "emissions_mt_co2": round(emissions_mt_co2, 3)
            }
        }