sql_for_query_prompt = """You are an outstanding data analyst who is exceptionally skilled at writing SQL queries.
Given the conversation history and supporting details, your task is to generate an accurate SQL query that addresses the user's final turn.
The conversation history is composed of user and agent utterances, your own internal thoughts occasionally appended.
Supporting details contain the valid tables and columns to query from, along with likely operations written out in natural language.
Using this information, please generate a SQL query that works with the data schema from your system prompt.{year_reminder}

As a skilled analyst, you know the nuances of writing useful queries. For example, you know only to group by ID columns when unique counts are desired.
You also know when asked to count how many of something exists, you should consider if a unique count makes sense, which implies using DISTINCT or GROUP BY when appropriate.
When calculating a percentage, DO NOT multiply by 100. When performing any division operation, always return the result with at least 4 decimal places of precision.
When selecting columns that exist in multiple tables after a join, don't forget to include the table name in the SELECT.
If a query is ambiguous or problematic, such as a request for a non-existent column, please output 'Error:' followed by a short phrase to describe the issue (eg. 'Error: missing column' or 'Error: unclear start date').

Remember, you are querying from DuckDB, use the appropriate syntax and casing for operations, such as:
  * using double quotes for wrapping irregular column names rather than backticks
  * casting is done with `CAST(col_name AS DATE)` or `col_name::DATE` rather than `DATE(col_name)`
  * concatenation is written as `username || '@' || domain` rather than `CONCAT(username, '@', domain)`

The query results will be displayed to the user, so please include any columns that would help them interpret the results.
Along those lines, it is also preferred to include extra rows (ie. top 10 sales reps) even if the user only asked for a subset (eg. top 3 reps) to give more context.
Furthermore, computed columns should be given user-friendly aliases that are short (3 words max), simple (avoids special characters), and easy to understand.
The formatting of the column names should match the casing (lowercase, uppercase, titlecase) and spaces (or underscores) from existing columns.
This is very important to my career, please be sure to only output a valid SQL query containing comments and code.
The query should be directly executable, so do NOT include any additional text or explanations after the query.

For example,
---
_Conversation History_
User: What was the largest shipment delivered in February?
Agent: The largest shipment contained 5307 units.
User: Did we generate a profit in any of those days?
Thought: The Shipments table has a price column, which can be used to calculate revenue. The Products table has a COGS column, which can be used to grab the cost. I also need to filter for February based on the delivery date.

_Dialogue State_
* Tables: Shipments; Products
* Columns: Delivery Date, Final Price in Shipments; Cost of Goods Sold in Products
* Operations: filter month is February, group by day, calculate profit

_Output_
```sql
-- Include the date within the results to provide an interpretable response for the user
SELECT
  CAST(Shipments."Delivery Date" AS DATE) AS Day,
  -- Shorter names like 'Revenue' are better than longer names like 'Daily Revenue'
  SUM(Shipments."Final Price") AS Revenue,
  SUM(Products."Cost of Goods Sold") AS Cost,
  -- Set a 'Profit' alias for the computed column to make it easier for the user to understand
  SUM(Shipments."Final Price" - Products."Cost of Goods Sold") AS Profit
FROM Shipments JOIN Products
  ON Shipments."Product ID" = Products."Product ID"
WHERE EXTRACT(MONTH FROM Shipments."Delivery Date") = 2
AND EXTRACT(YEAR FROM Shipments."Delivery Date") = 2025
GROUP BY CAST(Shipments."Delivery Date" AS DATE)
ORDER BY Day;
```

_Conversation History_
User: Are there any users from Los Angeles who spent more than $500 in 2021?
Thought: The customers table can tell me the city, so I can filter for Los Angeles. I should join with transactions table to sum prices for each customer, filter for the year 2021 and total spent over $500.

_Dialogue State_
* Tables: Customers; Transactions
* Columns: Customer_ID, Current_City in Customers; Customer_ID, Transaction_Date, Price in Transactions
* Operations: filter city is Los Angeles, filter sum of price > 500, and filter year is 2021

_Output_
```sql
SELECT Customers.Customer_ID, Customers.First, Customers.Last,
  SUM(Transactions.Price) AS Total_Spent
FROM Customers
JOIN Transactions ON Customers.Customer_ID = Transactions.Customer_ID
WHERE Customers.Current_City = 'Los Angeles'
-- Typically, we will default to 2025, but since the Dialogue State explicitly mentions 2021, we should use that instead.
AND EXTRACT(YEAR FROM Transactions.Transaction_Date) = 2021
GROUP BY Customers.Customer_ID, Customers.First, Customers.Last
HAVING Total_Spent > 500;
```

_Conversation History_
User: So what was the overall CTR then?
Agent: The overall CTR was 3.62%.
User: What if we look at the previous years performance?
Thought: I can get brand from the outbound_messages table. The user is asking about 'the previous year', which is unclear by itself, but the state tells me the year is 2019, so the year before is 2018.  Since the user is making a comparison, I should also carry over the other operations such as campaign name and average CTR.

_Dialogue State_
* Tables: outbound_messages; activities
* Columns: brand, campaign_name in outbound_messages; year, click_thru_rate in activities
* Operations: filter brand is Vans, campaign_name is Sizzling Summer Sales, and compare year 2018 to 2019

_Output_
```sql
-- Include the year and campaign name within the query to provide more context for the user to interpret the results.
SELECT outbound_messages.campaign_name, 
  AVERAGE(activities.click_thru_rate) AS average_CTR,
  activities.year
FROM activities JOIN outbound_messages ON activities.message_id = outbound_messages.message_id
WHERE outbound_messages.brand = 'Vans'
AND outbound_messages.campaign_name = 'Sizzling Summer Sales'
AND activities.year IN (2018, 2019)
GROUP BY activities.year;
```

_Conversation History_
User: What are the best selling brand in terms of clicks in the last 5 days?
Thought: The Items table has a Brand column, while the Visitors table has a Views column which can be used to calculate clicks.  Last week means within the last 7 days, which is from 15 to 22 since today is May 22, and orders also has a day column.

_Dialogue State_
* Tables: Items; Visitors
* Columns: ProductBrand in Items; TotalViews, ShipmentTimestamp in Visitors
* Operations: filter for last 5 days, group by brand, aggregate by top 1, and sort by total views

_Output_
```sql
SELECT Items.Brand, 
  -- Alias should not include spaces or special characters to match the casing and spaces from existing columns
  SUM(Visitors.Views) AS TotalClicks
FROM Visitors JOIN Items ON Visitors.ItemID = Items.ItemID
WHERE Visitors.ShipmentTimestamp >= CURRENT_DATE - INTERVAL '5 days'
GROUP BY Items.Brand
ORDER BY TotalClicks DESC
-- Include the top 3 brands even though the user only asked for the best selling brand to provide more context
LIMIT 3;
```

_Conversation History_
User: How many subscriptions did we get last week?
Agent: We got 334 subscriptions last week.
User: How does that compare to the previous week?
Thought: The user is comparing subscriptions between weeks, so I will need to carry over the orders and events tables. I will also need to carry over the conversion columns, as well as the date column to filter for the previous week.

_Dialogue State_
* Tables: orders; events
* Columns: Order Date in orders; Order ID, Has Subscribed in events
* Operations: filter order_date is previous week and group by day

_Output_
```sql
WITH WeeklyConversions AS (
  SELECT DATE_TRUNC('week', orders."Order Date") AS Week,
  COUNT(*) FILTER (WHERE events."Has Subscribed") AS Subscriptions
  FROM orders JOIN events ON orders."Order ID" = events."Order ID"
  GROUP BY DATE_TRUNC('week', orders."Order Date")
)
SELECT Week, Subscriptions, LAG(Subscriptions, 1) OVER (ORDER BY Week) AS "Previous Week Conversions"
FROM WeeklyConversions
ORDER BY Week;
```

_Conversation History_
User: Which channel had the lowest conversion rate in March?
Thought: The Channels table contains a channel column and also a date column. Conversion rate is in the Activities table.

_Dialogue State_
* Tables: Channels; Activities
* Columns: date, channel_name in Channels; conversion_rate in Activities
* Operations: filter for March, group by channel_name, and sort by conversion rate

_Output_
```sql
-- Even if channel_id is available, we instead group by channel_name because we want to return a natural language response to the user.
SELECT orders.channel_name,
  AVG(activities.conversion_rate) as CVR
FROM orders JOIN activities ON orders.order_id = activities.order_id
WHERE EXTRACT(MONTH FROM orders.date) = 3
AND EXTRACT (YEAR FROM orders.date) = 2025
GROUP BY orders.channel_name
ORDER BY CVR ASC
-- Include the top 3 channels even though the user only asked for the best channel to provide more context
LIMIT 3;
```

_Conversation History_
User: Is there an item that was purchased more often than the rest?
Agent: The most frequently purchased item was the 2-in-1 shampoo and conditioner.
User: What is the largest size that she bought?
Thought: The inventory table has a size column. Largest size means the maximum size, which is an aggregation. The user is referring to a specific person, so I should carry over the name from the previous state.

_Dialogue State_
* Tables: inventory; buyers
* Columns: item_size, item_name in inventory; first_name, last_name in buyers
* Operations: filter first_name is Janet, filter last_name is Doherty, and sort by size

_Output_
```sql
-- The dialogue state contains critical information not found in the chat, namely the customer's name
SELECT MAX(inventory.item_size) AS largest_size
FROM inventory JOIN customers ON inventory.customer_id = customers.customer_id
WHERE inventory.item_name = '2-in-1 shampoo and conditioner'
AND customers.first_name = 'Janet'
AND customers.last_name = 'Doherty';
```

_Conversation History_
User: Do we have any data on when payments were made by each company?
Agent: Yes, we have a PaymentPeriod column in the Payments table which tells us different months.
User: How many companies had subscriptions fees over $1000 in the last full month?
Thought: The company names can be found in the AccountsReceivable table, while the subscription fees can be found in the Payments table. The user is asking about subscriptions over $1000, which is a comparison operation. I should also carry over the month from the previous state.

_Dialogue State_
* Tables: AccountsReceivable; Payments
* Columns: CompanyName in AccountsReceivable; SubscriptionFee, PaymentPeriod in Payments
* Operations: filter for last month in June, group by company, and sort by revenue

_Output_
```sql
SELECT AccountsReceivable.CompanyID,
  -- Include CompanyName to provide an interpretable response for the user.
  AccountsReceivable.CompanyName,
  -- Alias should not include spaces and should match the casing from existing columns
  SUM(Payments.SubscriptionFee) AS TotalSubscribeFee
FROM AccountsReceivable
INNER JOIN Payments ON AccountsReceivable.CompanyID = Payments.CompanyID
WHERE Payments.PaymentPeriod = 'June'
GROUP BY AccountsReceivable.CompanyID, AccountsReceivable.CompanyName
-- Focus on cumulative subscription fees rather than individual fees exceeding $1000 because the focus is on unique companies, not unique payments
HAVING SUM(Payments.SubscriptionFee) > 1000
ORDER BY TotalSubscribeFee DESC;
```
---
For our real case, we also have a random (unordered) sample of rows for additional context:
{data_preview}

_Conversation History_
{history}
Thought: {thought}

_Dialogue State_
{valid_tab_col}
* Operations: {operations}

_Explanation_
We will use the conversation history, dialogue state and data preview to generate a high quality, directly executable SQL query.
{pref_reminder}
_Output_
"""

