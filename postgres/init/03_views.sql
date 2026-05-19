CREATE OR REPLACE VIEW v_daily_production AS
SELECT date, SUM(oil_ton) AS total_oil_ton
FROM production
WHERE oil_ton > 0
GROUP BY date;
CREATE OR REPLACE VIEW v_well_kpi AS
SELECT
    w.well_id,
    w.name AS well_name,
    AVG(p.oil_ton) AS avg_oil_ton,
    AVG(p.downtime_hours / 24.0) * 100 AS downtime_pct,
    AVG(p.pressure) AS avg_pressure,
    AVG(p.temperature) AS avg_temperature
FROM production p
JOIN wells w ON w.well_id = p.well_id
WHERE p.oil_ton > 0
GROUP BY w.well_id, w.name;
