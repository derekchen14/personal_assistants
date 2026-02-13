system_prompt = """You are an intelligent Data Analyst named Dana that is able to answer questions about {db_meta}.

You are given the below tables within a DuckDB database:
{table_meta}

When asked for anything related to time, note that {time_meta}. Therefore, if a year is not specified, you should peek at the data, and if the data doesn't have a year, you should assume the user is referring to {year}.
{pref_meta}"""

safety_guide = "I should steer the conversation back towards the topics of data cleaning and marketing analysis if we are not already there. As usual, I will be concise in my response, replying with no more than a few sentences at most."

persona_messages = [
  "You are a reliable and helpful assistant, who enjoys their role as a data analyst.",
  "Your friends would describe you as happy, cheerful and just a little bit geeky.",
  "Also, remember to be concise in your responses.",
]

intent_phrases = {
  "Analyze": "analyze the data or measure a metric",
  "Visualize": "generate a chart, modify a figure, or manage a report",
  "Clean": "update the values in the table to clean things up",
  "Transform": "manipulate the shape or structure of the spreadsheet",
  "Detect": "identify issues such as outliers, anomalies, null values or typos",
  "Converse": "have a conversation about non-data related subjects"
}

# Hard limit of 64 options total
dax_phrases = {
  '000': 'chat about some non-data related subjects',
  '001': 'filter, group, or sort the data',
  '002': 'calculate a marketing metric',
  '003': 'create a visual graph, chart, or figure',
  '004': 'get an answer from the FAQs',
  '005': 'add information into the table',
  '006': 'fill values in the table',
  '007': 'remove or hide some rows or columns',
  '008': 'provide some of your user preferences',
  '009': 'inquire what the agent said or did',
  '00A': 'reference a specific table',
  '00B': 'reference a specific row',
  '00C': 'reference a specific column',
  '00D': 'do something complicated involving multiple steps',
  '00E': 'celebrate the good results',
  '00F': 'express confusion or dissatisfaction',
  '012': 'perform analysis on some subset of the data',
  '13D': 'create and manage reports',
  '015': 'add a column and query it right away',
  '023': 'add a trendline or cluster the data',
  '02D': 'request guidance on segmentation analysis',
  '02F': 'express discontent',
  '01A': 'make or modify pivot tables',
  '014': 'know more about what data is available',
  '14C': "know if a certain column exists",
  '148': 'if there are any interest insights in this data',
  '28C': 'set metric definitions',
  '036': 'apply formatting elements to the figure',
  '038': 'summarize the information within the figure',
  '36A': 'format a table with an updated design',
  '36B': 'format a row with an updated design',
  '36C': "format a column with an updated design",
  '468': 'identify potential problems in the data',
  '46D': 'resolve typos',
  '46E': 'identify outliers, anomalies, or other issues',
  '46F': 'resolve issues with nulls or blank values',
  '048': 'pull existing user preferences',
  '05A': 'integrate data across tables',
  '05C': 'merge columns together',
  '057': 'cut and paste some values',
  '058': 'declare user preferences',
  '56B': 'transpose rows into columns',
  '56C': 'transpose columns into rows',
  '5CD': 'run text-to-columns',
  '06F': 'undo the last step',
  '067': 'update and delete some data',
  '068': 'update user preferences',
  '7BD': 'remove duplicate or repeated rows',
  '08E': 'confirm interest to look',
  '09E': "confirm the response",
  '09F': "question the accuracy of my answer",
  '138': "know how a visual was created",
  '028': "know how the analysis is performed",
  '08F': "declare the issue as not important",
  '02E': "confirmed the anaysis is correct",
  '049': "ask for my recommendation on something"
}

# BlankType(), UniqueType(), DateTimeType(), LocationType(), NumberType(), TextType()
type_descriptions = {
  'blank': 'empty or null values',
  'unique': 'booleans, categorical data, and IDs',
  'datetime': 'dates, times, and timestamps',
  'location': 'addresses, cities, states, and countries',
  'number': 'numerical values and percentages',
  'text': 'textual data and descriptions'
}

subtype_descriptions = {
  'null': 'null values',
  'missing': 'missing values',
  'default': 'default values',
  'boolean': 'binary values such as True/False',
  'status': 'possible object states chosen from a short, finite list',
  'category': 'categorical values that are not ordered',
  'id': 'unique identifiers for each row',
  'year': 'years or dates',
  'quarter': 'quarters of the year',
  'month': 'months of the year',
  'week': 'days of the week',
  'day': 'days of the month',
  'hour': 'hours of the day',
  'minute': 'minutes of the hour',
  'second': 'seconds within a minute',
  'date': 'full date with month, day, and year',
  'time': 'full time with hour, minute, and second',
  'timestamp': 'a full date and time',
  'street': 'street names or addresses',
  'city': 'city names',
  'state': 'states within a country',
  'zip': 'zip codes',
  'country': 'countries',
  'address': 'full street address locations',
  'currency': 'monetary values',
  'percent': 'percentage values',
  'whole': 'whole numbers',
  'decimal': 'decimal numbers',
  'email': 'email addresses',
  'phone': 'phone numbers',
  'name': 'names of people or things',
  'url': 'web addresses',
  'general': 'generic text or strings'
}

description_prompt = """Given a table and column name, along with a handful of examples, please write a few words to characterize the column's contents.
Note, the examples are not exhaustive, and you should write a description general enough to the full range of possible values.

Company: shoe store
Table name: products
Examples: Adidas, Nike, Vans, Reebok
Short description: shoe brands

Company: online jeweler
Table name: customers
Examples: New York, San Francisco, Los Angeles, Chicago
Short description: cities where customers live

Company: online jeweler
Table name: customers
Examples: California, New York, Florida, Texas
Short description: states where customers live

Company: we are a supermarket specializing in novelty foods
Table name: ice_cream
Examples: vanilla, cookies and cream, mint chocolate chip, strawberry
Short description: flavors of ice cream

Company: shoe store
Table name: {table_name}
Examples: {examples}
Short description:"""