sql_query_plan_prompt = """You are an outstanding data analyst who is exceptionally skilled at writing SQL queries.
Currently, we are in the middle of a multi-step analysis, and we are currently working on step {step_number}: {step_description}
Your task is to generate an accurate SQL query that is able to execute this operation.

To provide additional context, you will be given the overall plan of action, a preview of the relevant data, the dialogue state, and (when applicable) the previous query.
The first step in the plan that is not marked as 'complete' is the current step. Only focus on generating a query for this step; Do NOT try to generate a query that covers multiple steps at once.
The data preview is a random sample of rows from likely relevant columns, while the full schema of valid columns is provided in the dialogue state.
If prior steps produced staging tables, you will be given the table name and the query used to generate it, which can serve as reference for the current situation or used as part of a CTE.

Remember, you are querying from DuckDB, so use the appropriate syntax and casing for operations, such as double quotes for wrapping irregular column names rather than backticks.
If the operation is ambiguous or problematic, such as a request for a non-existent column, please output 'Error:' followed by a short phrase to describe the issue (eg. 'Error: missing column' or 'Error: unclear start date').
The query results will be displayed to the user, so please include any columns that would help them interpret the results.
Furthermore, computed columns should be given user-friendly aliases that are short (3 words max), simple (avoids special characters), and easy to understand.
When calculating a percentage, DO NOT multiply by 100. When performing any division operation, always return the result with at least 4 decimal places of precision.

Please start by generating some pseudo-code as a comment to outline the high-level structure of the query, and then proceed to fill in the details.
This is very important to my career, please be sure to only output a valid SQL query that is directly executable with no further explanations after the query.

For example,
---
_Plan of Action_
1. query - Create a unified view of the customer journey that limits the scope by filtering for deals that have closed and drops any irrelevant columns
2. compute - figure out the average time to complete the total sales cycle. Metric: Average Deal Velocity (ADV)
3. segment - break down deal velocity by each of the different stage we can measure. Variables: sales qualification, technical validation, contract negotiation, closing period, marketing to sales handoff
4. plot - visualize the average sales cycle with a bar chart that shows the average time spent in each stage

_Data Preview_
| stage             | deal_size | close_date | first_touch_date | first_contact_date| discovery_date | demo_date  | contract_sent | outreach_date |
|-------------------|-----------|------------|------------------|-------------------|----------------|------------|---------------|---------------|
| Contract Sent     | 125000    | 2025-06-15 | <N/A>            | 2024-12-28        | 2025-01-19     | 2025-02-12 | 2025-03-15    | 2024-12-12    |
| Negotiation       | 43000     | 2025-07-21 | <N/A>            | 2024-12-10        | 2024-12-24     | 2025-01-15 | 2025-02-10    | 2024-11-22    |
| Tech Validation   | 310000    | 2025-05-29 | <N/A>            | 2025-01-20        | 2025-02-07     | 2025-02-25 | None          | 2025-01-05    |
| Negotiation       | 62000     | 2025-08-01 | <N/A>            | 2024-12-28        | 2025-01-09     | 2025-01-28 | None          | 2024-12-03    |
| Discovery         | 95000     | NULL       | <N/A>            | 2024-12-05        | None           | None       | None          | 2024-11-15    |
| Discovery         | 180000    | 2025-05-21 | <N/A>            | 2025-02-12        | 2025-03-01     | None       | None          | 2025-01-22    |
| Tech Validation   | 540000    | 2025-07-12 | <N/A>            | 2024-11-20        | 2024-12-05     | 2025-01-02 | None          | 2024-10-19    |
| Negotiation       | 78000     | 2025-05-31 | <N/A>            | 2024-12-22        | 2025-01-10     | 2025-02-01 | 2025-03-01    | 2024-11-29    |

_Dialogue State_
* Goal: Average Deal Velocity (ADV)
* Tables: Salesforce; Hubspot
* Columns: opportunity_id, stage, deal_size, close_date, first_contact_date, last_contact_date, lead_source, lead_score, deal_size, account_size, owner_id, product_type, discovery_date, demo_date, contract_sent, industry, payment_terms in Salesforce;
lead_id, source, qualified, propensity_score, email, company_name, contact_name, first_touch_channel, first_touch_date, outreach_date, num_page_visits, form_submissions, opp_id in Hubspot
* Thought: The user has mentioned that we only care closed deals, so we should filter for deals that have a non-null close date. We should also drop any empty columns since they are not helpful.

_Previous Queries_
N/A

_Explanation_
One key motivation for querying is to limit the number of columns to help focus the analysis. Based on the preview, we can drop the first_touch_date column since it is always null.

_Output_
```sql
-- Create view for the customer journey
SELECT
  -- Include columns for contextualizing the deal
  sf.opportunity_id, sf.deal_size, sf.stage,
  -- Include date fields required for calculating deal velocity
  hs.outreach_date,
  sf.first_contact_date,
  sf.discovery_date,
  sf.demo_date,
  sf.contract_sent,
  sf.close_date
  -- Ignore first_touch_date since it is always null
FROM Salesforce sf
JOIN Hubspot hs ON sf.opportunity_id = hs.opp_id
WHERE
  -- Filter for closed deals only
  sf.close_date IS NOT NULL
ORDER BY sf.close_date DESC;
```

_Plan of Action_
1. query - Create a cohort of one month that filters for users who signed up a year ago. Variables: total_ad_cost, recurring_revenue, conversion_value
2. compute - calculate the customer acquisition cost based on total ad cost. Metrics: CAC
3. compute - calculate lifetime value by summing up all past revenue, and then apply a 10% discount rate to account for future value, extending out for three years. Metrics: LTV
4. describe - compare the customer LTV to CAC to review whether our actions are sustainable, flag any concerning trends

_Data Preview_
| cost_micros | conversion_value_micros| mrr_cents | billing_cycle_anchor | created_at_utc | date       |
|-------------|------------------------|-----------|----------------------|----------------|------------|
| 3750000     | 12500000               | 4900      | 2025-01-15           | 2024-12-10     | 12/10/2024 |
| 8920000     | 19800000               | 9900      | 2025-02-01           | 2025-01-21     | 01/21/2025 |
| 1250000     | 0                      | 2900      | 2025-01-05           | 2024-12-20     | 12/19/2024 |
| 5620000     | 28700000               | 14900     | 2025-02-12           | 2025-01-28     | 01/28/2025 |
| 9100000     | 6800000                | 4900      | 2025-03-01           | 2025-02-15     | 02/14/2025 |
| 2350000     | 19500000               | 9900      | 2025-01-20           | 2025-01-05     | 01/04/2025 |
| 7400000     | 31200000               | 24900     | 2025-02-28           | 2025-02-10     | 02/09/2025 |
| 4800000     | 0                      | 0         | 2025-01-25           | 2025-01-10     | 01/10/2025 |

_Dialogue State_
* Goal: LTV to CAC Ratio
* Tables: Stripe_Subscriptions_Raw; GAds_Spend_Export; AI_Usage_Metrics (Prod)
* Columns: subscription_id, customer_id, current_plan_name, mrr_cents, billing_cycle_anchor, trial_end_date, payment_failure_count, discount_code_applied, initial_plan_name, created_at_utc in Stripe_Subscriptions_Raw;
campaign_id, campaign_name, ad_group_id, date, cost_micros, clicks, impressions, utm_medium, utm_campaign, landing_page_path, device_type, conversion_tracking_id, bidding_strategy, quality_score, conversion_value_micros, final_url_suffix in GAds_Spend_Export;
user_email, prompt_id, content_type, tokens_consumed, prompt_cost_usd, accepted_suggestion, generated_timestamp, workspace_id, model_version, prompt_template_name in AI_Usage_Metrics (Prod)
* Thought: Before calculating metrics, I should query the data to rename columns and filter for the right time period. I will avoid calculating any variables, since that is reserved for future steps.

_Previous Queries_
N/A

_Output_
```sql
SELECT
  -- Core subscription data for LTV calculation
  s.customer_id,
  s.mrr_cents,
  s.current_plan_name,
  s.created_at_utc,
  s.billing_cycle_anchor,
  -- Key ad data for CAC calculation
  g.campaign_id,
  g.cost_micros / 1000000.0 AS ad_cost_usd,
  g.conversion_value_micros / 1000000.0 AS conversion_value_usd,
  g.date AS ad_click_date,
  -- Minimal usage metrics that might affect LTV
  u.tokens_consumed,
  u.prompt_cost_usd
FROM Stripe_Subscriptions_Raw s
LEFT JOIN GAds_Spend_Export g ON DATE(g.date) = DATE(s.created_at_utc)
LEFT JOIN "AI_Usage_Metrics (Prod)" u ON s.customer_id = u.user_email
WHERE
  -- Filter for users who signed up in January 2024
  s.created_at_utc >= '2024-01-01' AND
  s.created_at_utc < '2024-02-01'
ORDER BY s.created_at_utc;
```

_Plan of Action_
1. query - create a view of purchases from last three months only and combine the data to get flavor and age group information
2. pivot - sum up total volume (purchase_id) by flavor and age group, creating a new aggregated table
3. segment - for each type (young, teen, adult, senior), sort flavors by total volume to identify the most popular flavors per segment
4. describe - present the top flavors for each group, showing relative market share and highlighting any notable differences between segments

_Data Preview_
| fv_id | age_group | flavor         | total_volume |
|-------|-----------|----------------|--------------|
| 1     | young     | chocolate      | 100          |
| 2     | young     | vanilla        | 80           |
| 3     | young     | strawberry     | 60           |
| 4     | teen      | chocolate      | 120          |

_Dialogue State_
* Goal: Flavor Popularity
* Tables: flavor_volume
* Columns: fv_id, age_group, flavor, total_volume in flavor_volume table
* Thought: I should query the data to rename columns and filter for the right time period. I will avoid calculating any variables, since that is reserved for future steps.

_Previous Queries_
N/A

_Explanation_
This is a simple query, so we do not need to overcomplicate it with partitioning or window functions.

_Output_
```sql
SELECT flavor, total_volume
FROM flavor_volume
WHERE age_group = 'teen'
ORDER BY total_volume DESC
LIMIT 3;
```

_Plan of Action_
1. peek (complete) - look for anomalies in delivery_timestamp to ensure we have the date range we need, check that unsubscribe_flag is not set to True for all records
2. pivot (complete) - calculate delivery rate, open rate, click-thru rate, and unsubscribe rate, focused on the last year and grouped by campaign
3. insert (complete) - add rows for the mean, standard deviation, and number of campaigns for each metric to serve as a baseline
4. insert (complete) - add an additional row that filters for just the performance of the Knock Your Socks Off campaign
5. query - create a view that calculates a p-value for each of the four key metrics by comparing the target cohort to the baseline statistics

_Data Preview_
| Campaign                | Delivery Rate | Open Rate | Click-Through Rate | Unsubscribe Rate |
|-------------------------|---------------|-----------|--------------------|------------------|
| All Campaigns (Mean)    | 98.2%         | 22.4%     | 3.8%               | 0.12%            |
| All Campaigns (Std Dev) | 0.8%          | 4.2%      | 1.1%               | 0.05%            |
| Number of Campaigns     | 27            | 27        | 27                 | 27               |
| Knock Your Socks Off    | 99.1%         | 28.7%     | 5.2%               | 0.08%            |

_Dialogue State_
* Goal: Significance Testing
* Tables: constant_contact_campaigns; amplitude_analytics; Conferences List (Updated Jan 2025)
* Columns: campaign_id, campaign_name, template_variant, sender_email_alias, target_segment_id, subject_line, preview_text, utm_campaign_code, scheduled_datetime, actual_send_datetime;
amp_id, campaign_id, delivery_timestamp, recipient_email_hash, device_type, email_client, bounce_type, open_count, click_count, unsubscribe_flag;
conference_id, conference_name, organizer_entity, venue_name, city_location, state_province, expected_attendance, booth_number, booth_size_sqft, sponsorship_tier
* Thought: I should use the staging table to calculate the p-values for each metric since it has already calculated the baselines for each campaign.

_Previous Queries_
-- Step 2: BaselineStatistics
WITH campaign_metrics AS (
  -- Join campaign data with analytics data for the last year
  SELECT
    cc.campaign_id,
    cc.campaign_name,
    COUNT(aa.amp_id) AS total_sent,
    SUM(CASE WHEN aa.bounce_type IS NULL THEN 1 ELSE 0 END) AS delivered,
    SUM(CASE WHEN aa.open_count > 0 THEN 1 ELSE 0 END) AS opened,
    SUM(CASE WHEN aa.click_count > 0 THEN 1 ELSE 0 END) AS clicked,
    SUM(CASE WHEN aa.unsubscribe_flag = TRUE THEN 1 ELSE 0 END) AS unsubscribed
  FROM constant_contact_campaigns cc
  JOIN amplitude_analytics aa ON cc.campaign_id = aa.campaign_id
  -- Filter for the last year
  WHERE aa.delivery_timestamp >= DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR)
  GROUP BY cc.campaign_id, cc.campaign_name
)
-- Calculate rates for each campaign
SELECT
  campaign_name AS "Campaign",
  ROUND((delivered / total_sent) * 100, 4) AS "Delivery Rate",
  ROUND((opened / delivered) * 100, 4) AS "Open Rate",
  ROUND((clicked / opened) * 100, 4) AS "Click-Through Rate",
  ROUND((unsubscribed / delivered) * 100, 4) AS "Unsubscribe Rate"
FROM campaign_metrics
ORDER BY campaign_name;
```

_Output_
```sql
-- Rather than recalculating the rates, we can just use the existing results
SELECT
  -- Delivery Rate p-value (using Z-test)
  (1 - NORM_DIST(
    ABS((0.991 - 0.982) / (0.008 / SQRT(27)))
  ) * 2) AS "Delivery Rate p-value",
  -- Open Rate p-value
  (1 - NORM_DIST(
    ABS((0.287 - 0.224) / (0.042 / SQRT(27)))
  ) * 2) AS "Open Rate p-value",
  -- Click-Through Rate p-value
  (1 - NORM_DIST(
    ABS((0.052 - 0.038) / (0.011 / SQRT(27)))
  ) * 2) AS "Click-Through Rate p-value",
  -- Unsubscribe Rate p-value
  (1 - NORM_DIST(
    ABS((0.0008 - 0.0012) / (0.0005 / SQRT(27)))
  ) * 2) AS "Unsubscribe Rate p-value",
  -- Percentage differences
  ROUND((0.991 / 0.982) - 1, 4) AS "Delivery Rate Diff",
  ROUND((0.287 / 0.224) - 1, 4) AS "Open Rate Diff",
  ROUND((0.052 / 0.038) - 1, 4) AS "Click Rate Diff",
  ROUND((0.0008 / 0.0012) - 1, 4) AS "Unsub Rate Diff"
```
---
Now it's your turn to generate an accurate, directly executable SQL query.

_Plan of Action_
{overall_plan}

_Data Preview_
{data_preview}

_Dialogue State_
* Goal: {goal}
{valid_tab_col}
* Thought: {thought}

_Previous Queries_
{previous_queries}

_Explanation_
We will use the dialogue state and data preview to generate a high quality, directly executable SQL query to complete the current step of the plan.
{pref_reminder}
_Output_
"""

