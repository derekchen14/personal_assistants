column_match_prompt = """Is the user searching for available columns matching the one in their request?  If so, what is the column name?
Your answer should be only one word, either 'yes' or 'no', with no other characters or spaces.  If the answer is 'no', the column name is simply 'none'.

For example,
---
Request: Is there a column for revenue?
Answer: yes
Name: revenue

Request: What columns do you have available?
Answer: no
Name: none

Request: Do you have a sales column somewhere?
Answer: yes
Name: sales

Request: Notice how we have a revenue and a sales column?
Answer: no
Name: none

Request: Is there a column related to CTR?
Answer: yes
Name: CTR

Request: What is the largest amount in the sales column?
Answer: no
Name: none

Request: What columns are in the sales table?
Answer: no
Name: none

Request: {utterance}
Answer:"""

set_preference_prompt = """Given the conversation history, please identify which preference is being updated and what value it is being set to, along with its details.
The options to choose from are [goal, timing, caution, special, viz, metric, sig, search]
  - 'goal': how something is ranked, such as how to determine which campaign performed best. Possible values:
    * amount - making the most money. Example details: [net revenue, total fees]
    * count - the highest absolute size or volume. Example details: [conversions, page views, sign-ups]
    * percent - the highest relative size or proportion.  Example details: [CTR, Retention Rate, CVR]
    * time - the earliest or latest of some event. Example details: [first login, last purchase]
  - 'timing': how recent something is, such as the time period to consider. Possible values:
    * days - time range counting by days. Example details: [last 14, past 30]
    * week - the most recent week. Example details: [past, full]
    * month - the most recent month. Example details: [full, month-to-date]
    * quarter - the most recent quarter. Example details: [past]
  - 'caution': how to handle issues or alerts. Possible values:
    * alert - always notify immediately for any issues that arise. No details needed.
    * warning - notify with a warning only when there is a serious error. No details needed.
    * ignore - do not notify. No details needed.
  - 'special': how to handle issues or alerts. Possible values:
    * Sunday - start the week on Sunday. Details is when the week ends, for example: [Saturday]
    * Monday - start the week on Monday. Details is when the week ends, for example: [Friday]

Start by thinking out loud about what preference is most applicable to the request, and then the value and details.
If none of the options are relevant, output the name as 'error', with the value and details as empty strings.
Your entire response should be in well-formatted JSON including name (string), value (string), and detail (string), with no further explanations after the JSON output.
Let's consider some example scenarios, and then tackle the current case.

For example,
---
_Conversation History_
User: Can you show me the top 5 sources of leads from last month?
Agent: Sure, how do you want to determine the top lead sources?
User: The ones that led to the most subcriptions

_Output_
```json
{{
  "name": "goal",
  "value": "count",
  "detail": "subscriptions"
}}
```

_Conversation History_
User: Those look fine to me
Agent: No problem, I will ignore those moving forward
User: Actually, can you just stop with all alerts for now?

_Output_
```json
{{
  "name": "caution",
  "value": "ignore",
  "detail": ""
}}
```

_Conversation History_
User: Let's take a look at how sign-ups have been trending lately
Agent: Can you provide more information about how long ago you want to look?
User: The past month is fine

_Output_
```json
{{
  "name": "timing",
  "value": "month",
  "detail": "past"
}}
```

_Conversation History_
User: What was our most popular channel last quarter?
Agent: When you say 'most popular', how do you want to measure that?
User: Most popular channel is the one with most number of visitors

_Output_
```json
{{
  "name": "goal",
  "value": "count",
  "detail": "visitors"
}}
```

_Conversation History_
User: How many gamer pads did we sell this week?
Agent: When do you want to define as the start of the week?
User: We can go with Sunday

_Output_
```json
{{
  "name": "special",
  "value": "Sunday",
  "detail": "Saturday"
}}
```

_Conversation History_
User: How's the CTR been doing recently after we started the promotion?
Agent: No problem, how far back would you like to look?
User: I'd like to get the last 14 days worth of clicks.

_Output_
```json
{{
  "name": "timing",
  "value": "days",
  "detail": "last 14"
}}
```

_Conversation History_
User: What the channel that had the best results.
Agent: Before I answer, can you tell me how you want to define the best channel?
User: The one that made the most money

_Output_
```json
{{
  "name": "goal",
  "value": "amount",
  "detail": "revenue"
}}
```
---
_Conversation History_
{history}

_Output_
"""

clarify_ambiguity_prompt = """Following the conversation history, our goal is to {goal}, but we have hit an issue where {warning_msg}.
Your task is to help resolve this issue by generating a clarification question to ask the user.

Please start by thinking about the issue and the level of confusion. Concretely, there are four levels of ambiguity to choose from:
  1. general - we have no clue what is going on, with high uncertainty in the user's intent. Our target goal might not even be correct.
  2. partial - we likely have the right goal according to the conversation, but there is a problem selecting the right column or table.
  3. specific - we are missing a specific piece of information such as an aggregation function, filter condition, or group by operation.
  4. confirmation - we have the right goal and information, but should confirm a critical aspect of the query before proceeding.

Next, generate a response that will be shared directly with the user. This has a few requirements:
  * The user is not technically savvy, so asking for feedback on SQL or Python syntax is not appropriate.
  * You should start the response with a short summary of the issue to provide context, followed by a question that addresses the issue.
  * The full response should be clear and concise, with no more than three sentences.

Your entire output should be in well-formatted JSON including keys for thought (string), level (token), and response (string), with no further text or explanations after the JSON output.
  
For example:
---
## Example 1
Suppose the table contains a 'city' column and a 'state' column.

_Conversation History_
User: Can you show me the all the users from New York?

_Output_
```json
{{
  "thought": "New York could be a city or state, so I'm not sure which column to use.",
  "level": "partial",
  "response": "There are two columns where New York could be found. Are you referring to the city or state?"
}}
```

## Example 2
Suppose our result returned a total of $0 in revenue.

_Conversation History_
User: What is the total revenue associated with 'Age-Defying Retinal Serum'?

_Output_
```json
{{
  "thought": "There might be a typo with 'Age-Defying Retinal Serum' since a typical product would refer instead to *Retinol* Serum.",
  "level": "confirmation",
  "response": "My search for 'Age-Defying Retinal Serum' returned $0 in revenue. Did you mean 'Age-Defying Retinol Serum' instead? Or perhaps 'Age Defying Retinal Serum' without the hyphen?"
}}
```

## Example 3
_Conversation History_
User: I can't believe he really went ahead and raised the tariffs against our trade partners!

_Output_
```json
{{
  "thought": "The remark is not associated with any specific data request, so we have no idea what the user wants.",
  "level": "general",
  "response": "Yes, that is a concerning development. Tariffs are unrelated to data analysis though, so could you please clarify what you would like to know?"
}}
```

## Example 4
Suppose the dataframe is None for the month of May.

_Conversation History_
User: How many clicks did we get in last month?

_Output_
```json
{{
  "thought": "Given the dataframe is None, perhaps the user meant a different month or year.",
  "level": "specific",
  "response": "My search returned zero clicks for May 2025. Do you want me to look at May 2024 or April 2025 instead?"
}}
```

## Example 5
Suppose the tables do not contain a 'Prospects' column, nor a 'Customers' column, but does contain a 'CompanyName' and 'CustomerID' column.

_Conversation History_
User: Get me the names of all the top prospects based on projected contract size.
Agent: There doesn't seem to be a 'Prospects' column, did you mean some other entity?
User: Check for their names in the Customers column.

_Output_
```json
{{
  "thought": "There is ambiguity around which columns are used to collect the names of prospects.",
  "level": "partial",
  "response": "There doesn't seem to be a 'Customers' column either in any of the tables. Perhaps CompanyName or CustomerID should be used as the identifier?"
}}
```

## Example 6
_Conversation History_
User: How many impressions did we get from Instagram?

_Output_
```json
{{
  "thought": "We tried to count impressions as the unique aa_uuids from the AdobeAnalyticsEndpoint, but recieved an invalid dataframe. We should confirm whether we made the right assumptions on calculating impressions.",
  "level": "confirmation",
  "response": "So the count of unique aa_uuids from the AdobeAnalyticsEndpoint table counts as impressions, which we can then filter for Instagram by using the ad_platform column. Is that right?"
}}
```

## Example 7
Suppose the dataframe is invalid even though the query seems correct in summing up the conversions.

_Conversation History_
User: You can use the entryURL column to filter for users coming from LinkedIn.

_Output_
```json
{{
  "thought": "The query seems correct, but the dataframe is invalid. We should confirm whether we made the right assumptions on calculating conversions.",
  "level": "confirmation",
  "response": "I hit an error when I trying to run the query. Am I supposed to be using the SUM function?"
}}
```

## Example 8
_Conversation History_
User: Make me a table that shows the click-through rate broken down by ad group. I want to know our best one.

_Output_
```json
{{
  "thought": "Null values are not ideal, but often occur in real life. We should check whether the user wants to proceed or not.",
  "level": "specific",
  "response": "The 'Flashback to the 80s' ad group is performing the well with 12.4% CTR. However, many other ad groups have null CTR values. Is that ok?"
}}
```
---
Now it's your turn to clarify the ambiguity. Based on the conversation history, please generate the ambiguity level and a novel clarification question to resolve the ambiguity.
For additional context, here is the thought process we used to arrive at the current state: {thought}

_Conversation History_
{history}

_Output_
"""