find_col_prompt = """Given the predicted column and table names as input, compare against the lists of valid column options in each table.
If there is similar match in meaning or spelling, return 'yes' with the matching column name and table.
If there is anything remotely related, return 'maybe' with the matching column name and table.
Finally, if the column is not related to any of the valid options, return 'no' with 'N/A'

Only select column and table names from the provided options, including matching casing and plurality.
Your entire response should be well-formatted JSON with match (string) and output (dict). There should be no further explanations after the JSON output.

For example,
---
Input: size in orders
Options:
product_id, sku, type, brand, style, cost in products table.
order_id, product_id, customer_id, length, channel, price, month, day, year in orders table.
customer_id, first, last, city, state, membership in customers table.

_Output_
```json
{{
  "match": "maybe",
  "output": {{"tab": "orders", "col": "length"}}
}}
```

Input: revenue in Purchases
Options:
ActivityID, UserID, ActivityType, ActivityTime, PageURL, UserAgent, ReferrerURL, SessionID. Activitytypes in Activity table.
PurchaseID, UserID, ProductID, PurchaseTime, Quantity, Discount, Tax, UnitPrice, TotalSales, PaymentMethod, ShippingAddress in Purchases table.
ProductID, ProductName, ProductDescription, Category, Supplier, InitialQuantity, CurrentQuantity, ReorderLevel, LastReplenishmentDate, NextReplenishmentDate in Inventory table.

_Output_
```json
{{
  "match": "yes",
  "output": {{"tab": "Purchases", "col": "TotalSales"}}
}}
```

Input: source in traffic
Options:
product_id, traffic_id, user_id, product_name, description, category, supplier, color, shape, dimension in products table.
traffic_id, traffic_type, user_name, email_address, date_time, visited_page, session, user_agent, referrer in traffic table.
user_id, first_name, last_name, email_address, phone_number, street_address, city, state, zip_code, country, date_joined, last_login in users table.

_Output_
```json
{{
  "match": "maybe",
  "output": {{"tab": "traffic", "col": "referrer"}}
}}
```

Input: color in Orders
Options:
OrderID, CustomerID, Size, Price, Timestamp, Quantity, Brand, ServiceLevel, Category, Subcategory in Orders table.
CustomerID, FirstName, LastName, Email, Phone, StreetAddress, City, State, ZipCode, Country, DateJoined, LastLogin in Customers table.
ServiceID, ServiceName, Description, MajorCategory, MinorCategory, Pricing, Duration, Level in Services table.

_Output_
```json
{{
  "match": "no",
  "output": {{"tab": "N/A", "col": "N/A"}}
}}
```

Input: first_name in Customers
Options:
order_id, product_id, customer_id, shape, channel, price, month, day, year in orders table.
customer_id, first, last, city, state, membership in customers table.
product_id, sku, type, brand, style, cost in products table.

_Output_
```json
{{
  "match": "yes",
  "output": {{"tab": "customers", "col": "first"}}
}}
```

Input: cpc in channel
Options:
channel_id, channel_name, channel_type, amount_spent, metric, return_on_ad_spend, cost_per_click, cost_per_acquisition, cost_per_impression in channel table.
product_id, product_name, description, supplier, initial_quantity, current_quantity, reorder_level, last_replenishment_date, next_replenishment_date in inventory table.
activity_id, user_id, activity_type, activity_time, page_url, user_agent, referrer_url, session_id in activities table.

_Output_
```json
{{
  "match": "yes",
  "output": {{"tab": "channel", "col": "cost_per_click"}}
}}
```

Input: win_rate in leads
Options: 
contact_id, firstname, lastname, date_joined, email_address, opportunity_id, stage, dealsize, last_contact_date, next_step, decision_maker, location in sales table.
opportunities, won_deals, lost_deals, deal_value, sales_cycle_length, lead_source, sales_rep, product/service, region, time_peiod, customer_type in lead table.
LeadID, Username, Email, Source, PageVisited, VisitDateTime, FormSubmitted, FormSubmissionDateTime, LeadScore, DownloadedContent, IsConversion, ConversionTime in marketing table.

_Output_
```json
{{
  "match": "maybe",
  "output": {{"tab": "lead", "col": "won_deals"}}
}}
```

Input: Username in users
Options: 
ServiceID, ServiceName, Description, MajorCategory, MinorCategory, Pricing, Duration, Level in services table.
OrderID, CustomerID, Size, Price, Timestamp, Quantity, Brand, Color, Style, Category, Subcategory in orders table.
UserID, EmailAddress, Phone, StreetAddress, City, State, ZipCode, MemberStatus, DateJoined, LastSignIn in users table.

_Output_
```json
{{
  "match": "maybe",
  "output": {{"tab": "users", "col": "EmailAddress"}}
}}
```

Input: ate_time in Mailchimp
Options:
LeadID, Username, Email, Source, PageVisited, VisitedTime, FormSubmitted, FormSubmissionTime, LeadScore, DownloadedContent, IsConversion, ConversionTime in Hubspot table.
Subscriber_ID, First_Name, Last_Name, Email, Campaign_ID, Date_Time, Opened, Clicked, Unsubscribed, List_Segment, Clicked_Link in MailChimp table.
ContactID, FirstName, LastName, Date_Joined, Email_Address, OpportunityID, Stage, DealSize, LastContacted, NextStep, DecisionMaker, Location (city), Location (state), Location (country) in Salesforce table.
TicketID, RequesterName, RequesterEmail, OpenTimestamp, CloseTimestamp, Status, SatisfactionRating, AssignedAgent, IssueType, ResolutionTime in Zendesk table.

_Output_
```json
{{
  "match": "yes",
  "output": {{"tab": "MailChimp", "col": "Date_Time"}}
}}
```
---
Input: {given_col} in {given_tab}
Options:
{options}

_Output_
"""

rewrite_prompt = """Given an initial user request, a clarifying question from an agent and the user answer, please revise into a concise, summarized utterance that incorporates all details of the conversation. 
Assume that the rewritten utterance will be used to replace the user request.

For example,
---
User: How are the brands doing?
Agent: When it comes to performance, do you care about revenue or order volume?
User: I care about order volume.
Rewritten: How much is the total order volume of each brand?

User: When was the last customer contact for Peter Wright?
Agent: There is no customer with that name. Do you mean Piotr Rite?
User: Yea, that's the one.
Rewritten: When was the last customer contact for Piotr Rite?

User: What is the campaign style that generated the highest conversions last month?
Agent: Which column(s) in the activities tables are you referring to?
User: campaign name
Rewritten: What is the name of the campaign that generated the highest conversions last month?

User: Which sales rep converted the most leads in
Agent: I'm sorry, I don't understand. Please rephrase your question.
User: February
Rewritten: Which sales rep converted the most leads in February?

User: How are the brands doing?
Agent: When it comes to performance, do you care about revenue or order volume?
User: profit
Rewritten: What is the total profit of all orders, grouped by brand?

User: How many people bought annual subscriptions in June?
Agent: Are you referring to the column PaidSubs?
User: yeah
Rewritten: How many people bought any annual subscriptions according to the PaidSubs column in June?

User: How many user sign-ups did we have last month?
Agent: Do you mean sign-up to the email list or sign-up to the website?
User: Oh yea, that's a good point. Uhh, Kelly probably wants email.
Rewritten: How many user sign-ups did we have for the email list last month?

User: How many user purchases occured last Monday?
Agent: We not have have a purchases column.  Can you please clarify what you mean?
User: sales?
Rewritten: How many user sales occured last Monday?
---
{history}
User: {orig_request}
Rewritten:"""

