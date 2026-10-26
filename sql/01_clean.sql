-- =====================================================================
-- 01_clean.sql  —  raw CSV files  ->  four clean, typed tables
-- The raw files are read with every column as text (all_varchar) because
-- the open data mixes formats from year to year:
--   * numbers padded with spaces (" -1") or wrapped in brackets ("(1)")
--   * decimal commas in coordinates ("47,56277")
--   * the 2022 accident id column is called Accident_Id instead of Num_Acc
-- The macro num() turns any of those into an INTEGER, or NULL when the
-- value is missing ("-1", "", "N/A").
-- {RAW} is replaced by the Python loader with the data/raw folder.
-- =====================================================================

CREATE OR REPLACE MACRO num(x) AS
    CASE WHEN TRY_CAST(regexp_replace(trim(x), '[()]', '', 'g') AS INTEGER) < 0 THEN NULL
         ELSE TRY_CAST(regexp_replace(trim(x), '[()]', '', 'g') AS INTEGER) END;

-- ---------------------------------------------------------------- accidents
CREATE OR REPLACE TABLE accidents AS
SELECT
    CAST(COALESCE(Num_Acc, Accident_Id) AS BIGINT)            AS acc_id,
    num(an)                                                   AS year,
    num(mois)                                                 AS month,
    num(jour)                                                 AS day,
    make_date(num(an), num(mois), num(jour))                  AS date,
    dayofweek(make_date(num(an), num(mois), num(jour)))       AS weekday,   -- 0 = Sunday
    num(split_part(hrmn, ':', 1))                             AS hour,
    num(lum)                                                  AS lum,
    CASE WHEN regexp_full_match(trim(dep), '[0-9]')                 -- some years write "1" for "01"
         THEN lpad(trim(dep), 2, '0') ELSE upper(trim(dep)) END   AS dep,
    trim(com)                                                 AS com,
    num(agg) = 2                                              AS in_town,
    num("int")                                                AS intersection,
    num(atm)                                                  AS atm,
    num(col)                                                  AS col,
    TRY_CAST(replace(trim(lat),  ',', '.') AS DOUBLE)         AS lat,
    TRY_CAST(replace(trim("long"), ',', '.') AS DOUBLE)       AS lon
FROM read_csv('{RAW}/caract-*.csv', delim=';', header=true, all_varchar=true,
              union_by_name=true, quote='"');

-- ---------------------------------------------------------------- places
-- One row per accident in principle; a few accidents have duplicates, we
-- keep the first row.
CREATE OR REPLACE TABLE places AS
SELECT
    CAST(Num_Acc AS BIGINT) AS acc_id,
    num(catr)  AS road_cat,
    num(circ)  AS traffic,
    num(nbv)   AS lanes,
    num(prof)  AS slope,
    num(plan)  AS layout,
    num(surf)  AS surface,
    num(infra) AS infra,
    num(situ)  AS situ,
    CASE WHEN num(vma) BETWEEN 10 AND 130 THEN num(vma) END AS speed_limit  -- outliers (e.g. 500, 900) -> NULL
FROM read_csv('{RAW}/lieux-*.csv', delim=';', header=true, all_varchar=true, union_by_name=true)
QUALIFY row_number() OVER (PARTITION BY CAST(Num_Acc AS BIGINT) ORDER BY catr) = 1;

-- ---------------------------------------------------------------- vehicles
CREATE OR REPLACE TABLE vehicles AS
SELECT
    CAST(Num_Acc AS BIGINT)                 AS acc_id,
    replace(trim(id_vehicule), ' ', '')     AS veh_id,
    trim(num_veh)                           AS veh_letter,
    num(catv)                               AS catv,
    num(obs)                                AS fixed_obstacle,
    num(obsm)                               AS moving_obstacle,
    num(choc)                               AS impact,
    num(manv)                               AS manoeuvre,
    num(motor)                              AS motor
FROM read_csv('{RAW}/vehicules-*.csv', delim=';', header=true, all_varchar=true, union_by_name=true);

-- ---------------------------------------------------------------- users
CREATE OR REPLACE TABLE users AS
SELECT
    CAST(u.Num_Acc AS BIGINT)               AS acc_id,
    replace(trim(u.id_vehicule), ' ', '')   AS veh_id,
    num(u.catu)                             AS role,        -- 1 driver, 2 passenger, 3 pedestrian
    num(u.grav)                             AS severity,    -- 1 unhurt, 2 killed, 3 hospitalised, 4 slightly injured
    num(u.sexe)                             AS sex,         -- 1 male, 2 female
    num(u.an_nais)                          AS birth_year,
    num(u.trajet)                           AS trip,
    num(u.secu1)                            AS safety1
FROM read_csv('{RAW}/usagers-*.csv', delim=';', header=true, all_varchar=true, union_by_name=true) u;