sql_chart_plan_prompt = """You are an outstanding data analyst who is exceptionally skilled at writing SQL queries.
Currently, we are in the middle of a multi-step analysis, and we are currently working on step {step_number}: {step_description}
Your task is to generate an accurate SQL query for visualizing a chart or figure, so focus on the most pertinent columns for telling a story.

To provide additional context, you will be given the overall plan of action, a preview of the relevant data, the dialogue state, and (when applicable) the previous queries.
The first step in the plan that is not marked as 'complete' is the current step. Only focus on generating a query for plotting; Do NOT try to generate a query that covers any other steps in the plan.
The data preview is a random sample of rows from likely relevant columns, while the full schema of valid columns is provided in the dialogue state.
If prior steps produced staging tables, you will be given the previously executed queries, which can serve as reference for the current situation.

Remember, you are querying from DuckDB, so use the appropriate syntax and casing for operations, such as double quotes for wrapping irregular column names rather than backticks.
The query results will be displayed to the user through Plotly Express, so please include any columns that would help the plotting function interpret the results.
Furthermore, computed columns should be given short aliases (3 words max) and simple (avoids special characters) since they will be used as labels in the chart.
Pay attention to the schema since this can inform what to use for x-axis (usually a categorical variable) or y-axis (usually a numeric variable), as well as knowing when to cast to a float before division.

Please start by generating some pseudo-code as a comment to outline the high-level structure of the query, and then proceed to fill in the details.
This is very important to my career, please be sure to only output a valid SQL query that is directly executable, with no further explanations after the query.

For example,
---
_Plan of Action_
1. peek (complete) - examine the google_ad_groups table to validate data types and check for missing or outlier values in all the key variables
2. pivot (complete) - group data by 'Ad Group Name' and aggregate sums for Impressions, Clicks, Sign up, Sign up Conversion, and Amount spent
3. compute (complete) - calculate key performance metrics for each ad group: CTR (Clicks/Impressions), CVR (Sign up/Clicks), and CPA (Amount spent/Sign up)
4. plot - graph out the top 5 ad groups based on CVR, then CTR, and CPA to determine which ones are doing best, remembering that we need to normalize for scale

_Data Preview_
| Ad Group Name             | Impressions | Clicks | Conversions | Newsletter Sign up | Amount spent |
|---------------------------|-------------|--------|-------------|--------------------|--------------|
| Targeted Remarketing      | 1460        | 250    | 110         | 35                 | 100          |
| Family Mealtime           | 1580        | 175    | 95          | 30                 | 150          |
| Holiday Gift Sets         | 1350        | 150    | 60          | 25                 | 200          |
| Unbreakable Eco Solutions | 1310        | 165    | 93          | 30                 | 130          |
| Materials Education       | 1280        | 160    | 62          | 24                 | 120          |
| Energy Efficiency Tips    | 1820        | 140    | 28          | 10                 | 80           |
| Sustainable Home/Office   | 1170        | 145    | 29          | 15                 | 90           |
| EverWare Brand Terms      | 1920        | 155    | 81          | 28                 | 110          |

_Dialogue State_
* Goal: Ad Group Optimization
* Tables: google_ad_groups; klaviyo_emails
* Columns: Ad Group Name, Impressions, Clicks, Conversions, Newsletter Sign up, Amount spent;
Campaign Name, Lifecycle, Sent Date, Opened, Clicked, Unsubscribed in klaviyo_emails
* Thought: After calculating the key metrics, we should normalize for scale since CPA is a dollar amount and not directly comparable to the percentages from CTR and CVR.

_Previous Queries_
-- Step 2: ad_group_metrics
SELECT "Ad Group Name",
  SUM("Impressions") AS impressions,
  SUM("Clicks") AS clicks,
  SUM("Conversions") AS conversions,
  SUM("Newsletter Sign up") AS newsletter_signup,
  SUM("Amount spent") AS amount_spent
FROM google_ad_groups
GROUP BY "Ad Group Name";

-- Step 3:
SELECT "Ad Group Name",
  clicks / impressions AS CTR,
  conversions / clicks AS CVR,
  amount_spent / conversions AS CPA
FROM ad_group_metrics;

_Explanation_
Prior queries have calculated the key metrics for each ad group, so we can build on top of that to generate a plot.

_Output_
```sql
-- Step 4: Prepare data for visualization of top performing ad groups with normalized metrics
WITH performance_metrics AS (
  SELECT "Ad Group Name",
    ROUND((clicks::float / impressions) * 100, 2) AS CTR,
    ROUND((conversions::float / clicks) * 100, 2) AS CVR,
    ROUND(amount_spent::float / conversions, 2) AS CPA
  FROM ad_group_metrics
),
-- Normalize metrics to a 0-100 scale using min-max normalization
normalized_metrics AS (
  SELECT "Ad Group Name", CTR, CVR, CPA,
    -- Normalize CTR (higher is better)
    100 * (CTR - MIN(CTR) OVER()) / NULLIF((MAX(CTR) OVER() - MIN(CTR) OVER()), 0) AS norm_CTR,
    -- Normalize CVR (higher is better)
    100 * (CVR - MIN(CVR) OVER()) / NULLIF((MAX(CVR) OVER() - MIN(CVR) OVER()), 0) AS norm_CVR,
    -- Normalize CPA (lower is better, so invert)
    100 * (MAX(CPA) OVER() - CPA) / NULLIF((MAX(CPA) OVER() - MIN(CPA) OVER()), 0) AS norm_CPA,
    -- Combined score (equal weight to all three metrics)
    ROW_NUMBER() OVER (ORDER BY (CVR * 0.4) + (CTR * 0.3) - (CPA * 0.3) DESC) AS rank
  FROM performance_metrics
)
-- Select top 5 ad groups based on combined performance
SELECT
  "Ad Group Name", CTR, CVR, CPA,
  ROUND(norm_CTR, 1) AS normalized_CTR,
  ROUND(norm_CVR, 1) AS normalized_CVR,
  ROUND(norm_CPA, 1) AS normalized_CPA,
  -- Provide a performance score for visualization
  ROUND((norm_CTR + norm_CVR + norm_CPA) / 3, 1) AS overall_score
FROM normalized_metrics
WHERE rank <= 5
ORDER BY rank;
```

_Plan of Action_
1. query (complete) - Create a unified view of the customer journey that limits the scope by filtering for deals that have closed and drops any irrelevant columns
2. compute (complete) - figure out the average time to complete the total sales cycle. Metric: Average Deal Velocity (ADV)
3. segment (complete) - break down deal velocity by each of the different stage we can measure. Variables: sales qualification, technical validation, contract negotiation, closing period, marketing to sales handoff
4. plot - visualize the average sales cycle with a bar chart that shows the average time spent in each stage

_Data Preview_
| Stage                | Avg Days |
|--------------------- |----------|
| Marketing to Sales   |  1.4     |
| Sales Qualification  |  2.5     |
| Technical Validation |  3.2     |
| Contract Negotiation |  4.1     |
| Closing Period       |  2.8     |

_Dialogue State_
* Goal: Average Deal Velocity (ADV)
* Tables: Salesforce; Hubspot
* Columns: opportunity_id, stage, deal_size, close_date, first_contact_date, last_contact_date, lead_source, lead_score, deal_size, account_size, owner_id, product_type, discovery_date, demo_date, contract_sent, industry, payment_terms in Salesforce;
lead_id, source, qualified, propensity_score, email, company_name, contact_name, first_touch_channel, first_touch_date, outreach_date, num_page_visits, form_submissions, opp_id in Hubspot
* Thought: The user has mentioned that we only care closed deals, so we should filter for deals that have a non-null close date. We should also drop any empty columns since they are not helpful.

_Previous Queries_
-- Step 3:
WITH deal_timeline AS (
  SELECT sf.opportunity_id,
    DATEDIFF(day, hs.outreach_date, sf.first_contact_date) AS marketing_to_sales_days,
    DATEDIFF(day, sf.first_contact_date, sf.discovery_date) AS sales_qualification_days,
    DATEDIFF(day, sf.discovery_date, sf.demo_date) AS technical_validation_days,
    DATEDIFF(day, sf.demo_date, sf.contract_sent) AS contract_negotiation_days,
    DATEDIFF(day, sf.contract_sent, sf.close_date) AS closing_period_days
  FROM Salesforce sf
  LEFT JOIN Hubspot hs ON sf.opportunity_id = hs.opp_id
)
SELECT 'Marketing to Sales' AS Stage,
  AVG(CASE WHEN marketing_to_sales_days >= 0 THEN marketing_to_sales_days ELSE NULL END) AS "Avg Days"
FROM deal_timeline
WHERE marketing_to_sales_days IS NOT NULL
UNION ALL

SELECT 'Sales Qualification' AS Stage,
  AVG(CASE WHEN sales_qualification_days >= 0 THEN sales_qualification_days ELSE NULL END) AS "Avg Days"
FROM deal_timeline
WHERE sales_qualification_days IS NOT NULL
UNION ALL

SELECT 'Technical Validation' AS Stage,
  AVG(CASE WHEN technical_validation_days >= 0 THEN technical_validation_days ELSE NULL END) AS "Avg Days"
FROM deal_timeline
WHERE technical_validation_days IS NOT NULL
UNION ALL

SELECT 'Contract Negotiation' AS Stage,
  AVG(CASE WHEN contract_negotiation_days >= 0 THEN contract_negotiation_days ELSE NULL END) AS "Avg Days"
FROM deal_timeline
WHERE contract_negotiation_days IS NOT NULL
UNION ALL

SELECT 'Closing Period' AS Stage,
  AVG(CASE WHEN closing_period_days >= 0 THEN closing_period_days ELSE NULL END) AS "Avg Days"
FROM deal_timeline
WHERE closing_period_days IS NOT NULL

ORDER BY
  CASE 
    WHEN Stage = 'Marketing to Sales' THEN 1
    WHEN Stage = 'Sales Qualification' THEN 2
    WHEN Stage = 'Technical Validation' THEN 3
    WHEN Stage = 'Contract Negotiation' THEN 4
    WHEN Stage = 'Closing Period' THEN 5
  END;
```

_Explanation_
The segment step (step 3) has already built a staging table for us to plot, so we should just use the same query again rather than re-inventing the wheel.

_Output_
```sql
WITH deal_timeline AS (
  SELECT sf.opportunity_id,
    DATEDIFF(day, hs.outreach_date, sf.first_contact_date) AS marketing_to_sales_days,
    DATEDIFF(day, sf.first_contact_date, sf.discovery_date) AS sales_qualification_days,
    DATEDIFF(day, sf.discovery_date, sf.demo_date) AS technical_validation_days,
    DATEDIFF(day, sf.demo_date, sf.contract_sent) AS contract_negotiation_days,
    DATEDIFF(day, sf.contract_sent, sf.close_date) AS closing_period_days
  FROM Salesforce sf
  LEFT JOIN Hubspot hs ON sf.opportunity_id = hs.opp_id
)
SELECT 'Marketing to Sales' AS Stage,
  AVG(CASE WHEN marketing_to_sales_days >= 0 THEN marketing_to_sales_days ELSE NULL END) AS "Avg Days"
FROM deal_timeline
WHERE marketing_to_sales_days IS NOT NULL
UNION ALL

SELECT 'Sales Qualification' AS Stage,
  AVG(CASE WHEN sales_qualification_days >= 0 THEN sales_qualification_days ELSE NULL END) AS "Avg Days"
FROM deal_timeline
WHERE sales_qualification_days IS NOT NULL
UNION ALL

SELECT 'Technical Validation' AS Stage,
  AVG(CASE WHEN technical_validation_days >= 0 THEN technical_validation_days ELSE NULL END) AS "Avg Days"
FROM deal_timeline
WHERE technical_validation_days IS NOT NULL
UNION ALL

SELECT 'Contract Negotiation' AS Stage,
  AVG(CASE WHEN contract_negotiation_days >= 0 THEN contract_negotiation_days ELSE NULL END) AS "Avg Days"
FROM deal_timeline
WHERE contract_negotiation_days IS NOT NULL
UNION ALL

SELECT 'Closing Period' AS Stage,
  AVG(CASE WHEN closing_period_days >= 0 THEN closing_period_days ELSE NULL END) AS "Avg Days"
FROM deal_timeline
WHERE closing_period_days IS NOT NULL

ORDER BY
  CASE 
    WHEN Stage = 'Marketing to Sales' THEN 1
    WHEN Stage = 'Sales Qualification' THEN 2
    WHEN Stage = 'Technical Validation' THEN 3
    WHEN Stage = 'Contract Negotiation' THEN 4
    WHEN Stage = 'Closing Period' THEN 5
  END;
```

_Plan of Action_
1. peek (complete) - consider campaign_name, adset_name, referring_site, utm_parameters, first_utm_source, and last_utm_source columns to understand how the channels are related and normalize their format if necessary
2. pivot (complete) - combine the Facebook, Shopify, and Klayvio tables to create user journeys for each customer, keeping only the relevant columns for storing variables
3. segment (complete) - calculate channel contribution to ROAS and purchases using first-touch attribution
4. segment (complete) - calculate channel contribution to ROAS and purchases using last-touch attribution
5. segment (complete) - calculate channel contribution to ROAS and purchases using linear attribution
6. plot - aggregate results to rank the performance across channels and show the results in a graph

_Dialogue State_
* Goal: Multi-touch Attribution
* Tables: facebook_ads_manager_daily; shopify_orders_202401; klayvio_customer_timeline
* Columns: ad_id, campaign_name, adset_name, placement_type, daily_spend_cents, video_completion_rate, cta_button_type, audience_name, creative_format, instagram_eligible;
order_id, cart_token, landing_site_path, referring_site, discount_code_used, shipping_method, billing_postal_code, product_collection, total_price_cents, utm_parameters;
shopper_id, event_name, event_timestamp, device_fingerprint, last_utm_source, first_utm_source, session_number, cart_value_cents, products_viewed, time_to_purchase_sec
* Thought: I should first figure out a way to join all the tables together to form a single view of the customer journey. Then, I need to loop through the three attribution models, since each one calculates a metric broken down by channel, the 'segment' operation is a great fit. Ranking and plotting results is the final step.

_Data Preview_
N/A

_Previous Queries_
-- Step 3:
SELECT 'First-Touch' AS Attribution_Model,
  channel, SUM(ROAS) AS ROAS,
  SUM(Purchases) AS Purchases
FROM first_touch_attribution
GROUP BY channel
-- Step 4:
SELECT 'Last-Touch' AS Attribution_Model,
  channel, SUM(ROAS) AS ROAS,
  SUM(Purchases) AS Purchases
FROM last_touch_attribution
GROUP BY channel
-- Step 5:
SELECT 'Linear' AS Attribution_Model,
  channel, SUM(ROAS) AS ROAS,
  SUM(Purchases) AS Purchases
FROM linear_attribution
GROUP BY channel

_Output_
```sql
-- Combine the results from the three attribution models to rank the performance across channels
SELECT channel, SUM(ROAS) AS ROAS, SUM(Purchases) AS Purchases
FROM (
  SELECT 'First-Touch' AS Attribution_Model, channel, ROAS, Purchases
  FROM first_touch_attribution
  UNION ALL
  SELECT 'Last-Touch' AS Attribution_Model, channel, ROAS, Purchases
  FROM last_touch_attribution
  UNION ALL
  SELECT 'Linear' AS Attribution_Model, channel, ROAS, Purchases
  FROM linear_attribution
) AS combined_results
GROUP BY channel
```

_Plan of Action_
1. peek (complete) - look for anomalies in delivery_timestamp to ensure we have the date range we need, check that unsubscribe_flag is not set to True for all records
2. pivot (complete) - calculate delivery rate, open rate, click-thru rate, and unsubscribe rate, focused on the last year and grouped by campaign
3. plot - graph out the top 5 campaigns based on each of the four key metrics to determine which ones are doing best

_Data Preview_
| Campaigns               | Delivery Rate | Open Rate | Click-Through Rate | Unsubscribe Rate |
|-------------------------|---------------|-----------|--------------------|------------------|
| New Year's Eve Sale     | 98.2%         | 22.4%     | 3.8%               | 0.12%            |
| Party Like It's 2024    | 24.8%         | 4.2%      | 1.1%               | 0.05%            |
| Mother's Day Sale       | 27.2%         | 23.5%     | 3.6%               | 0.07%            |
| Knock Your Socks Off    | 29.1%         | 28.7%     | 5.2%               | 0.08%            |
| Spring Clearance Sale   | 31.4%         | 30.2%     | 4.5%               | 0.06%            |
[17 other rows ...]

_Dialogue State_
* Goal: Significance Testing
* Tables: constant_contact_campaigns; amplitude_analytics; Conferences List (Updated Jan 2025)
* Columns: campaign_id, campaign_name, template_variant, sender_email_alias, target_segment_id, subject_line, preview_text, utm_campaign_code, scheduled_datetime, actual_send_datetime;
amp_id, campaign_id, delivery_timestamp, recipient_email_hash, device_type, email_client, bounce_type, open_count, click_count, unsubscribe_flag;
conference_id, conference_name, organizer_entity, venue_name, city_location, state_province, expected_attendance, booth_number, booth_size_sqft, sponsorship_tier
* Thought: I can use the pivot table and just limit to the top 5 to make chart readable.

_Previous Queries_
-- Step 2:
WITH campaign_metrics AS (
  -- Join campaign data with analytics data for the last year
  SELECT
    cc.campaign_id,
    cc.campaign_name,
    COUNT(aa.amp_id) AS total_sent,
    SUM(CASE WHEN aa.bounce_type IS NULL THEN 1 ELSE 0 END) AS delivered,
    SUM(CASE WHEN aa.open_count > 0 THEN 1 ELSE 0 END) AS opened,
    SUM(CASE WHEN aa.click_count > 0 THEN 1 ELSE 0 END) AS clicked,
    SUM(CASE WHEN aa.unsubscribe_flag = TRUE THEN 1 ELSE 0 END) AS unsubscribed
  FROM constant_contact_campaigns cc
  JOIN amplitude_analytics aa ON cc.campaign_id = aa.campaign_id
  -- Filter for the last year
  WHERE aa.delivery_timestamp >= DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR)
  GROUP BY cc.campaign_id, cc.campaign_name
)
-- Calculate rates for each campaign
SELECT
  campaign_name AS "Campaign",
  ROUND((delivered / total_sent) * 100, 2) AS "Delivery Rate",
  ROUND((opened / delivered) * 100, 2) AS "Open Rate",
  ROUND((clicked / opened) * 100, 2) AS "Click-Through Rate",
  ROUND((unsubscribed / delivered) * 100, 3) AS "Unsubscribe Rate"
FROM campaign_metrics
ORDER BY campaign_name;

_Output_
```sql
SELECT * FROM campaign_performance
LIMIT 5;
```
---
Now it's your turn to generate an accurate, directly executable SQL query.

_Plan of Action_
{overall_plan}

_Data Preview_
{data_preview}

_Dialogue State_
* Goal: {goal}
{valid_tab_col}
* Thought: {thought}

_Previous Queries_
{previous_queries}

_Explanation_
We will use the dialogue state and data preview to generate a high quality, directly executable SQL query to complete the current step of the plan.
{pref_reminder}
_Output_
"""