rewrite_metric_prompt = """An initial user request had some ambiguity, so after some thinking we asked a clarification question that the user then answered.
Our task is to generate a concise, summarized utterance that incorporates all details of the conversation. This rewritten utterance will be used to replace the original user request.
Additionally, we should update the variables formula with any columns that were explicitly verified by the user in their answer.
Following the structure of the original equation, the verified variables include a comma-separated list of column names within the brackets.

For example,
#############
User: How much was our return on investment last year?
Metric: return on investment (ROI) = (revenue [unverified] - costs [unverified]) / costs [unverified]
Thought: There is no direct column for ROI, so we will need to calculate it ourselves. None of the variables are verified either, so I will go with sum of expenses as 'costs'.
With that said, many reasonable options exist for 'revenue', including license_fee, service_charge, or maintenance_income.
We also need to filter for last quarter, which was calculated using interact_date in the prior query, so I will use the same column this time as well.
Question: Should I use license_fee, service_charge, or maintenance_income to calculate revenue?
Answer: Revenue is the sum of licenses and maintenance
Rewritten: How much was our return on investment last year? We can calculate the 'revenue' variable of ROI as the sum of license_fee and maintenance_income.
Formula: return on investment (ROI) = (revenue [verified as license_fee, maintenance_income] - costs [unverified]) / costs [unverified]

#############
User: How are the new sports campaigns doing?
Metric: average order value (AOV) = revenue [verified as SalesPrice, UnitsSold] / orders [unverified]
Thought: We can calculate average order value by multiplying SalesPrice and UnitsSold, then dividing by the number of orders.
I should also check to see if there are other columns such as taxes, discounts, or other adjustments that might affect order value.
In order to perform an accurate calculation, we should divide by the unique number of orders rather than the number of rows, probably based on order_id.
We also need to filter for the new campaigns, but it is unclear which campaigns are considered 'new', so we should clarify with the user.
Question: How do we determine if a campaign is new?
Answer: Basically all the sports campaigns are new
Rewritten: How are the sports campaigns doing according to AOV. The 'total order value' can be calculated by multiplying SalesPrice and UnitsSold.
The average can then be calculated by dividing by the number of unique orders.
Formula: average order value (AOV) = revenue [verified as SalesPrice, UnitsSold] / orders [verified as order_id]

#############
User: what if we limited to just Google?
Metric: click-thru rate (CTR) = clicks [unverified] / impressions [unverified]
Thought: We should start by filtering for Google, likely using the ad_platform column AdobeAnalytics_final.
That table offers view_count to determine impressions, but there is also an impressions column in Canva Content (revised), so we should clarify which one to use.
There isn't a cost column, but cost_per_click and ad_spend can be used to approximate the number of clicks, which we should review with the user.
Question: Should I use view_count or impressions to calculate impressions? Also, is it appropriate to use divide ad_spend by cost_per_click to calculate clicks?
Answer: Use view counts and yea go ahead
Rewritten: What is the click-thru rate of Google ads? Number of 'impressions' can be calculated using the view_count column in AdobeAnalytics_final.
Number of 'clicks' can be inferred by using the ad_spend and cost_per_click columns.
Formula: click-thru rate (CTR) = clicks [verified as ad_spend, cost_per_click] / impressions [verified as view_count]

#############
User: What is the conversion rate in that time frame?
Metric: conversion rate (CVR) = conversions [unverified] / visits [unverified]
Thought: We previously determined that we should start by filtering for users coming from LinkedIn, likely by using the entryURL column.
We also need to filter for the past week, which can come from the saleDate or the activityTimestamp column.
Lastly, visits and conversions are both activity types in userActivity, using the 'view_site' and 'purchase' values respectively.
Question: Should I use saleDate or activityTimestamp to filter for the past week?
Answer: timestamp shoudl work
Rewritten: What is the conversion rate of LinkedIn ads last week? Please filter for users coming from LinkedIn using the entryURL column. Also filter for the past week using the activityTimestamp column.
Number of 'visits' is determined by the userActivity column where the value is 'view_site'. Similarly, the number of 'conversions' is determined by the userActivity column where the value is 'purchase'.
Formula: conversion rate (CVR) = conversions [verified as userActivity] / visits [verified as userActivity]

#############
User: Yea, clickCount looks good.
Metric: cost-per-click (CPC) = costs [unverified] / clicks [verified as clickCount]
Thought: clickCount can be used for measure the number of clicks. Both adSpend and totalCost are plausible options for cost though, so we should clarify.
We also need to filter for just the last month. When performing calculations, we should limit cost to only those that are directly attributable to clicks.
Question: Should I use adSpend or totalCost to calculate cost?
Answer: adSpend is fine
Rewritten: What is the cost-per-click last month? Number of 'clicks' can be calculated using the clickCount column. Total 'cost' can be calculated using the adSpend column. Please filter for just the last month.
Formula: cost-per-click (CPC) = costs [verified as adSpend] / clicks [verified as clickCount]

#############
User: Which of the campaigns did best over the weekend? profit wise
Metric: profit (Profit) = revenue [unverified] - costs [unverified]
Thought: There is no column for profit, so we will need to calculate it ourselves. There is a RecentSales table which may contain revenue with an amount column.
There is also an total_fee column in the Week12_Consolidated table, but many of the values seem to be empty or blank.
We should also remember to filter for the weekend, which can be done using the interaction_time column.
Question: In order to determine the number of total revenue, I can sum the values in the amount column of RecentSales, or sum the values in the total_fee column of Week12_Consolidated. Does either of these sound right?
Answer: sum the order amounts in RecentSales where the transaction is approved
Rewritten: Which of the campaigns did best over the weekend according to net profit? Total 'revenue' can be calculated by summing amount column in the RecentSales table where the transaction is approved.
Please also filter for the weekend using the interaction_time column.
Formula: profit (Profit) = revenue [verified as amount] - costs [unverified]

#############
User: Did the open rate improve at all?
Metric: open rate (Open) = opens [unverified] / sends [unverified]
Thought: We should filter for the past five days of activity, which can likely be found with the sent_timestamp.
There is no columns for count of sends or count of opens, so we will need to calculate it ourselves. There is a open_timestamp available though.
We can possibly use the open_timestamp to calculate the number of opens, but we should clarify with the user.
Question: I can use rows that are not null in the open_timestamp column to calculate the number of opens. Does that sound right?
Answer: There's actually is_viewed column.
Rewritten: How does the open rate in the last five days compare to the week before? Number of 'opens' can be calculated by counting the True values in the is_viewed column.
Formula: open rate (Open) = opens [verified as is_viewed] / sends [unverified]

#############
User: What is the churn rate in the past month? You can use the activity table to see if tell if they're active.
Metric: customer churn rate (Churn) = not (active customers [unverified]) / total customers [unverified]
Thought: We should start by filtering for the past month, which can likely be found with the last_login column.
Churn rate counts the number of inactive users, where a user who appears in the Activity table is considered active. This needs to be joined with the Customer table to get the total number of users.
However, there does not seem to be a customer id column in the Activity table to join on. We should clarify with the user.
Question: Do you have any suggestions on how to join the Activity table with the Customer table?
Answer: Good question, I was hoping you could help with that.
Rewritten: What is the customer churn rate in the past month? Please filter for the past month using the last_login column.
Number of 'inactive users' can be calculated by counting the number of rows in the Activity table that do not appear in the Customer table.
Please brainstorm methods for joining the two tables, possibly by entering a data integration flow.
Formula: customer churn rate (Churn) = not (active customers [unverified]) / total customers [unverified]

#############
Following the examples above, please rewrite the user request based on information in the thought, and then declare any variables that were explicitly verified by the user.
The formula of verified variables should only contain valid column names:
{valid_cols}
Any other details, such as 'where' clauses or table names, belong in the rewritten utterance and should not be within the variables formula.

User: {history}
Metric: {metric}
Thought: {thought}
Question: {question}
Answer: {answer}
Rewritten:"""

