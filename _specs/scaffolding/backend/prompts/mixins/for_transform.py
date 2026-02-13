# ------------------------------------------------------------------
# TRIMMED FOR SPEC BREVITY
# Original file: 5,243 lines with 28 prompt templates.
# Kept 3 representative prompts below (insert_prompt, delete_prompt, text2cols_prompt).
# Removed 25 prompts: merge_categories, merge_methods_prompt, merge_cols_prompt,
#   checkbox_opt_prompt, custom_code_prompt, columns_for_joining_prompt,
#   align_columns_prompt, join_tables_prompt, tab_col_move_prompt,
#   row_cell_move_prompt, ner_tag_prompt, prepare_join_by_date_prompt,
#   prepare_join_by_loc_prompt, prepare_join_by_org_prompt,
#   prepare_join_by_per_prompt, basic_preparation_prompt, split_style_prompt,
#   transpose_prompt, transform_issues_prompt, append_alignment_prompt,
#   append_target_prompt, append_rows_prompt, merge_target_prompt,
#   name_staging_col_prompt, complete_append_prompt, insert_staging_prompt
# ------------------------------------------------------------------

insert_prompt = """Given the conversation history and supporting details, follow the thought process to insert or add data using Pandas code.
Supporting details include the name of the column(s) to add, as well as possible operations for populating the values within the column.
For the final example, you will also be given the first few rows of the table to help you understand the data.
The existing dataframes you have are {df_tables}.

Focus on writing directly executable Python, which may contain comments to help with reasoning. If a request requires multiple steps, write each step on a new line.
When possible to do so easily, perform the operation in place rather than assigning to a dataframe.
When calculating a percentage, DO NOT multiply by 100. When performing any division operation, always return the result with at least 4 decimal places of precision.
Your final response should only contain well-formatted Python code, without any additional text or explanations after the output.

For example,
---
User: Create a formula that is True if the ad spend is greater than $1000 and False otherwise.
* Current columns: ad_spend in orders
* New columns: expensive in orders
* Operations: filter ad spend > 1000
* Thought: I can check if the ad spend is greater than $1000 by using a comparison operator.  I will then create a new column with a short descriptive name, such as 'expensive'.

_Output_
```python
db.orders['expensive'] = db.orders['ad_spend'] > 1000
```

User: We can make a new column for that
* Current columns: Europe, Americas, TotalAmount, ExchangeRate in InternationalSales
* New columns: AsiaPacific in InternationalSales
* Operations: none
* Thought: I should add a new column to hold the total sales in the Asia Pacific region.

_Output_
```python
db.InternationalSales['AsiaPacific'] = ''
```

User: Actually, can you add a column showing the change every month from last year to this year?
* Current columns: channel_id, mq_leads, and month in Qualified Leads; channel_id and channel_name in Channels with Spend
* New columns: monthly_mql_change in Qualified Leads
* Operations: filter for channel is newsletter, group by month, compare all months in the past year
* Thought: The new column will track the change in MQLs on a month-to-month basis. The values will be calculated using the formula (current month - previous month) / previous month.

_Output_
```python
db['Qualified Leads']['monthly_mql_change'] = db['Qualified Leads'].groupby('month')['mq_leads'].pct_change()
```

User: Add a column that applies the tax rate to the item_price.
* Current columns: tax_rate and item_price in purchases
* New columns: total_price in purchases
* Operations: apply tax rate to item price
* Thought: I can apply the tax rate by multiplying the price with 1 + rate.  I will then create a new column with a short descriptive name, such as 'total_price'.

_Output_
```python
db.purchases['total_price'] = db.purchases['item_price'] * (1 + db.purchases['tax_rate'])
```

User: OK, so let's mark customers with more than 1000 points and 10 purchases as high value, 500 points and 5 purchases as medium value, and everyone else as low.
* Current columns: CustomerID, FirstName, LastName, LoyaltyPoints in Customers; PurchaseID in Purchases
* New columns: CustomerValue in customers
* Operations: filter loyalty points > 1000; filter loyalty points > 500; filter purchases > 10; filter purchases > 5; group by customer
* Thought: The new column will assign customer status as either high, medium or low value. This is determined by a combination of loyalty points and purchase amount.

_Output_
```python
# calculate the number of purchases for each customer
purchase_counts = db.purchases['CustomerID'].value_counts().rename('PurchaseCount')
db.customers = db.customers.merge(purchase_counts, left_on='CustomerID', right_index=True, how='left')
db.customers['PurchaseCount'].fillna(0, inplace=True)

# assign customer value based on conditions
conditions = [
    (db.customers['LoyaltyPoints'] > 1000) & (db.customers['PurchaseCount'] >= 10),
    (db.customers['LoyaltyPoints'] > 500) & (db.customers['PurchaseCount'] >= 5)
]
choices = ['high', 'medium']
db.customers['CustomerValue'] = np.select(conditions, choices, default='low')
```

User: What if I want to know how long someone has been a member with us at Sixby Fitness
* Current columns: MemberID, FirstName, LastName, EndDate, StartDate in Members
* New columns: MemberDuration in AttendanceReport
* Operations: filter for EndDate is null
* Thought: The new column will calculate the duration of membership. The values can be calculated using the formula Present Date - StartDate.

_Output_
```python
db.AttendanceReport['MemberDuration'] = (pd.to_datetime('today') - db.Members['StartDate']).dt.days
```
---
Now it's your turn! Please output executable Python code with inline comments to insert the columns(s) as requested.

User: {utterance}
* Current columns: {source_cols}
* New columns: {target_cols}
* Operations: {operations}
* Thought: {thought}

For additional context, here are the first few rows of the table:
{example_rows}

_Output_
"""

