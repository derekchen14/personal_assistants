# ------------------------------------------------------------------
# TRIMMED FOR SPEC BREVITY
# Original file: 5,353 lines with 28 prompt templates.
# Kept 3 representative prompts below (update_prompt, update_routing_prompt, clean_issues_prompt).
# Removed 25 prompts: row_styles_prompt, validate_routing_prompt,
#   datatype_routing_prompt, format_routing_prompt, pattern_routing_prompt,
#   datetime_alignment_prompt, textual_alignment_prompt, first_batch_sentinel_msg,
#   second_batch_sentinel_msg, reformat_textual_prompt, reformat_datetime_prompt,
#   conflict_resolution_prompt, validate_prompt, validation_grouping_prompt,
#   backup_validation_prompt, datetime_format_prompt, textual_format_prompt,
#   find_pattern_prompt, pattern_code_prompt, change_datatype_prompt,
#   subtype_prompt, imputation_filtering_prompt, imputation_method_prompt,
#   impute_source_prompt, impute_function_prompt, pick_source_col_prompt,
#   impute_mapping_prompt, impute_routing_prompt, undo_prompt, persist_prompt
# ------------------------------------------------------------------

update_prompt = """Given the conversation history and supporting details, follow the thought process to generate Pandas code for updating the data.
Supporting details includes information on the columns of the table being changed with a likely datatype written in parentheses.
If an entire table is being changed, then the location will be written as 'all' instead, designating all columns in the table.
Examples of changes include renaming content, modifying values, or filling rows with new content based on other columns.

You can access dataframes as 'db' followed by a table name: `db.table_name`
Concretely, the dataframes you have are {df_tables}.

When possible to do so easily, perform the operation in place rather than assigning to a dataframe.
If multiple requests are presented in the conversation, only pay attention to instructions found in the most recent user turn.
Please only output executable Python, so any explanations must be written as comments. If a request requires multiple steps, write each step on a new line.

For example,
---
_Conversation History_
User: Can you capitalize all the columns in activity_log?
Agent: Sure, I can do that for you. How does this look?
User: That looks good, please do the same for the purchases table.

_Supporting Details_
Location: all columns in purchases
Thought: We have a purchases table which has columns that can be capitalized using title()
Explanation: Note, we should *NOT* make any changes to activity_log table since the final user turn is only concerned with purchases.

_Output_
```python
db.purchases.columns = [col.title() for col in db.purchases.columns]
```

_Conversation History_
User: Create a formula that is True if the price is greater than $1000 and False otherwise.

_Supporting Details_
Location: price (currency) column in orders
Thought: I can check if the price is greater than $1000 by using a comparison operator.  I will then create a new column with a short descriptive name, such as 'expensive'.

_Output_
```python
db.orders['expensive'] = db.orders['price'] > 1000
```

_Conversation History_
User: Simplify the table name from jpm_conference_lead_downloads_0108202 to just jpm_leads

_Supporting Details_
Location: all columns in jpm_conference_lead_downloads_0108202
Thought: We are changing the name of the table rather than just changing the column names.

_Output_
```python
db.jpm_leads = db.jpm_conference_lead_downloads_0108202
del db.jpm_conference_lead_downloads_0108202
```

_Conversation History_
User: Got it, please change them into first_name and last_name

_Supporting Details_
Location: first (name), last (name) columns in users
Thought: The user is updating columns from the previous turn, so I should carry over the tables and columns.

_Output_
```python
db.users.rename(columns={{'first': 'first_name', 'last': 'last_name'}}, inplace=True)
```

_Conversation History_
User: Can you drop the year from the column?

_Supporting Details_
Location: sales_by_state_in_2022 (currency) column in orders
Thought: The user is referring to the previous request, so the column likely refers to sales_by_state_in_2022. I can perform this operation by renaming the column in place.

_Output_
```python
db.orders.rename(columns={{'sales_by_state_in_2022': 'sales_by_state'}}, inplace=True)
```

_Conversation History_
User: What is the price of the most expensive shoe sold?
Agent: The most expensive shoe was New Balance - Men's Arrow with a price of $6112
User: That doesn't look right! We should reduce it by 100

_Supporting Details_
Location: product_id (id), product_name (general), product_type (category), retail_value (currency) in ProductAnalytics
Thought: The price of New Balance - Men's Arrow should be divided by 100.

_Output_
```python
db.productanalytics.loc[(db.productanalytics['product_type'] == 'shoe') & (db.productanalytics['product_name'] == 'New Balance - Men\\'s Arrow'), 'retail_value'] /= 100
```

_Conversation History_
User: Let's break that down into three new columns for month, day and year

_Supporting Details_
Location: date_due (date) column in orders
Thought: I can break the date_due column into three new columns by searching for the appropriate separator and then using the split method.
    I will also need to convert the values into integers so we can query them.

_Output_
```python
for separator in ['/', '-', '.', ' ']:
  if db.orders['date_due'].str.contains(separator).any():
    db.orders[['month', 'day', 'year']] = db.orders['date_due'].str.split(separator, expand=True)
    break
db.orders[['month', 'day', 'year']] = db.orders[['month', 'day', 'year']].astype(int)
```

_Conversation History_
User: Can you change the date of all arrivals in November back by one day?

_Supporting Details_
Location: shipment_id (id), arrival_time (timestamp) in inventory
Thought: The user is updating a row from the previous query, which I can do by first finding the shipment in November and then subtracting one day from the arrival_time.

_Output_
```python
db.inventory.loc[db.inventory['arrival_time'].dt.month == 11, 'arrival_time'] -= pd.DateOffset(days=1)
```

_Conversation History_
User: Are there any other problems in the data?
Agent: It seems that Stopify is also a typo.
User: Yes, that's a good find.

_Supporting Details_
Locations: OnlineVendors (general), ActiveVendors (general) in Partnerships
Thought: I should update both OnlineVendors and ActiveVendors columns by replacing all instances of 'Stopify' with 'Shopify'

_Output_
```python
db.Partnerships['OnlineVendors'].replace(to_replace='Stopify', value='Shopify', inplace=True)
db.Partnerships['ActiveVendors'].replace(to_replace='Stopify', value='Shopify', inplace=True)
```

_Conversation History_
User: Can you drop all cities that are blank or nans?

_Supporting Details_
Location: cities (city) column in customers
Thought: I can remove blank cities by searching for an empty string. Then, I will remove cities with nans using the dropna method.

_Output_
```python
db.customers = db.customers[db.customers['city'] != '']
db.customers = db.customers.dropna(subset=['city'])
```

_Conversation History_
User: The accounts payable deadline has changed and is no longer June.
Agent: What should the new deadline be?
User: Can you update this to September instead?

_Supporting Details_
Location: AccountsPayable (boolean), DueDate (date) column in orderagreements
Thought: I should update the formula in AccountsPayable column to use DueDate > September 1st, instead of June 1st.

_Output_
```python
db.orderagreements['AccountsPayable'] = db.orderagreements['DueDate'] > pd.Timestamp('2023-09-01')
```
---
Now it's your turn! Please generate well-formatted Python code for updating the data.

_Conversation History_
{history}

_Supporting Details_
Location: {location}
Thought: {thought}

_Output_
"""

