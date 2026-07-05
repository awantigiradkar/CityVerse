from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, JSON, Numeric
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

# Base class for our database models to inherit from
Base = declarative_base()

class Location(Base):
    __tablename__ = 'locations'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    latitude = Column(Numeric(9, 6), nullable=False)
    longitude = Column(Numeric(9, 6), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class WeatherForecast(Base):
    __tablename__ = 'weather_forecast'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    temperature = Column(Float, nullable=False)
    humidity = Column(Float, nullable=False)
    wind_speed = Column(Float, nullable=False)
    precipitation = Column(Float, nullable=False)
    condition = Column(String(50), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class TrafficCondition(Base):
    __tablename__ = 'traffic_conditions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    location_id = Column(Integer, ForeignKey('locations.id', ondelete='CASCADE'), nullable=False)
    congestion_index = Column(Float, nullable=False)  # 0 to 10
    avg_speed = Column(Float, nullable=False)         # km/h
    vehicle_count = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    location = relationship("Location")


class TourismDemand(Base):
    __tablename__ = 'tourism_demand'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    location_id = Column(Integer, ForeignKey('locations.id', ondelete='CASCADE'), nullable=False)
    visitor_count = Column(Integer, nullable=False)
    hotel_occupancy = Column(Float, nullable=False)   # Percentage (0-100)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    location = relationship("Location")


class EnergyConsumption(Base):
    __tablename__ = 'energy_consumption'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    location_id = Column(Integer, ForeignKey('locations.id', ondelete='CASCADE'), nullable=False)
    consumption_kwh = Column(Float, nullable=False)
    peak_load_kw = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    location = relationship("Location")


class WaterConsumption(Base):
    __tablename__ = 'water_consumption'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    location_id = Column(Integer, ForeignKey('locations.id', ondelete='CASCADE'), nullable=False)
    consumption_m3 = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    location = relationship("Location")


class AirQuality(Base):
    __tablename__ = 'air_quality'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    location_id = Column(Integer, ForeignKey('locations.id', ondelete='CASCADE'), nullable=False)
    aqi = Column(Integer, nullable=False)
    pm25 = Column(Float, nullable=False)
    pm10 = Column(Float, nullable=False)
    no2 = Column(Float, nullable=False)
    co = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    location = relationship("Location")


class PublicTransport(Base):
    __tablename__ = 'public_transport'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    location_id = Column(Integer, ForeignKey('locations.id', ondelete='CASCADE'), nullable=False)
    metro_ridership = Column(Integer, nullable=False)
    bus_ridership = Column(Integer, nullable=False)
    taxi_ridership = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    location = relationship("Location")


class CarbonEmission(Base):
    __tablename__ = 'carbon_emissions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    location_id = Column(Integer, ForeignKey('locations.id', ondelete='CASCADE'), nullable=False)
    emissions_mt_co2 = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    location = relationship("Location")


class ScenarioRun(Base):
    __tablename__ = 'scenario_runs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_timestamp = Column(DateTime, default=datetime.utcnow)
    scenario_name = Column(String(100), nullable=False)
    parameters = Column(JSON, nullable=False)
    results = Column(JSON, nullable=False)