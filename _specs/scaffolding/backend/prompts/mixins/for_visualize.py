# ------------------------------------------------------------------
# TRIMMED FOR SPEC BREVITY
# Original file: 863 lines with 6 prompt templates.
# Kept 3 representative prompts below (plot_prompt, design_prompt, carry_prompt).
# Removed 3 prompts: validate_prompt, validation_grouping_prompt,
#   pattern_routing_prompt
# ------------------------------------------------------------------

plot_prompt = """Given the conversation history and data preview, your task is to generate accurate Python code for creating a plotly express figure.
The conversation history includes multiple turns for context, but we are only interested in the request made in the user's final utterance.
The preview contains the top few rows of the likely relevant data, and should be used to determine the most appropriate columns to plot, as well as any minor data transformations that need to be applied.

Please start by considering the user's goal and the data preview to determine the type of diagram to create (eg. bar chart, line chart, scatterplot, etc.)
Then, think about the most appropriate columns to include in the figure, since not all columns are needed for every type of plot.
Finally, perform any necessary pre-processing, create a plotly express figure that takes in a dataframe object (df), and store the result in a variable named `fig`.

When generating the code, do NOT create any copies of the dataframe or modify its underlying contents. You are only using the dataframe for visualization purposes.
As such, you can consider sorting or filtering the dataframe, but you should avoid making any permanent changes.
Furthermore, use Plotly Express (px) exclusively to create the visualization. Do not use matplotlib, seaborn, or any other plotting libraries.
On a related note, you should not import any libraries (including plotly), since they have already been handled by the system.

Choose titles that are compact and distinctive, rather than long and descriptive.
  * Suppose the goal is to visualize the 7-day trailing average of the number of subscriptions starting from 2023 to the present:
    - Bad: 'Daily Subscriptions (7 Day Trailing Average) from 2023 Onwards'
    - Good: 'Trailing Average of Subscriptions'
  * Suppose the figure reports the distribution of weekly mobile visitors from United States, Canada, and Mexico:
    - Bad: 'Distribution of Mobile Visitors: US vs. Canada vs. Mexico'
    - Good: 'Mobile Visits by Country'
  * Suppose the figure compares the click-thru rate and conversion rate grouped by channel:
    - Bad: 'Click-Thru Rate and Conversion Rate Grouped by Channel'
    - Good: 'Channel Performance'
  * Suppose the chart showed the amount of signups generated in November by the top 10 sources of traffic to the newsletter signup form:
    - Bad: 'Top 10 Sources of Newsletter Signups in November'
    - Good: 'Newsletter Signup Sources'

Color is appropriate to distinguish categories or to show intensity/magnitude:
  * Avoid unnecessary color complexity. Default colors are the correct choice in most cases
  * When customr colors are needed, prefer vibrant, saturated color schemes over light themes or high-contrast options
  * Good options for sequential or continuous data include: 'viridis', 'plasma', or 'emrld'
  * For categorical data, solid colors (blue, green, red, orange, purple, etc.) are often the best choice
  * Apply color only when it adds meaningful information - it should enhance rather than clutter the figure

If the user's request is ambiguous, default to the most straightforward visualization that shows the key relationships in the data.
Your entire response should only contain well-formatted Python code and comments, without any additional text or explanations after the output.

For example,
---
_Conversation History_
User: Hey, can you pull up our newsletter data?
Agent: I've loaded the newsletter signup data. What specific metrics would you like me to check?
User: Show me the breakdown by source for Q4. I want to see which channels are actually driving our signups.

_Data Preview_
| signup_source | signup_rate |
|---------------|-------------|
| Social Media  | 0.1247      |
| Email Referral| 0.0892      |
| Direct        | 0.1634      |
| Paid Search   | 0.2156      |
| Organic       | 0.3743      |
[Truncated: showing 5 of 9 rows]

_Output_
```python
# Convert signup rate to percentage for better readability
df['signup_percent'] = df['signup_rate'] * 100
# Source breakdown shows proportional data, so a pie chart is appropriate
fig = px.pie(df, values='signup_percent', names='signup_source',
             labels={{
               'signup_percent': 'Signup Rate (%)',
               'signup_source': 'Source'
             }},
             title='Newsletter Signups')
# Format the pie chart labels to show percentages
fig.update_traces(texttemplate='%{{label}}<br>%{{value:.1f}}%', textposition='inside')
```

_Conversation History_
User: The call center team is swamped again. I think there's a pattern in the number of requests but want to confirm before we hire more reps.
Agent: What timeframe are you most concerned about?
User: Let me see the daily volume for the past 3 months.

_Data Preview_
| request_date | daily_volume | day_of_week |
|--------------|--------------|-------------|
| 2025-03-15   | 127          |  6          |
| 2025-03-16   | 89           |  7          |
| 2025-03-17   | 341          |  1          |
| 2025-03-18   | 298          |  2          |
| 2025-03-19   | 267          |  3          |
[Truncated: showing 5 of 78 rows]

_Output_
```python
# Convert day of week from numeric to text for better readability
weekday_map = {{1: 'Monday', 2: 'Tuesday', 3: 'Wednesday', 4: 'Thursday', 5: 'Friday', 6: 'Saturday', 7: 'Sunday'}}
df['day_of_week'] = df['day_of_week'].map(weekday_map)

# Daily volume over time with day-of-week patterns suggests a line chart
fig = px.line(df, x='request_date', y='daily_volume',
  labels={{
    'request_date': 'Date',
    'daily_volume': 'Daily Requests'
  }},
  color='day_of_week', title='Call Center Volume')
```

_Conversation History_
User: Our SDRs keep complaining about lead quality but I'm not convinced.
Agent: What specific concerns are they raising about the leads?
User: They say we're getting tons of MQLs but booking fewer discovery calls. Give me a chart of MQLs against actual bookings so I can see if there's really a correlation issue?

_Data Preview_
| Month    | MQLs | Discovery Calls Booked |
|----------|------|------------------------|
| 2025-01  | 743  | 127                    |
| 2025-02  | 892  | 156                    |
| 2025-03  | 1,156| 189                    |
| 2025-04  | 967  | 143                    |
| 2025-05  | 1,034| 201                    |
[Truncated: showing 5 of 876 rows]

_Output_
```python
# Correlation between two metrics is best shown with a scatter plot
fig = px.scatter(df, x='MQLs', y='Discovery Calls Booked',
  labels={{
    'MQLs': 'Marketing Qualified Leads',
    'Discovery Calls Booked': 'Discovery Calls'
  }},
  title='MQL to Call Correlation')
```
---
Now it's your turn! Following the same format in the examples, please generate the plotly express code to meet the user's goal.
This is very important to my career, do not include any explanations after the code output.

_Conversation History_
{history}

_Data Preview_
{data_preview}

_Output_
"""