update_routing_prompt = """The user is trying to update the data within the table, and we need to decide if this change can be assigned to a more granular form.
Given the conversation history, your task is to determine the scope of the cleaning presented in the user's request.
For our purposes, the valid scopes are:
  * impute: filling in missing values based on some pattern or formula, including interpolation
  * pattern: flash filling a column based on some pattern where each row is dependent on the previous row above it
  * format: adjusting the format or structure of data, such as applying YYYY-MM-DD format to a date column
  * validate: ensuring every row in the column belongs to some predefined set of values (such as accounts being active/inactive) or fall within some predefined range
  * typo: correcting spelling errors, or merging similar terms that mean the same thing
  * concern: removing or correcting numeric outliers or textual anomalies in the data
  * problem: resolving mixed data types or unsupported data structures
  * update: changing existing cells, such as trimming whitespace, or find and replace operations. This is a catch-all when none of the other options apply.

So far, our thought process has been: {thought}

Start by constructing a concise thought concerning what type of update the user is asking for. Then, predict the most likely scope, choosing only from the eight valid options.
Your entire response should be in well-formatted JSON with keys for a thought (string) and scope (string), with no further explanations after the JSON output.

For example,
---
_Conversation History_
User: yes, that looks good.
Agent: Great, I have created the JointAttribution column.
User: Fill in the missing attribution methods using the last known value from above it

_Output_
```json
{{
  "thought": "Filling in missing values is a 'pattern' operation.",
  "scope": "pattern"
}}
```

_Conversation History_
User: What's in the sing-ups table?
Agent: The Sign-Ups table includes user_id, name, signup_date, email, is_verified, is_active, role, preferences, profile_image, social_id
User: Can we make sure that all signup dates use the abbreviated month name?

_Output_
```json
{{
  "thought": "The user wants to standardize the month format",
  "scope": "format"
}}
```

_Conversation History_
User: Can you help me fill in the missing values in the 'Customer Lifetime Value' column?
Agent: Certainly! How would you like to approach this? We could use an average, median, or perhaps a more sophisticated method.
User: Let's use the average of the existing values.

_Output_
```json
{{
  "thought": "The user wants to fill in missing values in the 'Customer Lifetime Value' column using the average of existing values. This is a clear case of imputation.",
  "scope": "impute"
}}
```

_Conversation History_
User: We need to make sure all the values in the 'Customer Status' column are clean.
Agent: Certainly! How did you want to handle the values?
User: They should only be 'Active', 'Inactive', or 'Pending'. Anything else needs to be corrected.

_Output_
```json
{{
  "thought": "The user wants to ensure all values belong to a predefined set of valid statuses, so this is data validation.",
  "scope": "validate"
}}
```

_Conversation History_
User: Which anti-virus software packages have the highest CTR.
Agent: The Norton AntiVrus, Nortion Antivirus, and MacAfee Antivirus have the highest CTRs. See table for more details.
User: We need to only keep one version of each brand

_Output_
```json
{{
  "thought": "The user wants to merge similar terms, so this is a typo.",
  "scope": "typo"
}}
```

_Conversation History_
User: Oh man, we need to make some more money! What's the total conversion count for our metal tear solid page.
Agent: The Metal Tear Solid landing page has led to 936 conversions in the past month. There are some anomalies in the landing page copy which may be affecting the conversion rate.
User: How is that possible?

_Output_
```json
{{
  "thought": "Anomalies in the landing page copy are a type of concern, so this is a 'concern'.",
  "scope": "concern"
}}
```

_Conversation History_
User: What time periods did the most users visit that page?
Agent: Most users visited the page from 112355 to 113401.
User: These dates seem to be out of whack, can you check?

_Output_
```json
{{
  "thought": "The time periods seem to be stored as integers rather than dates, so this is a 'problem'.",
  "scope": "problem"
}}
```

_Conversation History_
User: I need to standardize the categories in the 'Product Category' column.
Agent: Sure, what kind of cleaning did you have in mind?
User: I want to change all instances of 'Electronics' to 'Electrical' and 'Clothing' to 'Apparel'.

_Output_
```json
{{
  "thought": "Standardizing values in the 'Product Category' column is akin to a find and replace operation, which involves updating existing values.",
  "scope": "typo"
}}
```

_Conversation History_
User: Can I take a look at the activities table?
Agent: Absolutely, here you go.
User: There should be no spaces in the columns, let's change them to underscores.

_Output_
```json
{{
  "thought": "Replacing spaces with underscores is a find and replace operation, which falls under 'update'.",
  "scope": "update"
}}
```
---
Now it's your turn! Given the conversation history, please decide on the scope of the cleaning presented in the user's request.
Remember that the valid scope are: impute, pattern, format, validate, typo, concern, problem, or update.
For additional context, a preview of the data is provided:
{data_preview}

_Conversation History_
{history}

_Output_
"""

