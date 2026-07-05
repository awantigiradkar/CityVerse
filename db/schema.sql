-- Schema for CityVerse: Dubai Smart City Digital Twin

-- Enable UUID extension just in case
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Locations master table
CREATE TABLE IF NOT EXISTS locations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    latitude NUMERIC(9, 6) NOT NULL,
    longitude NUMERIC(9, 6) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Weather forecasts (City-wide or regional)
CREATE TABLE IF NOT EXISTS weather_forecast (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    temperature DOUBLE PRECISION NOT NULL, -- Celsius
    humidity DOUBLE PRECISION NOT NULL,    -- Percentage
    wind_speed DOUBLE PRECISION NOT NULL,  -- km/h
    precipitation DOUBLE PRECISION NOT NULL, -- mm
    condition VARCHAR(50) NOT NULL,        -- Sunny, Rainy, Sandstorm, etc.
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_weather_timestamp ON weather_forecast(timestamp);

-- 3. Traffic conditions
CREATE TABLE IF NOT EXISTS traffic_conditions (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    location_id INT REFERENCES locations(id) ON DELETE CASCADE,
    congestion_index DOUBLE PRECISION NOT NULL, -- Scale 0 to 10
    avg_speed DOUBLE PRECISION NOT NULL,        -- km/h
    vehicle_count INT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_traffic_time_loc ON traffic_conditions(timestamp, location_id);

-- 4. Tourism demand
CREATE TABLE IF NOT EXISTS tourism_demand (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    location_id INT REFERENCES locations(id) ON DELETE CASCADE,
    visitor_count INT NOT NULL,
    hotel_occupancy DOUBLE PRECISION NOT NULL, -- Percentage (0 to 100)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_tourism_time_loc ON tourism_demand(timestamp, location_id);

-- 5. Energy consumption
CREATE TABLE IF NOT EXISTS energy_consumption (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    location_id INT REFERENCES locations(id) ON DELETE CASCADE,
    consumption_kwh DOUBLE PRECISION NOT NULL,
    peak_load_kw DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_energy_time_loc ON energy_consumption(timestamp, location_id);

-- 6. Water consumption
CREATE TABLE IF NOT EXISTS water_consumption (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    location_id INT REFERENCES locations(id) ON DELETE CASCADE,
    consumption_m3 DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_water_time_loc ON water_consumption(timestamp, location_id);

-- 7. Air quality
CREATE TABLE IF NOT EXISTS air_quality (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    location_id INT REFERENCES locations(id) ON DELETE CASCADE,
    aqi INT NOT NULL,
    pm25 DOUBLE PRECISION NOT NULL, -- ug/m3
    pm10 DOUBLE PRECISION NOT NULL, -- ug/m3
    no2 DOUBLE PRECISION NOT NULL,
    co DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_aqi_time_loc ON air_quality(timestamp, location_id);

-- 8. Public transport ridership
CREATE TABLE IF NOT EXISTS public_transport (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    location_id INT REFERENCES locations(id) ON DELETE CASCADE,
    metro_ridership INT NOT NULL,
    bus_ridership INT NOT NULL,
    taxi_ridership INT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_transport_time_loc ON public_transport(timestamp, location_id);

-- 9. Carbon emissions
CREATE TABLE IF NOT EXISTS carbon_emissions (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    location_id INT REFERENCES locations(id) ON DELETE CASCADE,
    emissions_mt_co2 DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_carbon_time_loc ON carbon_emissions(timestamp, location_id);

-- 10. Scenario runs log
CREATE TABLE IF NOT EXISTS scenario_runs (
    id SERIAL PRIMARY KEY,
    run_timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    scenario_name VARCHAR(100) NOT NULL,
    parameters JSONB NOT NULL,
    results JSONB NOT NULL
);