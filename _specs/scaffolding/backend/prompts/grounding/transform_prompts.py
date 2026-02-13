# =============================================================================
# Grounding prompts for the "transform" flow category.
# Trimmed to 3 representative templates out of 12 total.
# Removed templates: insert_methods, transpose_flow_prompt,
#   cut_and_paste_prompt, split_column_prompt, materialize_view_prompt,
#   join_tables_prompt, append_flow_prompt, merge_columns_prompt,
#   stage_table_prompt, call_external_api_prompt
# These followed the same few-shot pattern with scenario-based examples
# and a final "Current Scenario" block with {valid_tab_col}, {history},
# {prior_state}, and/or {current} placeholders.
# =============================================================================

insert_flow_prompt = """Given the conversation history and supporting details, your task is to determine what column (or row) to insert and how to populate its contents.
The previous state is given as the table name, followed by a list of column names. These represent the recently referenced data, which should be useful context.

Start by thinking about the reason for creating the new column and whether its clear how the column can be filled by a Pandas operation.
Based on this thought, generate an appropriate column name for insertion, along with the table in which it resides. When deciding on a name, consider the following:
  * What is the formatting convention based on the existing columns: underscores, spaces, or camelCase? lowercase or uppercase?
  * Do the other columns follow some sort of pattern? If so, what is the common theme? Perhaps, they tend to use abbreviations or acronyms?
  * Prefer intuitive names that hint at the column's purpose (ie. is_promising_lead) rather than literal names describing the contents (ie. score_greater_than_70).
  * If the user has declared a specific column name, then use that as the target. Otherwise, generate a new name matching the style of the existing columns.

If the target column is unclear, then label as 'unsure'. If the target table is unclear, then you can default to 'current'.
Your entire response should be in well-formatted JSON, including keys for thought (string), table (string), and target (string) with no further explanations after the JSON output.
Let's consider a few examples, and then tackle the current case.

## 1. Connected Column for Tracking Status
A common use case is status or indicator columns whose value changes depending on other columns.

_Conversation History_
User: and how many have more than 1000 loyalty points?
Agent: There are 193 customers with more than 1000 loyalty points.
User: OK, so let's mark customers with more than 1000 points and 10 purchases as high value, 500 points and 5 purchases as medium value, and everyone else as low.

_Previous State_
Customers - [CustomerID, FirstName, LastName, LoyaltyPoints]

_Output_
```json
{{
  "thought": "The new column will assign customer status as either high, medium or low value. This is determined by a combination of loyalty points and purchase amount. The column names capitalize the first letter and do not contain spaces.",
  "table": "Customers",
  "target": "CustomerValue"
}}
```

## 2. Snapshot Column for Storing Values
Another use case is creating a static column equivalent to copy/paste values without formulas

_Conversation History_
User: How many different social media platforms are we advertising on?
Agent: We are advertising on Twitter, Instagram, and Yelp.
User: I want the usernames for all the social media channels together in one column. Can you do that?

_Previous State_
CustomerRecords - [Twitter_Paid, Instagram_Paid, Yelp_Local]

_Output_
```json
{{
  "thought": "The new column will copy usernames over from existing rows that are related to social media platforms. The format uses underscores and title case.",
  "table": "CustomerRecords",
  "target": "Social_Media_Usernames"
}}
```

## 3. Connected Column for Calculating Formulas
Columns are often created as a result of some calculation, where the formula will be stored as a Pandas operation.

_Conversation History_
User: how many active members do we have right now?
Agent: We have 395 active members right now. See table for details.
User: What if I want to know how long someone has been a member with us at Sixby Fitness

_Previous State_
Members - [memberID, firstName, lastName, startDate, endDate]

_Output_
```json
{{
  "thought": "The new column will calculate the duration of membership. The values can be calculated using the formula endDate - startDate. The format uses camelCase without spaces.",
  "table": "Members",
  "target": "membershipDuration"
}}
```
---
## Current Scenario
Now, let's apply this logic to our current scenario. Please think about the reason for creating the new column and the name of the column.
When in doubt, the user's final utterance takes precedence over any other supporting information. As reference for naming style, the other tables and columns are:
{valid_tab_col}

_Conversation History_
{history}

_Previous State_
{prior_state}

_Output_
"""

