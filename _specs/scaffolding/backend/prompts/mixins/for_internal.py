peek_prompt = """Your task is to record the most pertinent characteristics found in the data preview to support {task}.
Specifically, the user is trying to peek at some data as part of a longer plan. The remaining steps in the plan are:
{task_desc}

Our main goal is to highlight anything unusual or unexpected in the data:
  1. Is there any mismatch between the column name and its values in terms of data type or format?
  2. Are there any outliers, anomalies, or other obvious data quality issues?
  3. Which columns could serve as a primary key for joining with other tables?
  4. Are there any steps in the plan that can be easily satisfied by the columns available?

Therefore, key characteristics to summarize include:
  * data type or formats, especially those that are unexpected given the column name
    - number: whole, decimal, currency, percentage
    - text: name, email, phone, url, company, username
    - datetime: year, month, date, hour, day of week, timestamp
    - location: street, city, state, country, zip code
    - categorical: boolean, category, ordinal
  * abnormalities in the distribution of values
    - outliers: especially if there is a clear pattern or trend
    - duplicates: are there any repeated values or near-duplicates?
    - missing values: especially if they are highly concentrated in a specific range
  * uniqueness of the values
    - is this column potentially useful as a unique identifier, serving as a good candidate for joins?
    - if there are only few unique values, it may be easier to just list them out
  * relevant information that may be useful for calculating metrics and KPIs
    - are there any metrics mentioned in the plan that are easily calculated from the columns? (CTR, CVR, DAU, ROAS, etc.)
    - if we can get a metric by simply dividing one column by another, then this helps to avoid complex calculations

Please start by thinking carefully about the data preview and then output a concise summary of the key characteristics.
A summary should consist of three to five points at most, so focus on reporting unexpected or surprising aspects rather than trying to cover everything.
For example, reporting distribution of values is not necessary if the min and max fall within a normal range. Also, reporting the number of rows and columns is not necessary because that is already known to the user.
Your entire response should be in well-formatted JSON including your thought (string) and summary (list of strings), with no further text or explanations after the JSON output.

For example,
---
_Data Preview_
| campaign_name        | start_date | end_date   | spend     | impressions | clicks | conversions |
|----------------------|------------|------------|-----------|-------------|--------|-------------|
| Spring Promo 2024    | 2024-03-01 | 2024-03-15 | $1,500.75 | 120,500     | 2,300  | <N/A>       |
| New User Welcome     | 2024-01-01 | <N/A>      | $950.20   | 5,000       | 800    | <N/A>       |
| Summer Sale Blitz    | 2024-02-15 | 2024-03-05 | $2,250.00 | 850,000     | 15,000 | <N/A>       |
| Q1 Brand Awareness   | 2024-01-01 | 2024-03-31 | $1600.30  | 15,000      | 300    | <N/A>       |
| Influencer Collab    | 2024-03-05 | 2024-03-12 | $800.00   | 60,000      | 1,200  | <N/A>       |
| Retargeting Campaign | 2024-03-10 | <N/A>      | $1,100    | 30,000      | 950    | <N/A>       |
| Brand Awareness Push | 2024-02-01 | 2024-02-29 | $1,030    | 200,000     | 0      | 0           |
| Holiday Flash Sale   | 2023-12-20 | 2023-12-26 | $210.00   | 18,000      | 2,500  | <N/A>       |

_Output_
```json
{{
  "thought": "This data is about ad campaigns performance, so I should focus looking for campaigns with unexpected metrics compared to the average.",
  "summary": [
    "Column data types are: campaign_name (text), start_date (date), end_date (date), spend (currency), impressions (number), clicks (number), conversions (number)",
    "The date format is YYYY-MM-DD, with some campaigns missing an end date",
    "No campaigns have any conversions recorded, which implies that conversion tracking is either broken or not being implemented",
    "Brand Awareness Push campaign has lots of impressions, but no clicks or conversions, which is unusual",
    "CTR and CVR can be easily calculated with the columns available"
  ]
}}
```

_Data Preview_
| ticket_id | priority | resolved_at         | resolution_time_hours |
|-----------|----------|---------------------|-----------------------|
| TKT-921A  | Medium   | 2024-03-14 11:30:00 | 1.41                  |
| TKT-J22B  | High     | 2024-03-15 09:15:00 | 1.87                  |
| TKT-G03C  | Urgent   | <N/A>               | <N/A>                 |
| TKT-8K4D  | High     | 2024-03-19 17:45:30 | 12.50                 |
| TKT-LL5E  | Low      | 2024-03-16 09:45:20 | 0.25                  |
| TKT-2F6F  | Medium   | <N/A>               | 1.50                  |
| TKT-2F7G  | Medium   | 2024-03-18 15:00:00 | 0.42                  |
| TKT-098H  | Low      | 2024-03-18 12:10:05 | 0.17                  |

_Output_
```json
{{
  "thought": "This data is about resolving customer services tickets. I should look for tickets with unexpected resolution times.",
  "summary": [
    "Column data types are: ticket_id (ID), priority (category), resolved_at (timestamp), resolution_time_hours (decimal)",
    "The date format is YYYY-MM-DD HH:MM:SS, with some tickets missing a resolved time",
    "The ticket_id format is TKT-XXXX, where XXXX is a four-digit alpha-numeric code. A very good candidate for a foreign key",
    "Ticket priorities are: Low, Medium, High, Urgent. Surprisingly, the only Urgent ticket is unresolved",
    "Typical resolution time is around 1-2 hours, but TKT-8K4D took 12.5 hours"
  ]
}}
```

_Data Preview_
| OrderDeliveryName | OrderTime | DeliveryTime | Status         | City        | State |
|-------------------|-----------|--------------|----------------|-------------|-------|
| David Kim         | 10:20     | 11:00        | Delivered      | Tampa       | FL    |
| Maria Garcia      | 12:00     | 14:05        | Delivered      | Chicago     | IL    |
| Alex Thompson     | 14:15     | <N/A>        | Pending        | Miami       | FL    |
| Emily Wilson      | 16:00     | <N/A>        | Delivered      |Jacksonville | FL    |
| Wei Chen          | 18:30     | 19:00        | Delivered      | Chicago     | IL    |
| Rachel O'Brien    | 20:00     | 21:30        | Pending        | Chicago     | IL    |
| Amanda Foster     | 22:00     | 23:00        | Delivered      | Orlando     | FL    |
| Lisa Parker       | 14:15     | <N/A>        | Pending        | Miami       | FL    |

_Output_
```json
{{
  "thought": "This data is about order deliveries, so I should look for orders with unexpected statuses or delivery times.",
  "summary": [
    "Column data types are: OrderDeliveryName (first and last name), OrderTime (time), DeliveryTime (time), Status (category), City (city name), State (state abbreviation)",
    "OrderTime and DeliveryTime are in HH:MM format, with some orders missing a delivery time",
    "Delivery locations are all in Florida and Illinois, with two orders in Miami and two in Chicago"
  ]
}}
```

_Data Preview_
| department      | warehouse_location | stock_level | avg_rating | num_reviews |
|-----------------|--------------------|-------------|------------|-------------|
| Electronics     | Aisle 3, Shelf C   | 700         | 4.7        | 180         |
| Groceries       | Bay 1, Shelf A     | 200         | 4.9        | 512         |
| Apparel         | Zone 5, Bin 12     | 0           | 2.8        | 0           |
| Sports/Outdoors | Aisle 8, Shelf A   | 100         | 3.8        | 150         |
| Home & Kitchen  | Bay 2, Shelf D     | 600         | 4.4        | 75          |
| Electronics     | Aisle 3, Shelf D   | 100         | 4.0        | 180         |
| Home Goods      | Zone 1, Bin 5      | 300         | 4.1        | 45          |
| Electronics     | Aisle 2, Shelf B   | 100         | 4.7        | 280         |

_Output_
```json
{{
  "thought": "This data is about inventory levels, so I should look for departments with unexpected stock levels or ratings.",
  "summary": [
    "Column data types are: category (text), warehouse_location (text), stock_level (integer), avg_rating (decimal), num_reviews (integer)",
    "Stock levels range from 0 to 700, and seem to be rounded to the nearest 100",
    "Although there are many departments, they are not all unique, with Electronics appearing three times. Thus, this is not a good candidate for joining.",
    "Apparel department seems to have a problem since it has no stock and no reviews, which likely also leads to a low rating of 2.8"
  ]
}}
```

_Data Preview_
| MemberContact   | MembershipStatus | JoinDate | member_email                   | registration_date  | username       |
|-----------------|------------------|----------|--------------------------------|--------------------|----------------|
| (111) 123-4567  | Premium          | May      | wanderlust.jess@gmail.com      | June 5, 2023       | jesswanderlust |
| (451) 889-2020  | Basic            | June     | pixel.pioneer@outlook.com      | May 12, 2022       | pixelpioneer   |
| <N/A>           | Student          | October  | codewarrior.tom@protonmail.com | November 21, 2021  | codewarrior3   |
| (650) 713-9012  | Premium          | October  | art.by.alex@studiohub.com      | August 3, 2022     | <N/A>          |
| (650) 256-5867  | Basic            | July     | <N/A>                          | July 1, 2000       | <N/A>          |
| <N/A>           | Student          | August   | melody.muse@harmonyverse.net   | May 8, 2023        | <N/A>          |
| (820) 450-8901  | Premium          | December | dr.tech.marcus@innovatix.com   | December 19, 2021  | doctoroftech   |
| (555) 444-4444  | Premium          | December | luna.skye@explorethestars.org  | October 27, 2022   | <N/A>          |

_Output_
```json
{{
  "thought": "This data is about members, so I should look for patterns in registration or unusual membership statuses.",
  "summary": [
    "The column data types are: MemberContact (phone number), MembershipStatus (category), JoinDate (month), member_email (email), registration_date (date), username (text)",
    "While the JoinDate column is written as a full month, the registration_date column is written in as month, day and year",
    "MembershipStatus has three unique values: Premium, Basic, and Student",
    "Many of the users are missing either a MemberContact phone number or a username. Some phone numbers are very likely to be fake."
  ]
}}
```
---
Now it's your turn! Please think about the key points of focus and generate a summary of points highlighting the most insightful aspects of the data.
For extra context, the conversation history for our real case is also provided.

_Conversation History_
{history}

_Data Preview_
{data_preview}

_Output_
"""

