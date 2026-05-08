-- Count yellow taxi trips for January 2024
-- Demonstrates partition pruning: only scans ~50 MB

SELECT COUNT(*) AS trip_count
FROM nyc_taxi_pipeline_raw_ake_2026_05
WHERE taxi_type = 'yellow' 
  AND year = '2024' 
  AND month = '01';