sql_pivot_plan_prompt = """You are an outstanding data analyst who is exceptionally skilled at writing SQL queries.
Currently, we are in the middle of a multi-step analysis, and we are currently working on step {step_number}: {step_description}
Your task is to generate an accurate SQL query to derive a staging table for future reference.

To provide additional context, you will be given the overall plan of action, a preview of the relevant data, the dialogue state, and possibly the previous queries.
The first step in the plan that is not marked as 'complete' is the current step. Just focus on this step; Do NOT try to generate a query that covers future steps in the plan.
The data preview is a random sample of rows from likely relevant columns, while the full schema of valid columns is provided in the dialogue state.
If prior steps generated a query, this will also be shown so you can use it as reference for the current situation or as part of a CTE.

Note that you should be writing a query that starts with SELECT with at least one GROUP BY operation - do not use CREATE to build a new table.
As a skilled analyst, you know the nuances of writing useful queries. For example, HAVING clause is rarely used in conjunction with the DISTINCT keyword.
You also know when asked to count how many of something exists, you should consider if a unique count makes sense, which implies using DISTINCT or GROUP BY when appropriate.
Remember, you are querying from DuckDB, use the appropriate syntax and casing for operations, such as double quotes for wrapping irregular column names rather than backticks.

The query results will be part of a larger plan, so please include any columns that would help the downstream analysis.
Computed columns should be given user-friendly aliases that are short (3 words max), simple (avoids special characters), and easy to understand.
The formatting of the column names should match the casing (lowercase, uppercase, titlecase) and spaces (or underscores) from existing columns.
When calculating a percentage, DO NOT multiply by 100. When performing any division operation, always return the result with at least 4 decimal places of precision.

Please start by generating some pseudo-code as a comment to outline the high-level structure of the query, and then proceed to fill in the details.
This is very important to my career, please be sure to only output a valid SQL query that is directly executable with no further explanations.

For example,
---
_Plan of Action_
1. query (complete) - Create a unified view of the customer journey that limits the scope by filtering for deals that have closed and drops any irrelevant columns
2. compute (complete) - figure out the average time to complete the total sales cycle. Metric: Average Deal Velocity (ADV)
3. pivot - break down deal velocity by each of the different stage we can measure. Variables: sales qualification, technical validation, contract negotiation, closing period, marketing to sales handoff
4. plot - visualize the average sales cycle with a bar chart that shows the average time spent in each stage

_Data Preview_
| stage             | deal_size | close_date | first_touch_date | first_contact_date| discovery_date | demo_date  | contract_sent | outreach_date |
|-------------------|-----------|------------|------------------|-------------------|----------------|------------|---------------|---------------|
| Contract Sent     | 125000    | 2025-06-15 | <N/A>            | 2024-12-28        | 2025-01-19     | 2025-02-12 | 2025-03-15    | 2024-12-12    |
| Negotiation       | 43000     | 2025-07-21 | <N/A>            | 2024-12-10        | 2024-12-24     | 2025-01-15 | 2025-02-10    | 2024-11-22    |
| Tech Validation   | 310000    | 2025-05-29 | <N/A>            | 2025-01-20        | 2025-02-07     | 2025-02-25 | None          | 2025-01-05    |
| Negotiation       | 62000     | 2025-08-01 | <N/A>            | 2024-12-28        | 2025-01-09     | 2025-01-28 | None          | 2024-12-03    |
| Discovery         | 95000     | 2025-06-10 | <N/A>            | 2024-12-05        | None           | None       | None          | 2024-11-15    |
| Discovery         | 180000    | 2025-05-21 | <N/A>            | 2025-02-12        | 2025-03-01     | None       | None          | 2025-01-22    |
| Tech Validation   | 540000    | 2025-07-12 | <N/A>            | 2024-11-20        | 2024-12-05     | 2025-01-02 | None          | 2024-10-19    |
| Negotiation       | 78000     | 2025-05-31 | <N/A>            | 2024-12-22        | 2025-01-10     | 2025-02-01 | 2025-03-01    | 2024-11-29    |

_Dialogue State_
* Goal: Average Deal Velocity (ADV)
* Tables: Salesforce; Hubspot
* Columns: opportunity_id, stage, deal_size, close_date, first_contact_date, last_contact_date, lead_source, lead_score, deal_size, account_size, owner_id, product_type, discovery_date, demo_date, contract_sent, industry, payment_terms in Salesforce;
lead_id, source, qualified, propensity_score, email, company_name, contact_name, first_touch_channel, first_touch_date, outreach_date, num_page_visits, form_submissions, opp_id in Hubspot
* Thought: The user has mentioned that we only care closed deals, so we should filter for deals that have a non-null close date. We should also drop any empty columns since they are not helpful.

_Previous Queries_
-- Step 1:
SELECT
  -- Include columns for contextualizing the deal
  sf.stage, sf.deal_size,
  -- Include date fields required for calculating deal velocity
  hs.first_touch_date,
  hs.outreach_date,
  sf.first_contact_date,
  sf.discovery_date,
  sf.demo_date,
  sf.contract_sent,
  sf.close_date
FROM Salesforce sf
JOIN Hubspot hs ON sf.opportunity_id = hs.opp_id
WHERE sf.close_date IS NOT NULL;

_Explanation_
One key motivation for querying is to limit the number of columns to help focus the analysis. Based on the preview, we can drop the first_touch_date column since it is always null.

_Output_
```sql
WITH deal_timeline AS (
  SELECT sf.opportunity_id,
    DATEDIFF(day, hs.outreach_date, sf.first_contact_date) AS marketing_to_sales_days,
    DATEDIFF(day, sf.first_contact_date, sf.discovery_date) AS sales_qualification_days,
    DATEDIFF(day, sf.discovery_date, sf.demo_date) AS technical_validation_days,
    DATEDIFF(day, sf.demo_date, sf.contract_sent) AS contract_negotiation_days,
    DATEDIFF(day, sf.contract_sent, sf.close_date) AS closing_period_days
  FROM Salesforce sf
  LEFT JOIN Hubspot hs ON sf.opportunity_id = hs.opp_id
)
SELECT 'Marketing to Sales' AS Stage,
  AVG(CASE WHEN marketing_to_sales_days >= 0 THEN marketing_to_sales_days ELSE NULL END) AS "Avg Days"
FROM deal_timeline
WHERE marketing_to_sales_days IS NOT NULL
UNION ALL

SELECT 'Sales Qualification' AS Stage,
  AVG(CASE WHEN sales_qualification_days >= 0 THEN sales_qualification_days ELSE NULL END) AS "Avg Days"
FROM deal_timeline
WHERE sales_qualification_days IS NOT NULL
UNION ALL

SELECT 'Technical Validation' AS Stage,
  AVG(CASE WHEN technical_validation_days >= 0 THEN technical_validation_days ELSE NULL END) AS "Avg Days"
FROM deal_timeline
WHERE technical_validation_days IS NOT NULL
UNION ALL

SELECT 'Contract Negotiation' AS Stage,
  AVG(CASE WHEN contract_negotiation_days >= 0 THEN contract_negotiation_days ELSE NULL END) AS "Avg Days"
FROM deal_timeline
WHERE contract_negotiation_days IS NOT NULL
UNION ALL

SELECT 'Closing Period' AS Stage,
  AVG(CASE WHEN closing_period_days >= 0 THEN closing_period_days ELSE NULL END) AS "Avg Days"
FROM deal_timeline
WHERE closing_period_days IS NOT NULL

ORDER BY
  CASE 
    WHEN Stage = 'Marketing to Sales' THEN 1
    WHEN Stage = 'Sales Qualification' THEN 2
    WHEN Stage = 'Technical Validation' THEN 3
    WHEN Stage = 'Contract Negotiation' THEN 4
    WHEN Stage = 'Closing Period' THEN 5
  END;
```

_Plan of Action_
1. insert (complete) - identify churned accounts from the Salesforce table to by looking at the policy status (renewal_date, payment_status). Variables: policy_status
2. pivot - combine claims history (claim_status, settlement_amount_usd, claim_type), risk assessments (building_age_years, flood_zone_category, property_type), and account characteristics into a single view
3. compute - analyze correlation between risk attributes and churned accounts to determine probability of churn. Metrics: Churn Probability
4. query - rank the policies by churn probability to help discover at-risk accounts in need of intervention

_Data Preview_
| sfdc_account | property_portfolio_value | annual_premium_usd | last_risk_assessment_date | payment_status | client_segment_tier | renewal_date | last_interaction_date |
|--------------|--------------------------|--------------------|---------------------------|----------------|---------------------|--------------|-----------------------|
| JVF935       | 500000                   | 10000              | 2024-12-02                | paid           | silver              | 2025-12-15   | 2024-12-15            |
| BCS883       | 750000                   | 15000              | 2024-11-20                | paid           | gold                | 2025-11-20   | 2024-11-20            |
| PED282       | 1000000                  | 20000              | 2024-10-20                | outstanding    | silver              | 2025-10-25   | 2024-10-25            |
| NNS023       | 1250000                  | 25000              | 2024-08-30                | paid           | bronze              | 2025-09-30   | 2024-09-30            |

_Dialogue State_
* Goal: Churned Accounts Analysis (churn)
* Tables: Salesforce; Claims History; Risk Assessments; Account Characteristics
* Columns: sfdc_account, property_portfolio_value, annual_premium_usd, last_risk_assessment_date, account_owner_email, payment_status, client_segment_tier, renewal_date, primary_contact_title, last_interaction_date;
claim_id, account_id, claim_type, reported_date, settlement_amount_usd, days_to_resolution, adjuster_notes, property_address, deductible_applied, claim_status;
building_age_years, flood_zone_category, property_type, policy_status, policy_expiration_date, policy_renewal_date, policy_premium_usd, policy_deductible_usd, policy_coverage_limit_usd;
* Thought: Before calculating metrics, I should pivot the data to filter for the key churn variables. I also need to summarize the risk factors into a single view. Then, computing the correlation should be straightforward.

_Previous Queries_
N/A

_Output_
```sql
SELECT
  -- Churn variables
  s.sfdc_account, s.payment_status, s.renewal_date,
  -- Risk factors
  r.building_age_years, r.flood_zone_category, r.property_type
FROM Salesforce s
JOIN Risk_Assessments r ON s.sfdc_account = r.account_id
WHERE
  -- Filter for relevant churn variables
  s.payment_status = 'outstanding' OR
  s.renewal_date IS NULL;
```

_Plan of Action_
1. peek (complete) - preview the purchases from last three months only and combine the data to get flavor and age group information
2. pivot - for each age group (young, teen, adult, senior), sum up total volume per flavor, then sort to identify the most popular flavors
3. describe - present the top flavors for each group, showing relative market share and highlighting any notable differences between segments

_Data Preview_
| fv_id | age_group | flavor         | total_volume |
|-------|-----------|----------------|--------------|
| 1     | young     | chocolate      | 100          |
| 2     | young     | vanilla        | 80           |
| 3     | young     | strawberry     | 60           |
| 4     | teen      | chocolate      | 120          |

_Dialogue State_
* Goal: Flavor Popularity (fp)
* Tables: flavor_volume
* Columns: fv_id, age_group, flavor, total_volume in flavor_volume table; 
* Thought: I should query the data to rename columns and filter for the right time period. I will avoid calculating any variables, since that is reserved for future steps.

_Previous Queries_
N/A

_Explanation_
This is a simple query, so we do not need to overcomplicate it with partitioning or window functions.

_Output_
```sql
SELECT flavor, total_volume
FROM flavor_volume
WHERE age_group = 'teen'
ORDER BY total_volume DESC
LIMIT 3;
```

_Plan of Action_
1. peek (complete) - look for anomalies in delivery_timestamp to ensure we have the date range we need, check that unsubscribe_flag is not set to True for all records
2. pivot - calculate delivery rate, open rate, click-thru rate, and unsubscribe rate, focused on the last year and grouped by campaign
3. insert - add rows for the mean, standard deviation, and number of campaigns for each metric to serve as a baseline
4. insert - add an additional row that filters for just the performance of the Knock Your Socks Off campaign
5. query - create a view that calculates a p-value for each of the four key metrics by comparing the target cohort to the baseline statistics

_Data Preview_
| campaign_id | delivery_timestamp       | bounce_type | open_count | click_count | unsubscribe_flag |
|-------------|--------------------------|-------------|------------|-------------|------------------|
| CAMP_47291  | 2024-08-12T14:23:45.000Z | NULL        | 3          | 1           | FALSE            |
| CAMP_47291  | 2024-08-12T14:25:12.000Z | HARD        | 0          | 0           | FALSE            |
| CAMP_83517  | 2024-11-03T09:15:32.000Z | NULL        | 1          | 0           | FALSE            |
| CAMP_83517  | 2024-11-03T09:15:45.000Z | NULL        | 5          | 2           | TRUE             |
| CAMP_92436  | 2025-01-22T16:45:27.000Z | SOFT        | 0          | 0           | FALSE            |
| CAMP_92436  | 2025-01-22T16:46:01.000Z | NULL        | 2          | 1           | FALSE            |
| CAMP_10583  | 2025-02-15T08:30:19.000Z | NULL        | 0          | 0           | TRUE             |
| CAMP_10583  | 2025-02-15T08:31:52.000Z | NULL        | 4          | 3           | FALSE            |

_Dialogue State_
* Goal: Significance Testing
* Tables: constant_contact_campaigns; amplitude_analytics; Conferences List (Updated Jan 2025)
* Columns: campaign_id, campaign_name, template_variant, sender_email_alias, target_segment_id, subject_line, preview_text, utm_campaign_code, scheduled_datetime, actual_send_datetime;
amp_id, campaign_id, delivery_timestamp, recipient_email_hash, device_type, email_client, bounce_type, open_count, click_count, unsubscribe_flag;
conference_id, conference_name, organizer_entity, venue_name, city_location, state_province, expected_attendance, booth_number, booth_size_sqft, sponsorship_tier
* Thought: I should first prepare the data to focus in on the last year and the variables of interest. Since we have so many metrics to compare, I will perform row-wise transformations to compute intermediate values at scale rather than calculating each metric separately.

_Previous Queries_
N/A

_Output_
```sql
WITH campaign_metrics AS (
  -- Join campaign data with analytics data for the last year
  SELECT
    cc.campaign_id,
    cc.campaign_name,
    COUNT(aa.amp_id) AS total_sent,
    SUM(CASE WHEN aa.bounce_type IS NULL THEN 1 ELSE 0 END) AS delivered,
    SUM(CASE WHEN aa.open_count > 0 THEN 1 ELSE 0 END) AS opened,
    SUM(CASE WHEN aa.click_count > 0 THEN 1 ELSE 0 END) AS clicked,
    SUM(CASE WHEN aa.unsubscribe_flag = TRUE THEN 1 ELSE 0 END) AS unsubscribed
  FROM constant_contact_campaigns cc
  JOIN amplitude_analytics aa ON cc.campaign_id = aa.campaign_id
  -- Filter for the last year
  WHERE aa.delivery_timestamp >= DATE_SUB(CURRENT_DATE(), INTERVAL 1 YEAR)
  GROUP BY cc.campaign_id, cc.campaign_name
)
-- Calculate rates for each campaign
SELECT
  campaign_name AS "Campaign",
  ROUND((delivered / total_sent) * 100, 4) AS "Delivery Rate",
  ROUND((opened / delivered) * 100, 4) AS "Open Rate",
  ROUND((clicked / opened) * 100, 4) AS "Click-Through Rate",
  ROUND((unsubscribed / delivered) * 100, 4) AS "Unsubscribe Rate"
FROM campaign_metrics
ORDER BY campaign_name;
```
---
Now it's your turn to generate an accurate, directly executable SQL query.

_Plan of Action_
{overall_plan}

_Data Preview_
{data_preview}

_Dialogue State_
* Goal: {goal}
{valid_tab_col}
* Thought: {thought}

_Previous Queries_
{previous_queries}

_Explanation_
We will use the dialogue state and data preview to generate a high quality, directly executable SQL query to complete the current step of the plan.
{pref_reminder}
_Output_
"""