edit_state_prompt = """Given the initial user utterance, the previous dialogue state, the agent's clarification question, and the user's answer, update the dialogue state.
The dialogue state is made up of the below:
* Table(s) needed to query to answer the user request
* Columns from these tables that are useful to query
* Filters and other operations to be applied to the columns
Think step by step first, before generating the updated dialogue state.

For example,
#############
Original user utterance: How are the channels doing?
Dialogue state:
* Table: orders
* Columns: channels in orders
* Operations: unsure
Agent question: When it comes to performance, do you care about revenue or order volume?
User clarification: Revenue is good
Thought: The user is asking for how much revenue each channel took, so I need to get the price and channels column. There is no more ambiguity for column or table to use to answer the original question.
Updated dialogue state:
* Table: orders
* Columns: price, channels in orders
* Operations: sum of price

#############
Original user utterance: Ok, let's give this a shot
Dialogue state:
* Table: unsure
* Columns: unsure
* Operations: current month is March
Agent question: I'm sorry, I didn't quite get that.  What would you like to know?
User clarification: What shoe brand sold the most in the last month?
Thought: The user would like to know the name of the shoe brand, so I need the brand column in products table.  The current month is March, so last month is February.
I can get the number of products sold by looking at the product_id in the orders table.
Updated dialogue state:
* Table: orders, products
* Columns: product_id, month in orders; brand in products
* Operations: month is February

#############
Original user utterance: {user_text}
Dialogue state:
{dialogue_state}
Agent question: {agent_question}
User clarification: {user_answer}
Thought:"""

similar_terms_prompt = """Given the set of unique values within a column, your task is to determine what sets of similar terms or typos might exist.
This may occur because terms are misspelled, abbreviated, or otherwise inconsistent. 
If there are any such candidates, please output the most likely canonical term, followed by the set of similar terms. Otherwise, simply output an empty dict.

Your entire response should a well-formatted JSON dict with the canonical term (string) as the key and similar terms (list) as the values. There should be no further explanations after the JSON output.
We will consider a handful of example scenarios, and then tackle the current case.

For example,
---
### channel column
search_bing, email_existing, email_new_user, search_google, Google, social_fb, affiliate_display, social_tiktok, TikTok, affiliate_text, GA, social_twitter, Google Analytics, Bing, Yahoo, google_search, FB, search_yahoo, email_newuser, Facebook Ads, Facebook, Twitter

_Candidates_
```json
{{
  "Google": ["search_google", "google_search", "Google"],
  "Google Analytics": ["GA", "Google Analytics"],
  "Facebook": ["social_fb", "FB", "Facebook Ads", "Facebook"],
  "TikTok": ["social_tiktok", "TikTok"],
  "Bing": ["search_bing", "Bing"],
  "Yahoo": ["search_yahoo", "Yahoo"],
  "Twitter": ["social_twitter", "Twitter"],
  "email_new_user": ["email_new_user", "email_newuser"],
}}
```

### brand column
Nike, Adidas, Reebok, Puma, New Balance, Converse, Vans, Timberland, Dr. Martens, Clarks, Sperry, Cole Haan, Merrell, ASICS, Brooks, UGG, Steve Madden, Sam Edelman, Tory Burch, Nine West, Jimmy Choo, Christian Louboutin, Manolo Blahnik, Gucci, Prada, Valentino, Chanel, Yves Saint Laurent, Alexander McQueen, Miu Miu, Stella McCartney, Rebook, Dolce & Gabbana, Salvatore Ferragamo, Versace, Fendi, Givenchy, Bottega Veneta

_Candidates_
```json
{{
  "Reebok": ["Reebok", "Rebook"]
}}
```

### State column
Illinois, New York, Ontario, GA, Nevada, Tennesee, Florida, Washington, New York City, Colorado, Californa, Ohio, Texas, California, CA, North Carolina, Oklahoma, New Jersey, Big Apple, Massachusetts, Indiana, Arizona, Pennsylvania, FL, New Mexico, TX, Rhode Island, NYC, Michigan, Maine

_Candidates_
```json
{{
  "New York": ["New York", "New York City", "Big Apple",  "NYC"],
  "California": ["Californa", "CA", "California"],
  "Florida": ["FL", "Florida"],
  "Texas": ["TX", "Texas"]
}}
```

### product_supplier column
LushLock Labs, SkinLove Laboratories, Aroma Elixir, CharmChic Creations, SilkenStrand Solutions, Natural Allure, StarDust Beauty, Eternal Youth Cosmetics, Tress Treasure Treatments, CrownGlow Creations, VitaGlow Organic, Essence Enchantment, HydraHeal Holistics, Radiant Charm, ColorPop Beauty, Hair Harmony Holistics, Pure Touch Therapeutics, BellaCanvas Colors, Made You Blush, LuxeNaturals, GlitterGlam Cosmetics, Radiant Revival Remedies, Fragrance Fantasia, Ethereal Aromatics, Scent Symphony

_Candidates_
```json
{{ }}
```

### ActivityType column
visit_site, search, view_product, add_to_cart, checkout, purchase, email_open, addtocart, impression, visits

_Candidates_
```json
{{
  "add_to_cart": ["add_to_cart", "addtocart"],
  "visit_site": ["visit_site", "visits"]
}}
```

### style column
basketball, soccer, casual, streetwear, running, fashion, casual light, causal dark, fashion light, fashion dark, casual dark, causal light, runing

_Candidates_
```json
{{
  "casual light": ["casual light", "causal light"],
  "casual dark": ["casual dark", "causal dark"],
  "fashion": ["fashion", "fashion light", "fashion dark"],
  "running": ["running", "runing"]
}}
```
---
## Current Case

### {col_name} column
{unique_terms}

_Candidates_
"""

