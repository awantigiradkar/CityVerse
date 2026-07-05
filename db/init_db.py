import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Ensure we can import from the src directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import settings
from db.models import Base

# Sample Dubai Locations to Seed
DUBAI_LOCATIONS = [
    {"name": "Downtown Dubai", "latitude": 25.1972, "longitude": 55.2744, "description": "Home to Burj Khalifa and Dubai Mall, commercial and tourist hub."},
    {"name": "Dubai Marina", "latitude": 25.0686, "longitude": 55.1400, "description": "High-density residential and tourist waterfront development."},
    {"name": "Deira", "latitude": 25.2644, "longitude": 55.3117, "description": "Historic trade center, traditional souks and older residential area."},
    {"name": "Palm Jumeirah", "latitude": 25.1124, "longitude": 55.1390, "description": "Iconic artificial archipelago, luxury resorts and villas."},
    {"name": "Jumeirah", "latitude": 25.2100, "longitude": 55.2500, "description": "Coastal residential area with low-rise villas and public beaches."},
    {"name": "Business Bay", "latitude": 25.1850, "longitude": 55.2700, "description": "Modern commercial district adjacent to Downtown."},
    {"name": "Al Barsha", "latitude": 25.1065, "longitude": 55.1983, "description": "Residential area containing Mall of the Emirates."},
    {"name": "Dubai International Airport (DXB)", "latitude": 25.2532, "longitude": 55.3657, "description": "Global aviation hub, high passenger traffic."}
]

def initialize_database():
    """
    Connects to the configured database, generates tables from models, and seeds master data.
    """
    db_url = settings.database_url
    print(f"Initializing database. Connection URL: {db_url}")
    
    try:
        # Create SQLAlchemy Engine
        engine = create_engine(db_url)
        
        # Create all tables registered with our Base model
        print("Creating tables and indexes...")
        Base.metadata.create_all(engine)
        print("Database schema initialized successfully.")

        # Seed Locations
        print("Seeding default Dubai locations...")
        
        # SQLite uses different conflict resolution syntax than PostgreSQL.
        # But we can write a dialect-agnostic INSERT OR IGNORE / ON CONFLICT bypass by checking first.
        with engine.begin() as conn:
            for loc in DUBAI_LOCATIONS:
                # Check if location already exists
                check_query = text("SELECT id FROM locations WHERE name = :name")
                result = conn.execute(check_query, {"name": loc["name"]}).fetchone()
                
                if result is None:
                    # Insert new location
                    insert_query = text("""
                        INSERT INTO locations (name, latitude, longitude, description)
                        VALUES (:name, :latitude, :longitude, :description)
                    """)
                    conn.execute(insert_query, loc)
                else:
                    # Update existing location
                    update_query = text("""
                        UPDATE locations 
                        SET latitude = :latitude, longitude = :longitude, description = :description
                        WHERE name = :name
                    """)
                    conn.execute(update_query, loc)
                    
        print("Location seeding completed successfully!")
        
    except Exception as e:
        print(f"Database initialization failed: {e}")

if __name__ == "__main__":
    load_dotenv()
    initialize_database()