sql_for_pivot_prompt = """You are an outstanding data analyst who is exceptionally skilled at writing SQL queries.
Given the conversation history and dialogue states, your task is to generate an accurate SELECT query to derive a staging table.
The conversation history is composed of user and agent utterances, occasionally interspersed with your own internal thoughts.
Using this information, please generate a SQL query that works with the data schema from your system prompt.

As a skilled analyst, you know the nuances of writing useful queries. For example, HAVING clause is rarely used in conjunction with the DISTINCT keyword.
You also know when asked to count how many of something exists, you should consider if a unique count makes sense, which implies using DISTINCT or GROUP BY when appropriate.
Note that you should be writing a query that starts with SELECT with at least one GROUP BY operation - do not use CREATE to build a new table.
When calculating a percentage, DO NOT multiply by 100. When performing any division operation, always return the result with at least 4 decimal places of precision.
If a query is ambiguous or problematic, such as a request for a non-existent column, please output 'Error:' followed by a short phrase to describe the issue (eg. 'Error: missing column' or 'Error: unclear start date').

Remember, you are querying from DuckDB, use the appropriate syntax and casing for operations, such as:
  * using double quotes for wrapping irregular column names rather than backticks
  * casting is done with `CAST(col_name AS DATE)` or `col_name::DATE` rather than `DATE(col_name)`
  * concatenation is written as `username || '@' || domain` rather than `CONCAT(username, '@', domain)`

The query results will be displayed to the user, so please include any columns that would help them interpret the results.
Furthermore, computed columns should be given user-friendly aliases that are short (3 words max), simple (avoids special characters), and easy to understand.
The formatting of the column names should match the casing (lowercase, uppercase, titlecase) and spaces (or underscores) from existing columns.
This is very important to my career, please be sure to only output a valid SQL query containing comments and code.
The query should be directly executable, so do NOT include any additional text or explanations after the query.

For example,
---
_Conversation History_
User: What was the largest shipment delivered in February?
Agent: The largest shipment contained 5307 boxes.
User: What are the minimum and maximum shipments each day that month?
Thought: The Shipments table has column for the number of boxes, which can be used to calculate the size. I also need to filter for February, and group by day.

_Dialogue State_
* Tables: Shipments
* Columns: Delivery Date, Num Boxes in Shipments
* Operations: filter month is February, group by day, calculate min and max

_Output_
```sql
SELECT
  -- Include the date within the results to provide an interpretable response for the user
  CAST(Shipments."Delivery Date" AS DATE) AS Day,
  -- Use a short name for the computed columns matching existing column style on spacing and capitalization
  MIN(Shipments."Num Boxes") AS "Min Shipment",
  MAX(Shipments."Num Boxes") AS "Max Shipment"
FROM Shipments
WHERE EXTRACT(MONTH FROM Shipments."Delivery Date") = 2
AND EXTRACT(YEAR FROM Shipments."Delivery Date") = 2025
GROUP BY CAST(Shipments."Delivery Date" AS DATE)
ORDER BY Day;
```

_Conversation History_
User: So what was the overall CTR then?
Agent: The overall CTR was 3.62%.
User: What if we look at the previous years performance?
Thought: I can get brand from the Outbound_Messages table. The user is asking about 'the previous year', which is unclear by itself, but the state tells me the year is 2019, so the year before is 2018.  Since the user is making a comparison, I should also carry over the other operations such as campaign name and average CTR.

_Dialogue State_
* Tables: Outbound_Messages; Activities
* Columns: Brand, Campaign_Name in Outbound_Messages; Year, Click_Thru_Rate in Activities
* Operations: filter Brand is Vans, Campaign_Name is Sizzling Summer Sales, and compare year 2018 to 2019
* Explanation: We include the year and campaign name within the query to provide more context for the user to interpret the results.

_Output_
```sql
SELECT Outbound_Messages.Campaign_Name, 
  AVERAGE(Activities.Click_Thru_Rate) AS Average_CTR,
  Activities.Year
FROM Activities JOIN Outbound_Messages ON Activities.Message_Id = Outbound_Messages.Message_Id
WHERE Outbound_Messages.Brand = 'Vans'
AND Outbound_Messages.Campaign_Name = 'Sizzling Summer Sales'
AND Activities.Year IN (2018, 2019)
GROUP BY Activities.Year;
```

_Conversation History_
User: How many clicks am I getting from each of my highly-performing channels? Only include the active ones.
Agent: Just to be clear, how do you define highly-performing channels? Do you mean the channels with the highest click-through rate, or perhaps channels with the most clicks overall?
User: anything with at least 1000 clicks. also, can you include total views as well?
Thought: Filter the data to include only the channels with over 1000 clicks and have an enabled ad status. Then group the filtered data by channel, calculating the sum of total views and clicks for each channel.

_Dialogue State_
* Tables: GoogleAds; PageAnalytics
* Columns: Ad Status, Page Views, Clicks (all), Channel_Id in GoogleAds; ChannelID, ChannelName in PageAnalytics
* Operations: filter for top channels, group by channel, filter for active channels, aggregate sum of total clicks, aggregate sum of total views

_Output_
```sql
SELECT
  pa.ChannelName,
  SUM(ga."Clicks (all)") AS "Total Clicks",
  SUM(ga."Page Views") AS "Total Views"
FROM GoogleAds ga
JOIN PageAnalytics pa ON ga.Channel_Id = pa.ChannelID
WHERE ga."Ad Status" = 'enabled'
GROUP BY pa.ChannelName
HAVING SUM(ga."Total Clicks") >= 1000
ORDER BY "Total Clicks" DESC;
```

_Conversation History_
User: what's the average play count for each video type?
Agent: The Pump It Up series recieved 27,204 views followed by 'Get Fit Now' with 24,511 views. See table for more.
User: can you break it down for each day the video was available?
Thought: We should group by video type and by date. We will also calculate the average play count. Joining is not needed.

_Dialogue State_
* Tables: Canva Content (revised)
* Columns: video_type, content_creation_date, play_count in Canva Content (revised)
* Operations: group by video type, group by date, and average play count
* Explanation: We need to remember to use quotes for the table name since it contains a space.

_Output_
```sql
SELECT video_type,
  CAST(content_creation_date AS DATE) AS creation_date,
  AVG(play_count) AS average_views
FROM "Canva Content (revised)"
GROUP BY video_type, creation_date
ORDER BY average_views DESC;
```

_Conversation History_
User: How many subscriptions did we get last week?
Agent: We got 334 subscriptions last week.
User: How does that compare to the previous week?
Thought: The user is comparing subscriptions between weeks, so I will need to carry over the orders and events tables. I will also need to carry over the conversion columns, as well as the date column to filter for the previous week.

_Dialogue State_
* Tables: orders; events
* Columns: order_date in orders; order_id, has_subscribed in events
* Operations: filter order_date is previous week, group by day

_Output_
```sql
WITH WeeklyConversions AS (
  SELECT DATE_TRUNC('week', orders.order_date) AS week,
  COUNT(*) FILTER (WHERE events.has_subscribed) AS subscriptions
  FROM orders JOIN events ON orders.order_id = events.order_id
  GROUP BY DATE_TRUNC('week', orders.order_date)
)
SELECT week, subscriptions, LAG(subscriptions, 1) OVER (ORDER BY week) AS previous_week_conversions
FROM WeeklyConversions
ORDER BY week;
```

_Conversation History_
User: Which month gave us the best conversions to paid plans?
Agent: I'm sorry, how should I define a paid plan? Also, how should I define a conversion?
User: Anything that is attached to a payment amount greater than $0 will work. Any subscription counts as a conversion.
Thought: We can group by month, filter for payment amounts greater than $0, and count the number of subscriptions based on unique subscription IDs.

_Dialogue State_
* Tables: subscriptionsAnnual
* Columns: subscription_id, plan_name, sub_timestamp, payment_amount in subscriptionsAnnual
* Operations: group by month, filter payment_amount > 0, count subscriptions, sum the payment amount
* Explanation: The user did not explicitly ask for payment amount, but it is very useful for context. I can also add the plan name to make the output more readable.

_Output_
```sql
SELECT 
  DATE_TRUNC('month', sub_timestamp) AS month,
  plan_name,
  COUNT(DISTINCT subscription_id) AS conversion_count,
  SUM(payment_amount) AS total_revenue
FROM subscriptionsAnnual
WHERE payment_amount > 0
GROUP BY 1, 2
ORDER BY conversion_count DESC;
```

_Conversation History_
User: Which types of email subject lines get the best open rates?
Thought: The pivot table requires grouping by subject line, and calculating sent emails, opened emails, and percentage opened. This requires columns from the email_campaigns table. Percentage opened can be calculated by comparing opened emails to sent emails.

_Dialogue State_
* Tables: email_campaigns; email_metrics
* Columns: EmailID, SubjectLineType, SendDate in email_campaigns; EmailID, Opened in email_metrics
* Operations: group by SubjectLineType, aggregate the count of sent emails, aggregate by sum of opened emails, insert open rate as OpenedEmails / SentEmails * 100
* Explanation: Since I am performing division in SQL, I should make sure to cast the values to float to avoid integer division.

_Output_
```sql
SELECT SubjectLineType,
  COUNT(EmailID) AS SentEmails,
  SUM(Opened) AS OpenedEmails,
  ROUND((SUM(Opened) / CAST(COUNT(EmailID) AS FLOAT)) * 100, 2) AS OpenRate
FROM email_campaigns
JOIN email_metrics USING (EmailID)
WHERE SendDate >= DATEADD(month, -3, CURRENT_DATE)
GROUP BY SubjectLineType
ORDER BY OpenRate DESC;
```

_Conversation History_
User: Do we have any data on when payments were made by each company?
Agent: Yes, we have a PaymentPeriod column in the Payments table which tells us different months.
User: How many companies had subscriptions fees over $500 in the last full month?
Thought: The company names can be found in the AccountsRecievable table, while the subscription fees can be found in the Payments table. The user is asking about subscriptions over $500, which is a comparison operation. I should also carry over the month from the previous state.

_Dialogue State_
* Tables: AccountsRecievable; Payments
* Columns: CompanyName in AccountsRecievable; SubscriptionFee, PaymentPeriod in Payments
* Operations: filter for last month in June, group by company, and sort by revenue
* Explanation: We consider cumulative subscription fees rather than individual fees exceeding $1000 because the focus is on unique companies, not unique payments. Also, we include CompanyName to provide an interpretable response for the user.

_Output_
```sql
SELECT AccountsReceivable.CompanyID, AccountsReceivable.CompanyName
FROM AccountsReceivable
INNER JOIN Payments ON AccountsReceivable.CompanyID = Payments.CompanyID
WHERE Payments.PaymentPeriod = 'June'
GROUP BY AccountsReceivable.CompanyID, AccountsReceivable.CompanyName
HAVING SUM(Payments.SubscriptionFee) > 500;
```
---
Now it's your turn to generate an accurate, directly executable SQL query. {pref_reminder}
For our real case, we also have a random (unordered) sample of rows for additional context:
{data_preview}

_Conversation History_
{history}
Thought: {thought}

_Dialogue State_
{valid_tab_col}
* Operations: {operations}

_Output_
"""

metric_generation_prompt = """You are an outstanding data analyst who is exceptionally skilled at writing SQL queries.
Given the conversation history and dialogue states, your task is to generate an accurate SQL query that answers the user's final turn.
The conversation history is composed of user and agent utterances, occasionally interspersed with your own internal thoughts.
Dialogue states contain the valid tables and columns to query from, along with likely operations written out in natural language.
Using this information, please generate a SQL query that works with the data schema from the system prompt.{year_reminder}

Note: When selecting columns that exist in multiple tables after a join, don't forget to include the table name in the SELECT.
As a skilled analyst, you know the nuances of writing useful queries. For example, you know only to group by ID columns when unique counts are desired.
You also know when asked to count how many of something exists, you should consider if a unique count makes sense, which implies using DISTINCT or GROUP BY when appropriate.
Pay attention to the provided thoughts and operations since they will affect how the optimal query is written.
Remember, you are querying from DuckDB, use the appropriate syntax and casing for operations.
If a query is ambiguous or problematic, such as a request for a non-existent column, please output 'Error:' followed by a short phrase to describe the issue (eg. 'Error: missing column' or 'Error: unclear start date').

This is very important to my career, please be sure to only output valid SQL queries that are directly executable with *no* explanations.

For example,
---
_Conversation History_
User: What was the largest shipment in February?
Agent: The largest shipment contained 5307 units.
User: Did we generate a profit that month?
Thought: The orders table has a price column, which can be used to calculate revenue. The products table has a cost column, which can be used to calculate the cost of goods sold. To calculate profit, I need to subtract the cost from the revenue. I also need to filter for February, which is found in the orders table.

_Dialogue State_
* Tables: orders; products
* Columns: date, price in orders; cost in products
* Target: the sum of profit
* Operations: filter month is February

_SQL Query_
SELECT orders.date, SUM(orders.price) - SUM(products.cost) AS profit 
FROM orders JOIN products ON orders.product_id = products.product_id
WHERE EXTRACT(MONTH FROM orders.date) = 2
AND EXTRACT(YEAR FROM orders.date) = 2025;

_Explanation_
We include the date within the results to provide an interpretable response for the user.

_Conversation History_
User: Are there any users from Los Angeles who spent more than $500 in 2021?
Thought: The customers table can tell me the city, so I can filter for Los Angeles. I should join with transactions table to sum prices for each customer, filter for the year 2021 and total spent over $500.

_Dialogue State_
* Tables: customers; transactions
* Columns: customer_id, city in customers; customer_id, transaction_date, price in transactions
* Target: the count of users
* Operations: filter city is Los Angeles, filter sum of price > 500, and filter year is 2021

_SQL Query_
SELECT customers.customer_id, customers.first, customers.last, SUM(transactions.price) AS total_spent
FROM customers
JOIN transactions ON customers.customer_id = transactions.customer_id
WHERE customers.city = 'Los Angeles'
AND EXTRACT(YEAR FROM transactions.transaction_date) = 2021
GROUP BY customers.customer_id, customers.first, customers.last
HAVING total_spent > 500;

_Explanation_
Typically, we will default to 2025, but since the Dialogue State explicitly mentions 2021, we should use that instead.

_Conversation History_
User: So what was the overall CTR then?
Agent: The overall CTR was 3.62%.
User: What if we look at the previous years performance?
Thought: I can get brand from the outbound_messages table. The user is asking about 'the previous year', which is unclear by itself, but the state tells me the year is 2019, so the year before is 2018.  Since the user is making a comparison, I should also carry over the other operations such as campaign name and average CTR.

_Dialogue State_
* Tables: outbound_messages; activities
* Columns: brand, campaign_name in outbound_messages; year, click_thru_rate in activities
* Target: the average click_thru_rate
* Operations: filter brand is Vans, campaign_name is Sizzling Summer Sales, and compare year 2018 to 2019

_SQL Query_
SELECT outbound_messages.campaign_name,
  AVERAGE(activities.click_thru_rate) AS average_CTR,
  activities.year
FROM activities JOIN outbound_messages ON activities.message_id = outbound_messages.message_id
WHERE outbound_messages.brand = 'Vans'
AND outbound_messages.campaign_name = 'Sizzling Summer Sales'
AND activities.year IN (2018, 2019)
GROUP BY activities.year;

_Explanation_
We include the year and campaign name within the query to provide more context for the user to interpret the results.

_Conversation History_
User: What are the top 3 brands in terms of clicks in the last 5 days?
Thought: The Items table has a Brand column, while the Visitors table has a Views column which can be used to calculate clicks.  Last week means within the last 7 days, which is from 15 to 22 since today is May 22, and orders also has a day column.

_Dialogue State_
* Tables: Items; Visitors
* Columns: Brand in Items; Views, ShipmentTimestamp in Visitors
* Target: the top 3 brands
* Operations: filter for last 5 days, group by brand, and sort by views

_SQL Query_
SELECT Items.Brand, SUM(Visitors.Views) AS TotalClicks
FROM Visitors JOIN Items ON Visitors.ItemID = Items.ItemID
WHERE Visitors.ShipmentTimestamp >= CURRENT_DATE - INTERVAL '5 days'
GROUP BY Items.Brand
ORDER BY TotalClicks DESC LIMIT 3;

_Conversation History_
User: How many subscriptions did we get last week?
Agent: We got 334 subscriptions last week.
User: How does that compare to the previous week?
Thought: The user is comparing subscriptions between weeks, so I will need to carry over the orders and events tables. I will also need to carry over the conversion columns, as well as the date column to filter for the previous week.

_Dialogue State_
* Tables: orders; events
* Columns: order_date in orders; order_id, has_subscribed in events
* Target: the count of subscriptions
* Operations: filter order_date is previous week and group by day

_SQL Query_
WITH WeeklyConversions AS (
  SELECT DATE_TRUNC('week', orders.order_date) AS week,
  COUNT(*) FILTER (WHERE events.has_subscribed) AS subscriptions
  FROM orders JOIN events ON orders.order_id = events.order_id
  GROUP BY DATE_TRUNC('week', orders.order_date)
)
SELECT week, subscriptions, LAG(subscriptions, 1) OVER (ORDER BY week) AS previous_week_conversions
FROM WeeklyConversions
ORDER BY week;

_Conversation History_
User: Which channel had the lowest conversion rate in March?
Thought: The Channels table contains a channel column and also a date column. Conversion rate is in the Activities table.

_Dialogue State_
* Tables: Channels; Activities
* Columns: date, channel_name in Channels; conversion_rate in Activities
* Target: the min channel
* Operations: filter for March, group by channel_name, and sort by conversion rate

_SQL Query_
SELECT orders.channel_name, AVG(activities.conversion_rate) as CVR
FROM orders JOIN activities ON orders.order_id = activities.order_id
WHERE EXTRACT(MONTH FROM orders.date) = 3
AND EXTRACT (YEAR FROM orders.date) = 2025
GROUP BY orders.channel_name
ORDER BY CVR ASC LIMIT 1;

_Explanation_
Even if channel_id is available, we instead group by channel_name because we want to return a natural language response to the user.

_Conversation History_
User: Is there an item that was purchased more often than the rest?
Agent: The most frequently purchased item was the 2-in-1 shampoo and conditioner.
User: What is the largest size that she bought?
Thought: The inventory table has a size column. Largest size means the maximum size, which is an aggregation. The user is referring to a specific person, so I should carry over the name from the previous state.

_Dialogue State_
* Tables: inventory; buyers
* Columns: item_size, item_name in inventory; first_name, last_name in buyers
* Target: the max size
* Operations: filter first_name is Janet, filter last_name is Doherty, and sort by size

_SQL Query_
SELECT MAX(inventory.item_size) AS largest_size
FROM inventory JOIN customers ON inventory.customer_id = customers.customer_id
WHERE inventory.item_name = '2-in-1 shampoo and conditioner'
AND customers.first_name = 'Janet'
AND customers.last_name = 'Doherty';

_Explanation_
Pay attention to the dialogue state since it often contains critical information for generating the query not found in the conversation history.

_Conversation History_
User: Do we have any data on when payments were made by each company?
Agent: Yes, we have a PaymentPeriod column in the Payments table which tells us different months.
User: How many companies had subscriptions fees over $1000 in the last full month?
Thought: The company names can be found in the AccountsRecievable table, while the subscription fees can be found in the Payments table. The user is asking about subscriptions over $1000, which is a comparison operation. I should also carry over the month from the previous state.

_Dialogue State_
* Tables: AccountsRecievable; Payments
* Columns: CompanyName in AccountsRecievable; SubscriptionFee, PaymentPeriod in Payments
* Target: the count of company
* Operations: filter for last month in June, group by company, and sort by revenue

_SQL Query_
SELECT AccountsReceivable.CompanyID, AccountsReceivable.CompanyName
FROM AccountsReceivable
INNER JOIN Payments ON AccountsReceivable.CompanyID = Payments.CompanyID
WHERE Payments.PaymentPeriod = 'June'
GROUP BY AccountsReceivable.CompanyID, AccountsReceivable.CompanyName
HAVING SUM(Payments.SubscriptionFee) > 1000;

_Explanation_
We consider cumulative subscription fees rather than individual fees exceeding $1000 because the focus is on unique companies, not unique payments. Also, we include CompanyName to provide an interpretable response for the user.
---
Now it's your turn to generate an accurate, directly executable SQL query.

_Conversation History_
{convo_history}
{thought}

_Dialogue State_
{dialogue_state}

_SQL Query_
"""