delete_prompt = """Given the conversation history and supporting details, follow the thought process to delete or drop data using Pandas code.
Supporting details includes the location of the data to remove. You can access dataframes as 'db' followed by a table name: `db.table_name`.
Concretely, you have {df_tables}.

Please write directly executable Python, which may contain comments to help with reasoning. If a request requires multiple steps, write each step on a new line.
When possible to do so easily, perform the operation in place rather than assigning to a dataframe.
When comparing dates, make sure to use `.date()` rather than relying on `to_datetime` alone, since the latter makes implicit conversions that behave unexpectedly.
Only focus on the request in the final user turn. You should ignore any requests in previous turns since they have already been addressed.
Your final response should only contain well-formatted Python code, without any additional text or explanations after the output.

For example,
---
User: Can you delete all rows that have empty values?
* Tables: purchases
* Columns: * in purchases

Thought: I should look for all rows within the purchases table and drop those that have empty values.

_Output_
```python
# drop rows with null values
db.purchases.dropna(inplace=True)
```

User: Please remove all users without a valid phone number.
Agent: You got it, I have removed 152 rows from the users table.
User: Great, now remove everyone without a last name.
* Tables: customers
* Columns: first, last in customers

Thought: I should look in the customers table for rows where the last name is null and remove them.

_Output_
```python
# drop rows with null last names
db.customers.dropna(subset=['last'], inplace=True)
```

User: Delete all columns containing 'deprecated'.
* Tables: EmailCampaigns
* Columns: mulitple columns in EmailCampaigns

Thought: I should look in all tables for columns containing 'deprecated' and remove them using the drop method.

_Output_
```python
# find all columns containing 'deprecated' and drop them
to_be_dropped = [col for col in db.EmailCampaigns.columns if 'deprecated' in col]
db.EmailCampaigns.drop(columns=to_be_dropped, inplace=True)
```

User: Please show me a graph of the clicks for each day this month.
Agent: No problem, here you go.
User: Shoot, we're double counting. Can you get rid of all events recorded after the pixel was installed on 8/23/2024?
* Tables: activities
* Columns: EventTimestamp in activities

Thought: I should look in the activities table for rows where the EventTimestamp is after 8/23/2024 and remove them.

_Output_
```python
# make sure to use .date() so we are comparing dates rather than timestamps
cutoff_date = pd.to_datetime('2024-08-23').date()
db.activities = db.activities[db.activities['EventTimestamp'].dt.date <= cutoff_date]
```

User: Yes, remove the customer with id 15900276 from both tables.
* Tables: customers; orders
* Columns: customer_id from customers; customer_id from orders

Thought: I will first find and remove the customer with id 15900276 from the customers table. Then, I will do the same on the orders table.

_Output_
```python
# remove customer with id 15900276 from both tables
db.customers = db.customers[db.customers['customer_id'] != 15900276]
db.orders = db.orders[db.orders['customer_id'] != 15900276]
```

User: Can you drop all states that are blank or null?
* Tables: customers
* Columns: state in customers

Thought: I can remove blank states by searching for an empty string. Then, I will remove states with null using the dropna method.

_Output_
```python
# search for empty states
db.customers = db.customers[db.customers['state'] != '']
# drop rows with null states
db.customers.dropna(subset=['state'], inplace=True)
```

User: Erase all rows where the year is before 2019 and the revenue is negative.
* Tables: orders
* Columns: year, price in orders

Thought: The orders table has a year and price column, which be used for revenue calculations.  I can filter for before 2019 and negative price, and then remove them.

_Output_
```python
# Eliminate unwanted rows by keeping the reverse of the condition
db.orders = db.orders[(db.orders['year'] >= 2019) & (db.orders['price'] >= 0)]
```
---
Now it's your turn! Please generate executable Python with inline comments to guide your thinking followed by code to delete the data as requested.

{history}
{location}

Thought: {thought}

_Output_
"""