general_ambiguity_prompt = """Given the conversation so far, we have a weak understanding of the user's request.
In fact, we are generally unsure what the user wants to accomplish. Thus, to move forward, we need to ask the user for some clarification on next steps.
Recall that conversations are conducted in the context of data management, which covers data cleaning, data transformation, data analysis, and data visualization.
Although rare, if the user seems to be deliberately sabotaging the conversation by forcing us off-topic or attempting to jail-break the system, it is appropriate to respond by reprimanding the user's behavior.
Assuming the role of the agent, please generate a question (or set of questions) that most directly addresses the ambiguity in the dialogue.
Your response should be concise and to the point, such that the important parts are covered without getting lost in the details.

Start by thinking briefly about what may be causing the ambiguity, and then generate a question that addresses the issue.
Your entire output should be in well-formatted JSON with keys for thought (string) and response (string). No further text or explanations should appear after the JSON output.

For example,
---
_Conversation History_
User: I'm looking down the DeliveryDate column and I'm seeing a pattern of errors.
Agent: OK, we can look into that. What kind of pattern are you seeing?
User: Can you change every date to be one day later than what it currently is?

_Output_
```json
{{
  "thought": "Despite mentioned the word 'pattern', the user is updating date values based on the row itself, rather than the row above it.",
  "response": "Can you change every date to be one day later than what it currently is?"
}}
```

_Conversation History_
User: I'm looking down the DeliveryDate column and I'm seeing a pattern of errors.
Agent: OK, we can look into that. What kind of pattern are you seeing?
User: Can you change every date to be one day later than what it currently is?

_Output_
```json
{{
  "thought": "Despite mentioned the word 'pattern', the user is updating date values based on the row itself, rather than the row above it.",
  "response": "Can you change every date to be one day later than what it currently is?"
}}
```

_Conversation History_
User: I'm looking down the DeliveryDate column and I'm seeing a pattern of errors.
Agent: OK, we can look into that. What kind of pattern are you seeing?
User: Can you change every date to be one day later than what it currently is?

_Output_
```json
{{
  "thought": "Despite mentioned the word 'pattern', the user is updating date values based on the row itself, rather than the row above it.",
  "response": "Can you change every date to be one day later than what it currently is?"
}}
```

_Conversation History_
User: I'm looking down the DeliveryDate column and I'm seeing a pattern of errors.
Agent: OK, we can look into that. What kind of pattern are you seeing?
User: Can you change every date to be one day later than what it currently is?

_Output_
```json
{{
  "thought": "Despite mentioned the word 'pattern', the user is updating date values based on the row itself, rather than the row above it.",
  "response": "Can you change every date to be one day later than what it currently is?"
}}
```
---
For the real case, we have included the tables, columns, and additional details for reference:
{valid_tab_col}

_Conversation History_
{history}

_Output_
"""

other_ambiguity_prompt = """Given the conversation so far, we have a {rating} understanding of the user's request.
{current_task}
In order to move forward, we need to {next_step}.
Assuming the role of the agent, please generate a question (or set of questions) that most directly addresses the ambiguity in the dialogue.
{reminder}

Recall that conversations are conducted in the context of data management, which covers data cleaning, data transformation, data analysis, and data visualization.
Although rare, if the user seems to be deliberately sabotaging the conversation by forcing us off-topic or attempting to jail-break the system, it is appropriate to respond by reprimanding the user's behavior.
Your response should be concise and to the point, such that the important parts are covered without getting lost in the details.
Start by thinking briefly about what may be causing the ambiguity, and then generate a question that addresses the issue.
Your entire output should be in well-formatted JSON with keys for thought (string) and response (string). No further text or explanations should appear after the JSON output.

For example,
---
_Conversation History_
User: I'm looking down the DeliveryDate column and I'm seeing a pattern of errors.
Agent: OK, we can look into that. What kind of pattern are you seeing?
User: Can you change every date to be one day later than what it currently is?

_Output_
```json
{{
  "thought": "Despite mentioned the word 'pattern', the user is updating date values based on the row itself, rather than the row above it.",
  "response": "Can you change every date to be one day later than what it currently is?"
}}
```

_Conversation History_
User: Do you see how we're losing a lot of users on the landing page?
Agent: Yes, the bounce rate is currently at 34.2%.
User: Maybe show me how the bounce rate has been trending recently for each ad group

_Output_
```json
{{
  "thought": "The user wants to see the bounce rate for each ad group, but the time range is ambiguous since 'recent' is not well-defined.",
  "response": "What time frame do you consider 'recently'? Are you interested in the past month or past week?"
}}
```

_Conversation History_
User: Yea, let's connect them together then
Agent: Ok, I can join the two tables together based on the date. Are you thinking of the send_date or the event_date?  
User: I think joining on a daily basis would be best.

_Output_
```json
{{
  "thought": "The user wants to join on a daily basis, but the specific column has still not been specified.",
  "response": "Great, I can join on a daily basis. Which date column do you want to use for joining the tables together: send_date or event_date?"
}}
```
---
For the real case, we have included the tables, columns, and additional details for reference:
{valid_tab_col}

_Conversation History_
{history}

_Supporting Details_
{details}

_Output_
"""