sql_for_chart_prompt = """You are an outstanding data analyst who is exceptionally skilled at writing SQL queries.
Given the conversation history and dialogue states, your task is to generate the SQL query needed to produce the requested chart or figure.
The conversation history is composed of user and agent utterances, occasionally interspersed with your own internal thoughts.
Dialogue states contain the valid tables and columns to query from, along with likely operations written out in natural language.
Using this information, please generate a SQL query that works with the data schema from your system prompt.{year_reminder}

As a skilled analyst, you know the nuances of writing useful queries. For example, you know only to group by ID columns when unique counts are desired.
You also know when asked to count how many of something exists, you should consider if a unique count makes sense, which implies using DISTINCT or GROUP BY when appropriate.
When selecting columns that exist in multiple tables after a join, don't forget to include the table name in the SELECT.
When calculating a percentage, DO NOT multiply by 100. When performing any division operation, always return the result with at least 4 decimal places of precision.
If a query is ambiguous or problematic, such as a request for a non-existent column, please output 'Error:' followed by a short phrase to describe the issue (eg. 'Error: missing column' or 'Error: unclear start date').

Remember, you are querying from DuckDB, use the appropriate syntax and casing for operations, such as:
  * using double quotes for wrapping irregular column names rather than backticks
  * casting is done with `CAST(col_name AS DATE)` or `col_name::DATE` rather than `DATE(col_name)`
  * concatenation is written as `username || '@' || domain` rather than `CONCAT(username, '@', domain)`

The chart created from the query will be directly displayed to the user, so please include any columns that might be useful for interpreting the results.
Along those lines, it is also preferred to include extra rows (ie. top 10 sales reps) even if the user only asked for a subset (eg. top 3 reps) to give more context.
Furthermore, computed columns should be given user-friendly aliases that are short (3 tokens max), simple (avoids special characters), and easy to understand.
This is very important to my career, please be sure to only output a valid SQL query containing comments and code.
The query should be directly executable, so do NOT include any additional text or explanations after the query.

For example,
---
_Conversation History_
User: What was the largest shipment delivered in February?
Agent: The largest shipment contained 5307 units.
User: Did we generate a profit in any of those days?
Thought: The Shipments table has a price column, which can be used to calculate revenue. The Products table has a COGS column, which can be used to grab the cost. I also need to filter for February based on the delivery date.

_Dialogue State_
* Tables: Shipments; Products
* Columns: Delivery Date, Final Price in Shipments; Cost of Goods Sold in Products
* Operations: filter month is February, group by day, calculate profit

_Output_
```sql
-- Include the date within the results to provide an interpretable response for the user
SELECT
  CAST(Shipments."Delivery Date" AS DATE) AS Day,
  -- Shorter names like 'Revenue' are better than longer names like 'Daily Revenue'
  SUM(Shipments."Final Price") AS Revenue,
  SUM(Products."Cost of Goods Sold") AS Cost,
  -- Set a 'Profit' alias for the computed column to make it easier for the user to understand
  SUM(Shipments."Final Price" - Products."Cost of Goods Sold") AS Profit
FROM Shipments JOIN Products
  ON Shipments."Product ID" = Products."Product ID"
WHERE EXTRACT(MONTH FROM Shipments."Delivery Date") = 2
AND EXTRACT(YEAR FROM Shipments."Delivery Date") = 2025
GROUP BY CAST(Shipments."Delivery Date" AS DATE)
ORDER BY Day;
```

_Conversation History_
User: Are there any users from Los Angeles who spent more than $500 in 2021?
Thought: The customers table can tell me the city, so I can filter for Los Angeles. I should join with transactions table to sum prices for each customer, filter for the year 2021 and total spent over $500.

_Dialogue State_
* Tables: customers; transactions
* Columns: customer_id, city in customers; customer_id, transaction_date, price in transactions
* Target: the count of users
* Operations: filter city is Los Angeles, filter sum of price > 500, and filter year is 2021

_Output_
```sql
SELECT Customers.Customer_ID, Customers.First, Customers.Last,
  SUM(Transactions.Price) AS Total_Spent
FROM Customers
JOIN Transactions ON Customers.Customer_ID = Transactions.Customer_ID
WHERE Customers.Current_City = 'Los Angeles'
-- Typically, we will default to 2025, but since the Dialogue State explicitly mentions 2021, we should use that instead.
AND EXTRACT(YEAR FROM Transactions.Transaction_Date) = 2021
GROUP BY Customers.Customer_ID, Customers.First, Customers.Last
HAVING Total_Spent > 500;
```

_Conversation History_
User: So what was the overall CTR then?
Agent: The overall CTR was 3.62%.
User: What if we look at the previous years performance?
Thought: I can get brand from the outbound_messages table. The user is asking about 'the previous year', which is unclear by itself, but the state tells me the year is 2019, so the year before is 2018.  Since the user is making a comparison, I should also carry over the other operations such as campaign name and average CTR.

_Dialogue State_
* Tables: outbound_messages; activities
* Columns: brand, campaign_name in outbound_messages; year, click_thru_rate in activities
* Target: the average click_thru_rate
* Operations: filter brand is Vans, campaign_name is Sizzling Summer Sales, and compare year 2018 to 2019

_Output_
```sql
-- Include the year and campaign name within the query to provide more context for the user to interpret the results.
SELECT outbound_messages.campaign_name, 
  AVERAGE(activities.click_thru_rate) AS average_CTR,
  activities.year
FROM activities JOIN outbound_messages ON activities.message_id = outbound_messages.message_id
WHERE outbound_messages.brand = 'Vans'
AND outbound_messages.campaign_name = 'Sizzling Summer Sales'
AND activities.year IN (2018, 2019)
GROUP BY activities.year;
```

_Conversation History_
User: What are the best selling brands in terms of clicks in the last 5 days?
Thought: The Items table has a Brand column, while the Visitors table has a Views column which can be used to calculate clicks.  Last week means within the last 7 days, which is from 15 to 22 since today is May 22, and orders also has a day column.

_Dialogue State_
* Tables: Items; Visitors
* Columns: Brand in Items; Views, ShipmentTimestamp in Visitors
* Target: the top 3 brands
* Operations: filter for last 5 days, group by brand, and sort by views

_Output_
```sql
SELECT Items.Brand, 
  -- Alias should not include spaces or special characters to match the casing and spaces from existing columns
  SUM(Visitors.Views) AS TotalClicks
FROM Visitors JOIN Items ON Visitors.ItemID = Items.ItemID
WHERE Visitors.ShipmentTimestamp >= CURRENT_DATE - INTERVAL '5 days'
GROUP BY Items.Brand
ORDER BY TotalClicks DESC
-- Include the top 3 brands even though the user only asked for the best selling one to provide more context
LIMIT 3;
```

_Conversation History_
User: How many subscriptions did we get last week?
Agent: We got 334 subscriptions last week.
User: How does that compare to the previous week?
Thought: The user is comparing subscriptions between weeks, so I will need to carry over the orders and events tables. I will also need to carry over the conversion columns, as well as the date column to filter for the previous week.

_Dialogue State_
* Tables: orders; events
* Columns: order_date in orders; order_id, has_subscribed in events
* Operations: filter order_date is previous week and group by day

_Output_
```sql
WITH WeeklyConversions AS (
  SELECT DATE_TRUNC('week', orders.order_date) AS week,
  COUNT(*) FILTER (WHERE events.has_subscribed) AS subscriptions
  FROM orders JOIN events ON orders.order_id = events.order_id
  GROUP BY DATE_TRUNC('week', orders.order_date)
)
SELECT week, subscriptions, LAG(subscriptions, 1) OVER (ORDER BY week) AS previous_week_conversions
FROM WeeklyConversions
ORDER BY week;
```

_Conversation History_
User: Which channel had the lowest conversion rate in March?
Thought: The Channels table contains a channel column and also a date column. Conversion rate is in the Activities table.

_Dialogue State_
* Tables: Channels; Activities
* Columns: date, channel_name in Channels; conversion_rate in Activities
* Operations: filter for March, group by channel_name, and sort by conversion rate

_Output_
```sql
-- Even if channel_id is available, we instead group by channel_name because we want to return a natural language response to the user.
SELECT orders.channel_name,
  AVG(activities.conversion_rate) as CVR
FROM orders JOIN activities ON orders.order_id = activities.order_id
WHERE EXTRACT(MONTH FROM orders.date) = 3
AND EXTRACT (YEAR FROM orders.date) = 2025
GROUP BY orders.channel_name
ORDER BY CVR ASC
-- Include the bottom 3 channels even though the user only asked for the worst one to provide more context
LIMIT 3;
```

_Conversation History_
User: Is there an item that was purchased more often than the rest?
Agent: The most frequently purchased item was the 2-in-1 shampoo and conditioner.
User: What is the largest size that she bought?
Thought: The inventory table has a size column. Largest size means the maximum size, which is an aggregation. The user is referring to a specific person, so I should carry over the name from the previous state.

_Dialogue State_
* Tables: inventory; buyers
* Columns: item_size, item_name in inventory; first_name, last_name in buyers
* Operations: filter first_name is Janet, filter last_name is Doherty, and sort by size

_Output_
```sql
-- The dialogue state contains critical information not found in the chat, namely the customer's name
SELECT MAX(inventory.item_size) AS largest_size
FROM inventory JOIN customers ON inventory.customer_id = customers.customer_id
WHERE inventory.item_name = '2-in-1 shampoo and conditioner'
AND customers.first_name = 'Janet'
AND customers.last_name = 'Doherty';
```

_Conversation History_
User: Do we have any data on when payments were made by each company?
Agent: Yes, we have a PaymentPeriod column in the Payments table which tells us different months.
User: How many companies had subscriptions fees over $1000 in the last full month?
Thought: The company names can be found in the AccountsRecievable table, while the subscription fees can be found in the Payments table. The user is asking about subscriptions over $1000, which is a comparison operation. I should also carry over the month from the previous state.

_Dialogue State_
* Tables: AccountsRecievable; Payments
* Columns: CompanyName in AccountsRecievable; SubscriptionFee, PaymentPeriod in Payments
* Operations: filter for last month in June, group by company, and sort by revenue

_Output_
```sql
SELECT AccountsReceivable.CompanyID,
  -- Include CompanyName to provide an interpretable response for the user.
  AccountsReceivable.CompanyName,
  -- Alias should not include spaces and should match the casing from existing columns
  SUM(Payments.SubscriptionFee) AS TotalSubscribeFee
FROM AccountsReceivable
INNER JOIN Payments ON AccountsReceivable.CompanyID = Payments.CompanyID
WHERE Payments.PaymentPeriod = 'June'
GROUP BY AccountsReceivable.CompanyID, AccountsReceivable.CompanyName
-- Focus on cumulative subscription fees rather than individual fees exceeding $1000 because the focus is on unique companies, not unique payments
HAVING SUM(Payments.SubscriptionFee) > 1000
ORDER BY TotalSubscribeFee DESC;
```
---
For our real case, we also have a random (unordered) sample of rows for additional context:
{data_preview}

_Conversation History_
{history}
Thought: {thought}

_Dialogue State_
{valid_tab_col}
* Operations: {operations}

_Explanation_
We will use the conversation history, dialogue state and data preview to generate a high quality, directly executable SQL query.
{pref_reminder}
_Output_
"""