clean_issues_prompt = """Given the conversation history and a preview of the data, generate pandas code for updating the data to comply with the user's request.
{df_description}
For simplicity, the data displayed only focuses on relevant subset of data contained within the full `main_df` dataframe.
If you see 'None', 'NaN', or equivalent in the table, these are strings representing a missing value. In contrast, if you see '<N/A>', this refers to a true Pandas null value.
Any changes you make will be applied to the entire dataframe, not just the rows shown:
  * if your changes should be conditional, make sure to filter for the appropriate rows first
  * the rows with issues are indexed and typically at the end of the data preview, which can be useful for filtering
  * pay extra attention to certain operations (ie. adding, dividing, or multiplying) since they are likely applicable only to rows with issues, so filtering becomes doubly important

Please start by constructing a concise thought before writing any code to make sure we address the user's intent.
If multiple updates are requested in the conversation, focus on the most recent user turn only. Prior instructions have already been addressed.
When performing mathematical operations, pay special attention to the syntax since `main_df` is a Pandas dataframe. For example, replace `^` with `**` for exponents.
Your entire response should include a thought and then the executable Python code (starting from ```python), with no further explanations after the code block.

For example,
---
_Conversation History_
Agent: There were 5 blank values in the SatisfactionScore column.
User: OK, fill in the blanks with the average of the other scores.

_Data Preview_
|    | SatisfactionScore  |
|---:|:-------------------|
|  0 | 4.5                |
|  1 | 3.8                |
|  2 | 4.2                |
|  3 | 3.9                |
|  4 | 4.7                |
|  5 | 3.6                |
|  6 | 4.1                |
|  7 | 4.4                |
|  8 | <N/A>              |
|  9 | <N/A>              |

_Output_
```python
# Since I need to grab the global average, so I will first calculate the average
average_score = main_df['SatisfactionScore'].mean()
# Then fill in the null values afterwards
main_df['SatisfactionScore'].fillna(average_score, inplace=True)
```

_Conversation History_
Agent: The date issues include , , and 12:0. See the table for more details.
User: Bleh, this is sort of messy. Let's change 12:0 to 12:00:00 and delete the blank rows.

_Data Preview_
|     |  OrderTime  |
|----:|:------------|
|  0  | 08:30:15    |
|  1  | 11:45:22    |
|  2  | 14:20:08    |
|  3  | 09:15:33    |
|  4  | 16:50:45    |
|  5  | 13:25:17    |
|  6  | 10:35:28    |
|  7  | 15:10:52    |
|  8  | 12:05:39    |
| 156 |             |
| 158 |             |
| 289 |  12:0       |

_Output_
```python
# Replace the broken time format
main_df['OrderTime'] = main_df['OrderTime'].replace('12:0', '12:00:00')
# Then separately remove the blank rows
main_df = main_df[main_df['OrderTime'] != '']
```
---
Remember, we are only concerned with updating the data based on the final user turn. All prior utterances in the conversation only serve to provide context.
Now, please generate a thought and then write the pandas code to clean the data, with no additional text after the code block.

_Conversation History_
{convo_history}

_Data Preview_
{issues}

_Output_
"""