measure_clarification_prompt = """Given the conversation so far, we have an incomplete understanding of how to calculate the {full_name} metric.
Your task is to generate a question (or set of questions) that most directly addresses the ambiguity in building the formula.

For context, metrics are defined as formulas that combine variables, which can then be broken down into further variables as needed.
At the higher levels, variables are connected by relationships such as addition, subtraction, multiplication or division.
The list of valid relations include: add (+), subtract (-), multiply (*), divide (/), not (!), exponent (^), and (&), or (|), less_than (<), greater_than (>), equals (=), conditional (?).
There is one last relationship called 'placeholder', which is used when we are unsure about how to properly structure the expression at that level.
This is particularly relevant to our situation, since it hints at the main ambiguity we are facing (and therefore sort of question to ask)

At the lowest level, variables are constructed as aggregations of columns in a table.
Valid aggregations include: sum, count, average, top, bottom, min, max, greater_than, less_than, equals, empty, filled, constant, all.
For the aggregations of [top, bottom, greater_than, less_than, equals, constant], the 'row' field is used to specify the value of N.

Our current belief is that {short_name} is calculated as follows: {thoughts}.
However, this may be incorrect, so we need to get the user's feedback to confirm our understanding.
Concretely, we want the user to {ambiguity}.

As the agent, you have full access to the metric formula, but the user is only aware of what has been discussed in the conversation.
Thus, you must provide any missing information in your response in order to make the question comprehensible within the dialogue context.
Furthermore, do not distance yourself from the process by saying 'I noticed our current calculation does X' or 'I see that the formula does Y'.
Instead, take ownership of the formulation by phrasing it along the lines of 'My calculation does X' or 'The formula currently contains Y'.

Your entire response should be in well-formatted JSON with keys for thought (string) and response (string). No further text or explanations should appear after the JSON output.

For example,
---
_Conversation History_
User: Let's look at just the month of April.
Agent: The revenue in April was approximately $272,100
User: So what is our net profit at that time?
In this example, we are trying to calculate Net Profit (Profit).
Additional thought: The discrepancy comes from choosing whether to include renewal_revenue. We will go with generated_revenue alone because it shares the same table as final_expenses, but we should clarify with the user.

_Current Formula_
{{
  "name": "Net Profit",
  "relation": "and"
  "variables": [
    {{
      "name": "Profit",
      "relation": "subtract",
      "variables": [
        {{"name": "revenue", "agg": "sum", "tab": "Q4Bookings", "col": "generated_revenue"}},
        {{"name": "expenses", "agg": "sum", "tab": "Q4Bookings", "col": "final_expenses"}},
      ]
    }}, {{
      "name": "In_April", "agg": "equals", "tab": "Q4Bookings", "col": "start_date", "row": "April"
    }}
  ]
}}

_Output_
```json
{{
  "thought": "The main ambiguity is whether to include renewal_revenue in the calculation of Net Profit.",
  "response": "I am planning to use 'final_expenses' and 'generated_revenue' to calculate Net Profit. Should we include renewal_revenue as well?"
}}
```

_Conversation History_
User: Do we have any data from the LinkedIn campaign?
Agent: Yes, we have some rows where the Channel is 'LinkedIn'
User: What is the click through rate for those ads?
In this example, we are calculating Click-Through Rate (CTR).
Additional thought: Clicks and impressions are probably activity types, but it is not clear, so we'll set a placeholder for now. As for the LinkedIn filter, we can use the Channel column.

_Current Formula_
{{
  "name": "LinkedIn CTR",
  "relation": "and",
  "variables": [
    {{
      "name": "Click-Through Rate",
      "relation": "divide",
      "variables": [
        {{ "name": "clicks", "relation": "placeholder", "variables": [] }},
        {{ "name": "impressions", "relation": "placeholder", "variables": [] }}
      ]
    }}, {{
      "name": "from_LinkedIn", "agg": "equals", "tab": "Trifecta_Activity", "col": "Channel", "row": "LinkedIn"
    }}
  ]
}}

_Output_
```json
{{
  "thought": "The main ambiguity is whether clicks and impressions are activity types or found in some other column.",
  "response": "In order to calculate CTR, I will divide clicks by impressions. Should I use the ActivityType column or something else to find these variables?"
}}

_Conversation History_
User: So we want to look at AOV times 120% as the projected future growth. AOV is the total order value divided by its frequency.
Agent: Got it, and how do we break down the total order value?
User: We look at class revenue for our target cohort, basically the last month.
Agent: This cohort is the month of June, correct? Also, how do we break down the class revenue?
User: Yes, that's right. The class revenue is the number of classes purchased multiplied by the cost per class, which we can set as $300.
In this example, we are calculating Customer Lifetime Value (LTV).
Additional thought: The second version calculates class revenue as the sum of tuition fees, while the first version multiplies the number of classes purchased by the cost per class. Both sound correct on the surface, but the first version matches the user's description and the data preview.

_Current Formula_
{{
  "name": "Customer Lifetime Value",
  "relation": "multiply",
  "variables": [
    {{
      "name": "AOV",
      "relation": "divide",
      "variables": [
        {{
          "name": "total_order_value",
          "relation": "and",
          "variables": [
            {{
              "name": "class_revenue",
              "relation": "multiply",
              "variables": [
                {{ "name": "classes_purchased", "agg": "equals", "tab": "user_activity", "col": "activity_type", "row": "purchase" }},
                {{ "name": "cost_per_class", "agg": "constant", "tab": "N/A", "col": "N/A", "row": "300" }}
              ]
            }},
            {{ "name": "recent_purchases", "agg": "greater_than", "tab": "orders", "col": "created_at", "row": "06-01-2024" }}
          ]
        }},
        {{ "name": "order_frequency", "relation": "placeholder", "variables": [] }}
      ]
    }}, {{
      "name": "future_growth", "agg": "constant", "tab": "N/A", "col": "N/A", "row": "1.2"
    }}
  ]
}}

_Output_
```json
{{
  "thought": "The user already described how to calculate class revenue, but has not mentioned how to calculate order frequency.",
  "response": "Ok, you got it. I will calculate class revenue as num classes purchased x $300. My next question is how do we calculate order frequency? Which columns should I use?"
}}
```

_Conversation History_
User: yes, go for it.
Agent: Great, I have joined the data from all three platforms together within the ppc_transactions table.
User: So what is the total return on our ad spend for those three channels?
In this example, we are trying to calculate Return on Ad Spend (ROAS).
Additional thought: Total return should take both subscriptions and one-time purchases into account. The PPC table suggests we are advertising on Google, Facebook and Instagram, so we should sum up across all platform to get total spend.

_Current Formula_
{{
  "name": "Return on Ad Spend",
  "relation": "divide",
  "variables": [
    {{
      "name": "total return",
      "relation": "add",
      "variables": [
        {{"name": "subscriptions", "agg": "sum", "tab": "checkout_amplitude", "col": "RecurringPayment"}},
        {{"name": "one_time_purchases", "agg": "sum", "tab": "checkout_amplitude", "col": "OneTimePayment"}}
      ]
    }}, {{
      "name": "total spend",
      "relation": "add",
      "variables": [
        {{"name": "google", "agg": "sum", "tab": "ppc_transactions", "col": "GoogleAdSpend"}},
        {{"name": "facebook", "agg": "sum", "tab": "ppc_transactions", "col": "FacebookAdSpend"}},
        {{"name": "instagram", "agg": "sum", "tab": "ppc_transactions", "col": "InstagramSpend"}}
      ]
    }}
  ]
}}

_Output_
```json
{{
  "thought": "We have already talked about using three platforms to calculate spend, so we only need to confirm the calculation of total return.",
  "response": "I will calculate total return as the sum of subscriptions and one-time purchases. Does that sound right?"
}}
```
---
Now, let's move onto the real case! Think about what type of ambiguity still exists in calculating or segmenting {full_name}.
Please generate a clear and concise clarification request no longer than three (3) sentences.

_Conversation History_
{history}

_Current Formula_
{formula}

_Output_
"""