combine_cte_prompt = """You are an outstanding data analyst who is exceptionally skilled at writing SQL queries.
Given the conversation history and related thought process, your task is to generate the simplest SQL query that still addresses the user's request.
As a skilled analyst, you know the nuances of writing complex queries. Consequently, you know that when calculating ratios, the numerator should be derived directly from the base formed by the denominator.
You are also adept at navigating the complexities of writing queries containing CTEs. As a result, you know when a filter or grouping should be applied globally across the entire query versus locally within a CTE.

To guide the {metric} calculation, you are also given a partially filled query template with a CTE.
We also have access to the list of valid tables and columns since an accurate query will only refer to actual columns.
Using all this information, please revise the template to form a DuckDB compatible SQL query with appropriate syntax and casing for operations.

Please start your query with a comment to explain your thought process.
If a query is ambiguous or problematic, use the comment section instead to write an error response followed by a short phrase to describe the issue.
Concretely, suppose there is a request for a non-existent column, then you would output '-- Error: missing column', or if the start date is unclear, then you would output '-- Error: unclear start date'.
In all cases, your entire response should be a valid SQL query with no additional text before or after the code output.

Let's consider three alternate scenarios with a handful of examples each, and then tackle the current case.
---
## E-commerce Online Advertiser Scenario
* Tables: GoogleAds_Q3; SalesRecord_Shopify_0812; Product_Details
* Columns: gAd_ID, clickCount, campaignInitDate, campaignTermDate, userActivity, adBounceRate, adSpend, adContentCode, referrerURL in GoogleAds_Q3;
orderRef, prodSKU, saleDate, acquisitionCost, buyerID, gAdRef, revenueGenerated, unitsMoved, fulfillmentStatus, customerNotes in SalesRecord_Shopify_0812;
SKU, itemName, itemCategory, retailPrice, totalCost, stockLevel in Product_Details

### Example 1
User: Yea, you can join with the Shopify data on the gAdReference id
Agent: Should I include all data available in the GoogleAds_Q3 table, or only consider a specific time frame?
User: Focusing on just the past week is good
Thought: we should start by filtering for users coming from LinkedIn, likely by using the referrerURL column.
We also need to filter for the past week, which can be found by joining against the saleDate column.
Lastly, visits and conversions are both activity types in userActivity, using the the 'clicks' and 'purchase' values respectively.
Goal: Calculate conversion rate according to the following template ->
```sql
WITH LinkedInVisitors AS (
  SELECT DISTINCT buyerID
  FROM SalesRecord_Shopify_0812
  JOIN GoogleAds_Q3 ON SalesRecord_Shopify_0812.gAdRef = GoogleAds_Q3.gAd_ID
  WHERE GoogleAds_Q3.referrerURL LIKE '%linkedin%'
  AND GoogleAds_Q3.userActivity = 'clicks'
), LinkedInPurchases AS (
  SELECT buyerID
  FROM SalesRecord_Shopify_0812
  JOIN GoogleAds_Q3 ON SalesRecord_Shopify_0812.gAdRef = GoogleAds_Q3.gAd_ID
  WHERE GoogleAds_Q3.userActivity = 'purchase'
  AND SalesRecord_Shopify_0812.saleDate >= CURRENT_DATE - INTERVAL '1 week'
  AND SalesRecord_Shopify_0812.buyerID IN (SELECT buyerID FROM LinkedInVisitors)
)
SELECT
  <conversions_result>,
  <visits_result>,
  COALESCE(<conversions_result> * 1.0) / NULLIF(<visits_result>, 0), 0) AS CVR
FROM <CTE_alias>;
```

_Output_
```sql
-- The optimal conversions result depends directly on the buyerIDs from the visits result. In this way, the CVR formula shares a common base of users.
WITH LinkedInVisitors AS (
  SELECT DISTINCT buyerID
  FROM SalesRecord_Shopify_0812
  JOIN GoogleAds_Q3 ON SalesRecord_Shopify_0812.gAdRef = GoogleAds_Q3.gAd_ID
  WHERE GoogleAds_Q3.referrerURL LIKE '%linkedin%'
  AND GoogleAds_Q3.userActivity = 'clicks'
  AND SalesRecord_Shopify_0812.saleDate >= CURRENT_DATE - INTERVAL '1 week'
), LinkedInPurchases AS (
  SELECT buyerID
  FROM SalesRecord_Shopify_0812
  JOIN GoogleAds_Q3 ON SalesRecord_Shopify_0812.gAdRef = GoogleAds_Q3.gAd_ID
  WHERE GoogleAds_Q3.userActivity = 'purchase'
  AND SalesRecord_Shopify_0812.buyerID IN (SELECT buyerID FROM LinkedInVisitors)
),
LinkedInConversions AS (
  SELECT
  (SELECT COUNT(DISTINCT buyerID) FROM LinkedInPurchases) AS TotalConversions,
  (SELECT COUNT(DISTINCT buyerID) FROM LinkedInVisitors) AS TotalVisits
)
SELECT
  TotalConversions,
  TotalVisits,
  COALESCE(TotalConversions * 1.0 / NULLIF(TotalVisits, 0), 0) AS CVR
FROM LinkedInConversions;
```

### Example 2
User: What is the CPC for our ads?
Agent: Sure, I will need to verify the cost and clicks first. Does this look right?
User: Yea, clickCount looks good.
Thought: We previously determined that both adSpend and totalCost are plausible options for cost, but I will choose adSpend because it comes from the same table as clickCount, which is verified.
When performing calculations, we should limit cost to only those that are directly attributable to clicks.
Goal: Calculate cost-per-click according to the following template ->
```sql
WITH ClickCounts AS (
  SELECT SUM(clickCount) AS totalClicks
  FROM GoogleAds_Q3
  WHERE userActivity = 'clicked_ad'
), GoogleSpend AS (
  SELECT SUM(adSpend) AS totalSpend
  FROM GoogleAds_Q3
  WHERE userActivity = 'clicked_ad'
),
SELECT
  <cost_result>,
  <clicks_result>,
  COALESCE(<cost_result> * 1.0) / NULLIF(<clicks_result>, 0), 0) AS CPC
FROM <CTE_alias>;
```

_Output_
```sql
-- To line up TotalClicks and TotalSpend, we must use the exact same filter of 'clicked_ad' to form a shared based of users.
WITH GoogleMetrics AS (
  SELECT
    SUM(CASE WHEN userActivity = 'clicked_ad' THEN clickCount ELSE 0 END) AS TotalClicks,
    SUM(CASE WHEN userActivity = 'clicked_ad' THEN adSpend ELSE 0 END) AS TotalSpend
  FROM GoogleAds_Q3
)
SELECT
  TotalSpend,
  TotalClicks,
  COALESCE(TotalSpend * 1.0 / NULLIF(TotalClicks, 0), 0) AS CPC
FROM GoogleMetrics;
```

## Enterprise Data Security Scenario
* Tables: HubspotCRM; TransactionHistory; InteractionLogs
* Columns: cust_id, signup_date, cust_name, email, region, tracking_id, channel, acct_status in HubspotCRM;
trans_id, cust_id, trans_date, product_id, amount, trans_type, license_fee, service_charge, maintenance_income in the TransactionHistory;
interaction_id, cust_id, interact_date, interact_type, interact_duration, issue_resolved, expenses in the InteractionLogs

### Example 3
User: How many new customers did we get in the past month from the west coast?
Agent: We acquired 2,398 new customers in the past month in the west coast.
User: Can you help me calculate the retention?
Thought: We previously determined that we should start by filtering for the west coast, likely using the region column. There doesn't seem to be a retention column, so we will need to calculate the variables ourselves.
Signup date is likely the best way to determine if someone is a customer. Grouping by customer id will allow us to form the base of total customers.
We can then use the transaction date to determine whether that customer is active in the last month.
Goal: Calculate retention rate according to the following template ->
```sql
WITH WestCoastCustomers AS (
  SELECT COUNT(DISTINCT HubspotCRM.cust_id)
  FROM HubspotCRM
  WHERE HubspotCRM.region = 'West'
  AND HubspotCRM.signup_date >= CURRENT_DATE - INTERVAL '1 year'
), ActiveLastMonth AS (
  SELECT COUNT(WestCoastCustomers.cust_id) AS active_customers
  FROM WestCoastCustomers
  JOIN TransactionHistory ON TransactionHistory.cust_id = WestCoastCustomers.cust_id
  AND TransactionHistory.trans_date >= CURRENT_DATE - INTERVAL '1 month'
),
SELECT
  <active_customers_result>,
  <total_customers_result>,
  COALESCE(<active_customers_result> * 1.0) / NULLIF(<total_customers_result>, 0), 0) AS retention_rate
FROM <CTE_alias>;
```

_Output_
```sql
-- To avoid mis-counting, we only include active customers that are directly associated with the WestCoastCustomers to form a common base of users.
WITH WestCoastCustomers AS (
  SELECT DISTINCT HubspotCRM.cust_id AS customer_id
  FROM HubspotCRM
  WHERE HubspotCRM.region = 'West'
  AND HubspotCRM.signup_date >= CURRENT_DATE - INTERVAL '1 year'
), ActiveLastMonth AS (
  SELECT COUNT(DISTINCT WestCoastCustomers.customer_id) AS active_customers
  FROM WestCoastCustomers
  JOIN TransactionHistory ON TransactionHistory.cust_id = WestCoastCustomers.customer_id
  AND TransactionHistory.trans_date >= CURRENT_DATE - INTERVAL '1 month'
), WestCoastRetention AS (
  SELECT
    (SELECT active_customers FROM ActiveLastMonth) AS ActiveCustomers,
    (SELECT COUNT(DISTINCT customer_id) FROM WestCoastCustomers) AS TotalCustomers
)
SELECT
  ActiveCustomers,
  TotalCustomers,
  COALESCE(ActiveCustomers * 1.0 / NULLIF(TotalCustomers, 0), 0) AS RetentionRate
FROM WestCoastRetention;
```

### Example 4
User: How much was our return on investment last quarter?
Agent: Should I use license_fee, service_charge, or maintenance_income to calculate revenue?
User: Revenue is the sum of licenses and maintenance
Thought: We will go with sum of expenses as 'costs' and the sum or licenses and maintenance as 'revenue'.
We should also filter for last quarter, which can be calculated using interact_date as in the prior query.
Goal: Calculate return on investment according to the following template ->
```sql
WITH Revenue AS (
  SELECT
  SUM(TransactionHistory.license_fee) AS TotalLicenses,
  SUM(TransactionHistory.maintenance_income) AS TotalMaintenance
  FROM TransactionHistory
  JOIN InteractionLogs ON TransactionHistory.cust_id = InteractionLogs.cust_id
  WHERE InteractionLogs.interact_date >= CURRENT_DATE - INTERVAL '1 quarter'
), Costs AS (
  SELECT SUM(expenses) AS TotalExpenses
  FROM InteractionLogs
  WHERE interact_date >= CURRENT_DATE - INTERVAL '1 quarter'
),
SELECT
  <revenue_result>,
  <cost_result>,
  COALESCE(<revenue_result> * 1.0) / NULLIF(<cost_result>, 0), 0) AS ROI
FROM <CTE_alias>;
```

_Output_
```sql
-- We are guaranteed a common base of revenue and costs since both metrics are queried using the shared filters in the same CTE.
WITH FinancialMetrics AS (
  SELECT
    SUM(TransactionHistory.license_fee) AS TotalLicenseFee,
    SUM(TransactionHistory.maintenance_income) AS TotalMaintenanceFee,
    (SELECT SUM(expenses) FROM InteractionLogs WHERE interact_date >= CURRENT_DATE - INTERVAL '1 quarter') AS TotalExpenses
  FROM TransactionHistory
  JOIN InteractionLogs ON TransactionHistory.cust_id = InteractionLogs.cust_id
  WHERE InteractionLogs.interact_date >= CURRENT_DATE - INTERVAL '1 quarter'
)
SELECT
  TotalLicenseFee,
  TotalMaintenanceFee,
  TotalLicenses + TotalMaintenance AS TotalRevenue,
  TotalExpenses,
  COALESCE(TotalRevenue * 1.0 / NULLIF(TotalExpenses, 0), 0) AS ROI
FROM FinancialMetrics;
```

## Mobile Workout Community Scenario
* Tables: AdobeAnalytics_final; SubscriptionMembership; Canva Content (revised); VendorExpenses
* Columns: campaign_id, ad_platform, ad_spend, ad_type, ad_copy, user_activity, view_count, cost_per_click in AdobeAnalytics_final;
member_id, last_payment_date, next_renewal_date, subscription_tier, monthly_fee, activity, member_status in SubscriptionMembership;
video_id, trainer_id, video_campaign_id, creation_date, video_type, trainer_fee, impressions in Canva Content (revised);
vendor_id, campaign_foreign_key, service_provided, expense_date, expense_amount, vendor_category in VendorExpenses

### Example 5
User: can we see just the past week for Google Ads, broken down by day?
Agent: OK, I have filtered to just the past week
User: what is the CTR during that time?
Thought: We previously determined that we should start by filtering for Google using the ad_platform column, along with view_count to determine impressions.
I can't find a single column to represent cost, but the user has verified that we can use cost_per_click in conjunction with ad_spend to derive an approximate number of clicks.
Goal: Calculate click-thru rate according to the following template ->
```sql
WITH GoogleImpressions AS (
  SELECT DISTINCT view_count
  FROM AdobeAnalytics_final
  WHERE ad_platform = 'Google'
), GoogleClicks AS (
  SELECT SUM(ad_spend) / cost_per_click AS total_clicks
  FROM AdobeAnalytics_final
  WHERE ad_platform = 'Google'
  AND GoogleImpressions.view_count > 0
),
SELECT
  <clicks_result>,
  <impressions_result>,
  COALESCE(<clicks_result> * 1.0) / NULLIF(<impressions_result>, 0), 0) AS CTR
FROM <CTE_alias>;
```

_Output_
```sql
-- We can fix misalignment in the template (ie. revising TotalImpressions) in order to match the user's main intention (ie. calculating CTR)
WITH GoogleImpressions AS (
  SELECT SUM(view_count) AS TotalImpressions
  FROM AdobeAnalytics_final
  WHERE ad_platform = 'Google'
), GoogleClicks AS (
  SELECT SUM(
    CASE WHEN cost_per_click > 0 THEN ad_spend / cost_per_click ELSE 0 END
  ) AS TotalClicks
  FROM AdobeAnalytics_final
  WHERE ad_platform = 'Google'
)
SELECT
  GoogleClicks.TotalClicks,
  GoogleImpressions.TotalImpressions,
  COALESCE(GoogleClicks.TotalClicks * 1.0 / NULLIF(GoogleImpressions.TotalImpressions, 0), 0) AS CTR
FROM GoogleClicks, GoogleImpressions;
```

### Example 6
User: How many videos have over 1000 views?
Agent: 17 videos have over 1000 views.
User: Did we make a profit from any of them?
Agent: Does monthly_fee or trainer_fee count as revenue?
User: Go with monthly
Thought: The user has confirmed that revenue can be derived from monthly_fee. Possible costs include expense_amount and ad_apend, but I will choose expense_amount because we are discussing videos.
We also need to remember to filter for view count over 1000. We can use the time range and campaign keys to tie together the different tables.
Goal: Calculate profit according to the following template ->
```sql
WITH VideoCosts AS (
  SELECT SUM(expense_amount) AS total_expenses
  FROM VendorExpenses
  WHERE vendor_category = 'video'
  AND expense_date >= CURRENT_DATE - INTERVAL '1 month'
), VideoRevenue AS (
  SELECT SUM(monthly_fee) AS total_revenue
  FROM SubscriptionMembership
  AND SubscriptionMembership.last_payment_date >= CURRENT_DATE - INTERVAL '1 month'
)
SELECT
  <costs_result>,
  <revenue_result>,
  COALESCE(<revenue_result> - <costs_result>, 0) AS profit
FROM <CTE_alias>;
```

_Output_
```sql
-- Ideally, we would connect video revenue directly to video costs, but given the lack of join options, we follow the Thought's suggestion to tie together the metrics using time range.
WITH VideoCosts AS (
  SELECT SUM(expense_amount) AS total_expenses
  FROM VendorExpenses
  JOIN AdobeAnalytics_final ON VendorExpenses.campaign_foreign_key = AdobeAnalytics_final.campaign_id
  WHERE VendorExpenses.vendor_category = 'video'
  AND AdobeAnalytics_final.view_count > 1000
  AND VendorExpenses.expense_date >= CURRENT_DATE - INTERVAL '1 month'
), VideoRevenue AS (
  SELECT SUM(monthly_fee) AS total_revenue
  FROM SubscriptionMembership
  WHERE SubscriptionMembership.last_payment_date >= CURRENT_DATE - INTERVAL '1 month'
)
SELECT
  VideoCosts.total_expenses AS costs_result,
  VideoRevenue.total_revenue AS revenue_result,
  (VideoRevenue.total_revenue - VideoCosts.total_expenses) AS profit
FROM VideoCosts, VideoRevenue;
```
---
## Current Scenario
{valid_tab_col}

{history}
Thought: {thought}
Goal: Calculate {metric} according to the following template ->
{template}

_Output_
"""

analyze_hint_prompt = """Given the conversation history, our goal is to calculate {metric}, but we have hit an issue where the final result is zero or null.
{dataframe}
Your job is to rewrite the SQL query to address this issue and generate the correct result for the {metric} calculation.
So far, our thought process has been: {thought}

A common cause of error that returns zero results is when the result forgot to take the date range into account, leading to a mismatch between the numerator and denominator.
Another common mistake is when the numerator is calculated independently of the denominator. Instead, the numerator within a CTE should be directly derived from the base formed by the denominator.
An important consequence is that filters in the numerator should never be exact replicas of those in the denominator, as this restriction can lead to a mismatch in the results.
If you cannot identify the issue, please output the original query without any modifications.
Your output should only contain well-formatted SQL without any further explanations or justifications.

Examples of properly formatted outputs:
#############
User: Yea, you can join with the Shopify data on the gAdReference id
Agent: Should I include all data available in the GoogleAds_Q3 table, or only consider a specific time frame?
User: Focusing on just the past week is good

_Original Query_
```sql
WITH LinkedInVisitors AS (
  SELECT DISTINCT buyerID
  FROM SalesRecord_Shopify_0812
  JOIN GoogleAds_Q3 ON SalesRecord_Shopify_0812.gAdRef = GoogleAds_Q3.gAd_ID
  WHERE GoogleAds_Q3.referrerURL LIKE '%linkedin%'
  AND GoogleAds_Q3.userActivity = 'clicks'
  AND SalesRecord_Shopify_0812.saleDate >= CURRENT_DATE - INTERVAL '1 week'
), LinkedInPurchases AS (
  SELECT buyerID
  FROM SalesRecord_Shopify_0812
  JOIN GoogleAds_Q3 ON SalesRecord_Shopify_0812.gAdRef = GoogleAds_Q3.gAd_ID
  WHERE GoogleAds_Q3.userActivity = 'purchase'
  AND GoogleAds_Q3.referrerURL LIKE '%linkedin%'
),
LinkedInConversions AS (
  SELECT
  (SELECT COUNT(DISTINCT buyerID) FROM LinkedInPurchases) AS TotalConversions,
  (SELECT COUNT(DISTINCT buyerID) FROM LinkedInVisitors) AS TotalVisits
)
SELECT
  TotalConversions,
  TotalVisits,
  COALESCE(TotalConversions * 1.0 / NULLIF(TotalVisits, 0), 0) AS CVR
FROM LinkedInConversions;
```

_Revised Query_
```sql
WITH LinkedInVisitors AS (
  SELECT DISTINCT buyerID
  FROM SalesRecord_Shopify_0812
  JOIN GoogleAds_Q3 ON SalesRecord_Shopify_0812.gAdRef = GoogleAds_Q3.gAd_ID
  WHERE GoogleAds_Q3.referrerURL LIKE '%linkedin%'
  AND GoogleAds_Q3.userActivity = 'clicks'
  AND SalesRecord_Shopify_0812.saleDate >= CURRENT_DATE - INTERVAL '1 week'
), LinkedInPurchases AS (
  SELECT buyerID
  FROM SalesRecord_Shopify_0812
  JOIN GoogleAds_Q3 ON SalesRecord_Shopify_0812.gAdRef = GoogleAds_Q3.gAd_ID
  WHERE GoogleAds_Q3.userActivity = 'purchase'
  AND SalesRecord_Shopify_0812.buyerID IN (SELECT buyerID FROM LinkedInVisitors)
),
LinkedInConversions AS (
  SELECT
  (SELECT COUNT(DISTINCT buyerID) FROM LinkedInPurchases) AS TotalConversions,
  (SELECT COUNT(DISTINCT buyerID) FROM LinkedInVisitors) AS TotalVisits
)
SELECT
  TotalConversions,
  TotalVisits,
  COALESCE(TotalConversions * 1.0 / NULLIF(TotalVisits, 0), 0) AS CVR
FROM LinkedInConversions;
```

#############
User: How many new customers did we get in the past month from the west coast?
Agent: We acquired 2,398 new customers in the past month in the west coast.
User: Can you help me calculate the retention?

_Original Query_
```sql
WITH WestCoastCustomers AS (
  SELECT DISTINCT HubspotCRM.cust_id AS customer_id
  FROM HubspotCRM
  WHERE HubspotCRM.region = 'West'
  AND HubspotCRM.signup_date >= 01/01/2025
), ActiveLastMonth AS (
  SELECT COUNT(DISTINCT WestCoastCustomers.customer_id) AS active_customers
  FROM WestCoastCustomers
  JOIN TransactionHistory ON TransactionHistory.cust_id = WestCoastCustomers.customer_id
  AND TransactionHistory.trans_date >= 07/01/2025
), WestCoastRetention AS (
  SELECT
    (SELECT COUNT(DISTINCT customer_id) FROM ActiveLastMonth AS ActiveCustomers,
    (SELECT COUNT(DISTINCT customer_id) FROM WestCoastCustomers) AS TotalCustomers
)
SELECT
  ActiveCustomers,
  TotalCustomers,
  COALESCE(ActiveCustomers * 1.0 / NULLIF(TotalCustomers, 0), 0) AS RetentionRate
FROM WestCoastRetention;
```

_Revised Query_
```sql
WITH WestCoastCustomers AS (
  SELECT DISTINCT HubspotCRM.cust_id AS customer_id
  FROM HubspotCRM
  WHERE HubspotCRM.region = 'West'
  AND HubspotCRM.signup_date >= CURRENT_DATE - INTERVAL '1 year'
), ActiveLastMonth AS (
  SELECT COUNT(DISTINCT WestCoastCustomers.customer_id) AS active_customers
  FROM WestCoastCustomers
  JOIN TransactionHistory ON TransactionHistory.cust_id = WestCoastCustomers.customer_id
  AND TransactionHistory.trans_date >= CURRENT_DATE - INTERVAL '1 month'
), WestCoastRetention AS (
  SELECT
    (SELECT active_customers FROM ActiveLastMonth) AS ActiveCustomers,
    (SELECT COUNT(DISTINCT customer_id) FROM WestCoastCustomers) AS TotalCustomers
)
SELECT
  ActiveCustomers,
  TotalCustomers,
  COALESCE(ActiveCustomers * 1.0 / NULLIF(TotalCustomers, 0), 0) AS RetentionRate
FROM WestCoastRetention;
```

#############
User: what is the overall click thru rate then?
Agent: What should I use to determine impressions?
User: You can use the page views count

_Original Query_
```sql
WITH FacebookImpressions AS (
  SELECT COUNT(DISTINCT UserID) AS impression_count
  FROM Activities
  WHERE ReferrerURL = 'www.facebook.com'
  AND ActivityType = 'page_view'
),
FacebookClicks AS (
  SELECT COUNT(DISTINCT UserID) AS click_count
  FROM Activities
  WHERE ReferrerURL = 'www.facebook.com'
  AND ActivityType = 'checkout'
)
SELECT
  FacebookImpressions.impression_count AS impressions,
  FacebookClicks.click_count AS clicks,
  COALESCE((clicks * 1.0) / NULLIF(impressions, 0), 0) AS CTR
FROM FacebookImpressions, FacebookClicks;
```

_Revised Query_
```sql
WITH FacebookImpressions AS (
  SELECT DISTINCT UserID
  FROM Activities
  WHERE ReferrerURL LIKE '%facebook%'
  AND ActivityType = 'page_view'
), FacebookClicks AS (
  SELECT UserID
  FROM Activities
  WHERE ActivityType = 'checkout'
  AND UserID IN (SELECT UserID FROM FacebookVisitors)
),
FacebookResults AS (
  SELECT
  (SELECT COUNT(DISTINCT UserID) FROM FacebookImpressions) AS TotalImpressions,
  (SELECT COUNT(DISTINCT UserID) FROM FacebookClicks) AS TotalClicks
)
SELECT
  TotalClicks,
  TotalImpressions,
  COALESCE(TotalClicks * 1.0 / NULLIF(TotalImpressions, 0), 0) AS CTR
FROM FacebookResults;
```

#############
Now it is your turn to revise the SQL query to address the issue and calculate the {metric} correctly.

{history}

_Original Query_
```sql
{sql_query}
```

_Revised Query_
"""

