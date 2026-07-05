import os
import sys
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Ensure we can import from the project root (3 levels up from this file)
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.config import settings
from src.data_collection.weather_api import WeatherAPIClient
from src.data_collection.simulator import CityDataSimulator

def run_etl_pipeline(days_back: int = 30):
    """
    ETL Pipeline:
    1. Fetches real Dubai weather history from Open-Meteo.
    2. Queries locations from the database.
    3. Runs the CityDataSimulator hourly to generate correlated indicators.
    4. Performs bulk insertion into the database tables.
    """
    print("--- STARTING CITYVERSE ETL PIPELINE ---")
    db_url = settings.database_url
    engine = create_engine(db_url)
    
    # 1. Fetch real weather data
    weather_client = WeatherAPIClient()
    weather_df = weather_client.fetch_hourly_weather(days_back=days_back)
    
    if weather_df is None or weather_df.empty:
        print("Error: Could not retrieve weather data. Aborting pipeline.")
        return
        
    # 2. Get registered locations from DB
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT id, name, latitude, longitude FROM locations"))
            locations = [dict(row._mapping) for row in result]
            
        if not locations:
            print("Error: No locations found in the database. Run db/init_db.py first.")
            return
        print(f"Retrieved {len(locations)} locations from database.")
    except Exception as e:
        print(f"Failed to query locations: {e}")
        return

    # 3. Process and write Weather Data to DB
    print("Writing weather forecast data to DB...")
    try:
        # Deduplicate weather before writing
        weather_df = weather_df.drop_duplicates(subset=["timestamp"])
        weather_df.to_sql("weather_forecast", con=engine, if_exists="append", index=False)
        print(f"Successfully inserted {len(weather_df)} weather records.")
    except Exception as e:
        print(f"Failed to write weather records: {e}")
        return

    # 4. Run simulation hourly for each location
    print("Running smart city simulation engine...")
    simulator = CityDataSimulator(locations)
    
    # Prepare batch insertion lists
    traffic_records = []
    tourism_records = []
    energy_records = []
    water_records = []
    air_quality_records = []
    transport_records = []
    carbon_records = []
    
    # Iterate through each weather reading
    for _, weather_row in weather_df.iterrows():
        timestamp = weather_row["timestamp"]
        if hasattr(timestamp, "to_pydatetime"):
            timestamp = timestamp.to_pydatetime()
            
        weather_data = {
            "temperature": weather_row["temperature"],
            "humidity": weather_row["humidity"],
            "wind_speed": weather_row["wind_speed"],
            "precipitation": weather_row["precipitation"],
            "condition": weather_row["condition"]
        }
        
        # Simulate each location for this hour
        for loc in locations:
            sim = simulator.simulate_hour(timestamp, loc, weather_data)
            loc_id = loc["id"]
            
            traffic_records.append({
                "timestamp": timestamp, "location_id": loc_id,
                "congestion_index": sim["traffic"]["congestion_index"],
                "avg_speed": sim["traffic"]["avg_speed"],
                "vehicle_count": sim["traffic"]["vehicle_count"]
            })
            
            tourism_records.append({
                "timestamp": timestamp, "location_id": loc_id,
                "visitor_count": sim["tourism"]["visitor_count"],
                "hotel_occupancy": sim["tourism"]["hotel_occupancy"]
            })
            
            energy_records.append({
                "timestamp": timestamp, "location_id": loc_id,
                "consumption_kwh": sim["energy"]["consumption_kwh"],
                "peak_load_kw": sim["energy"]["peak_load_kw"]
            })
            
            water_records.append({
                "timestamp": timestamp, "location_id": loc_id,
                "consumption_m3": sim["water"]["consumption_m3"]
            })
            
            air_quality_records.append({
                "timestamp": timestamp, "location_id": loc_id,
                "aqi": sim["air_quality"]["aqi"],
                "pm25": sim["air_quality"]["pm25"],
                "pm10": sim["air_quality"]["pm10"],
                "no2": sim["air_quality"]["no2"],
                "co": sim["air_quality"]["co"]
            })
            
            transport_records.append({
                "timestamp": timestamp, "location_id": loc_id,
                "metro_ridership": sim["transport"]["metro_ridership"],
                "bus_ridership": sim["transport"]["bus_ridership"],
                "taxi_ridership": sim["transport"]["taxi_ridership"]
            })
            
            carbon_records.append({
                "timestamp": timestamp, "location_id": loc_id,
                "emissions_mt_co2": sim["carbon"]["emissions_mt_co2"]
            })

    # 5. Bulk insert records
    print("Performing bulk inserts into smart-city tables...")
    try:
        pd.DataFrame(traffic_records).to_sql("traffic_conditions", con=engine, if_exists="append", index=False)
        pd.DataFrame(tourism_records).to_sql("tourism_demand", con=engine, if_exists="append", index=False)
        pd.DataFrame(energy_records).to_sql("energy_consumption", con=engine, if_exists="append", index=False)
        pd.DataFrame(water_records).to_sql("water_consumption", con=engine, if_exists="append", index=False)
        pd.DataFrame(air_quality_records).to_sql("air_quality", con=engine, if_exists="append", index=False)
        pd.DataFrame(transport_records).to_sql("public_transport", con=engine, if_exists="append", index=False)
        pd.DataFrame(carbon_records).to_sql("carbon_emissions", con=engine, if_exists="append", index=False)
        
        print("ETL pipeline executed successfully! Database populated.")
        print(f"Inserted: {len(traffic_records)} rows per table across 7 domain tables.")
    except Exception as e:
        print(f"Failed during bulk inserts: {e}")

if __name__ == "__main__":
    load_dotenv()
    run_etl_pipeline(days_back=30)