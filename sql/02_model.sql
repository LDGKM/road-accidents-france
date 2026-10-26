-- =====================================================================
-- 02_model.sql  —  analysis-ready views built on the clean tables
-- =====================================================================

-- Vehicle categories (official catv codes) grouped into 9 travel modes
CREATE OR REPLACE TABLE mode_map AS
SELECT * FROM (VALUES
  (1,'Bicycle'),(80,'E-bike'),(50,'E-scooter'),(60,'E-scooter'),
  (2,'Moped / scooter <50cc'),(30,'Moped / scooter <50cc'),(41,'Moped / scooter <50cc'),
  (31,'Motorcycle'),(32,'Motorcycle'),(33,'Motorcycle'),(34,'Motorcycle'),(42,'Motorcycle'),(43,'Motorcycle'),
  (35,'Car'),(36,'Car'),(3,'Car'),(7,'Car'),(10,'Van'),
  (13,'Heavy vehicle'),(14,'Heavy vehicle'),(15,'Heavy vehicle'),(16,'Heavy vehicle'),(17,'Heavy vehicle'),
  (20,'Heavy vehicle'),(21,'Heavy vehicle'),(37,'Bus / coach / tram'),(38,'Bus / coach / tram'),
  (39,'Bus / coach / tram'),(40,'Bus / coach / tram')
) AS t(catv, mode);

-- Metropolitan France only (96 departments): overseas territories use a
-- simplified record and very different road networks.
CREATE OR REPLACE VIEW acc_metro AS
SELECT * FROM accidents
WHERE dep IN (SELECT lpad(CAST(i AS VARCHAR), 2, '0') FROM range(1, 96) t(i) WHERE i <> 20)
   OR dep IN ('2A', '2B');

-- One row per victim (and unhurt user), with age and travel mode.
-- Pedestrians are attached to the vehicle that hit them, so their mode
-- is forced to 'Pedestrian'.
CREATE OR REPLACE VIEW people AS
SELECT
    u.*,
    a.year, a.dep, a.com, a.in_town, a.hour, a.lum,
    CASE WHEN u.birth_year BETWEEN 1900 AND a.year THEN a.year - u.birth_year END AS age,
    CASE WHEN u.role = 3 THEN 'Pedestrian' ELSE COALESCE(m.mode, 'Other / unknown') END AS mode
FROM users u
JOIN acc_metro a USING (acc_id)
LEFT JOIN vehicles v ON v.acc_id = u.acc_id AND v.veh_id = u.veh_id
LEFT JOIN mode_map m ON m.catv = v.catv;

-- One row per accident with its outcome and the main risk factors.
CREATE OR REPLACE VIEW acc_full AS
WITH outcome AS (
    SELECT acc_id,
           count(*) FILTER (WHERE severity = 2)          AS killed,
           count(*) FILTER (WHERE severity IN (3, 4))    AS injured,
           count(*) FILTER (WHERE role = 3)              AS pedestrians
    FROM users GROUP BY acc_id
), veh AS (
    SELECT v.acc_id,
           count(*)                                                    AS n_vehicles,
           bool_or(m.mode = 'Motorcycle')                              AS has_motorcycle,
           bool_or(m.mode IN ('Bicycle', 'E-bike'))                    AS has_bicycle,
           bool_or(m.mode = 'E-scooter')                               AS has_escooter,
           bool_or(m.mode = 'Heavy vehicle')                           AS has_heavy,
           bool_or(v.fixed_obstacle BETWEEN 1 AND 17)                  AS hit_obstacle
    FROM vehicles v LEFT JOIN mode_map m USING (catv)
    GROUP BY v.acc_id
)
SELECT a.*, p.road_cat, p.speed_limit, p.surface, p.layout,
       o.killed, o.injured, o.pedestrians, o.killed > 0 AS fatal,
       v.n_vehicles, v.has_motorcycle, v.has_bicycle, v.has_escooter, v.has_heavy, v.hit_obstacle
FROM acc_metro a
LEFT JOIN places  p USING (acc_id)
LEFT JOIN outcome o USING (acc_id)
LEFT JOIN veh     v USING (acc_id);