text2cols_prompt = """Given the conversation history and supporting details, think briefly about the best way to split a single column into multiple columns, and then generate the Pandas code for doing so.
Supporting details includes the head of the source column and the resulting target columns. Sometimes, the target columns may be unknown, in which case you should use your best judgement to name them.

You are given access to the source dataframe in form of `db.{tab_name}`, which means you can access the columns directly.
Please only output executable Python code and inline comments. If a request requires multiple steps, write each step on a new line.
It is absolutely critical that there are no explanations after the code.

For example,
---
_Conversation History_
User: Are there any patterns if we look at it on a monthly basis?
Agent: Should I look for patterns based on the submission_date or the delivery_date?
User: Go with the delivery date

_Supporting Details_
|    | delivery_date  |
|---:|:---------------|
|  0 |  02/03/23      |
|  1 |  02/18/23      |
|  2 |  03/13/23      |
|  3 |  09/15/23      |
|  4 |  10/27/23      |
Target: ['month', 'day', 'year']
Delimiter: '/' (slash)

_Output_
```python
# try to extract the date directly
try:
  db.Deliveries['delivery_date'] = pd.to_datetime(db.Deliveries['delivery_date'], format='%m/%d/%y')
  db.Deliveries['month'] = db.Deliveries['delivery_date'].dt.month
  db.Deliveries['day'] = db.Deliveries['delivery_date'].dt.day
  db.Deliveries['year'] = db.Deliveries['delivery_date'].dt.year

# otherwise, split the date by slash delimiter
except AttributeError:
  db.Deliveries[['month', 'day', 'year']] = db.Deliveries['delivery_date'].str.split('/', expand=True)
  db.Deliveries['month'] = db.Deliveries['month'].astype(int)
  db.Deliveries['day'] = db.Deliveries['day'].astype(int)
  db.Deliveries['year'] = db.Deliveries['year'].astype(int)
```

_Conversation History_
User: Yea, those seem fine to me
Agent: No problem, I'll ignore those for now
User: Can you divide up the attributes for each lead into their own columns?

_Supporting Details_
|    | lead_attributes                            |
|---:|:-------------------------------------------|
|  0 |  filled form & contacted & high net worth  |
|  1 |  return visitor & downloaded brochure      |
|  2 |  referral                                  |
|  3 |  filled form & return visitor              |
|  4 |  high net worth & referral                 |
Target: <unknown>
Delimiter: '&' (ampersand)

_Output_
```python
# Split by ampersand and strip nulls to identify unique attributes
split_attributes = db.mql_reviewed['lead_attributes'].fillna('').str.split('&').apply(lambda x: [item.strip() for item in x if item])
unique_attributes = split_attributes.explode().replace('', pd.NA).dropna().unique()

# Create binary columns for each unique attribute
for attr in unique_attributes:
  target_col_name = f"{{attr}}_attr"
  db.mql_reviewed[target_col_name] = split_attributes.apply(lambda row: attr in row)

# the original column is not useful anymore, so we can remove it
db.mql_reviewed.drop('lead_attributes', axis=1, inplace=True)
```

_Conversation History_
User: Which city had the highest number of signups?
Agent: There isn't a city column, but I can create one by splitting the location column. How does that sound?
User: That works for me

_Supporting Details_
|    | location         |
|---:|:-----------------|
|  0 |  Los Angeles,CA  |
|  1 |  New York, NY    |
|  2 |  Chicago,IL      |
|  3 |  Miami, FL       |
|  4 |  Seattle, WA     |
Target: <unknown>
Delimiter: ',' (comma)

_Output_
```python
# split the location column by comma, but with a regex to account for any spaces
db.february_signups[['city', 'state']] = db.february_signups['location'].str.split(r',\\s*', expand=True)
# unlike a date object, searching by location is better off querying the city or state directly, so we can remove the original column
db.february_signups.drop('location', axis=1, inplace=True)
```
---
Now it's your turn! When we are simply running text-to-columns, we can simply split the column by a delimiter.
However, if we are creating binary columns (and targets are not given), then remember to first capture all unique values in the source column to determine the new target columns.
Also, when determining the unique values we should avoid null values whenever possible.

_Conversation History_
{history}

_Supporting Details_
{source_markdown}
Target: {target_cols}
Delimiter: {delimiter}

_Output_
"""
