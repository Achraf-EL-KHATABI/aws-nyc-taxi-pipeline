SELECT 
  pickup_period,
  COUNT(*) AS num_trips,
  ROUND(AVG(fare_amount), 2) AS avg_fare,
  ROUND(AVG(tip_percentage), 2) AS avg_tip_pct
FROM <NOM_TABLE_CURATED>
GROUP BY pickup_period
ORDER BY num_trips DESC;