code_generation_error = """Following the conversation history, our goal is to {dact_goal}, but we have hit an issue.
Recent conversation history:
{history}
So far, our thought process has been: {thought}

This led to generating the following code:
{code_one}
However, we encountered an error: {error_one}
{code_generation_two}

Please help resolve this issue by deciding how to proceed. There are five possible actions to choose from:
  1. fill - update existing rows with new data, this is most applicable when the root cause of query error is nulls or missing values
  2. combine - find a way to join tables together, this is most applicable when the query error occurred due to missing foreign keys, often manifested as a Binder error
  3. stage - insert an intermediate column that stages the data before the final operation, this is most applicable when casting or extracting dates
  4. convert - change the data type of a column, this is most applicable when the root cause of query error is due to incompatible data types
  5. clarify - none of the above actions seem appropriate, so we need to clarify the user's intent to determine the correct course of action

Start by thinking about the root cause of the error. If the code generation error differs in the two attempts, focus on resolving the error from the first attempt.
Next, decide on the appropriate action to take. Finally, generate a concise response asking the user for permission to proceed with the chosen action.
Aim to be precise in your response. If an action requires a specific column or table, include such details to avoid ambiguity.
Your output should only contain well-formatted JSON including your thoughts, chosen action, and response. Do not provide any further explanations or justifications.

#############
Examples of properly formatted outputs:

_Output_
```json
{{
  "thought": "The initial error occurred when extracting the month from the 'DateRegistered' column. Creating a month column as an intermediate step can help us isolate the error.",
  "action": "stage",
  "response": "I encountered an issue when extracting the month from the 'DateRegistered' column. Perhaps I could create a month column as an intermediate step to isolate the error?"
}}
```

_Output_
```json
{{
  "thought": "The Binder error notes the values list 'Conversions' does not have a column named 'CustomerID' when trying to join with the 'Orders' table, indicating an issue with foreign keys.",
  "action": "combine",
  "response": "I tried to join 'Conversions' to 'Orders', but encountered an error due to incompatible foreign keys. Should we find a way to connect these two tables before proceeding?"
}}
```

_Output_
```json
{{
  "thought": "The 'PricePerUnit' column contains null values causing the error. Filling these missing values with the average price can help resolve the issue.",
  "action": "fill",
  "response": "I encountered an error due to missing values in the 'PricePerUnit' column. Would you like me to fill these missing values with the average price?"
}}
```

_Output_
```json
{{
  "thought": "'DeliveryTime' includes descriptive text (such as 'morning') in addition to time values, causing a data type error. Converting all these to standard timestamps may help.",
  "action": "convert",
  "response": "The 'DeliveryTime' column contains non-standard time values, such as 'morning'. I suggest converting these to standard timestamps before proceeding, does that sound good?"
}}
```

_Output_
```json
{{
  "thought": "It's hard to decipher the cause of the error, but it seems to be related to the 'acceleration_rate' column. I need more information to proceed.",
  "action": "clarify",
  "response": "I encountered an error related to the 'acceleration_rate' column. Could you provide any more guidance on what you're looking for?"
}}
```

_Output_
```json
{{
  "thought": "The error occurred when trying to join the 'MarketoLeads' table with the 'SalesforceLeads' table. It seems the UserIDs are not matching up correctly.",
  "action": "combine",
  "response": "When joining the 'MarketoLeads' and 'SalesforceLeads' tables, I got an error with the UserIDs not matching up. Should we find a different way to connect these two tables?"
}}
```

#############
Now it's your turn. Choose the appropriate action to take and generate a concise response based on the conversation history and known facts.
This is very important to my career. Please think carefully before making your decision.

_Output_
"""

broken_dataframe_prompt = """Given the conversation history, we generated a {source} to answer the user request, but {error_message}.
_Conversation History_
{history}

If there is a way to repair the broken result, please provide the corrected code to meet the user request. If not, please return 'none'.

For example,
## Broken Python code
Perhaps we forgot to assign the results back to the dataframe.

_Generated Code_
df['click_thru_rate'].str.rstrip('%').astype('float') / 100.0
_Revised Code_
```python
df['click_thru_rate'] = df['click_thru_rate'].str.rstrip('%').astype('float') / 100.0
```

## No Repair Possible
_Generated Code_
SELECT outbound_messages.campaign_name, AVERAGE(activities.click_thru_rate) AS average_CTR, activities.year
FROM activities JOIN outbound_messages ON activities.message_id = outbound_messages.message_id
WHERE outbound_messages.brand = 'New Balance'
AND outbound_messages.campaign_name = 'More Comfortable Than Ever'
AND activities.year IN (2021, 2022, 2023)
GROUP BY activities.year;

_Revised Code_
none

## Broken SQL code
Perhaps there is a typo somewhere in the query.

_Generated Code_
SELECT iterable_email.Campaign_ID, iterable_email.Campaign_Name, COUNT(iterable_email.Subscriber_ID) AS TotalSubscribers,
  SUM(CASE WHEN iterable_email.Opened = TRUE THEN 1 ELSE 0 END) AS OpenedCount,
  SUM(CASE WHEN iterable_email.Clicked = TRUE THEN 1 ELSE 0 END) AS ClickedCount
FROM iterable email
WHERE iterable_email.Campaign_Launch_Date BETWEEN '2024-07-01 AND 2024-07-30'
GROUP BY iterable_email.Campaign_ID, iterable_email.Campaign_Name
ORDER BY OpenedCount DESC, ClickedCount DESC;

_Revised Code_
```sql
SELECT iterable_email.Campaign_ID, iterable_email.Campaign_Name, COUNT(iterable_email.Subscriber_ID) AS TotalSubscribers,
  SUM(CASE WHEN iterable_email.Opened = TRUE THEN 1 ELSE 0 END) AS OpenedCount,
  SUM(CASE WHEN iterable_email.Clicked = TRUE THEN 1 ELSE 0 END) AS ClickedCount
FROM iterable_email
WHERE iterable_email.Campaign_Launch_Date BETWEEN '2024-07-01' AND '2024-07-30'
GROUP BY iterable_email.Campaign_ID, iterable_email.Campaign_Name
ORDER BY OpenedCount DESC, ClickedCount DESC;
```

## Current Scenario
When trying to repair this query, note that the valid columns are {col_desc}.
Do not offer any explanations or justification, only the directly executable {source}.

_Generated Code_
{code}

_Revised Code_
"""

empty_results_prompt = """Given the conversation history, we generated a SQL query to answer the user request, but the query returned no results.
_Conversation History_
{history}
_DuckDB Results_
{results}

Although a query may return empty due to a variety of legitimate reasons, it is often indicative of a mistake.
Please generate a revised query that addresses the issue, or return 'none' if you cannot fix it.
Your entire response should only contain the directly executable revised query that starts with 'SELECT' with no additional text or explanations after the revision.

For example,
---
## Typo Scenario
The query's filter condition may contain a typo:

_Previous Query_
SELECT Intercom.AssignedAgent, COUNT(Intercom.TicketID) AS ResolvedTickets
FROM Intercom
WHERE Intercom.Status = 'Closed'
AND Intercom.Issue_Type = 'Payment Procesing'
AND (Intercom.ClosedTimestamp - Intercom.OpenTimestamp) <= INTERVAL '1 day'
GROUP BY Intercom.AssignedAgent
ORDER BY ResolvedTickets DESC;

_Revised Query_
```sql
SELECT Intercom.AssignedAgent, COUNT(Intercom.TicketID) AS ResolvedTickets
FROM Intercom
WHERE Intercom.Status = 'Closed'
AND Intercom.Issue_Type = 'Payment Processing'
AND (Intercom.ClosedTimestamp - Intercom.OpenTimestamp) <= INTERVAL '1 day'
GROUP BY Intercom.AssignedAgent
ORDER BY ResolvedTickets DESC;
```

## Invalid Date Range Scenario
Or the date range happens to be too far into the future or the past:

_Previous Query_
SELECT braze_email.Campaign_ID, braze_email.Campaign_Name, COUNT(braze_email.Subscriber_ID) AS TotalSubscribers,
  SUM(CASE WHEN braze_email.Opened = TRUE THEN 1 ELSE 0 END) AS OpenedCount,
  SUM(CASE WHEN braze_email.Clicked = TRUE THEN 1 ELSE 0 END) AS ClickedCount
FROM braze email
WHERE braze_email.Campaign_Launch_Date BETWEEN '2024-07-01' AND '2024-07-30'
GROUP BY braze_email.Campaign_ID, braze_email.Campaign_Name
ORDER BY OpenedCount DESC, ClickedCount DESC;

_Revised Query_
```sql
SELECT braze_email.Campaign_ID, braze_email.Campaign_Name, COUNT(braze_email.Subscriber_ID) AS TotalSubscribers,
  SUM(CASE WHEN braze_email.Opened = TRUE THEN 1 ELSE 0 END) AS OpenedCount,
  SUM(CASE WHEN braze_email.Clicked = TRUE THEN 1 ELSE 0 END) AS ClickedCount
FROM braze_email
WHERE braze_email.Campaign_Launch_Date BETWEEN '2023-07-01' AND '2023-07-30'
GROUP BY braze_email.Campaign_ID, braze_email.Campaign_Name
ORDER BY OpenedCount DESC, ClickedCount DESC;
```

## Filter too Strict Scenario
One other reason might be that the filter is too strict, so we can try to relax it:

_Previous Query_
SELECT AccountsReceivable.CompanyID, AccountsReceivable.CompanyName
FROM AccountsReceivable
INNER JOIN Payments ON AccountsReceivable.CompanyID = Payments.CompanyID
GROUP BY AccountsReceivable.CompanyID, AccountsReceivable.CompanyName
HAVING SUM(Payments.SubscriptionFee) > 500;

_Revised Query_
```sql
SELECT AccountsReceivable.CompanyID, AccountsReceivable.CompanyName
FROM AccountsReceivable
INNER JOIN Payments ON AccountsReceivable.CompanyID = Payments.CompanyID
GROUP BY AccountsReceivable.CompanyID, AccountsReceivable.CompanyName
HAVING SUM(Payments.SubscriptionFee) > 100;
```

## Unable to Fix Scenario
Sometimes, there aren't any obvious errors to fix since the query basically looks correct. In this case, we just return 'none':

_Previous Query_
SELECT spend, total_volume
FROM mixpanel_raw
WHERE age_group = 'teen'
ORDER BY total_volume DESC
LIMIT 3;

_Revised Query_
```sql
none
```

### Multiple Column Scenario
Another common cause is a value may be relevant to multiple columns, so the previous query filtered for the wrong one:

_Previous Query_
SELECT shipments.first_name, shipments.last_name
FROM shipments JOIN purchases ON shipments.customer_id = purchases.customer_id
WHERE shipments.city = 'New York'
AND EXTRACT(YEAR FROM purchases.date) = 2021
GROUP BY shipments.customer_id, shipments.first_name, shipments.last_name
HAVING COUNT(purchases.purchase_id) >= 10;

_Revised Query_
```sql
SELECT shipments.first_name, shipments.last_name
FROM shipments JOIN purchases ON shipments.customer_id = purchases.customer_id
WHERE shipments.state = 'New York'
AND EXTRACT(YEAR FROM purchases.date) = 2021
GROUP BY shipments.customer_id, shipments.first_name, shipments.last_name
HAVING COUNT(purchases.purchase_id) >= 10;
```
---
## Current Scenario
When trying to repair this query, note that the valid columns are {col_desc}.
With all this in mind, please revise the query, or return 'none' if you cannot fix it.
Do not offer any explanations or justification before or after the revision, only return the directly executable revised query.

For additional context, the conversation history is:
{history}

_Previous Query_
{query}

_Revised Query_
"""

