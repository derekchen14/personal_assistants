# =============================================================================
# Grounding prompts for the "detect" flow category.
# Trimmed to 3 representative templates out of 9 total.
# Removed templates: connect_flow_prompt, resolve_flow_prompt,
#   swebench_prompt, insight_flow_prompt, typos_prompt, problems_prompt
# These followed the same few-shot pattern with scenario-based examples
# and a final "Current Scenario" block with {valid_tab_col}, {history},
# {columns}, {curr_tab}, {status}, {row_desc}, and/or {current} placeholders.
# =============================================================================

identify_issues_prompt = """Given the set of valid columns and the user history, decide which table and columns (if any) are being referenced.
Start by constructing a concise thought concerning what issue the user is trying to resolve. Possible issues include:
  * problems - mixed data types and non-standard formatting which will break a SQL query, such as mixing MM/YY with MM/DD/YYYY
  * concerns - textual anomalies and numeric outliers, these won't break a query, but may need to be addressed
  * typos - misspellings and inconsistent naming conventions, possibly caused by similar terms or abbreviations
  * blanks - empty cells or null values that need to be handled, especially in calculations

Next, choose what table might be relevant, and then what columns are being referenced from that table.
If no specific columns are mentioned, but data __is__ being requested from a table, return '*' to represent all columns.
Note the current table is '{curr_tab}'. When multiple tables are appropriate, just return the {curr_tab} table as your response.
Conversely, if no tables seem appropriate, using the current table is once again a safe default.
Most importantly, only choose from the set of valid columns. This is very important to my career, pay attention to casing and please do NOT return any invalid columns.

Your entire response should be in well-formatted JSON including keys for thought (string), table (string) and columns (list), with no further explanations after the JSON output.
We will go through three sample spreadsheets with a couple of examples each, and then tackle the final real scenario.

## Mobile-First Car Rental Scenario
For our first sample spreadsheet, suppose the valid options are:
* Tables: Bookings; Promotions; CustomerSupport
* Columns: BookingID, CustomerID, VehicleID, StartDate, EndDate, PickupLocation, DropoffLocation, BookingStatus, TotalAmount, PaymentStatus in Bookings;
PromotionID, DiscountAmount, ApplicableVehicleTypes, TermsConditions, RedemptionCount in Promotions;
TicketID, CustomerID, IssueDate, IssueType, IssueDescription, AssignedAgent, ResolutionStatus, ResolutionDate, Feedback, FollowUpRequired in CustomerSupport

Agent: I found 3 outliers in the DiscountAmount column. Would you like to investigate?
Agent: The average discount amount was $34. See table for more details.
User: Sure, what are the values?

_Output_
```json
{{
  "thought": "The user is concerned about outliers in the DiscountAmount column in the Promotions table.",
  "table": "Promotions",
  "columns": ["DiscountAmount"]
}}
```

User: Are there any typos to watch out for in our bookings data?

_Output_
```json
{{
  "thought": "The user wants to check for typos in the bookings data.",
  "table": "Bookings",
  "columns": ["*"]
}}
```

## Luxury Online Retailer Scenario
For our second sample spreadsheet, suppose the valid options are:
* Tables: customers; campaigns; inventory; promotions
* Columns: CustomerID, FirstName, LastName, Email, PhoneNumber, DateRegistered, PurchaseHistory, LoyaltyPoints, Address, PreferredBrand in customers;
CampaignID, CampaignName, StartDate, EndDate, TargetAudience, Channel, Budget, ResponseRate, CreativeAsset in campaigns;
ItemID, BrandName, Category, Price, StockQuantity, DateAdded, Supplier in inventory;
PromoID, PromoName, StartTime, EndTime, DiscountPercentage, ApplicableProducts, PromoCode, RedemptionCount in promotions

User: Are there any misspelled brand names?
Agent: I found 5 groups of similar terms: [Versache, Versace, Versaci], [Givenchy, Givenchi, Givenche, Givency], [Dolce and Gabbanna, Dolce & Gabbana, Dolce & Gabanna]. See table for more.
User: Yes, let's merge those into one term each.

_Output_
```json
{{
  "thought": "The user wants to resolve typos in the BrandName column in the inventory table.",
  "table": "inventory",
  "columns": ["BrandName"]
}}
```

## Real Scenario
For our current case, recall that the valid set of tables and columns are:
{columns}

{history}

_Output_
"""

