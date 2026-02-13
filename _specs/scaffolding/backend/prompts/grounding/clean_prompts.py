# =============================================================================
# Grounding prompts for the "clean" flow category.
# Trimmed to 3 representative templates out of 10 total.
# Removed templates: validate_flow_prompt, format_flow_prompt,
#   pattern_fill_prompt, remove_duplicates_prompt, assign_datatype_prompt,
#   undo_flow_prompt, persist_preference_prompt
# These followed the same few-shot pattern with scenario-based examples
# and a final "Current Scenario" block with {valid_tab_col}, {history},
# {prior_state}, and/or {current} placeholders.
# =============================================================================

update_flow_prompt = """Given the conversation history and previous state, your task is to determine what part of the table the user wants to update.
The previous state is given as the table name, followed by a list of column names. These represent the recently referenced data, which should be useful context.

Please start by thinking out loud about the how we can clean the data, and what kind of operations are needed to achieve this.
Then decide on the specific entities involved, where each entity is a dict with keys for tab (string), col (string), and row (string).
Tables and columns are specified by their names, and must be chosen from the valid options.
If you want to select all columns from a table, then use '*' for the column name.

In contrast, specifying rows has more flexibility. Concretely, rows can take the form of:
  * a specific value (eg. 'New York')
  * a formula (eg. '= col1 + col2')
  * a special keyword (eg. 'all' or 'header')
  * a general description (eg. 'outliers' or 'abbreviated metrics')

Your entire response should be in well-formatted JSON including keys for thought (string), source (list of entities), and target (list of entities).
Neither the source nor target lists should contain more than ten entities. If the situation seems call for more, then use a formula, keyword, or general description to represent multiple entities at once.

For example,
---
## Update Values Across Multiple Columns
_Conversation History_
User: Which anomalies?
Agent: The Impressions and PageViews columns contain blank values such as N/A, Unknown, and Unknown.
User: Change all of those into just zero.

_Previous State_
Landing Page - [Impressions, Clicks, PageViews]

_Output_
```json
{{
  "thought": "I should replace 'Unknown' and 'N/A' into 0 in the Impressions and PageViews columns.",
  "source": [
    {{"tab": "Landing Page", "col": "Impressions", "row": "Unknown"}},
    {{"tab": "Landing Page", "col": "Impressions", "row": "N/A"}},
    {{"tab": "Landing Page", "col": "PageViews", "row": "Unknown"}},
    {{"tab": "Landing Page", "col": "PageViews", "row": "N/A"}}
  ],
  "target": [
    {{"tab": "Landing Page", "col": "Impressions", "row": "0"}},
    {{"tab": "Landing Page", "col": "PageViews", "row": "0"}}
  ]
}}
```

## Collapse Multiple Rows into One
_Conversation History_
User: Yup, that's right
Agent: OK, I have split up the location into city and state columns.
User: Can you please rewrite both each state in its abbreviated form, so that New York becomes NY, California becomes CA, etc.

_Previous State_
Hubspot_Downloads - [location, city, state]

_Output_
```json
{{
  "thought": "There are 50 states in the US, which is too many to list out. Instead, I can use special keywords and general descriptions to represent the rows that need to be updated.",
  "source": [
    {{"tab": "Hubspot_Downloads", "col": "state", "row": "all"}}
  ],
  "target": [
    {{"tab": "Hubspot_Downloads", "col": "state", "row": "abbreviated"}}
  ]
}}
```

## Update Cells Referencing Itself
_Conversation History_
User: Are there any outliers in the price column?
Agent: There are is $53800 for Emma Europe - Queen Size that is significantly more expensive than the other prices.
User: Oh that's not in dollars! It should be divided by 100.

_Previous State_
AmplitudeAnalytics - [amp_id, product_name, product_type, bed_size, price]

_Output_
```json
{{
  "thought": "The price of 'Brooklinen - Queen Size' should be divided by 100.",
  "source": [{{"tab": "AmplitudeAnalytics", "col": "product_name", "row": "Brooklinen - Queen Size"}}],
  "target": [{{"tab": "AmplitudeAnalytics", "col": "price", "row": "= price / 100"}}]
}}
```
---
## Current Scenario
Follow the same format above to determine the source of changes and the target outcome. There should be no text before nor any explanations after the JSON output.
As reference, the valid tables and columns are:
{valid_tab_col}

_Conversation History_
{history}

_Previous State_
{prior_state}

_Output_
"""

