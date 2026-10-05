# Verified business findings

## 1. United Kingdom generated the largest share of observed valid revenue.

- Metric: 85.0% of valid revenue (£17,410,196.12).
- Executed SQL: `sql/analysis/03_country_performance.sql`
- Business relevance: The observed revenue base is geographically concentrated, so country-level performance can materially affect total results.
- Limitation: Country is the customer country recorded on the invoice; it does not establish nationality or shipment profitability.

## 2. The ten highest-revenue identified customers generated a measurable share of total valid revenue.

- Metric: 13.6% of valid revenue (£2,787,079.44).
- Executed SQL: `sql/analysis/06_revenue_concentration.sql`
- Business relevance: A concentrated customer base makes retention of a small group commercially important.
- Limitation: Missing customer IDs are excluded from the ranking but their revenue remains in the denominator.

## 3. The ten highest-revenue stock codes generated a limited share of total valid revenue.

- Metric: 10.3% of valid revenue (£2,113,090.51).
- Executed SQL: `sql/analysis/06_revenue_concentration.sql`
- Business relevance: The result shows how dependent revenue is on a small group of items or invoice charge codes.
- Limitation: The source has no product category and includes non-merchandise codes such as postage or adjustments.

## 4. A majority of identified customers placed at least two valid sales invoices.

- Metric: 72.4%: 4,255 of 5,878 identified customers.
- Executed SQL: `sql/analysis/07_repeat_customers.sql`
- Business relevance: Repeat purchasing is an observable retention indicator for the identified-customer population.
- Limitation: Anonymous customers are excluded, and the metric is limited to the observation window.

## 5. November 2011 was the highest-revenue complete calendar month.

- Metric: £1,503,866.78 across 2,769 valid sales invoices.
- Executed SQL: `sql/analysis/02_monthly_revenue.sql`
- Business relevance: The monthly pattern provides a factual starting point for capacity and inventory planning.
- Limitation: The dataset has no promotion, inventory, margin, or causal demand-driver fields.
