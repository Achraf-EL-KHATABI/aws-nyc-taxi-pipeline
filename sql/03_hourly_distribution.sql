-- Hourly trip distribution and average fare for January 2024
-- Useful for understanding peak demand patterns

SELECT 
  HOUR(tpep_pickup_datetime) AS pickup_hour,
  COUNT(*) AS num_trips,
  ROUND(AVG(fare_amount), 2) AS avg_fare
FROM nyc_taxi_pipeline_raw_ake_2026_05
WHERE taxi_type = 'yellow' 
  AND year = '2024' 
  AND month = '01'
GROUP BY HOUR(tpep_pickup_datetime)
ORDER BY pickup_hour;