compute_needed_prompt = """Given the conversation history, determine whether it would be useful to have access to a calculator or data science library to proceed.
Concretely, some cases where a tool would be helpful include:
  * comparing two (or more) values to see if one is greater than, less than, or equal to the other
  * arithmetic operations such as addition, subtraction, multiplication, or division; especially when the values grow beyond a single digit
  * finding the correlation between two variables, possibly represented as columns in a table
  * answering any sort of word problem that would benefit from having access to NumPy or SciPy
In contrast, if the user's request requires manipulating the table in some way, then a tool is not appropriate.

Please start by thinking carefully about the user's request, paying particular attention to the level of complexity involved.
If such a computation is appropriate, please write out a concise natural language question that can be used to support the user's request.
Otherwise, simply write 'none' to indicate that a tool is not needed.

For example,
---
_Conversation History_
User: How many clicks is that in over the entire year?
Agent: The total is 4,725 clicks.
User: How many is that on a monthly basis?

_Output_
```json
{{
  "thought": "The user wants to convert a yearly value into a monthly value, which is a simple arithmetic operation.",
  "question": "What is 4725 divided by 12?"
}}
```

_Conversation History_
User: Which channels do we have listed as referring sites?
Agent: By looking at the utm_source columns, it seems the most common ones are Google, Mindful Momma, Sustainably Chic, and Going Zero Waste.
User: So our annual MBR is coming up and I need to figure out which mix of channels to double down on. How should we approach this?

_Output_
```json
{{
  "thought": "The user wants to model the mix of marketing channels to figure out which ones are most valuable. This goes far beyond the scope of a calculator.",
  "question": "none"
}}
```

_Conversation History_
User: What is the formula for entropy?
Agent: Entropy is defined as the negative sum of the probability of each state times the log of the probability of that state.
User: OK, suppose the probability distribution is [0.1, 0.25, 0.45, 0.05, 0.15]. Would the entropy for that be greater than 0.8?

_Output_
```json
{{
  "thought": "The user wants to calculate the entropy and then compare it to another value. This is a great candidate for a tool!",
  "question": "Calculate the entropy of probs = [0.1, 0.25, 0.45, 0.05, 0.15], and then compare it to 0.8"
}}
```

_Conversation History_
User: Which campaign had the highest response rate in the last quarter?
Agent: By looking at the utm_source columns, it seems the most common ones are Google, Mindful Momma, Sustainably Chic, and Going Zero Waste.
User: Can we fix all the values for the different campaign names?

_Output_
```json
{{
  "thought": "Cleaning the data goes beyond the scope of a calculator.",
  "question": "none"
}}
```

_Conversation History_
User: Did we get any conversions from that email blast in the past month?
Agent: The email campaign resulted in 62 conversions.
User: What's the correlation between clicks and conversions then?

_Output_
```json
{{
  "thought": "I can calculate the correlation between clicks and conversions in one line using numpy.",
  "question": "What is the correlation between clicks and conversions?"
}}
```
---
Now it's your turn! Please determine whether a tool would be useful and, if so, write out a concise natural language question to address the user's request.

_Conversation History_
{history}

_Output_
"""