problems_prompt = """Given the conversation history, your task is to determine the row ids the user is referencing to address the problems in the data.
For our context, the term 'problems' refers to the rows belonging to a data type of subtype that are different from the majority of the column.
To help in this task, you will be given the general status of the column in the form of `Most are <sub_type>, but X are <sub_type> type`.
This is followed by a list of potential problems written as `Row row_id) <sub_type> - <value>`, which might be truncated for brevity.
The possible data types are:
  * unique - each value holds a unique meaning, with subtypes such as IDs, pre-defined categories, statuses, or boolean values
  * datetime - the values are related to dates or times, including subtypes such as months, weeks, quarters, or timestamps
  * location - the values are related to geographical locations, including subtypes such as cities, states, countries, or addresses
  * number - the values are numeric and can be used for calculations, including subtypes such a percent, currency, or decimals
  * text - the values are textual, including subtypes such as phone numbers, emails, names or general descriptions

Using this information, please think deeply about how the user is addressing the problems. The possible methods include:
  * convert - changing the rows to a different data type or sub type without affecting the content
  * update - modifying the content through calculating new values or changing the underlying text
  * delete - removing the rows that are causing the problems
  * beyond - the user is moving on to a different topic beyond the problems displayed
  * unsure - it is unclear how to proceed, such as when the user makes a non-committal response

If we are intepreting values a different type, this is a 'convert' method. If we are changing the underlying value, this is an 'update' method.
Afterwards, please output which rows are being referenced in the final conversation turn based on the row_id.
If the user is referencing all issues at once, use a negative value (like -1) to indicate this. If the user is unclear or going beyond the limits, please output an empty list.
Your entire response should be in well-formatted JSON including keys for thought (string), method (string) and rows (list of integers), with no further explanations after the JSON output.

For example,
---
User: Those are actually dollar amounts.
Agent: Sure, I have changed 21.33 to a currency type. What should I do with the rest?
User: Oh, yea do the same for the rest
Status: Most are currency, but 4 are decimal type
Row 23) decimal - 19.53
Row 22) decimal - 14.36
Row 37) decimal - 15.01
Row 39) decimal - 16.77

_Output_
```json
{{
  "thought": "The discussion involves the currency subtype, so this is a convert method",
  "method": "convert",
  "rows": [-1]
}}
```

Agent: The AttendedEvent column is mostly boolean data type, but I found some general text. Here are some samples of both to help compare.
User: the maybes can just be removed
Status: Most are boolean, but 17 are general type
Row 3) general - maybe
Row 17) general - not sure
Row 32) general - maybe
Row 23) general - maybe
Row 35) general - not sure
Row 36) general - maybe
Row 37) general - maybe
Row 41) general - later
[9 more rows ...]

_Output_
```json
{{
  "thought": "The user wants to delete the rows where the text is 'maybe'",
  "method": "delete",
  "rows": [3, 32, 23, 36, 37]
}}
```

Agent: Done. What would you like to do with the remaining issues?
User: The Thur and Fiday ones should be Thursday and Friday
Status: Most are week, but 4 are general type
251) general - Thur
162) general - Fiday
163) general - weekend
184) general - Thur

_Output_
```json
{{
  "thought": "Thur and Fiday are found in rows 251, 162, and 184",
  "method": "update",
  "rows": [251, 162, 184]
}}
```
---
Now it is your turn, please think carefully, then decide on the appropriate method and rows. Remember to only output JSON with no further text.

{history}
Status: {status}
{row_desc}

_Output_
"""