blanks_prompt = """Given the conversation history, your task is to determine which blank rows the user is referencing in the data.
To help in this task, you will also be shown some supporting data from relevant columns, along with the blank issues in the format of `blank_type: value1, value2, value3, ... valueN`
The set of possible blank types are:
  * missing - tokens that represent empty or missing data, such as 'not available', 'NaN', 'NULL', or 'unknown'
  * default - tokens used as placeholders or default values, such as 'example', 'john doe', 'lorem ipsum', or 'test'
  * null - actual null values, these are very straightforward to recognize because they will be represented as '<N/A>'

Using this information, please think deeply about how the user is addressing the blanks. The possible methods include:
  * some - referring a subset of rows based on a specific type or attribute. May also reference values in other columns to filter the blanks.
  * all - referencing all blank rows at once, aka. the entire set of blanks
  * beyond - the user is making changes that go beyond the blank rows, extending to other rows or even the entire column
  * ignore - brushing off the blanks or saying none of them are valid. This includes explicitly dismissing the blanks or simply moving onto a different topic.
  * unsure - when the user is not clear about how to deal with the blanks, such as making a non-committal response

Afterwards, please output pandas code that crafts a subset dataframe containing only the rows the user references in the final converation turn.
You have access to 'issue_df' as the full dataframe, which allows you to filter rows based on the column values if needed.
You also have access to 'all_rows' as a list of all row ids with blank values.  If the method is unsure, then return 'none' as the code.
Your entire response should be in well-formatted JSON including keys for thought (string), method (single token) and dataframe (code snippet), with no further explanations after the JSON output.

For example,
#############
User: Are there any problems with delivery time data?
Agent: I found 4 null values in the DeliveryTime column. Here are some samples to help you compare. What should I do with them?
User: We can set them to one hour after the OrderTime

_Supporting Data_
Relevant columns: OrderTime, DeliveryTime, Address, Status
  * null - <N/A>

_Output_
```json
{{
  "thought": "The term 'them' refers to all the null values",
  "method": "all",
  "dataframe": "subset_df = issue_df[issue_df['DeliveryTime'].isnull()]"
}}
```

Agent: I found 4 missing leads and 1 default lead. What should I do with them?
User: How about we just drop the missing ones?

_Supporting Data_
Relevant columns: Score, LeadName, Company, LeadSource
  * missing - ' ', n/a
  * default - John Smith

_Output_
```json
{{
  "thought": "the user explicitly mentions the missing emails",
  "method": "some",
  "dataframe": "subset_df = issue_df[(issue_df['LeadName'].isin([' ', 'n/a']))]"
}}
```

Agent: I found 16 missing emails, 4 null emails and 5 default emails for the sign_up_email. What should I do with them?
User: That's too bad. Can we fill them in when the username is available?

_Supporting Data_
Relevant columns: member_email, registration_date, username
  * missing - no email, do not want to share, n/a, do not have one
  * null - <N/A>
  * default - fakeemail@example.com

_Output_
```json
{{
  "thought": "The blank values should be interpolated when the username is not null",
  "method": "some",
  "dataframe": "subset_df = issue_df.loc[all_rows].loc[issue_df['username'].notnull(), :]"
}}
```
#############
Now, please think about what method the user is applying and then produce the appropriate code snippet. Unless the method is 'unsure', remember to always define 'subset_df' within the dataframe output.
{history}

_Supporting Data_
Relevant columns: {status}
{row_desc}

_Output_
"""

