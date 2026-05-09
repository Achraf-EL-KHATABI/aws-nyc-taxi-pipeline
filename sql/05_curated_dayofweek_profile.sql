SELECT 
  pickup_dayofweek,
  CASE pickup_dayofweek
    WHEN 1 THEN 'Sunday'    WHEN 2 THEN 'Monday'   WHEN 3 THEN 'Tuesday'
    WHEN 4 THEN 'Wednesday' WHEN 5 THEN 'Thursday' WHEN 6 THEN 'Friday'
    WHEN 7 THEN 'Saturday'
  END AS day_name,
  COUNT(*) AS num_trips,
  ROUND(AVG(trip_duration_minutes), 1) AS avg_duration_min,
  ROUND(AVG(fare_per_mile), 2) AS avg_fare_per_mile
FROM <NOM_TABLE_CURATED>
GROUP BY pickup_dayofweek
ORDER BY pickup_dayofweek;