delete_flow_prompt = """Given the conversation history, your task is to determine what data the user wants to remove.
Start by thinking out loud about what Pandas operations are most applicable to the request and which tables, rows, and columns to target for removal.
If the user wants to:
  - remove rows based on some criteria, consider which columns are most relevant for filtering
  - delete an entire row, then use '*' for the column to indicate all columns
  - remove columns based on some criteria in the row, you can also use '*' to indicate all columns, and then filter based on the row value

You are given all available table and column names, so only choose from those options, and matching the exact spelling and capitalization.
When in doubt, you should default to 'unsure' for the column names rather than making assumptions. If the entire target is unclear, then leave the result list empty.
Your entire response should be in well-formatted JSON including keys for thought (string) and result (list), where each item is a dict with table (tab), column (col), and row (row) keys.
There should be no further explanations or comments after the JSON output.

For example,
---
_Available Data_
* Tables: DeliveryStatus, Product
* Columns: DeliveryID, DeliveryStatus, SendDate, ReceiveDate, RecipientName, RecipientAddress, ProductID, ProductName, ProductDescription

_Conversation History_
User: I want take a quick look at the delivery status
Agent: Certainly, here is the DeliveryStatus table.
User: We don't need the SendDate or ReceiveDate columns anymore

_Output_
```json
{{
  "thought": "I should drop the SendDate and ReceiveDate columns",
  "result": [
    {{"tab": "DeliveryStatus", "col": "SendDate", "row": "all"}},
    {{"tab": "DeliveryStatus", "col": "ReceiveDate", "row": "all"}}
  ]
}}
```

_Available Data_
* Tables: orders
* Columns: OrderID, OrderStatus, PurchaseTime

_Conversation History_
User: Sure, let's take a look
Agent: The purchase time for order 20533B was 2022-01-01 00:00:00.
User: Got it, probabaly used that as a default date. We should just get rid of anything older than 2023.

_Output_
```json
{{
  "thought": "I should remove all rows with purchase times strictly less than 2023.",
  "result": [
    {{"tab": "orders", "col": "PurchaseTime", "row": "< 2023-01-01"}}
  ]
}}
```

_Available Data_
* Tables: Pardot
* Columns: UserSignups, SignUpDate, EmailAddress, Fees Paid, LastLogin, NumLogins, NumSessions, ConversionsMade, TotalViews, TotalClicks, TotalSpend, ROI in Pardot

_Conversation History_
User: How big is the Pardot table?
Agent: The Pardot table has 61,436 rows and 12 columns.
User: This is too big, can you drop any columns where the sum of values is less than a hundred?

_Output_
```json
{{
  "thought": "We are removing all columns where the sum of values is less than 100. We should select all columns, and then specify the sum condition in the row.",
  "result": [
    {{"tab": "Pardot", "col": "*", "row": "sum < 100"}}
  ]
}}
```
---
Now it's your turn, start with a concise thought followed by a list of tabs, cols, and rows.
The table and column output must exactly match the names listed under "_Available Data_" with no further explanations or text after the JSON output.

_Available Data_
{valid_tab_col}
* Current table: {current}

_Conversation History_
{history}

_Output_
"""