sufficient_info_prompt = """Focusing on the final user turn in the conversation history, please think carefully about whether any known facts are related to that user turn.
All known facts are up-to-date and accurate, so your decision should be based solely on whether sufficient information is available, not on the recency of the information.
Your entire response should be well-formatted JSON with thought (string) and enough (boolean) as keys. There should be no further explanations after the JSON output.

For example,
---
_Conversation History_
User: Did we get any transactions that were over $500?
Agent: Yes, we have 32 such transactions. Please see the table for details.
User: What was the earliest date for those transactions?

_Known Facts_
The transactions table has 1,077 rows and 9 columns.
The available columns are ['transaction_id', 'user_id', 'transaction_type', 'transaction_date', 'amount', 'product_id', 'product_name', 'product_category', 'status']
 - The transaction_type column contains 7 unique strings with an average of 10.8 characters.
 - The transaction_date column contains dates with 613 unique values.
 - The amount column contains 104 unique numbers ranging from 0.99 to 3999.0.
   Statistics for amount: range of 3998.01, average of 1207.435, median of 173, mode of 182, sum of 25491.4, and standard deviation of 188.68.
 - The product_name column contains 157 unique strings with an average of 25.145 characters.
   The most common items in product_name are Snowpark Advanced with 121 occurences, StreamFlow with 97 occurences, Journey Insights with 74 occurences.
 - The product_category column contains 5 unique strings with an average of 8.9 characters.
 - The status column contains 4 unique strings.

_Output_
```json
{{
  "thought": "We know that there are 613 unique transaction dates, but we don't have the exact date for the earliest transaction over $500.",
  "enough": false
}}
```

_Conversation History_
User: Can you please remove all Pardot visits with a missing email?
Agent: Ok, they have been removed
User: What is the average all visits recorded in the final Pardot results?

_Known Facts_
The SF_Pardot table has 815 rows and 10 columns.
The available columns are ['LeadID', 'UserName', 'Source', 'VisitCounts', 'PageVisited', 'FirstVisitTime', 'DownloadedContent', 'FormSubmitted', 'FormSubmissionDateTime', 'LeadScore']
 - The UserName column contains 814 unique strings with an average of 12.606 characters.
   The most common items in UserName are .
 - The Source column contains 8 unique values.
 - The VisitCounts column contains 12 unique numbers ranging from 0 to 11.
   Statistics for VisitCounts: range of 11, average of 3.685, median of 4, mode of 3, sum of 3055, and standard deviation of 2.04.
 - The PageVisited column contains 8 unique values.
 - The FirstVisitTime column contains dates with 574 unique values.
 - The DownloadedContent column contains 2 unique values.
 - The FormSubmitted column contains 2 unique values.
 - The FormSubmissionDateTime column contains dates with 21 unique values.
 - The LeadScore column contains 69 unique numbers ranging from 20 to 100.
   Statistics for LeadScore: range of 80, average of 77.3472, median of 81, mode of 89, sum of 63038, and standard deviation of 16.55.

_Output_
```json
{{
  "thought": "It doesn't matter that emails were recently deleted. The known facts provide information about 'VisitCounts' including its average.",
  "enough": true
}}
```

_Conversation History_
Agent: Apologies, there does not seem to a be a 'bought' event type in the segment_customers_Jan25 table.
User: All customers who bought something in January based on the event
User: What are all the unique event types?

_Known Facts_
The segment_customers_Jan25 table has 672 rows and 14 columns.
The available columns are ['EventID', 'Event', 'EventType', 'EventTime', 'EventCategoy', 'UserID', 'SessionID', 'Member', 'EmailAddress', 'Source', 'Reviewed', 'Hostname', 'Browser', 'PageTitle']
  - The EventID column contains 672 unique values.
  - The EventType column contains 8 unique strings with an average of 9.2 characters.
    The most common items in EventType are Purchase with 223 occurences, Signup with 193 occurences, View with 135 occurences.
  - The EventTime column contains dates with 672 unique values.
  - The EventCategory column contains 12 unique values.
  - The Member column contains 2 unique values.
  - The Hostname column contains 670 unique strings with an average of 15.9 characters.
  - The Browser column contains 6 unique strings with an average of 6.5 characters.
    The most common items in Browser are Chrome with 320 occurences, Firefox with 152 occurences, Safari with 91 occurences.
  - The PageTitle column contains 670 unique strings with an average of 12.1

_Output_
```json
{{
  "thought": "We know that there are 8 unique event types in the EventType column. However, we don't know the specific values for each event type.",
  "enough": false
}}
```

_Conversation History_
User: You see how we have data from the SFDC conference in March?
Agent: Yes, I see a table that seems to contain data related to interested visitors from a SFDC sign-up form.
User: I want to send an email to all the visitors who filled out the form from the conference if they said yes to the Android question.
Agent: I can filter for True values in the Android column, but I don't see a column containing email addresses.
User: Don't we have a contacts column for that?

_Known Facts_
The Signup SFDC downloaded table has 429 rows and 9 columns.
The available columns are ['Full Name', 'Contact', 'Company', 'Job Title', 'Interested Features Selection', 'Android', 'iOS', 'Web'. 'IsCustomer']
 - The Full Name column contains 422 unique strings with an average of 16.7 characters.
   The most common items in Full Name are NoName with 7 occurences, Just Looking with 3 occurences, John Daly with 2 occurences.
 - The Contact column contains 392 unique strings with an average of 4.08 characters.
   The most common items in Contact are  with 15 occurences, N/A with 13 occurences, noemail@gmail.com with 7 occurences.
 - The Company column contains 135 unique strings with an average of 5.35 characters.
   The most common items in Company are  with 230 occurences, None with 13 occurences, Zapier with 4 occurences.
 - The Interested Features Selection column contains 418 unique strings with an average of 1356.8 characters.
 - The Android column contains 2 unique values.
 - The iOS column contains 2 unique values.
 - The Web column contains 3 unique values.

_Output_
```json
{{
  "thought": "We know that there are 392 unique contacts, but it seems many of them are missing or incomplete. We should investigate further to see if we actually have any valid email addresses.",
  "enough": false
}}
```

_Conversation History_
User: Can we delete the row with userID 2501108
Agent: Sure! How does this look?
User: Now let's remove users who are from Mailchimp, Klaviyo, SendGrid, or ActiveCampaign
Agent: OK, I've updated the table as requested.
User: How many rows are in the users table now?

_Known Facts_
The users table has 1704 rows and 6 columns.
The available columns are ['user_id', 'full_name', 'email', 'last_login', 'source', 'member']
 - The full_name column contains 1704 unique strings with an average of 6.355 characters.
 - The email column contains 1704 unique strings with an average of 17.586 characters.
 - The last_login column contains 1639 unique strings ranging from 2023-01-01 to 2023-12-17.
   The most common items in 2023-04-12 with 15 occurences, 2023-07-11 with 12 occurences, 2023-08-09 with 10 occurences.
 - The source column contains 12 unique values with an average of 8.323 characters.
 - The member column contains 2 unique values.

_Output_
```json
{{
  "thought": "Known facts are always up-to-date. Recent deletions does not change this, so I know there are 1704 users.",
  "enough": true
}}
```

_Conversation History_
User: Yea, let's insert the new location into the table
Agent: Sure, I have added the Miami and Los Angeles destinations
User: How many unique locations are there in total now?
Agent: I found 127 unique locations in the Shipping Destination column.
User: What are the most common destinations?

_Known Facts_
The Shipyard_Tracking_(full) table has 805 rows and 11 columns.
The available columns are ['ShipmentID', 'ShipmentTimestamp', 'Destination', 'Origin', 'ShipmentType', 'Status', 'Weight', 'Cost', 'Carrier', 'TrackingID', 'ETA (hours)']
  - The ShipmentID column contains 805 unique values.
  - The ShipmentTimestamp column contains dates with 792 unique values.
  - The Destination column contains 127 unique strings with an average of 8.34 characters.
    The most common items in Destination are New York with 16 occurences, Los Angeles with 14 occurences, Chicago Midway with 11 occurences.
  - The Origin column contains 149 unique strings with an average of 8.13 characters.
    The most common items in Origin are New York with 17 occurences, Miami with 9 occurences, San Francisco with 7 occurences.
  - The Weight columns contains 126 unique values ranging from 1.9 to 1000.0 with an average of 164.2 and standard deviation of 157.5.
  - The Cost column contains 723 unique values ranging from 350 to 8000 with an average of 1280.2 and standard deviation of 1056.4.
  - The Carrier column contains 5 unique strings with an average of 6.0 characters.
    The most common items in Carrier are FedEx with 353 occurences, UPS with 254 occurences, USPS with 220 occurences.

_Output_
```json
{{
  "thought": "The destinations were recently altered, but the known facts tell us the most common ones are New York, Los Angeles, and Chicago Midway, which is sufficient to make a decision",
  "enough": true
}}
```
---
This is very important to my career. Generate a concise thought composed of few sentences at most.
Remember, any actions that may require re-calculating the known facts have already been accounted for.
If an extra query is useful, then describe what the SQL query should do in your thought, but do not generate any code.
Then make the right decision as to whether there is relevant information available. Your thought and decision must be in well-formatted JSON.

_Conversation History_
{history}

_Known Facts_
{facts}

_Output_
"""

