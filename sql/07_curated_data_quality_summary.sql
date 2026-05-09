-- Compare raw vs curated row counts to validate the ETL filtering
SELECT
  'raw' AS layer,
  COUNT(*) AS row_count
FROM nyc_taxi_pipeline_raw_ake_2026_05
WHERE taxi_type = 'yellow' AND year IN ('2024')
UNION ALL
SELECT
  'curated' AS layer,
  COUNT(*) AS row_count
FROM <NOM_TABLE_CURATED>;