impute_flow_prompt = """Given the conversation history and available tables, your task is to determine which source and target columns are relevant for imputation.
The source columns are the ones that will be used to fill in the target column, while the target column is the one that needs to be filled in.
In terms of deciding on the table, note that the currently active table is '{current}', which should serve as a useful default.

When deciding on source columns, keep in mind:
  * If it is unclear what the source columns are, then output up to eight (8) columns that may be useful in determining the target.
  * At this early stage, prefer to include more columns rather than less when there is uncertainty.
  * You can use the wildcard '*' to represent all columns in the table, but only do so if there are 8 or fewer columns in the table.
  * If the user has explicitly mentioned the columns to use, then include those and no others.

When deciding on the target column, keep in mind:
  * If it is unclear what the target column is, then output an empty list as the target.
  * If there are multiple possible options for the target, then include all of them so we can review them.
  * Occasionally, there may even be multiple target columns, which is why the target is a list.

Please start by thinking out loud about the how we might impute the missing values and which columns are involved.
Your entire response should be in well-formatted JSON including keys for thought (string), source (list), and target (list).
Both the source and target should be a list of dicts with keys for tab (string) and col (string). There should be no further explanations after the JSON output.

For example,
---
_Conversation History_
User: You see how many of the cities are missing?
Agent: Yes, I found 24 rows with missing cities. What would you like to do with those?
User: Is there a way to grab it from the shipping address?

_Valid Tables and Columns_
* Tables: customerContact, customerOrders, marketingOffers
* Columns: CustomerID, CustomerName, FavCuisineType, ShippingAddress, customerCity, customerState, ContactNumber, IsActive in customerContact;
OrderID, CustomerID, RestaurantID, OrderDate, TotalAmount, DeliveryAddress, OrderStatus, EstDeliveryTime, SpecialInstructions in customerOrders;
OfferID, OfferTitle, OfferDescription, OrderKey, StartDate, EndDate, DiscountAmount, ApplicableRestaurants, RedemptionCode in marketingOffers

_Output_
```json
{{
  "thought": "I should impute the missing cities by grabbing it from the shipping address.",
  "source": [ {{"tab": "customerContact", "col": "ShippingAddress"}} ],
  "target": [ {{"tab": "customerContact", "col": "customerCity"}} ]
}}
```

_Conversation History_
User: Please fill in all the empty approval statuses.

_Valid Tables and Columns_
* Tables: Testimonials, CanvasOutreach
* Columns: TestimonialID, StudentID, CourseID, CourseName, TestimonialText, DateProvided, Rating, Featured, ApprovalStatus, PhotoLink in Testimonials;
CampaignName, TargetAudience, ViewCount, ClickCount, CostPerClick, SignupCount, ResponseRate, Collaborators in CanvasOutreach

_Output_
```json
{{
  "thought": "It's clear we are targeting the ApprovalStatus column in Testimonials, but it's uncertain which ones to use as source. I will pick multiple columns that might provide clues.",
  "source": [
    {{"tab": "Testimonials", "col": "CourseName"}},
    {{"tab": "Testimonials", "col": "TestimonialText"}},
    {{"tab": "Testimonials", "col": "DateProvided"}},
    {{"tab": "Testimonials", "col": "Rating"}},
    {{"tab": "Testimonials", "col": "Featured"}},
    {{"tab": "Testimonials", "col": "ApprovalStatus"}}
  ],
  "target": [ {{"tab": "Testimonials", "col": "ApprovalStatus"}} ]
}}
```
---
Now it's your turn to tackle the current case. Choosing only from the valid tables and columns, output the source and target columns for imputation.
Even if a column is only tangentially related to the target, please include it as a source column since it may still be useful.

_Conversation History_
{history}

_Valid Tables and Columns_
{valid_tab_col}

_Output_
"""

# -----------------------------------------------------------------------------
# The following 7 prompts were removed for brevity. Each followed the same
# few-shot pattern as the templates above: scenario-based examples with JSON
# output, ending with a "Current Scenario" block using {valid_tab_col},
# {history}, {prior_state}, and/or {current} placeholders.
#
# Removed prompts:
#   - validate_flow_prompt: Column validation with clear/peek/unsure actions
#   - format_flow_prompt: Column formatting with clear/peek/unsure actions
#   - pattern_fill_prompt: Pattern-based column filling with table/target/support
#   - remove_duplicates_prompt: Duplicate removal column selection
#   - assign_datatype_prompt: Data type assignment (unique/datetime/location/number/text)
#   - undo_flow_prompt: Undo last action (placeholder + current)
#   - persist_preference_prompt: Save user preference (placeholder + current)
# -----------------------------------------------------------------------------