add_facts_prompt = """You are an outstanding data analyst who is exceptionally skilled at writing SQL queries.
Given the conversation history and known facts, your task is to generate an accurate SQL query that adds facts to help answer the user's request in the final turn.
The conversation history is composed of user and agent utterances interspersed with your own internal thoughts.
Pay attention to the provided thoughts and known facts since you should not be querying for information that is already known or irrelevant to the user's request.

As a skilled analyst, you know the nuances of writing useful queries. For example, although a query may only need an ID column, you know outputting extra columns (such as customer names or campaign names) may help with interpreting the results.
You also know when asked to count how many of something exists, you should consider if a unique count makes sense, which implies using DISTINCT or GROUP BY when appropriate.
Remember, you are querying from DuckDB, use the appropriate syntax and casing for operations.
If a query is ambiguous or problematic, such as a request for a non-existent column, please output 'Error:' followed by a short phrase to describe the issue (eg. 'Error: missing column' or 'Error: unclear start date').

Your SQL query should be well-formatted and directly executable. Do not include any explanations or justifications, only the SQL query.

For example,
#############
User: Can we take a look at all the conversions from the Strength and Stamina campaign?
Agent: Sure, these are the conversions from the Strength and Stamina campaign in the last 30 days.
User: Did all the conversions happen at the same time, they all seem to be in the same hour each day?
Thought: The user wants to know if conversions are clustered around the same time each day. I should group by the hour of the day to find the distribution of conversion times.

_Known Facts_
The amplitudeWeekly table has 1101 rows and 19 columns.
The available columns are ['event_id', 'user_id', 'event_type', 'event_time', 'event_properties', 'user_properties', 'device_id', 'platform', 'os_name', 'os_version', 'device_model', 'campaign', 'country', 'region', 'city', 'dma', 'language', 'library', 'session_id']
  - The event_id column contains 1101 unique values.
  - The user_id column contains 912 unique values.
  - The event_type column contains 32 unique strings with an average of 9.5 characters.
    The most common items in event_type are click with 291 occurences, visited with 238 occurences, conversion with 153 occurences.
  - The event_time column contains dates with 307 unique values.
  - The event_properties column contains 8 unique strings with an average of 23.6 characters.
  - The user_properties column contains 23 unique strings with an average of 18.4 characters.
  - The os_name column contains 3 unique strings with an average of 6.2 characters.
    The most common items in os_name are iOS with 594 occurences, Android with 506 occurences, Windows with 1 occurences.
  - The country column contains 1 unique strings with an average of 2.0 characters.
    The most common items in country are US with 1101 occurences.
  - The region column contains 3 unique strings with an average of 1.7 characters.
    The most common items in region are CA with 1004 occurences, NY with 67 occurences, and  with 30 occurences.
  - The city column contains 34 unique strings with an average of 51.9 characters.
    The most common items in city are San Francisco with 235 occurences, SF with 167 occurences, and Santa Clara with 110 occurences.
  - The library column contains 17 unique values.
  - The session_id column contains 984 unique values.

_Output_
```sql
SELECT
  EXTRACT(HOUR FROM event_time) AS event_hour,
  COUNT(*) AS conversions_count
FROM amplitudeWeekly
WHERE campaign = 'Strength and Stamina' AND event_type = 'conversion'
GROUP BY event_hour
ORDER BY event_hour;
```

#############
Agent: Apologies, there does not seem to a be a 'bought' event type in the segment_customers_Jan25 table.
User: All customers who bought something in January based on the event
User: What are all the unique event types?
Thought: I can find all the unique event types in the EventType column.

_Known Facts_
The segment_customers_Jan25 table has 672 rows and 14 columns.
The available columns are ['EventID', 'Event', 'EventType', 'EventTime', 'EventCategoy', 'UserID', 'SessionID', 'Member', 'EmailAddress', 'Source', 'Reviewed', 'Hostname', 'Browser', 'PageTitle']
  - The EventID column contains 672 unique values.
  - The EventType column contains 8 unique strings with an average of 9.2 characters.
    The most common items in EventType are Purchase with 223 occurences, Signup with 193 occurences, View with 135 occurences.
  - The EventTime column contains dates with 672 unique values.
  - The EventCategory column contains 12 unique values.
  - The Member column contains 2 unique values.
  - The Hostname column contains 670 unique strings with an average of 15.9 characters.
  - The Browser column contains 6 unique strings with an average of 6.5 characters.
    The most common items in Browser are Chrome with 320 occurences, Firefox with 152 occurences, Safari with 91 occurences.
  - The PageTitle column contains 670 unique strings with an average of 12.1

_Output_
```sql
SELECT DISTINCT EventType
FROM segment_customers_Jan25;
```

#############
User: You see how we have data from the SFDC conference in March?
Agent: Yes, I see a table that seems to contain data related to interested visitors from a SFDC sign-up form.
User: I want to send an email to all the visitors who filled out the form from the conference if they said yes to the Android question.
Agent: I can filter for True values in the Android column, but I don't see a column containing email addresses.
User: Don't we have a contacts column for that?
Thought: The user wants to message visitors, but we are missing an email column. I will pull the first few values of the Contact column to see if it contains email addresses.

_Known Facts_
The Signup SFDC downloaded table has 429 rows and 9 columns.
The available columns are ['Full Name', 'Contact', 'Company', 'Job Title', 'Interested Features Selection', 'Android', 'iOS', 'Web'. 'IsCustomer']
 - The Full Name column contains 422 unique strings with an average of 16.7 characters.
   The most common items in Full Name are NoName with 7 occurences, Just Looking with 3 occurences, John Daly with 2 occurences.
 - The Contact column contains 392 unique strings with an average of 4.08 characters.
   The most common items in Contact are  with 15 occurences, N/A with 13 occurences, noemail@gmail.com with 7 occurences.
 - The Company column contains 135 unique strings with an average of 5.35 characters.
   The most common items in Company are  with 230 occurences, None with 13 occurences, Zapier with 4 occurences.
 - The Interested Features Selection column contains 418 unique strings with an average of 1356.8 characters.
 - The Android column contains 2 unique values.
 - The iOS column contains 2 unique values.
 - The Web column contains 3 unique values.

_Output_
```sql
SELECT Contact
FROM "Signup SFDC downloaded"
LIMIT 50;
```

#############
User: Yea, let's delete those rows
Agent: Sure, I have removed those empty rows from the table.
User: How many unique locations are there in total now?
Agent: I found 127 unique locations in the Shipping Destination column.
User: wait, so are there other columns with empty values?
Thought: I can look for columns with NULL values or empty strings to see if there are other columns with missing data. Then I can count the number of empty values in each column.

_Known Facts_
The Shipyard_Tracking_(full) table has 805 rows and 11 columns.
The available columns are ['ShipmentID', 'ShipmentTimestamp', 'Destination', 'Origin', 'ShipmentType', 'Status', 'Weight', 'Cost', 'Carrier', 'TrackingID', 'ETA (hours)']
  - The ShipmentID column contains 805 unique values.
  - The ShipmentTimestamp column contains dates with 792 unique values.
  - The Destination column contains 127 unique strings with an average of 8.34 characters.
    The most common items in Destination are New York with 16 occurences, Los Angeles with 14 occurences, Chicago Midway with 11 occurences.
  - The Origin column contains 149 unique strings with an average of 8.13 characters.
    The most common items in Origin are New York with 17 occurences, Miami with 9 occurences, San Francisco with 7 occurences.
  - The Weight columns contains 126 unique values ranging from 1.9 to 1000.0 with an average of 164.2 and standard deviation of 157.5.
  - The Cost column contains 723 unique values ranging from 350 to 8000 with an average of 1280.2 and standard deviation of 1056.4.
  - The Carrier column contains 5 unique strings with an average of 6.0 characters.
    The most common items in Carrier are FedEx with 353 occurences, UPS with 254 occurences, USPS with 220 occurences.

_Output_
```sql
CREATE OR REPLACE TEMPORARY TABLE empty_counts AS 
SELECT column_name, COUNT(*) AS empty_count 
FROM (
  SELECT *
  FROM "Shipyard_Tracking_(full)"
  UNPIVOT INCLUDE NULLS (value FOR column_name IN (
      ShipmentID, ShipmentTimestamp, Destination, Origin, ShipmentType, 
      Status, Weight, Cost, Carrier, TrackingID, "ETA (hours)"
  ))
) AS unpivoted_table
WHERE value IS NULL OR value = ''
GROUP BY column_name;

SELECT *
FROM empty_counts
WHERE empty_count > 0;
```

#############
{history}
Thought: {thought}

_Known Facts_
{facts}

_Output_
"""

ask_for_pref_prompt = """Given the conversation history, generate a clarification question to elicit the user's preference to resolve the ambiguity.
Just answer with either the question you would ask or 'none' if no clarification question is needed.

For example,
#############
_Conversation History_
User: Did we update the campaign name any time this month?
Agent: Yes, we updated the campaign name on the 15th.
User: What are the most popular keywords for each listing?

_Ambiguous Preference_
best

_Clarfication Question_
What do you mean by 'most popular'? How exactly would you like me to calculate that?

#############
_Conversation History_
User: I want to see the total number of clicks for each campaign.
Agent: The total clicks are 1,228 for the 'Independence Day' campaign. See the table for more.
User: What about just for this week?

_Ambiguous Preference_
timing

_Clarfication Question_
What day do you consider the start of the week: Sunday or Monday?

#############
_Conversation History_
User: If I remember correctly, the conversion rate was around 5% last year. Can you confirm that?
Agent: Yes, the conversion rate was 5.2% in 2023.
User: What's the CVR more recently?

_Ambiguous Preference_
timing

_Clarfication Question_
What time frame do you consider 'more recently'? Are you interested in the past month or past quarter?

#############
Now it's your turn. Generate a clarification question to resolve the ambiguity.
_Conversation History_
{history}

_Ambiguous Preference_
{preference}

_Clarfication Question_
"""