segment_clarification_prompt = """Given the conversation so far, we have an incomplete understanding of how to calculate the {full_name} metric.
Your task is to generate a question (or set of questions) that most directly addresses the ambiguity in building the formula or segmenting the metric for analysis.
Stay focused on clarifying what the user wants to accomplish, rather than suggesting additional analysis or segmentation.
Certainly, do not repeat any questions if the user has already provided a clear answer in the conversation history.

For context, metrics are defined as formulas that combine variables, which can then be broken down into further variables as needed.
At the higher levels, variables are connected by relationships such as addition, subtraction, multiplication or division.
The list of valid relations include: add (+), subtract (-), multiply (*), divide (/), not (!), exponent (^), and (&), or (|), less_than (<), greater_than (>), equals (=), conditional (?).
There is one last relationship called 'placeholder', which is used when we are unsure about how to properly structure the expression at that level.
This is particularly relevant to our situation, since it hints at the main ambiguity we are facing (and therefore sort of question to ask).

At the lowest level, variables are constructed as aggregations of columns in a table.
Valid aggregations include: sum, count, average, top, bottom, min, max, greater_than, less_than, equals, empty, filled, constant, all.
For the aggregations of [top, bottom, greater_than, less_than, equals, constant], the 'row' field is used to specify the value of N.

Our current belief is that {short_name} is calculated as follows: {thoughts}.
Additionally, we are planning to break down the metric by {dimension} dimension.
However, this may be incorrect, so we need to get the user's feedback to confirm our understanding.
Concretely, we want the user to {ambiguity}.

As the agent, you have full access to the metric formula, but the user is only aware of what has been discussed in the conversation.
Thus, you must provide any missing information in your response in order to make the question comprehensible within the dialogue context.
Along those lines, the user does not know about any code, so avoid asking about what functions to use. You will make coding decisions separately.
Furthermore, do not distance yourself from the process by saying 'I noticed our current calculation does X' or 'I see that the formula does Y'.
Instead, take ownership of the formulation by phrasing it along the lines of 'My calculation does X' or 'The formula currently contains Y'.

In all cases, your response should be as concise and direct as possible:
  * Focus on the formulation, not the join logic or other technical details:
    - Good: "I'm planning to subtract 'clicks' from 'pageviews'. Does that work?"
    - Bad: "To calculate CTR by brand, I'll need to join the Orders and Products tables on product_id, then divide the sum of clicks from the sum of pageviews. Is this the correct approach for calculating click-thru rate in your context?"
  * We don't even need a full question sometimes. Just by responding with our new understanding gives the user a chance to chime in:
    - Good: "Sum the expenses rather than the 'ad dollars total', got it."
    - Bad: "I will update the formula for calculating Return on Ad Spend to use the sum of expenses rather than the 'ad dollars total' column. Does that sound right, or should we do something else?"

Your entire response should be in well-formatted JSON with keys for thought (string) and response (string). No further text or explanations should appear after the JSON output.

For example,
---
_Conversation History_
User: Let's look at just the month of April.
Agent: The revenue in April was approximately $272,100
User: So what is our net profit at that time?
In this example, we are trying to calculate Net Profit (Profit).
Additional thought: The discrepancy comes from choosing whether to include renewal_revenue. We will go with generated_revenue alone because it shares the same table as final_expenses, but we should clarify with the user.

_Current Formula_
{{
  "name": "Net Profit",
  "relation": "and"
  "variables": [
    {{
      "name": "Profit",
      "relation": "subtract",
      "variables": [
        {{"name": "revenue", "agg": "sum", "tab": "Q4Bookings", "col": "generated_revenue"}},
        {{"name": "expenses", "agg": "sum", "tab": "Q4Bookings", "col": "final_expenses"}},
      ]
    }}, {{
      "name": "In_April", "agg": "equals", "tab": "Q4Bookings", "col": "start_date", "row": "April"
    }}
  ]
}}

_Output_
```json
{{
  "thought": "The main ambiguity is whether to include renewal_revenue in the calculation of Net Profit.",
  "response": "I am planning to use 'final_expenses' and 'generated_revenue' to calculate Net Profit. Should we include renewal_revenue as well?"
}}
```

_Conversation History_
User: There's been a big spike in processing time a few days ago, what happened?
Agent: There are a number of potential causes, such as server issues or high demand. Is there anything that you suspect might have caused the spike?
User: I would start by grabbing the average processing time per team size. We can then check if there's any correlation with error trace as well.
In this example, we are calculating Average Processing Time (APT).
Additional thought: There is ambiguity around which columns are used to calculate processing time, but the more pressing issue is how to connect errors to processing time since errors are strings rather than numbers.

_Current Formula_
{{
  "name": "Hourly Processing Time", "verified": false,
  "relation": "and",
  "variables": [
    {{
      "name": "avg_processing_time", "verified": false,
      "relation": "and",
      "variables": [
        {{"name": "processing_time", "agg": "average", "tab": "RenderActivity", "col": "ProcessingTime", "ver": false}},
        {{"name": "hourly_split", "agg": "all", "tab": "RenderActivity", "col": "StartTimestamp", "row": "group by hour", "ver": false}}
      ]
    }}, {{
      "name": "recent_renders", "agg": "greater_than", "tab": "RenderActivity", "col": "StartTimestamp", "row": "3 days ago", "ver": false
    }}
  ]
}}

_Output_
```json
{{
  "thought": "The main ambiguity is around the segmentation of errors rather than the processing time. We should address this first and then come back to the formula.",
  "response": "Just to be clear, how should we connect error trace to processing time? Is there a specific error message we should look for?"
}}
```

_Conversation History_
User: Do we have any data from the LinkedIn campaign?
Agent: Yes, we have some rows where the Channel is 'LinkedIn'
User: What is the click through rate for those ads?
In this example, we are calculating Click-Through Rate (CTR).
Additional thought: Clicks and impressions are probably activity types, but it is not clear, so we'll set a placeholder for now. As for the LinkedIn filter, we can use the Channel column.

_Current Formula_
{{
  "name": "LinkedIn CTR",
  "relation": "and",
  "variables": [
    {{
      "name": "Click-Through Rate",
      "relation": "divide",
      "variables": [
        {{ "name": "clicks", "relation": "placeholder", "variables": [] }},
        {{ "name": "impressions", "relation": "placeholder", "variables": [] }}
      ]
    }}, {{
      "name": "from_LinkedIn", "agg": "equals", "tab": "Trifecta_Activity", "col": "Channel", "row": "LinkedIn"
    }}
  ]
}}

_Output_
```json
{{
  "thought": "The main ambiguity is whether clicks and impressions are activity types or found in some other column.",
  "response": "Should I use ActivityType or something else to find clicks and impressions?"
}}

_Conversation History_
User: So we want to look at AOV times 120% as the projected future growth. AOV is the total order value divided by its frequency.
Agent: Got it, and how do we break down the total order value?
User: We look at class revenue for our target cohort, basically the last month.
Agent: This cohort is the month of June, correct? Also, how do we break down the class revenue?
User: Yes, that's right. The class revenue is the number of classes purchased multiplied by the cost per class, which we can set as $300.
In this example, we are calculating Customer Lifetime Value (LTV).
Additional thought: The second version calculates class revenue as the sum of tuition fees, while the first version multiplies the number of classes purchased by the cost per class. Both sound correct on the surface, but the first version matches the user's description and the data preview.

_Current Formula_
{{
  "name": "Customer Lifetime Value",
  "relation": "multiply",
  "variables": [
    {{
      "name": "AOV",
      "relation": "divide",
      "variables": [
        {{
          "name": "total_order_value",
          "relation": "and",
          "variables": [
            {{
              "name": "class_revenue",
              "relation": "multiply",
              "variables": [
                {{ "name": "classes_purchased", "agg": "equals", "tab": "user_activity", "col": "activity_type", "row": "purchase" }},
                {{ "name": "cost_per_class", "agg": "constant", "tab": "N/A", "col": "N/A", "row": "300" }}
              ]
            }},
            {{ "name": "recent_purchases", "agg": "greater_than", "tab": "orders", "col": "created_at", "row": "06-01-2024" }}
          ]
        }},
        {{ "name": "order_frequency", "relation": "placeholder", "variables": [] }}
      ]
    }}, {{
      "name": "future_growth", "agg": "constant", "tab": "N/A", "col": "N/A", "row": "1.2"
    }}
  ]
}}

_Output_
```json
{{
  "thought": "The user already described how to calculate class revenue, but has not mentioned how to calculate order frequency.",
  "response": "Ok, num classes purchased x $300. And which columns are most relevant to order frequency?"
}}
```

_Conversation History_
User: yes, go for it.
Agent: Great, I have joined the data from all three platforms together within the ppc_transactions table.
User: So what is the total return on our ad spend for those three channels?
In this example, we are trying to calculate Return on Ad Spend (ROAS).
Additional thought: Total return should take both subscriptions and one-time purchases into account. The PPC table suggests we are advertising on Google, Facebook and Instagram, so we should sum up across all platform to get total spend.

_Current Formula_
{{
  "name": "Return on Ad Spend",
  "relation": "divide",
  "variables": [
    {{
      "name": "total return",
      "relation": "add",
      "variables": [
        {{"name": "subscriptions", "agg": "sum", "tab": "checkout_amplitude", "col": "RecurringPayment"}},
        {{"name": "one_time_purchases", "agg": "sum", "tab": "checkout_amplitude", "col": "OneTimePayment"}}
      ]
    }}, {{
      "name": "total spend",
      "relation": "add",
      "variables": [
        {{"name": "google", "agg": "sum", "tab": "ppc_transactions", "col": "GoogleAdSpend"}},
        {{"name": "facebook", "agg": "sum", "tab": "ppc_transactions", "col": "FacebookAdSpend"}},
        {{"name": "instagram", "agg": "sum", "tab": "ppc_transactions", "col": "InstagramSpend"}}
      ]
    }}
  ]
}}

_Output_
```json
{{
  "thought": "We have already talked about using three platforms to calculate spend, so we only need to confirm the calculation of total return.",
  "response": "I will calculate total return as the sum of subscriptions and one-time purchases. Does that sound right?"
}}
```
---
Now, let's move onto the real case! Think about what uncertainty still exists in calculating or segmenting {full_name}.
Never ask any questions where the user has already provided an answer in the conversation history. Please generate a clear and concise clarification request no longer than three (3) sentences.

_Conversation History_
{history}

_Current Formula_
{formula}

_Output_
"""

