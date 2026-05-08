-- Multi-month aggregation showing partition pruning benefits
-- Yellow taxi: trip counts and revenue per month

SELECT 
  year, 
  month, 
  COUNT(*) AS trips,
  ROUND(SUM(total_amount), 2) AS revenue_usd
FROM nyc_taxi_pipeline_raw_ake_2026_05
WHERE taxi_type = 'yellow'
GROUP BY year, month
ORDER BY year, month;