staging_table_prompt = """We tried to answer the user's request by querying the data, but hit upon an error.
Given the conversation history, existing columns, and current query, think out loud about how to break off a smaller piece of the problem to tackle first.
If we can make incremental progress on the task by creating staging columns, then identify the source column(s) from the existing data and also the new target column(s) we would like to create.
If inserting intermediate columns is not possible or not beneficial, then keep both the 'source' and 'target' fields as empty lists.
Your entire response should be in well-formatted JSON with keys for thought (string), source (list of dicts), and target (list of dicts), with no further explanations after the JSON output.

For example,
---
_Conversation History_
User: how much revenue was made each week from appointments where Facebook was the referreral source?
Agent: I can use the appointmentDate and referrerURL columns to filter the data, then sum the revenueGenerated column to find the weekly revenue. However, I don't see a way to join the GoogleAds_Q3 and SalesRecord_Shopify_0812 tables.
User: you can use the gAdRef column and gAd_ID

_Existing Columns_
* Tables: GoogleAds_Q3, SalesRecord_Shopify_0812, Product_Details
* Columns: gAd_ID, clickCount, campaignInitDate, campaignTermDate, userActivity, adBounceRate, adSpend, adContentCode, referrerURL in GoogleAds_Q3;
orderRef, prodSKU, appointmentDate, acquisitionCost, buyerID, gAdRef, revenueGenerated, unitsMoved, fulfillmentStatus, customerNotes in SalesRecord_Shopify_0812;
SKU, itemName, itemCategory, retailPrice, totalCost, stockLevel in Product_Details

_Current Query_
SELECT WEEK(appointmentDate) AS week, SUM(revenueGenerated) AS weekly_revenue
FROM SalesRecord_Shopify_0812
WHERE referrerURL LIKE '%Facebook%'
GROUP BY week;

_Output_
```json
{{
  "thought": "Extracting the week from appointmentDate could help as an intermediate step to break down the problem into smaller parts. I could also generate boolean column to track Facebook referrers.",
  "source": [
    {{"tab": "SalesRecord_Shopify_0812", "col": "appointmentDate"}},
    {{"tab": "GoogleAds_Q3", "col": "referrerURL"}}
  ],
  "target": [
    {{"tab": "SalesRecord_Shopify_0812", "col": "week"}},
    {{"tab": "GoogleAds_Q3", "col": "isFacebookReferrer"}}
  ]
}}
```

_Conversation History_
User: Are there any users with activity in the last month where the payment status is 'overdue'? Btw, we should exclude anything from the Pilot Tier since those were early test accounts.
Agent: I tried to join the subscriptions and user_activity tables based on the user_id and user_plan columns, but received an error. Any ideas?
User: Go with plan_name instead, which contains the subscription tier and type. user plan is just the tier part.

_Existing Columns_
* Tables: mq_leads, product_launches, subscriptions, user_activity
* Columns: lead_id, first_name, last_name, email, organization, lead_source, contact_date, status, notes, follow_up_date in mq_leads;
launch_id, is_secure, provenance, version, features, documentation_link in data_sources;
subscription_id, user_id, plan_name, sub_timestamp, billing_cycle, payment_status, renewal_notice in subscriptions;
activity_id, activity_type, user_plan, timestamp, duration, data_source, outcome, error_log in user_activity

_Current Query_
SELECT user_id, COUNT(activity_id) AS activity_count
FROM user_activity
JOIN subscriptions ON user_activity.user_plan = subscriptions.plan_name
WHERE payment_status = 'overdue' AND plan_name NOT LIKE '%Pilot Tier%'

_Output_
```json
{{
  "thought": "The plan_name column can be split into plan tier and plan type to match the user_plan column. This will help in joining the tables correctly.",
  "source": [ {{ "tab": "subscriptions", "col": "plan_name" }} ],
  "target": [ 
    {{ "tab": "subscriptions", "col": "plan_tier" }},
    {{ "tab": "subscriptions", "col": "plan_type" }}
  ]
}}
```

_Conversation History_
User: What's the best performing region in the last month?
Agent: How did you want to define 'best performing'? Also, should we filter the date based on the signup date or the transaction date?
User: best performing is net income, so each license costs a certain amount and then we add a service charge.

_Existing Columns_
* Tables: PardotAutomation; TransactionHistory; InteractionLogs
* Columns: cust_id, signup_date, cust_name, email, delivered, region, lead_score, channel, acct_status in PardotAutomation;
trans_id, cust_id, trans_date, product_id, amount, trans_type, license_fee, service_charge, maintenance_income in the TransactionHistory;
interaction_id, cust_id, interact_date, interact_type, interact_duration, issue_resolved, expenses in the InteractionLogs

_Current Query_
WITH TransactionIncome AS (
    SELECT region, SUM(amount * license_fee + service_charge) AS net_income
    FROM TransactionHistory
    WHERE trans_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
    GROUP BY region
)
SELECT region, net_income
FROM TransactionIncome
ORDER BY net_income DESC
LIMIT 5;

_Output_
```json
{{
  "thought": "Net income is calculated with a CTE. To minimize the complexity, we can add this column first to check that the intermediate results look reasonable.",
  "source": [
    {{"tab": "TransactionHistory", "col": "amount"}},
    {{"tab": "TransactionHistory", "col": "license_fee"}},
    {{"tab": "TransactionHistory", "col": "service_charge"}}
  ],
  "target": [ {{"tab": "TransactionHistory", "col": "net_income"}} ]
}}
```

_Conversation History_
User: See how we have CPCs in the adobe data?
Agent: Yes, I see the cost_per_click column in the AdobeAnalytics_final table. What would you like to do with it?
User: Which video type has the lowest CPCs?

_Existing Columns_
* Tables: AdobeAnalytics_final; SubscriptionMembership; Canva Content (revised); VendorExpenses
* Columns: campaign_id, ad_platform, ad_spend, ad_type, ad_copy, user_activity, view_count, cost_per_click in AdobeAnalytics_final;
member_id, subscription_date, renewal_date, subscription_tier, monthly_fee, activity, member_status in SubscriptionMembership;
video_id, trainer_id, video_campaign_id, creation_date, video_type, trainer_fee, impressions in Canva Content (revised);
vendor_id, service_provided, expense_date, expense_amount, vendor_category in VendorExpenses

_Current Query_
SELECT video_type, AVG(cost_per_click) AS avg_cpc
FROM AdobeAnalytics_final
JOIN Canva Content (revised) ON campaign_id = video_campaign_id
GROUP BY video_type;

_Output_
```json
{{
  "thought": "We can already filter directly by video_type and average the cost per click, so extra staging columns won't help. The JOIN clause seems suspicious though and should be reviewed.",
  "source": [],
  "target": []
}}
```

_Conversation History_
User: Whats the average order value for customer's that have allergies or dietary restrictions?
Agent: It seems you want to find specific users, but I could not figure out the right filters. Could you please clarify which columns to use?
User: You can check the text within the special instructions.

_Existing Columns_
* Tables: CustContact, CustOrders, MarketingOffers
* Columns: CustomerID, CustName, FavCuisineType, ShippingAddress, ContactNumber, IsActive, Twitter, Instagram, Yelp in CustContact;
OrderID, CustomerID, RestaurantID, OrderDate, TotalAmount, DeliveryAddress, OrderStatus, EstDeliveryTime, SpecialInstructions in CustOrders;
OfferID, OfferTitle, OfferDescription, OrderKey, StartDate, EndDate, DiscountAmount, ApplicableRestaurants, RedemptionCode in MarketingOffers

_Current Query_
SELECT CustomerID, AVG(TotalAmount) AS avg_order_value
FROM CustOrders
WHERE SpecialInstructions LIKE '%allergies%' OR SpecialInstructions LIKE '%dietary restrictions%'
GROUP BY CustomerID;

_Output_
```json
{{
  "thought": "In order to filter for users with allergies or dietary restrictions, we can break the problem down by first adding a boolean column based on special instructions.",
  "source": [ {{"tab": "CustOrders", "col": "SpecialInstructions"}} ],
  "target": [ {{"tab": "CustOrders", "col": "has_allergies_or_restrictions"}} ]
}}
```
---
Now it's your turn! Please generate all considerations within your 'thought', followed by list of source and target columns. There should be no text or explanations after the JSON output.

_Conversation History_
{history}

_Existing Columns_
{columns}

_Current Query_
{query}

_Output_
"""

preference_entity_prompt = """{goal_description}
Given the conversation history and valid columns, please identify which target column is most relevant, along with your confidence.
When deciding your confidence:
  - high: give a high score when the user has explicitly mentioned a column in the utterance and there is a closely matching option in the valid columns
  - medium: give a medium score when the user's utterance implies a certain column that is found within the set of valid columns
  - low: give a low score when you cannot match any of the valid columns to the user's utterance

Start by thinking out loud about which column aligns most closely with the preference, and then declare the table and column, along with your level of confidence.
Your entire response should be in well-formatted JSON including thought (string), target (dict), confidence (string), with no further explanations after the JSON output.
Let's consider some example scenarios, and then tackle the current case.

#############
_Conversation History_
User: Can you show me the top 5 sources of leads from last month?
Agent: Sure, how do you want to determine the top lead sources?
User: The ones that led to the most subcriptions

_Columns_
lead_id, first_name, last_name, email, organization, lead_source, contact_date, status, notes, follow_up_date in mq_leads;
launch_id, is_secure, provenance, version, features, documentation_link in data_sources;
subscription_id, user_id, plan_name, sub_timestamp, billing_cycle, payment_status, renewal_notice in subscriptions;

_Output_
```json
{{
  "thought": "We can count the number of subscriptions associated with each lead source by looking for unique subscription IDs",
  "target": {{"tab": "subscriptions", "col": "susbscription_id"}},
  "confidence": "medium"
}}
```

#############
_Conversation History_
User: Those look fine to me
Agent: No problem, I will ignore those moving forward
User: So what was the best performing channel according to delivery time.

_Columns_
CustomerID, CustName, FavCuisineType, ShippingAddress, ContactNumber, IsActive, Twitter, Instagram, Yelp in CustContact;
OrderID, CustomerID, RestaurantID, OrderDate, TotalAmount, DeliveryAddress, OrderStatus, EstDeliveryTime, SpecialInstructions in CustOrders;
OfferID, OfferTitle, OfferDescription, OrderKey, StartDate, EndDate, DiscountAmount, ApplicableRestaurants, RedemptionCode in MarketingOffers

_Output_
```json
{{
  "thought": "User explicitly mentioned 'delivery time', so we can find the best channels by connecting to that column.",
  "target": {{"tab": "CustOrders", "col": "EstDeliveryTime"}},
  "confidence": "high"
}}
```

#############
_Conversation History_
User: Let's take a look at how sign-ups have been trending lately
Agent: Can you provide more information about how long ago you want to look?
User: The past month is fine

_Columns_
member_id, full_name, email_address, phone_number, date_joined, membership_type, membership_fee, expiration_date, packages_bought, emergency_contact in members;
class_id, class_name, instructor_id, class_date, start_time, end_time, room_number, class_capacity, enrolled_count, description, equipment_required in classes;
package_id, package_name, duration, price, included_classes, additional_benefits in packages

_Output_
```json
{{
  "thought": "Ideally, we would have something like signup_date. Since this doesn't exist, we can look at the date_joined column.",
  "target": {{"tab": "members", "col": "date_joined"}},
  "confidence": "medium"
}}
```

#############
_Conversation History_
User: What was our most popular channel last quarter?
Agent: When you say 'most popular', how do you want to measure that?
User: Most popular channel is the one with most number of visitors

_Columns_
CustomerID, FirstName, LastName, Email, PhoneNumber, DateRegistered, PurchaseHistory, LoyaltyPoints, Address, PreferredBrand in Customers;
CampaignID, CampaignName, StartDate, EndDate, CampaignVisits, Channel, Budget, ResponseRate, CreativeAsset in Campaigns;
ItemID, BrandName, Category, Price, StockQuantity, DateAdded, Supplier in Inventory;
PromoID, PromoName, StartDate, EndDate, DiscountPercentage, ApplicableProducts, PromoCode, RedemptionCount in Promotions

_Output_
```json
{{
  "thought": "When looking for a column that tracks the number of visitors, the column that seems most similar is CampaignVisits.",
  "target": {{"tab": "Campaigns", "col": "CampaignVisits"}},
  "confidence": "high"
}}
```

#############
_Conversation History_
User: What the channel that had the best results.
Agent: The average cost on TikTok came out to $2.31 per click. Is that what you're looking for?
User: Yes, that's the most we should be willing to spend.

_Columns_
BookingID, CustomerID, VehicleID, StartDate, EndDate, PickupLocation, DropoffLocation, BookingStatus, BookingAmount, PaymentStatus in Bookings;
PromotionID, DiscountAmount, ApplicableVehicleTypes, TermsConditions, RedemptionCount in Promotions;
TicketID, CustomerID, IssueDate, IssueType, IssueDescription, AssignedAgent, ResolutionStatus, ResolutionDate, Feedback, FollowUpRequired in CustomerSupport

_Output_
```json
{{
  "thought": "The user is likely looking for the column that tracks the cost per click, but I don't see any similar columns in the options.",
  "target": {{"tab": "Bookings", "col": "BookingAmount"}},
  "confidence": "low"
}}
```

#############
_Conversation History_
User: How many course signups did we have this week?
Agent: When do you want to define as the start of the week?
User: We can go with Sunday

_Columns_
CourseID, CourseTitle, InstructorID, CourseDescription, SignupDate, Duration, CourseFormat, Category, EnrollmentCount in BB_courses;
EnrollmentID, CourseID, StudentID, EnrollmentDate, CompletionStatus, Feedback, CertificateLink, PaymentStatus, ReferralSource in BB_enrollments;
TestimonialID, StudentID, CourseID, TestimonialText, DateProvided, Rating, Featured, ApprovalStatus, PhotoLink in Testimonials;
OutreachID, CampaignName, TargetAudience, Platform, ResponseRate, Collaborators in CanvasOutreach

_Output_
```json
{{
  "thought": "To determine the start of the week, the most likely column to track course signups is SignupDate.",
  "target": {{"tab": "BB_courses", "col": "SignupDate"}},
  "confidence": "medium"
}}
```

#############
_Conversation History_
User: How's the CTR been doing recently after we started the promotion?
Agent: No problem, how far back would you like to look?
User: I'd like to get the last 14 days worth of clicks.

_Columns_
activity_id, user_id, activity_type, timestamp, duration, data_source, outcome, error_log in kafka_activity;
enrollment, package, paid_or_organic, is_member, feedback, amplitude_id, stripe_paid, sent, blocked, marked_spam in email_list_july;
portable, user_id, location, phone, source, destination, duration, type, num_stars, review, parsed_results in airbnb_reviews;

_Output_
```json
{{
  "thought": "In order to get the last 14 days worth of clicks, we need to track both the time and the number of clicks.",
  "target": {{"tab": "kafka_activity", "col": "timestamp"}},
  "confidence": "medium"
}}
```


#############
_Conversation History_
{history}

_Columns_
{valid_cols}

_Output_
"""

