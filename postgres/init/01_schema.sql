CREATE TABLE wells (
    well_id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    field_name TEXT,
    region TEXT,
    start_date DATE,
    operator TEXT,
    status TEXT
);
CREATE TABLE production (
    prod_id SERIAL PRIMARY KEY,
    well_id INT REFERENCES wells(well_id),
    date DATE NOT NULL,
    oil_ton NUMERIC(10,2),
    gas_m3 NUMERIC(12,2),
    water_m3 NUMERIC(12,2),
    energy_kwh NUMERIC(12,2),
    downtime_hours NUMERIC(5,2),
    temperature NUMERIC(5,2),
    pressure NUMERIC(5,2)
);
CREATE TABLE well_telemetry (
    record_id SERIAL PRIMARY KEY,
    well_id INT REFERENCES wells(well_id),
    timestamp TIMESTAMP,
    pump_speed_rpm NUMERIC(8,2),
    pump_current NUMERIC(8,2),
    pressure_in NUMERIC(8,2),
    pressure_out NUMERIC(8,2),
    temperature NUMERIC(5,2),
    vibration NUMERIC(5,2),
    oil_flow_rate NUMERIC(8,2)
);
CREATE TABLE well_targets (
    well_id INT REFERENCES wells(well_id),
    date DATE,
    daily_oil_ton NUMERIC(10,2)
);
CREATE TABLE pumps (
    pump_id SERIAL PRIMARY KEY,
    well_id INT REFERENCES wells(well_id),
    type TEXT,
    install_date DATE,
    manufacturer TEXT,
    model TEXT
);
CREATE TABLE pump_sensors (
    record_id SERIAL PRIMARY KEY,
    pump_id INT REFERENCES pumps(pump_id),
    timestamp TIMESTAMP,
    temperature NUMERIC(5,2),
    vibration NUMERIC(5,2),
    current NUMERIC(8,2),
    rpm NUMERIC(8,2),
    pressure NUMERIC(8,2)
);
CREATE TABLE pump_failures (
    failure_id SERIAL PRIMARY KEY,
    pump_id INT REFERENCES pumps(pump_id),
    failure_date TIMESTAMP,
    failure_type TEXT,
    downtime_hours NUMERIC(5,2)
);
CREATE TABLE deliveries (
    delivery_id SERIAL PRIMARY KEY,
    date DATE,
    source TEXT,
    destination TEXT,
    product_type TEXT,
    volume_ton NUMERIC(10,2),
    cost_usd NUMERIC(10,2),
    delay_hours NUMERIC(6,2),
    distance_km NUMERIC(8,2),
    weather_conditions TEXT,
    driver_id INT,
    vehicle_id INT
);
CREATE TABLE drivers (
    driver_id SERIAL PRIMARY KEY,
    name TEXT,
    experience_years INT,
    region TEXT
);
CREATE TABLE vehicles (
    vehicle_id SERIAL PRIMARY KEY,
    plate_number TEXT,
    capacity_ton NUMERIC(8,2),
    fuel_type TEXT
);
CREATE TABLE oil_stations (
    station_id SERIAL PRIMARY KEY,
    station_name VARCHAR(100),
    latitude FLOAT,
    longitude FLOAT,
    oil_flow_per_day FLOAT
);
INSERT INTO oil_stations (station_name, latitude, longitude, oil_flow_per_day)
VALUES
('Ufa Station', 54.7388, 55.9721, 12500),
('Perm Station', 58.0105, 56.2294, 8700),
('Omsk Station', 54.9893, 73.3682, 15600),
('Tyumen Station', 57.1530, 65.5343, 11200),
('Kazan Station', 55.7963, 49.1088, 9400),
('Samara Station', 53.1959, 50.1008, 10800),
('Saratov Station', 51.5331, 46.0342, 9700),
('Volgograd Station', 48.7080, 44.5133, 8800),
('Yaroslavl Station', 57.6261, 39.8845, 7600),
('Moscow Station', 55.7558, 37.6173, 14300),
('Chelyabinsk Station', 55.1644, 61.4368, 11900),
('Novosibirsk Station', 55.0084, 82.9357, 16700),
('Kurgan Station', 55.4410, 65.3411, 8200),
('Nizhny Novgorod Station', 56.2965, 43.9361, 10200),
('Rostov Station', 47.2357, 39.7015, 9100),
('Krasnodar Station', 45.0355, 38.9753, 8900),
('Voronezh Station', 51.6720, 39.1843, 9800),
('Orenburg Station', 51.7682, 55.0969, 9400),
('Ekaterinburg Station', 56.8389, 60.6057, 13300),
('Astrakhan Station', 46.3497, 48.0408, 8700);