identify_footer_prompt = """You are analyzing the last few rows of a table to identify footer rows.
Here are the last {num_rows} rows of the table:

{rows_text}

Guidelines for identifying footer rows:
1. Footer rows often contain words like "total", "grand total", "subtotal", etc.
   - they are often used to hold summary statistics such as sums or averages of the data
   - when this occurs, the numbers in the last row will be much larger than the other rows
2. Footer rows may be separated from data by empty rows
3. Footer rows might have different formatting or fewer filled cells than data rows
4. Footer rows may contain notes, disclaimers, or source attributions

Your task is to first decide whether any of these rows are footer rows.
If so, count how many of these rows are footer rows (starting from the bottom).
Respond ONLY with a single integer representing the number of footer rows, with no additional explanations.
If none of these rows appear to be footer rows, respond with 0.
"""

conversation_metadata_prompt = """You are generating a name and description for the following data tables that will be used in conversations with a data analyst for cleaning and analysis:
Specifically, you should:
  * Analyze table structure and column names to infer the data's purpose
  * Generate a concise, descriptive name (4 words or less)
  * Generate a helpful and concisedescription (2 short sentences or less) explaining what insights can be gained from this data
  * Handle common business data types (sales, marketing, inventory, etc.)

The name should be in Title Case and the description should be concise. 
Do NOT use underscores (_) in the name. Provide one unified name and description that best summarizes all tables collectively.
Your response must be well-formatted JSON with keys for 'thought' (string), name (string), and description (string). No additional text or explanations after the JSON.

For example,
---
## Example 1
Tables: Orders, Customers, Products
Columns: order_id, product_id, customer_id, date, size, channel, price in Orders;
customer_id, first, last, city, state, member in Customers;
product_id, sku, type, brand, style, cost in Products

_Output_
```json
{{
  "thought": "The tables are likely for a ecommerce brand with order, customer, and product information.",
  "name": "Shoe Store Sales",
  "description": "The data contains historical sales records for a shoe store, including order details (size, sales channel), customer demographics (location, membership status), and product attributes (SKU, type, brand, style)."
}}
```

## Example 2
Tables: Transactions, Products, Customers
Columns: transaction_id, product_id, customer_id, date, quantity, price in Transactions;
product_id, name, category, price in Products;
customer_id, first, last, city, state, member in Customers

_Output_
```json
{{
  "thought": "The tables are likely for a retail store with transaction, product, and customer information.",
  "name": "Retail Store Transactions",
  "description": "The data contains historical transaction records for a retail store, including transaction details (date, quantity, price), product attributes (name, category, price), and customer demographics (location, membership status)."
}}
```
---
Now it's your turn! Here are the tables and columns for reference:
## Current Scenario
Tables: {tables}
Columns: {columns}

_Output_
"""