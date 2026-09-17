-- Portfolio case study. The exact runnable pipeline and source audits live in
-- src/growth/pipeline.py. The source warehouse is data/warehouse/olist.sqlite.
-- Monetary units: BRL. Order-item price, not fee revenue or company profit.

-- This query preserves lead grain. A LEFT JOIN keeps qualified leads with no win.
WITH lead_funnel AS (
  SELECT l.mql_id, COALESCE(l.origin, 'missing') AS source,
    l.first_contact_date, w.seller_id, w.won_date,
    julianday(w.won_date) - julianday(l.first_contact_date) AS elapsed_days
  FROM leads AS l LEFT JOIN wins AS w ON l.mql_id = w.mql_id
)
SELECT source,
  COUNT(*) AS eligible_qualified_leads,
  SUM(CASE WHEN elapsed_days BETWEEN 0 AND 90 THEN 1 ELSE 0 END) AS wins_within_90d,
  ROUND(1.0 * SUM(CASE WHEN elapsed_days BETWEEN 0 AND 90 THEN 1 ELSE 0 END)
        / NULLIF(COUNT(*), 0), 4) AS observed_conversion_90d
FROM lead_funnel
WHERE first_contact_date <= '2018-08-16 23:59:59'
GROUP BY source ORDER BY eligible_qualified_leads DESC;

-- Use item grain to allocate multi-seller orders correctly. The WIN date is
-- compared at timestamp grain; only full 90-day win cohorts are admitted.
WITH eligible_deals AS (
  SELECT w.mql_id, w.seller_id, w.won_date, COALESCE(l.origin, 'missing') AS source
  FROM wins AS w JOIN leads AS l ON l.mql_id = w.mql_id
  WHERE w.won_date <= '2018-06-02 23:59:59'
    AND julianday(w.won_date) - julianday(l.first_contact_date) BETWEEN 0 AND 90
), observed_item_sales AS (
  SELECT d.seller_id, i.order_id, i.price,
    o.order_purchase_timestamp AS purchased
  FROM eligible_deals AS d
  JOIN items AS i ON d.seller_id = i.seller_id
  JOIN orders AS o ON o.order_id = i.order_id
  WHERE o.order_status = 'delivered'
    AND o.order_purchase_timestamp >= d.won_date
    AND o.order_purchase_timestamp < datetime(d.won_date, '+90 days')
    AND o.order_purchase_timestamp <= '2018-08-31 23:59:59'
), seller_outcomes AS (
  SELECT d.seller_id, d.source,
    COALESCE(SUM(s.price), 0) AS recorded_item_gmv_brl,
    COUNT(DISTINCT s.order_id) AS delivered_orders_90d
  FROM eligible_deals AS d LEFT JOIN observed_item_sales AS s ON d.seller_id = s.seller_id
  GROUP BY d.seller_id, d.source
)
SELECT source, COUNT(*) AS matured_wins,
  SUM(CASE WHEN delivered_orders_90d > 0 THEN 1 ELSE 0 END) AS wins_with_recorded_sales,
  ROUND(SUM(recorded_item_gmv_brl), 2) AS recorded_90d_gmv_brl,
  ROUND(AVG(recorded_item_gmv_brl), 2) AS mean_gmv_per_matured_win_brl
FROM seller_outcomes GROUP BY source ORDER BY matured_wins DESC;