concerns_prompt = """Given the conversation history, your task is to determine the row ids the user is referencing to address the concerns in the data.
To help in this task, you will also be shown the potential issues as `Row row_id) concern_type in column1:value1, column2:value2, column3:value3, ... columnX:valueX`
The possible concern types include:
  * outlier - numeric values that are significantly different
  * anomaly - textual values that are unusual or unexpected
  * date_issue - datetime values that are incorrect or misformatted
  * loc_issue - location values that are incorrect or misformatted

Using this information, please think deeply about how the user is addressing the concerns. The possible methods include:
  * some - referring to rows of a specific type or a specific position. Could also be based on selecting rows based their values or attributes
  * all - referencing all concerns at once, aka. the entire set of concerns
  * ignore - brushing off the concerns or saying none of them are valid. This includes explicitly dismissing the concerns or simply moving onto a different topic.
  * beyond - the user is addressing more than just the concerns shown, extending to the entire column or table instead
  * unsure - when the user is not clear about how to address the concerns, such as making a non-committal response

Afterwards, please output which rows are being referenced in the final conversation turn based on the row_id.
If the user is referencing all issues at once, you can use a negative value (like -1) as a shortcut. If the user is unclear about their rows, please output an empty list.
Your entire response should be in well-formatted JSON including keys for thought (string), method (string) and rows (list of integers), with no further explanations after the JSON output.

For example,
#############
Agent: I found 4 potential outliers in the collected_fees column.
User: The positive ones all look fine actually
Row 1613) outlier in first_name:michael, last_name:syned, collected_fees:202800, repayment_schedule:monthly, background_check:pass
Row 1620) outlier in first_name:ahmed, last_name:al-ghamdi, collected_fees:200597, repayment_schedule:monthly, background_check:fail
Row 1623) outlier in first_name:paul, last_name:simon, collected_fees:-40, repayment_schedule:weekly, background_check:pass
Row 1647) outlier in first_name:lydia, last_name:riddell, collected_fees:193602, repayment_schedule:monthly, background_check:pass

_Output_
```json
{{
  "thought": "The user is ignoring the collected fees with positive values",
  "method": "ignore",
  "rows": [1613, 1623, 1647]
}}
```

Agent: There are two anomalies and two datetime issues in the ApartmentRental table.
User: Those dates should probably be deleted.
Row 304) anomaly in city:Me^silla
Row 319) anomaly in city:Pin~on Canyon
Row 331) date_issue in lease_start:01/01/2025
Row 537) date_issue in lease_start:04/01/2025

_Output_
```json
{{
  "thought": "The user is referencing all the datetime issues",
  "method": "some",
  "rows": [331, 537]
}}
```

Agent: There are three datetime issues the entry_verified_date column.
User: Let's change all of them to 2023
Row 15) date_issue in entry_verified_date: 2024-05-19
Row 22) date_issue in entry_verified_date: 2024-03-13
Row 23) date_issue in entry_verified_date: 2024-10-21

_Output_
```json
{{
  "thought": "The user is referencing all the rows at once",
  "method": "all",
  "rows": [-1]
}}
```
#############
Now it is your turn, please think carefully, then decide on the appropriate method and rows. Remember to only output JSON with no further text.
{history}
{row_desc}

_Output_
"""

# -----------------------------------------------------------------------------
# The following 6 prompts were removed for brevity. Each followed the same
# few-shot pattern as the templates above: scenario-based examples with JSON
# output, ending with a "Current Scenario" or "Real Scenario" block using
# {valid_tab_col}, {history}, {columns}, {current}, {status}, and/or
# {row_desc} placeholders.
#
# Removed prompts:
#   - connect_flow_prompt: Connect two data sources (table/columns/API output)
#   - resolve_flow_prompt: Fix issues in spreadsheet (table/columns/rows output)
#   - swebench_prompt: Open-source issue fixing workflow (no placeholders)
#   - insight_flow_prompt: Find insights in data (table/columns output)
#   - typos_prompt: Similar term group resolution (row id selection)
#   - problems_prompt: Duplicate of clean_prompts.problems_prompt with identical
#       structure (convert/update/delete/beyond/unsure methods, row id output)
# -----------------------------------------------------------------------------
