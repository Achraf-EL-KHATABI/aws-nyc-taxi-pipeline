-- Top 10 busiest days in January 2024 with distance & fare averages

SELECT 
  DATE(tpep_pickup_datetime) AS pickup_date,
  COUNT(*) AS num_trips,
  ROUND(AVG(trip_distance), 2) AS avg_distance_miles,
  ROUND(AVG(fare_amount), 2) AS avg_fare_usd
FROM nyc_taxi_pipeline_raw_ake_2026_05
WHERE taxi_type = 'yellow' 
  AND year = '2024' 
  AND month = '01'
GROUP BY DATE(tpep_pickup_datetime)
ORDER BY num_trips DESC
LIMIT 10;