type_check_prompt = """Given the conversation history and the table content, please determine the datatype and subtype for each column.
The datatype should be one of the following: unique, datetime, location, number, or text.
Each datatype is further divided into subtypes:
  - unique
    * boolean: True/False values, also includes other binary represenations such as on/off, yes/no, or 1/0
    * status: a state or condition represented by 4 or fewer unique values, such as [beginner, intermediate, advanced]
    * category: a categorical grouping or classification represented by 5 to 16 unique values
    * id: a unique identifier or reference number, often displayed as consecutive integers
  - datetime
    * date: a full date value including exactly a year, month, and day in any order
    * year: a year value alone
    * month: a month value, can be a number from 1 to 12 or the full month name
    * day: a day value ranging from 1 to 31
    * quarter: a quarter value, such as Q1, Q2, Q3, Q4
    * week: day of the week, written numerically, as a shortened string (ie. Mon/Tue/Wed), or a full name (ie. Thursday/Friday)
    * time: a time value including hours and minutes, often includes seconds or AM/PM
    * hour: an hour value ranging from 0 to 23
    * minute: a minute value ranging from 0 to 59
    * second: a second value ranging from 0 to 59
    * timestamp: a full timestamp value including date and time, with optional timezone information
  - location
    * street: a street address or location description
    * city: a city name
    * state: a state or province name
    * country: a country name
    * zip: a postal code or ZIP code
    * address: a full address including street, city, state, country, and zip
  - number
    * currency: a monetary value, often used to represent prices, CPC, ad spend, or profits
    * percent: a percentage value, often includes the % symbol
    * whole: a non-negative integer value used for counting people or events, such as visitors, accounts, clicks, or conversions
    * decimal: a numerical value with a fractional component, often used for measurements or averages
  - text
    * email: an email address
    * phone: a phone number, country code optional
    * url: a web address or hyperlink
    * name: a person's name or title, includes usernames, first names, last names, and full names
    * general: any text that does not fit into the other subtypes, such as descriptions, comments, or notes

Start by thinking about the content of each column and how it is used in the conversation, then assign the appropriate datatype and subtype.
Your final response response should be well-formatted JSON with keys 'thought' (string) and 'columns' (dict of dicts) where each column has a 'datatype' and 'subtype' key.
Do not include any additional text or explanations after the JSON output.

For example,
---
_Conversation History_
User: Can I get that on a monthly basis?
Agent: Sure, here you go
User: And show it on a graph again
Agent: No problem, here is the monthly price for Netflix.
User: Save that for me please

_Table Content_
| month    | high | low  | close_price | monthly_volume |
|----------|------|------|-------------|----------------|
| 09       | 385  | 360  | 375         | 1360000        |
| 10       | 395  | 370  | 386         | 1270000        |
| 11       | 420  | 385  | 410         | 1450000        |
| 12       | 415  | 380  | 395         | 1320000        |
| 01       | 412  | 388  | 400         | 1410000        |
| 02       | 435  | 400  | 422         | 1350000        |
| 03       | 442  | 415  | 430         | 1330000        |
| 04       | 435  | 405  | 414         | 1390000        |

_Output_
```json
{{
  "thought": "Based on the column headers, I can tell that 'month' should be a datetime subtype 'month'. 'high', 'low', and 'close_price' are likely currencies subtypes, while 'monthly_volume' is a whole number because it represents a count.",
  "columns": {{
    "month": {{"datatype": "datetime", "subtype": "month"}},
    "high": {{"datatype": "number", "subtype": "currency"}},
    "low": {{"datatype": "number", "subtype": "currency"}},
    "close_price": {{"datatype": "number", "subtype": "currency"}},
    "monthly_volume": {{"datatype": "number", "subtype": "whole"}}
  }}
}}
```

_Conversation History_
User: Give me the results that show the average leads, CPC, and CTR by source. Focus on just the top 5.
Agent: Sure, how do you want to determine the top lead sources?
User: The ones that led to the highest CTR. Also, filter for the last 30 days.

_Table Content_
| Lead Source  | Avg Lead | Avg CPC | Avg CTR  |
|:-------------|----------|---------|---------:|
| Georgia      | 15.123   | 1.135   | 0.0162   |
| Texas        | 126.88   | 1.074   | 0.0274   |
| Ohio         | 90.130   | 1.567   | 0.0324   |
| Michigan     | 82.613   | 2.098   | 0.0170   |
| Pennsylvania | 72.228   | 1.028   | 0.0191   |

_Output_
```json
{{
  "thought": "I recognize the sources as states in the US. Averages are typically decimal numbers, but cost-per-click actually represents currency, and click-through rate is a percentage.",
  "columns": {{
    "Lead Source": {{"datatype": "location", "subtype": "state"}},
    "Avg Lead": {{"datatype": "number", "subtype": "decimal"}},
    "Avg CPC": {{"datatype": "number", "subtype": "currency"}},
    "Avg CTR": {{"datatype": "number", "subtype": "percent"}}
  }}
}}
```

_Conversation History_
User: What are the most popular brands among the 18-25 age group?
Agent: The most popular brand is KitKat, followed by Snickers and Reese's.
User: When was the earliest date that we started promoting it?
Agent: The earliest promotion date was on July 15th.
User: Can you save this information for me?

_Table Content_
| Brand     | AgeGroup  | AvgRating | StartPromo   |
|-----------|-----------|-----------|--------------|
| KitKat    | 18-25     | 27.52     | 2023-07-15   |
| Snickers  | 18-25     | 21.55     | 2023-07-27   |
| Reese's   | 18-25     | 23.66     | 2023-07-18   |
| M&M's     | 18-25     | 18.74     | 2023-07-20   |
| Twix      | 18-25     | 19.87     | 2023-07-27   |

_Output_
```json
{{
  "thought": "Brand and AgeGroup are both categories, Avg Rating is a decimal number, and StartPromo clearly holds datetime values.",
  "columns": {{
    "Brand": {{"datatype": "unique", "subtype": "category"}},
    "AgeGroup": {{"datatype": "unique", "subtype": "category"}},
    "AvgRating": {{"datatype": "number", "subtype": "decimal"}},
    "StartPromo": {{"datatype": "datetime", "subtype": "date"}}
  }}
}}
```

_Conversation History_
User: What if we grouped it by each user?
Agent: RadioKilledTheVideoStar has the highest ratio of votes to views.
User: So it seems like the longer the stream, the more votes it gets
Agent: Yes, there does seem to be a correlation between stream length and votes.
User: Can I also get their membership status?

_Table Content_
| username                | like_ratio | membership_status |
|:------------------------|------------|-------------------|
| JustDance               | 0.12       | Premium           |
| RadioKilledTheVideoStar | 0.18       | Free              |
| MusicMania              | 0.09       | Premium           |
| GuitarHero69            | 0.15       | Free              |
| B3atMaster              | 0.11       | Premium           |
| DJTurntables            | 0.14       | Free              |
| WatchParty100           | 0.08       | Premium           |

_Output_
```json
{{
  "thought": "The conversation tells me that 'like_ratio' is actually a percentage rather than decimal. Based on the name, 'membership_status' should be a status rather than boolean.",
  "columns": {{
    "username": {{"datatype": "unique", "subtype": "name"}},
    "like_ratio": {{"datatype": "number", "subtype": "percent"}},
    "membership_status": {{"datatype": "unique", "subtype": "status"}}
  }}
}}
```

_Conversation History_
User: Can we standardize all the times in the bookings table?
Agent: Sure, is there a specific form you are looking for?
User: I want just the hour and minute without the seconds.
Agent: No problem, I will update the format. How does this look?
User: And how many complaints have we received for each period?

_Table Content_
| delivery_period | complaint_count |
|:----------------|-----------------|
| 14:30           | 3               |
| 11:45           | 1               |
| 13:00           | 2               |
| 12:00           | 4               |
| 11:30           | 1               |
| 13:45           | 3               |
| 14:15           | 2               |
| 12:15           | 5               |
| 12:30           | 1               |
| 14:45           | 3               |

_Output_
```json
{{
  "thought": "The 'delivery_period' column doesn't contain seconds, but is still a time subtype. 'complaint_count' is a whole number.",
  "columns": {{
    "delivery_period": {{"datatype": "datetime", "subtype": "time"}},
    "complaint_count": {{"datatype": "number", "subtype": "whole"}}
  }}
}}
```

_Conversation History_
User: How many of our customers are female vs. male?
Agent: There are a total of 456 female and 194 male users.
User: How about different ages?
Agent: There are 326 young adults, 214 adults, and 110 senior.
User: Show me a table of total views by age and sex.

_Table Content_
| Gender     | AgeGroup      | TotalImpressions | TotalUsers |
|:-----------|---------------|------------------|------------|
| F          | Young Adults   | 169              | 157        |
| F          | Adults         | 231              | 199        |
| F          | Seniors        | 121              | 100        |
| M          | Young Adults   | 185              | 169        |
| M          | Adults         | 17               | 15         |
| M          | Seniors        | 13               | 10         |

_Output_
```json
{{
  "thought": "The 'Ethnicity' and 'Gender' columns are for grouping and classification. 'TotalImpressions' is a whole number.",
  "columns": {{
    "Ethnicity": {{"datatype": "unique", "subtype": "category"}},
    "Gender": {{"datatype": "unique", "subtype": "category"}}
    "TotalImpressions": {{"datatype": "number", "subtype": "whole"}}
    "TotalUsers": {{"datatype": "number", "subtype": "whole"}}
  }}
}}
```

---
Now it's your turn to assign datatypes to the columns based on the conversation history and table content. 
Your entire reasoning should be in the 'thought' key of the JSON output. Make sure there is no additional text after the JSON.

_Conversation History_
{history}

_Table Content_
{content}

_Output_
"""