append_flow_prompt = """Given the valid tables along with the conversation history, our goal is to determine which table(s) the user wants to connect together.
Start by thinking carefully about what type of connection should be used. Specifically, we define two types:
  * join - connect the source and target tables based on a common column; a foreign key relationship is often used
  * append - adding data from the source to target table directly, since most or all columns are shared

Furthermore, consider the order of the tables being connected. If the user is trying to join two tables, then the order does not matter.
However, when the user is trying to append data from one table to another, then the order is important.
Ideally, we would identify a semantic relationship between the tables, such that one naturally follows the other (ie. data from 2023 is appended to 2022)
As a backup, we can consider the alphabetical order of the table names. In the absence of any relationships, just list the tables in the order they were mentioned.

If the connection type is ambiguous, then default to 'append'. If the source tables are ambiguous, then output an empty list.
Your entire response should be in well-formatted JSON including keys for thought (string), method (string), and sources (list), with no further explanations after the JSON output.

For example,
---
## Time Period Scenario
* Tables: AugustEmails, OctoberEmails, SeptemberEmails, NovemberEmails
* Columns: Email ID, Campaign Name, Total Sends, Total Opens, Total Clicks, Total Unsubscribes, Total Bounces in AugustEmails;
Email ID, Campaign Name, Total Sends, Total Opens, Total Clicks, Total Unsubscribes, Total Bounces in OctoberEmails;
Email ID, Campaign Name, Total Sends, Total Opens, Total Clicks, Total Unsubscribes, Total Bounces in SeptemberEmails;
Email ID, Campaign Name, Total Sends, Total Opens, Total Clicks, Total Unsubscribes, Total Bounces in NovemberEmails;

_Conversation History_
User: Can you delete all the rows with 0 clicks?
Agent: No problem, I have removed them. There are now 624 rows left for August.
User: OK, now let's join all the data together into one table.

_Output_
```json
{{
  "thought": "Since all the tables have the same columns, we can append them together. A natural order would go from August to November.",
  "method": "append",
  "sources": ["AugustEmails", "SeptemberEmails", "OctoberEmails", "NovemberEmails"]
}}
```

## Social Media Scenario
* Tables: Weekly Report (social), Weekly Report (email), Weekly Report (paid), LinkedIn_download, Twitter_download, Tiktok_download
* Columns: report_date, total_engagement, total_impressions, total_clicks, high_clicks, platform_spend, conversion_rate, follower_growth, content_count in Weekly Report (social);
report_date, open_rate, click_rate, bounce_rate, total_sends, unsubscribe_rate, revenue_generated, campaign_count in Weekly Report (email);
report_date, ad_spend, cost_per_click, total_clicks, return_on_spend, impression_count, conversion_value, campaign_active in Weekly Report (paid);
post_date, sponsored_content, organic_content, company_followers, engagement_rate, click_through_rate, job_applies, impressions_delivered in LinkedIn_download;
tweet_datetime, retweet_count, like_count, impression_count, profile_clicks, url_clicks, reply_count, media_engagements in Twitter_download;
video_date, view_count, share_count, comment_count, play_duration, total_likes, follower_growth, engagement_rate in Tiktok_download

_Conversation History_
User: Now let's add a column which signifies whenever the number of clicks is greater than 1000.
Agent: Sure, do you know what you would like to name this column?
User: Let's call it 'high_clicks'
Agent: OK, I have added the column.
User: I'd like to append the LinkedIn data to the social media report as well.

_Output_
```json
{{
  "thought": "Despite the request to 'append' LinkedIn data, the columns between the tables are clearly not compatible, so a join is more appropriate.",
  "method": "join",
  "sources": ["Weekly Report (social)", "LinkedIn_download"]
}}
```

## CRM Scenario
* Tables: ms_dynamics_all, account_info, customers_list, qualified_leads, opportunities_cold, opportunities_warm
* Columns: email_address, first_name, last_name, company_name, job_title, phone_number, lead_source, last_contact_date, lead_score, status, lead_owner in ms_dynamics_all;
account_id, company_name, industry, annual_revenue, account_owner, territory, customer_since, payment_terms, account_status, primary_contact_email in account_info;
customer_id, business_name, contact_person, email, subscription_tier, signup_date, billing_cycle, last_purchase_date, lifetime_value, account_manager, active_status in customers_list;
Email_Address, First_Name, Last_Name, Company_Name, Job_Title, Phone_Number, Lead_Source, Last_Contact_Date, Lead_Score, Status, Lead_Owner in qualified_leads;
email_address, first_name, last_name, company, job_title, phone_number, lead_source, last_contacted, lead_score, lead_status, lead_owner in opportunities_cold;
email_address, first_name, last_name, company, job_title, phone_number, lead_source, last_contacted, lead_score, lead_status, lead_owner in opportunities_warm;

_Conversation History_
User: I need to full list of emails so I can blast them all with our latest offer, can you pull that for me?
Agent: There are multiple tables with email addresses, which one would you like?
User: Ok, let's start by extending the CRM data with the latest batch of leads from the AEs

_Output_
```json
{{
  "thought": "The CRM table most likely refers to ms_dynamics_all, so that should go first, while the leads tables can be appended afterwards. The account and customers tables are missing key columns (ie. first and last names), so they are excluded.",
  "method": "append",
  "sources": ["ms_dynamics_all", "qualified_leads", "opportunities_cold", "opportunities_warm"]
}}
```
---
Now it's your turn! Please think carefully about the relevant tables for connection, and then output the method along with the source tables in the appropriate order.
When choosing the sources, copy the table names exactly from the valid options, making sure to preserve any formatting, capitalization, or spelling.

## Real Scenario
{valid_tab_col}
* Current table: {current}

_Conversation History_
{history}

_Output_
"""

# -----------------------------------------------------------------------------
# The following 9 prompts were removed for brevity. Each followed the same
# few-shot pattern as the templates above: scenario-based examples with JSON
# output, ending with a "Current Scenario" block using {valid_tab_col},
# {history}, {prior_state}, and/or {current} placeholders.
#
# Removed prompts:
#   - insert_methods: Short description of column insertion method types
#   - transpose_flow_prompt: Row/column transposition direction
#   - cut_and_paste_prompt: Column/row reordering with source/destination
#   - split_column_prompt: Text-to-columns with delimiter detection
#   - materialize_view_prompt: Save temporary view to memory or disk
#   - join_tables_prompt: Table join with PER/ORG/LOC/DATE/ID/O methods
#   - merge_columns_prompt: Source column identification for merging
#   - stage_table_prompt: Stage data in a direct table (placeholder + current)
#   - call_external_api_prompt: External API retrieval (placeholder + current)
# -----------------------------------------------------------------------------
