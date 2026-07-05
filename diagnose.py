# diagnose.py
from sqlalchemy import create_engine, text
import pandas as pd
from src.config import settings

engine = create_engine(settings.database_url)
with engine.connect() as conn:
    weather_count = conn.execute(text("SELECT COUNT(*) FROM weather_forecast")).scalar()
    traffic_count = conn.execute(text("SELECT COUNT(*) FROM traffic_conditions")).scalar()
    
    join_count = conn.execute(text("""
        SELECT COUNT(*) 
        FROM traffic_conditions t 
        JOIN weather_forecast w ON t.timestamp = w.timestamp
    """)).scalar()
    
    print(f"Total Weather Rows: {weather_count}")
    print(f"Total Traffic Rows: {traffic_count}")
    print(f"Joined Rows (Perfect Matches): {join_count}")
    
    print("\nTraffic Timestamp Sample:")
    print(conn.execute(text("SELECT timestamp FROM traffic_conditions LIMIT 3")).fetchall())
    
    print("\nWeather Timestamp Sample:")
    print(conn.execute(text("SELECT timestamp FROM weather_forecast LIMIT 3")).fetchall())