think_prompt = """Given the conversation history and supporting details, think carefully about the best way to calculate the '{metric}' metric.
The supporting details will include the relevant columns and their positions in the table.
For our real case, the available data includes:
{valid_tab_col}

_Conversation History_
{history}

_Supporting Details_
{supporting_details}

_Output_
"""

compute_type_prompt = """Given the conversation history and proposed question, decide on the format of the inputs and outputs for calculation.
In particular, we want to know if any data from the available tables would serve as useful inputs, and if so, what columns that would be.

Separately, we want to know whether the output of the calculation is a numeric (number) or textual (string). For our purposes:
  * the only options are 'number' or 'string', so boolean answers are not allowed
  * a datetime value is considered a number since it can be represented as a Unix timestamp
  * an address is considered a string since it is a combination of numbers and text
  * a list of numbers is considered a number
  * a list of strings is considered a string

Please start by thinking carefully about the user's request, and consider what information is needed to answer it.
Your entire response should be well-formatted JSON including a key for thought (string), columns (list), and output_type (token), with no further text or explanations after the JSON output.
The columns should be a list of dicts with keys for tab (string) and col (string), and the output_type should be one of either 'number' or 'string'.

For example,
---
_Conversation History_
User: How many clicks is that in over the entire year?
Agent: The total is 4,725 clicks.
User: How many is that on a monthly basis?

_Available Data_
* Tables: Ad Group Download
* Columns: date, impressions, page_views, clicks, sign_ups, bounce_rate, time_on_site, page_depth

_Proposed Question_
What is 4725 divided by 12?

_Output_
```json
{{
  "thought": "The user wants to convert a yearly value into a monthly value, which is a simple arithmetic operation.",
  "columns": [ ],
  "output_type": "number"
}}
```

_Conversation History_
User: What is the formula for entropy?
Agent: Entropy is defined as the negative sum of the probability of each state times the log of the probability of that state.
User: OK, the probability distribution of our revenue is found in the probability column. What would that be?

_Proposed Question_
What is the entropy of revenue distribution based on the values found in the probability column?

_Available Data_
* Tables: customer_purchase_distribution
* Columns: product_id, product_name, prob_distribution, revenue

_Output_
```json
{{
  "thought": "Calculating the entropy requires access to a column, and the output is a single number.",
  "columns": [
    {{"tab": "customer_purchase_distribution", "col": "prob_distribution"}}
  ],
  "output_type": "number"
}}
```

_Conversation History_
User: Suppose there are two friends, Alex and Brooke who are both saving money for college. Alex deposits $2,000 in a savings account with 3.25% annual interest, compounded monthly. You got that so far?
Agent: Sure, Alex has $2,000 in his account.
User: Next, Brooke deposits $1,750 in a different account with 3.75% annual interest, also compounded monthly. Now, which friend will have more money after 6 years?

_Proposed Question_
Who will have more money after 6 years?

_Available Data_
* Tables: College Savings Plan
* Columns: StudentName, InitialDeposit, APR, MonthlyContribution, DesiredCollege, YearsUntilGraduation

_Output_
```json
{{
  "thought": "The numbers are all available in the conversation history, so no columns are needed. The output is a string since we ultimately want a name of a person, either Alex or Brooke.",
  "columns": [ ],
  "output_type": "string"
}}
```

_Conversation History_
User: Which is smaller, 7.11 or 7.6?

_Proposed Question_
Which is smaller, 7.11 or 7.6?

_Available Data_
* Tables: customers
* Columns: customer_id, first_name, last_name, email, address, city, state

_Output_
```json
{{
  "thought": "The numbers are all available in the conversation history, so no columns are needed. The output is a number since we want to return the smaller value.",
  "columns": [ ],
  "output_type": "number"
}}
```

_Conversation History_
User: Let's merge those two tables together to form a giant one for Google.
Agent: OK, I have merged the tables together to form a new table called 'GoogleAdGroup' with 613 rows.
User: Can we sort them by click-thru rate? Then find the one with the best one?

_Proposed Question_
Which ad group has the highest CTR?

_Available Data_
* Tables: GoogleAdGroup, FacebookAdSets
* Columns: campaign_name, ad_group_name, date, impressions, page_views, clicks, conversions in GoogleAdGroup;
campaign_name, ad_set_name, created_date, views, clicks (all), sign_ups, cost in FacebookAdSets

_Output_
```json
{{
  "thought": "I should look in the Google table (and not Facebook) since we are interested in ad groups. The output is a string since we want the name of the ad group.",
  "columns": [
    {{"tab": "GoogleAdGroup", "col": "ad_group_name"}},
    {{"tab": "GoogleAdGroup", "col": "clicks"}},
    {{"tab": "GoogleAdGroup", "col": "impressions"}}
  ]
  "output_type": "string"
}}
```
---
Now it's your turn! Please determine the appropriate inputs and outputs for calculation.

_Conversation History_
{history}

_Proposed Question_
{question}

_Available Data_
{valid_tab_col}

_Output_
"""