design_prompt = """Given the user request and supporting details, follow the thought process to generate Pandas code for updating the data.
Supporting details includes information on the part of the table being changed, a description of the change, and the method for deriving the new values.
Changes include renaming content, modifying values, or filling rows with new content based on other columns.
The dataframes you have are {df_tables}.
Please only output executable Python without any explanations. If a request requires multiple steps, write each step on a new line.
When possible to do so easily, perform the operation in place rather than assigning to a dataframe.

For example,
#############
<This is just a placeholder>

#############
User request: {utterance}
* Description: {description}
* Method: {method}
Thought: {thought}
Result:"""


carry_prompt = """Our goal is to visualize the data in a way that addresses the user's intent.
We currently have access to a dataframe that was generated from a previous query, but it may or may not be appropriate for our current situation.
Your task is to decide if this existing dataframe is already sufficient, or whether we should query the database for an updated dataframe instead.
To aid in your decision, you will be provided with the conversation history, the previous SQL query, and a preview of the data.

The obvious case for carrying over the previous dataframe is when the user is simply asking for a visualization of the previous turn.
The obvious case for querying the database again is when the current turn is unrelated to the previous turn.

For more nuanced cases, keep the following guidelines in mind:
  * If the user is building upon previous analysis by slightly tweaking the parameters, then it does *not* make sense to carry over the previous data
    - this constitutes an adjustment to the previous analysis, so the previous query is outdated
    - examples include changing date ranges, filters, groupings, or adding/removing conditions
  * It is acceptable to carry over a dataframe containing extraneous columns because we can simply ignore them during plotting
  * Similarly, if the user wants a different visualization type or revised chart format, then the previous dataframe can still be used
  * However, if the user asks for additional metrics, fields, or level of granularity, then we should generate a new query

Please start by considering whether the user is visualizing prior results, building upon previous analysis, or starting a new direction.
Then decide whether the previous dataframe is fully sufficient to answer the user's current request, by answering with `true` if it is enough or `false` if we should generate an updated query.
Your entire response should be in well-formatted JSON including keys for thought (string) and carry (boolean), with no further explanations after the JSON output.

For example,
---
## Scenario 1
_Previous SQL Query_
```sql
SELECT ad_source,
  SUM(email_signups) AS prospects,
  SUM(completed_purchases) AS signups
FROM platform_aggregated
WHERE signup_timestamp >= DATE_SUB(CURRENT_DATE, INTERVAL 1 WEEK)
  AND signup_timestamp < CURRENT_DATE
GROUP BY ad_source
ORDER BY signups DESC;
```

_Data Preview_
| ad_source | signups   |
|-----------|-----------|
| Facebook  | 241       |
| Google    | 189       |
| LinkedIn  | 102       |
| Instagram | 78        |
| TikTok    | 54        |

_Conversation History_
User: Right, the signups actually uses completed purchases, the email signups are just prospects.
Agent: We had 241 signups from Facebook, 189 from Google, and 102 from LinkedIn. See table for more details.
User: Can you show this as a bar chart?

_Output_
```json
{{
  "thought": "The user is simply asking for a visualization of the previous turn, so we should just carry over the previously queried data.",
  "carry": true
}}
```

_Conversation History_
User: Right, the signups actually uses completed purchases, the email signups are just prospects.
Agent: We had 241 signups from Facebook, 189 from Google, and 102 from LinkedIn. See table for more details.
User: Can I get the number of emails sent as well?

_Output_
```json
{{
  "thought": "The user is building upon a previous analysis by asking for additional metrics, so we need to query the database again.",
  "carry": false
}}
```

## Scenario 2
_Previous SQL Query_
```sql
SELECT supplier, available_units, date_added
FROM inventory
WHERE supplier = 'warehouse - Colorado'
  AND date_added >= DATE_SUB(CURRENT_DATE, INTERVAL 1 MONTH)
  AND date_added < CURRENT_DATE;
```

_Data Preview_
| supplier             | available_units | date_added   |
|----------------------|-----------------|--------------|
| warehouse - Colorado | 120             | 2025-02-15   |
| warehouse - Colorado | 85              | 2025-02-18   |
| warehouse - Colorado | 150             | 2025-02-20   |
| warehouse - Colorado | 98              | 2025-02-22   |
| warehouse - Colorado | 110             | 2025-02-25   |
[Truncated: showing 5 of 6,134 rows]

_Conversation History_
User: I'd like to see the number of units available for each item in the Colorado warehouse.
Agent: Sure, is there a specific time range you want to look back to?
User: Yea, go back 1 month
Agent: How does this look?
User: Actually, I want to see this in a pie chart, rather than a line graph

_Output_
```json
{{
  "thought": "The final turn is merely asking for a different visualization type, so we can reuse the previous data.",
  "carry": true
}}
```
---
## Current Scenario
Now it's your turn to decide! Based on the available information, decide whether carrying over the previous data is enough to create a visualization for the user's request.

_Previous SQL Query_
```sql
{sql_query}
```

_Data Preview_
{data_preview}

_Conversation History_
{history}

_Output_
"""