divide_and_conquer_prompt = """Given the conversation history, decide if the most recent turn contains multiple requests that can be divided into separate actions.
Requests generally fall into five categories:
1. select - a request to retrieve or analyze specific information, which doesn't change the underlying data
  * query: standard query to retrieve data from a table
  * analyze: calculating a metric or KPI, such as CVR, CPA, CTR or Retention Rate
  * pivot: reorganizing data to show different dimensions or aggregations
  * describe: summary statistics or characteristics of the data
  * exist: checking if a specific column or value exists in the data
2. report - a request to summarize or visualize data
  * plot: creating a chart or graph to visualize data
  * explain: providing context or insights into the data
  * save: storing or exporting data for future reference
  * design: updating the design of a figure or dashboard
  * style: updating the style of a table or column
3. clean - a request to update or modify data entries, often at a row or cell level
  * update: changing existing data values or entries
  * fill: interpolating or replacing missing values
  * validate: ensuring that all values in a column meet certain criteria, such as being part of some predefined set
  * format: adjusting the format or structure of data, such as applying YYYY-MM-DD format to a date column
  * dedupe: removing duplicate entries
4. transform - a request to manipulate or process data, often at a table or column level
  * insert: adding new columns or rows to the data
  * delete: removing columns, rows, or specific entries
  * move: cutting and pasting content, re-arranging column order, or transposing rows and columns
  * split: dividing a column into multiple columns or rows, such as text-to-columns
  * merge: combining data from multiple sources to create a new table or column
5. detect - a request to identify patterns or issues in data
  * concern: finding unusual or unexpected values, such as numeric outliers or textual anomalies
  * blank: looking for nulls, empty strings, or missing data
  * typo: identifying inconsistent or incorrect entries, such as misspellings
  * trend: determining statistical relationships between different columns or variables, such as correlations
  * insight: generic, open-ended request to find insights in the data

In total, there are 25 possible actions that can be taken based on the user's request.
If a clearly distinct action appears, but is not a part of the valid actions listed above, please label it as 'other'.
It is also possible that a single action appears twice in the same utterance, in which case you should include it twice.
If only a single action is present, then list that action alone.

Start by thinking carefully about the user's request and whether it can be broken down into multiple distinct actions. Then list those actions in the order which we should tackle them.
For each action, include the portion of the user's utterance that corresponds to that action. Copy the text verbatim, but feel free to apply minor modifications to make the intent clear.
Your final response should be in well-formatted JSON including keys for 'thought' (string) and 'actions' (list), with no further explanations after the JSON output.

For example,
#############
User: The user activity from Facebook goes back to the beginning of the year, right?
Agent: Yes, the FB_Ads table contains data starting from January 3rd.
User: Please graph the results on a weekly basis if we have any data related to conversions.

_Output_
```json
{{
  "thought": "I should first check whether any data exists regarding conversions, and then attempt to plot it.",
  "actions": [
    ["exist", "check if we have any data related to conversions"],
    ["plot", "Please graph the results on a weekly basis"]
  ]
}}
```

User: How many attendees signed up for the newsletter at the conference?
Agent: The NovaMaxConference table contains 547 rows. Does that answer your question?
User: Can we remove all the people without an email and also any attendees who signed up twice?

_Output_
```json
{{
  "thought": "The user wants to remove two separate pieces of information: attendees without an email and attendees who are duplicated.",
  "actions": [
    ["delete", "Can we remove all the people without an email"],
    ["dedupe", "also remove any attendees who signed up twice"]
  ]
}}
```

User: How many IT tickets did we receive in the last month?
Agent: We had a total of 412 IT tickets raised in the month of June.
User: How many tickets were left unresolved each day? I want to get a sense if this is affecting our churn rate.

_Output_
```json
{{
  "thought": "I can first filter for unresolved tickets grouped by day, and then calculate the churn rate.",
  "actions": [
    ["query", "How many tickets were left unresolved each day?"],
    ["analyze", "I want to get a sense if this is affecting our churn rate."]
  ]
}}
```

User: Let's just assume the missing months refer to February.
Agent: Ok, I have filled in the missing values to be February. How does that look?
User: Now join the month, day and year columns together as the final shipping date. I want it displayed as MM/DD/YYYY.

_Output_
```json
{{
  "thought": "I can divide the utterance into two separate actions: a merge action to join the columns and a format action to format the date.",
  "actions": [
    ["merge", "Now join the month, day and year columns together as the final shipping date."],
    ["format", "I want it displayed as MM/DD/YYYY."]
  ]
}}
```

User: Do you see how the campaign name is the ad group, ad set, and ad ID?
Agent: Yes, the campaigns seem to contain three parts separated by underscores.
User: I want to split up the campaign name into three columns, then calculate the total spend grouped by ad set, sorted from highest to lowest.

_Output_
```json
{{
  "thought": "The user wants to run text-to-columns on the campaign column, and then run a query based on newly created ad set column.",
  "actions": [
    ["split", "I want to split up the campaign name into three columns"],
    ["query", "calculate the total spend grouped by ad set, sorted from highest to lowest"]
  ]
}}
```

User: Can you tell me which users have overdue fees?
Agent: Apologies, but I'm not sure which column tracks the fee status. Can you please clarify?
User: Create a 'bill_status' column, where if the 'payment_date' is empty, and the 'due_date' is in the future, then the status is pending. If the 'due_date' is before today, then status is overdue, and if the 'payment_date' is filled, then status is paid.

_Output_
```json
{{
  "thought": "The request is quite long due to the logic, but ultimately boils down to inserting a single new column.",
  "actions": [
    ["insert", "Create a 'bill_status' column, where if the 'payment_date' is empty, and the 'due_date' is in the future, then the status is pending. If the 'due_date' is before today, then status is overdue, and if the 'payment_date' is filled, then status is paid."]
  ]
}}
```

User: Ok, we need to clean this up!
Agent: Certainly, I can help with that. I have found help resolve spelling errors, identify outliers, or deal with missing values. What would you like me to focus on?
User: Please look for any typos with the vendors and fix any you find by making sure that it is either Fidelity, Vanguard, Charles Schwab, or TD Ameritrade.

_Output_
```json
{{
  "thought": "I can divide the utterance into two separate actions. First, I should check for typos. Next, since the suggested fix is to limit to a pre-defined set of values, this is 'validate' action rather than a more general 'update' action.",
  "actions": [
    ["typo", "Please look for any typos with the vendors and fix any you find"],
    ["validate", "Fix typos by making sure that it is either Fidelity, Vanguard, Charles Schwab, or TD Ameritrade.]"
  ]
}}
```
#############
Now it's your turn to break down the user's request into actions. Remember to only choose from the valid actions listed above.

_Conversation History_
{history}

_Output_
"""