computation_prompt = """Based on the conversation history, we have determined that performing some computation would be useful.
Your task is to write code that can be executed directly, and ultimately returns a {output_type} stored in the `result` variable.

{df_message}
With that said, the available dataframes are {df_names}.
You also have access to the math library (as `math`), regex (as `re`), Pandas (as `pd`), NumPy (as `np`), and SciPy (as `scipy`), so feel free to use any functions from those libraries.
However, you do not have access to any other libraries, and you should *not* try to import them. Tasks involving SciKit-Learn, PyTorch, or other machine learning libraries are out-of-scope.
If the task is beyond your abilities or out-of-scope, then simply set the result to 'error'.

Focus on writing directly executable Python, which may contain comments to help with reasoning. We are currently using Python 3.8, so act accordingly.
If a request requires multiple steps, write each step on a new line. When possible to do so easily, perform the operation in place rather than assigning to a dataframe.
When calculating a percentage, DO NOT multiply by 100. When performing any division operation, always return the result with at least 4 decimal places of precision.
Your final response should only contain well-formatted Python code, without any additional text or explanations after the output.

For example,
---
_Conversation History_
User: How many clicks is that in over the entire year?
Agent: The total is 4,725 clicks.
User: How many is that on a monthly basis?

_Question_
What is 4725 divided by 12?

_Related Data_
None

_Output_
```python
# Python v3.8 uses true division by default
result = 4725 / 12
```

_Conversation History_
User: What is the formula for entropy?
Agent: Entropy is defined as the negative sum of the probability of each state times the log of the probability of that state.
User: OK, the probability distribution of our revenue is found in the probability column. What would that be?

_Question_
What is the entropy of revenue distribution based on the values found in the probability column?

_Related Data_
Table: customer_purchase_distribution
| prob_distribution |
|-------------------|
| 0.1               |
| 0.25              |
| 0.45              |
| 0.05              |
| 0.15              |

_Output_
```python
# Entropy is calculated using the formula: H = -sum(p * log(p))
probs = db.customer_purchase_distribution['prob_distribution']
result = -sum(probs * np.log(probs))
```

_Conversation History_
User: Suppose there are two friends, Alex and Brooke who are both saving money for college. Alex deposits $2,000 in a savings account with 3.25% annual interest, compounded monthly. You got that so far?
Agent: Sure, Alex has $2,000 in his account.
User: Next, Brooke deposits $1,750 in a different account with 3.75% annual interest, also compounded monthly. Now, which friend will have more money after 6 years?

_Question_
Who will have more money after 6 years?

_Related Data_
None

_Output_
```python
# Initial deposits
alex_principal = 2000
brooke_principal = 1750
# Monthly interest rates
alex_rate = 0.0325 / 12
brooke_rate = 0.0375 / 12
# Calculate balances after 6 years (72 months)
alex_balance = alex_principal * (1 + alex_rate) ** 72
brooke_balance = brooke_principal * (1 + brooke_rate) ** 72
# Compare final balances to determine the winner
result = 'Alex' if alex_balance > brooke_balance else 'Brooke'
```

_Conversation History_
User: Which is smaller, 7.11 or 7.6?

_Question_
What is the minimum value between 7.11 and 7.6?

_Related Data_
None

_Output_
```python
result = min(7.11, 7.6)
```

_Conversation History_
User: Let's merge those two tables together to form a giant one for Google.
Agent: OK, I have merged the tables together to form a new table called 'GoogleAdGroup' with 613 rows.
User: Can we sort them by click-thru rate? Then find the one with the best one?

_Question_
Which ad group has the highest CTR?

_Related Data_
Table: GoogleAdGroup
| ad_group_name        | clicks | impressions |
|----------------------|--------|-------------|
| Summer Chic          | 103    | 502         |
| Makeup Masterclass   | 154    | 753         |
| Go Get It Today      | 202    | 1032        |
| Take me to the Beach | 251    | 1255        |
| Sunshine Vibes       | 308    | 1501        |

_Output_
```python
google_data = db.GoogleAdGroup
google_data['CTR'] = round( google_data['clicks'] / google_data['impressions'], 4 )
result = google_data.sort_values(by='CTR', ascending=False).iloc[0]['ad_group_name']
```

_Conversation History_
User: Did we get any conversions from that email blast in the past month?
Agent: The email campaign resulted in 62 conversions.
User: What's the correlation between clicks and conversions then?

_Question_
What is the correlation between clicks and conversions?

_Related Data_
Table: email_marketing
| date       | clicks | conversions |
|------------|--------|-------------|
| 2024-01-01 | 103    | 12          |
| 2024-01-02 | 154    | 18          |
| 2024-01-03 | 202    | 25          |
| 2024-01-04 | 251    | 31          |
| 2024-01-05 | 308    | 38          |
[Truncated: showing 5 of 31 rows]

_Output_
```python
clicks = db.email_marketing['clicks'].values
conversions = db.email_marketing['conversions'].values
# Calculate the correlation coefficient using NumPy
result = np.corrcoef(clicks, conversions)[0, 1]
```
---
Now it's your turn! Please write code to perform the necessary computation, then store the result in a variable called `result`.

_Conversation History_
{history}

_Question_
{question}

_Related Data_
{related_data}

_Output_
"""