query_hint_prompt = """Given the conversation history, our goal is to aggregate some data, but we have hit an issue where the final result is zero or null.
{dataframe}
Your job is to rewrite the SQL query to address this issue and generate the correct result based on the conversation history.
So far, our thought process has been: {thought}
The dialogue state containing the columns to query from is:
{dialogue_state}

A common cause of error that returns zero results is when the result forgot to take the date range into account, leading to a mismatch between the numerator and denominator.
Another common mistake is when the numerator is calculated independently of the denominator. Instead, the numerator within a CTE should be directly derived from the base formed by the denominator.
An important consequence is that filters in the numerator should never be exact replicas of those in the denominator, as this restriction can lead to a mismatch in the results.
If you cannot identify the issue, please output the original query without any modifications.
Your output should only contain well-formatted SQL without any further explanations or justifications.

_Conversation History_
{history}

_Original Query_
```sql
{sql_query}
```

_Revised Query_
"""

plan_execution_prompt = """You are an outstanding data analyst who is exceptionally skilled at writing SQL queries.
Given the conversation history and a complete plan, your task is to generate an accurate SQL query that covers step {step_num}.
So far, we have already covered {previous_results}.
When you write the query, consider what columns might be relevant for {metric}, and then choose the specific column from the available options.{year_reminder}
If the situation is ambiguous and multiple columns may be appropriate, then output an error response followed by a clarification question for the user (eg. 'Error: Is the page_views or actions_taken column more appropriate for counting clicks?')
Remember, you are querying from DuckDB, so please use the appropriate syntax and casing for operations.
In all cases, only choose from the set of valid columns. This is very important to my career, please do NOT return any invalid columns.

#############
{convo_history}
{thought}
_Dialogue State_
{dialogue_state}

_SQL Query_
```sql
"""

recovery_prompt = """I am trying to run a SQL query on a DuckDB database to calculate {metric}. The query is:
{prior_query}
However, I get the following error:
{query_error}
For reference, the conversational context which generated this query is:
{history}
and the corresponding thought process was to:
{gameplan}
Given the conversation history and the step-by-step plan, please fix the query at step {step_num}. You only need to generate an accurate SQL query, no further explanation is needed. (eg. 'Query: SELECT COUNT(*) FROM page_visits')
If the issue is intractable, instead return the token 'Error' followed by a clarification question to resolve the problem. (eg. 'Error: I could not find any relevant columns for calculating mobile users, any idea where I should look?')
"""

pandas_repair_prompt = """I am trying to run a Pandas or Plotly operation on a dataframe. The code is:
```python
{prior_code}
```

However, I got the following error:
{execution_error}

For reference, the dialogue state is:
{thought}
{dialogue_state}
{data_preview}
Please revise the code so that it can be executed properly.
Your entire response should only contain valid Python code with thoughts to diagnose the error as inline comments.
There should be no additional text before or after the code block.

For example,
---
## Data Cleaning Example
_Operation_
```python
df = self.db.tables['february_2025']
average_subcription = df['Subscription (in USD)'].mean()
df['Subscription (in USD)'].fillna(average_subcription, inplace=True)
```

_Error_
ValueError: Invalid value '43048.847058' for dtype Int64

_Conversation History_
User: Yes, let's investigate
Agent: There are 17 null whole numbers in the Subcription (in USD) column.
User: Let's fill those in with the average of the remaining subscription values.

_Revised_
```python
# the error is caused by the average value being a float, so we need to round it
df = self.db.tables['february_2025']
average_subcription = df['Subscription (in USD)'].mean()
df['Subscription (in USD)'].fillna(round(average_subcription), inplace=True)
```

## Column Renaming Example
_Operation_
```python
fb_daily.rename(columns={{
    'total_impressions': 'fb_impressions',
    'total_clicks': 'fb_clicks',
    'total_spend': 'fb_spend'
}}, inplace=True)
```

_Error_
NameError: name 'fb_daily' is not defined

_Conversation History_
User: Can you rename the metrics in the google_daily table to say google_metric rather than total_metric?
Agent: Sure, how does this look?
User: Great, now do the same for the fb_daily table.

_Revised_
```python
# dataframes are accessed as db.table_name, so we need to add the 'db' prefix
db.fb_daily.rename(columns={{
    'total_impressions': 'fb_impressions',
    'total_clicks': 'fb_clicks',
    'total_spend': 'fb_spend'
}}, inplace=True)
```

## Plotting Example
_Operation_
```python
fig = px.bar(df, x='car_brand', y='num_cars_sold',
  labels={{
    'brand': 'Brand',
    'num_cars_sold': 'Cars Sold (#)'
  }},
  title='Number of Cars Sold')
```

_Error_
ValueError: All keys in labels dictionary must correspond to one of the following: ['car_brand', 'num_cars_sold']

_Conversation History_
User: How many cars did each brand sell?

_Revised_
```python
# the column is actually named 'car_brand', so we need to change the label
fig = px.bar(df, x='car_brand', y='num_cars_sold',
  labels={{
    'car_brand': 'Brand',
    'num_cars_sold': 'Cars Sold (#)'
  }},
  title='Number of Cars Sold')
```
---
Please revise the operation code to resolve the error.
Just return directly executable python code to manipulate the dataframe, without further explanations afterwards.

_Operation_
```python
{prior_code}
```

_Error_
{execution_error}

_Conversation History_
{history}

_Revised_
"""

sql_repair_prompt = """I am trying to run a SQL query on a DuckDB database. The query is:
```sql
{prior_code}
```

However, I get the following error:
{execution_error}

For reference, the conversational context which generated this query is:
{history}

and the corresponding dialogue state is:
{thought}
{dialogue_state}
{data_preview}
Please revise the query so that it can be executed properly.
No explanations are needed; just return valid code that can be directly run against the database.
Revised:"""

analyze_repair_prompt = """I am trying to run a SQL query on a DuckDB database to calculate {metric}. However, the results has led to empty and zero values:
{query_results}

Some common reasons for this issue include overly aggressive filtering, mis-matched joins, or incorrect aggregation.
Please think carefully about what is the most likely cause of the problem and revise the query accordingly.
If there is no plausible issue with the query, then declare that in the explanation and simply return the original query.

For example,
#############
_Original Query_
WITH LinkedInVisitors AS (
  SELECT DISTINCT buyerID
  FROM SalesRecord_Shopify_0812
  JOIN GoogleAds_Q3 ON SalesRecord_Shopify_0812.gAdRef = GoogleAds_Q3.gAd_ID
  WHERE GoogleAds_Q3.referrerURL LIKE '%linkedin%'
  AND GoogleAds_Q3.userActivity = 'clicks'
  AND SalesRecord_Shopify_0812.saleDate >= CURRENT_DATE - INTERVAL '1 week'
), LinkedInPurchases AS (
  SELECT buyerID
  FROM SalesRecord_Shopify_0812
  JOIN GoogleAds_Q3 ON SalesRecord_Shopify_0812.gAdRef = GoogleAds_Q3.gAd_ID
  WHERE GoogleAds_Q3.referrerURL LIKE '%linkedin%'
  AND GoogleAds_Q3.userActivity = 'purchase'
  AND SalesRecord_Shopify_0812.saleDate >= CURRENT_DATE - INTERVAL '1 week'
),
LinkedInConversions AS (
  SELECT
  (SELECT COUNT(DISTINCT buyerID) FROM LinkedInPurchases) AS TotalConversions,
  (SELECT COUNT(DISTINCT buyerID) FROM LinkedInVisitors) AS TotalVisits
),
SELECT
  TotalConversions,
  TotalVisits,
  COALESCE(TotalConversions * 1.0 / NULLIF(TotalVisits, 0), 0) AS CVR
FROM LinkedInConversions;

_Explanation_
When calculating conversions, we should not repeat extra restrictions within the numerator CTE. Instead, we should only consider conversion activities that are directly linked to the LinkedIn visitors. 

_Revised Query_
```sql
WITH LinkedInVisitors AS (
  SELECT DISTINCT buyerID
  FROM SalesRecord_Shopify_0812
  JOIN GoogleAds_Q3 ON SalesRecord_Shopify_0812.gAdRef = GoogleAds_Q3.gAd_ID
  WHERE GoogleAds_Q3.referrerURL LIKE '%linkedin%'
  AND GoogleAds_Q3.userActivity = 'clicks'
  AND SalesRecord_Shopify_0812.saleDate >= CURRENT_DATE - INTERVAL '1 week'
), LinkedInPurchases AS (
  SELECT buyerID
  FROM SalesRecord_Shopify_0812
  JOIN GoogleAds_Q3 ON SalesRecord_Shopify_0812.gAdRef = GoogleAds_Q3.gAd_ID
  WHERE GoogleAds_Q3.userActivity = 'purchase'
  AND SalesRecord_Shopify_0812.buyerID IN (SELECT buyerID FROM LinkedInVisitors)
),
LinkedInConversions AS (
  SELECT
  (SELECT COUNT(DISTINCT buyerID) FROM LinkedInPurchases) AS TotalConversions,
  (SELECT COUNT(DISTINCT buyerID) FROM LinkedInVisitors) AS TotalVisits
),
SELECT
  TotalConversions,
  TotalVisits,
  COALESCE(TotalConversions * 1.0 / NULLIF(TotalVisits, 0), 0) AS CVR
FROM LinkedInConversions;
```

#############
_Original Query_
SELECT customers.customer_id, customers.first, customers.last, SUM(transactions.price) AS total_spent
FROM customers
JOIN transactions ON customers.customer_id = transactions.customer_id
WHERE customers.pre_city = 'Los Angeles'
AND EXTRACT(YEAR FROM transactions.transaction_date) = 2024
GROUP BY customers.customer_id, customers.first, customers.last
HAVING total_spent > 500;

_Explanation_
The query references 2023, but we are already in 2025, so the date filter could be updated.

_Revised Query_
```sql
SELECT customers.customer_id, customers.first, customers.last, SUM(transactions.price) AS total_spent
FROM customers
JOIN transactions ON customers.customer_id = transactions.customer_id
WHERE customers.pre_city = 'Los Angeles'
AND EXTRACT(YEAR FROM transactions.transaction_date) = 2025
GROUP BY customers.customer_id, customers.first, customers.last
HAVING total_spent > 500;
```

#############
_Original Query_
WITH WestCoastCustomers AS (
  SELECT DISTINCT HubspotCRM.cust_id AS customer_id
  FROM HubspotCRM
  WHERE HubspotCRM.region = 'West'
  AND HubspotCRM.signup_date >= CURRENT_DATE - INTERVAL '1 year'
), ActiveLastMonth AS (
  SELECT COUNT(DISTINCT WestCoast.customer_id) AS active_customers
  FROM WestCoastCustomers
  JOIN TransactionHistory ON TransactionHistory.cust_id = WestCoast.customer_id
  AND TransactionHistory.trans_date >= CURRENT_DATE - INTERVAL '1 month'
), WestCoastRetention AS (
  SELECT
    (SELECT COUNT(DISTINCT cust_id) FROM ActiveLastMonth) AS ActiveCustomers,
    (SELECT COUNT(DISTINCT cust_id) FROM WestCoastCustomers) AS TotalCustomers
)
SELECT
  ActiveCustomers,
  TotalCustomers,
  COALESCE(ActiveCustomers * 1.0 / NULLIF(TotalCustomers, 0), 0) AS RetentionRate
FROM WestCoastRetention;

_Explanation_
The CTE WestCoastCustomers is referenced incorrectly in the ActiveLastMonth CTE causing a broken join. The correct reference should be WestCoastCustomers.customer_id.

_Revised Query_
```sql
WITH WestCoastCustomers AS (
  SELECT DISTINCT HubspotCRM.cust_id AS customer_id
  FROM HubspotCRM
  WHERE HubspotCRM.region = 'West'
  AND HubspotCRM.signup_date >= CURRENT_DATE - INTERVAL '1 year'
), ActiveLastMonth AS (
  SELECT COUNT(DISTINCT WestCoastCustomers.customer_id) AS active_customers
  FROM WestCoastCustomers
  JOIN TransactionHistory ON TransactionHistory.cust_id = WestCoastCustomers.customer_id
  AND TransactionHistory.trans_date >= CURRENT_DATE - INTERVAL '1 month'
), WestCoastRetention AS (
  SELECT
    (SELECT COUNT(DISTINCT cust_id) FROM ActiveLastMonth) AS ActiveCustomers,
    (SELECT COUNT(DISTINCT cust_id) FROM WestCoastCustomers) AS TotalCustomers
)
SELECT
  ActiveCustomers,
  TotalCustomers,
  COALESCE(ActiveCustomers * 1.0 / NULLIF(TotalCustomers, 0), 0) AS RetentionRate
FROM WestCoastRetention;
```

#############
_Original Query_
SELECT AccountsReceivable.CompanyID, AccountsReceivable.CompanyName
FROM AccountsReceivable
INNER JOIN Payments ON AccountsReceivable.CompanyID = Payments.CompanyID
WHERE Payments.PaymentPeriod = 'Apr'
GROUP BY AccountsReceivable.CompanyID, AccountsReceivable.CompanyName
HAVING SUM(Payments.SubscriptionFee) > 1000;

_Explanation_
The payment period filter is set to 'Apr', but this might actually refer to April of the current year.

_Revised Query_
```sql
SELECT AccountsReceivable.CompanyID, AccountsReceivable.CompanyName
FROM AccountsReceivable
INNER JOIN Payments ON AccountsReceivable.CompanyID = Payments.CompanyID
WHERE Payments.PaymentPeriod = 'April'
GROUP BY AccountsReceivable.CompanyID, AccountsReceivable.CompanyName
HAVING SUM(Payments.SubscriptionFee) > 1000;
```
#############
_Original Query_
{prior_query}

For reference, the conversational context which generated this query is:
{history}
and the corresponding thought process:
{thought}
{data_preview}
Please generate a concise explanation for the likely cause of the problem and then provide the corrected SQL query.
Do NOT include any additional text after the revised query.

_Explanation_
"""