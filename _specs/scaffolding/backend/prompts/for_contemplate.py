merge_col_confidence = """Given the conversation history and supporting details, decide the source and target columns in the user's request:
  * Source - the user is merging data from these column(s) to populate a new column
  * Target - this is the name of the new column the user wants to insert or create

Supporting details include:
  * valid column names along with the table; when deciding on source columns you MUST choose from these options
  * previously predicted source columns that can serve as a guide, these do NOT count as explicit mentions

Additionally, note how certain you are on a scale of 1 to 5 for each assignment:
  * 5 - completely certain, the user explicitly mentioned this column
  * 4 - mostly certain, the result is obvious due to the conversation history or due to common sense
  * 3 - somewhat likely, but there is a degree of uncertainty
  * 2 - just a guess, the assignment is a complete shot in the dark
  * 1 - totally unsure, it seems like the user is not actually inserting a new column; set the column value as 'none'

If the conversation mentions multiple targets, only assign the most recent one. Think about how certain you are before assigning any columns.
Your entire response should be well-formatted JSON with thought, source, and target as keys. There should be no further explanations after the JSON output.

For example,
#############
User: I want to figure out which promos we've spent the most on.
Agent: Certainly, I can help with that. Here are the top 3 promos by cost.
User: Create a formula that is True if the ad cost is greater than $1000 and False otherwise.

_Supporting Details_
Valid: PromoID, PromoName, StartDate, EndDate, DiscountPercentage, ApplicableProducts, PromoCode, PromoCost, RedemptionCount in Promotions table
Predicted: none

_Output_
```json
{{
  "thought": "ad cost and PromoCost are likely the same, but the target column is not specified, so I will generate a reasonable guess.",
  "source": [["PromoCost", 4]],
  "target": [["Expensive", 3]]
}}
```

#############
User: Can we sort the orders by date?
Agent: I can make a merge the month, day, and year columns into a single date column. Would you like me to do that?
User: yea, go for it

_Supporting Details_
Valid: event_id, product_id, customer_first, customer_last, quantity, revenue, cost, month, day, year, status, priority in events table;
Predicted: month, day, and year

_Output_
```json
{{
  "thought": "Month, day, and year are explicitly mentioned, so I can assign high certainty score. The name of the target column is not given, so I will generate a new one.",
  "source": [["month", 5], ["day", 5], ["year", 5]],
  "target": [["order_date", 4]]
}}
```

#############
User: we have lots of users coming from China now!
Agent: Yes, that is wonderful. Is there a specific metric you'd like to see?
User: Can we make a new ExchangeRate column for that?

_Supporting Details_
Valid: CountryID, Europe, Americas, AsiaPacific, TaxRate, TotalAmount, ExchangeRate (EUR), ExchangeRate (USD) in Countries table
Predicted: none

_Output_
```json
{{
  "thought": "China is located in AsiaPacific, so that is likely one source. China uses RMB as currency, so that is our target. Our user base is in the US, so the other source is possibly Americas, but that is a guess.",
  "source": [["Americas", 2], ["AsiaPacific", 4]],
  "target": [["ExchangeRate (RMB)", 4]]
}}
```

#############
User: What if we looked at marketing attribution for new users across each channel?
Agent: Certainly, to start what do you consider a new user?
User: Let's start by creating a column for that

_Supporting Details_
Valid: Lead ID, User Name, Source, Sum of Clicks, Pages Visited, Firsttime Visit, Downloaded Content, Form Submitted, Form Submission Datetime, Lead Score in MarCommLeads table
Predicted: none

_Output_
```json
{{
  "thought": "The user wants to track new users, but the definition is unclear. Perhaps 'Firsttime Visit' can determine new users.",
  "source": [["Firsttime Visit", 2]],
  "target": [["New User", 4]]
}}
```

#############
User: Can we combine the price and quantity sold into a new Revenue column?
Agent: Sure, a new 'Revenue' column has been created.
User: Let's also make a column that combines the review status and the approval status.

_Supporting Details_
Valid: TestimonialID, StudentID, CourseID, TestimonialText, DateProvided, Rating, Featured, ReviewStatus, ApprovalStatus, PhotoLink in Testimonials table
Predicted: ReviewStatus and ApprovalStatus

_Output_
```json
{{
  "thought": "Review status and approval status can be directly copied from the utterances, so I can assign a high confidence level.",
  "source": [["ReviewStatus", 5], ["ApprovalStatus", 5]],
  "target": [["CombinedStatus", 4]]
}}
```

#############
User: How much did we make from all our Pro members in January?
Agent: I found the membership_type to filter for Pro members, but I'm not sure which column to use for the revenue.
User: There should be a column for membership pricing somewhere.

_Supporting Details_
Valid: member_id, full_name, email_address, phone_number, date_joined, membership_type, membership_fee, expiration_date, packages_bought, emergency_contact in members table
Predicted: membership_type and membership_pricing

_Output_
```json
{{
  "thought": "Membership type is mentioned explicitly, but I need to find a column related to membership pricing. Membership fee seems like a good guess, but I am not completely certain. There is no clue as to the target column at all.",
  "source": [["membership_type", 5], ["membership_fee", 3]],
  "target": [["none", 1]]
}}
```

#############
User: How many different types of subscriptions do we have?
Agent: According to the plan_name column, we have 17 different types of subscriptions.
User: Can we track the retention rate for each plan?

_Supporting Details_
Valid: subscription_id, user_id, plan_name, sub_timestamp, billing_cycle, payment_status, renewal_notice in subscriptions table
Predicted: plan_name

_Output_
```json
{{
  "thought": "plan_name is mentioned explicitly, so I can assign a high certainty score. Retention rate can possibly be explained by sub_timestamp and billing_cycle, but I am very uncertain."
  "source": [["plan_name", 5], ["sub_timestamp", 2], ["billing_cycle", 2]],
  "target": [["retention_rate", 4]]
}}
```

#############
User: Do we have any information on the website pages that the user visited?
Agent: We have the PageURL and the ReferrerURL columns.
User: What's the difference between the two?

_Supporting Details_
Valid: ActivityID, UserID, ActivityType, ActivityTime, PageURL, UserAgent, ReferrerURL, SessionID. Activitytypes in Activity table
Predicted: PageURL and ReferrerURL

_Output_
```json
{{
  "thought": "PageURL and ReferrerURL can be directly copied from the utterances, so I can assign a high confidence level. However, this may not be the best approach to calculate the difference between two URLs, so the target is none.",
  "source": [["PageURL", 5], ["ReferrerURL", 5]],
  "target": [["none", 1]]
}}
```

#############
User: So what's the total amount if you add the price and the fee?
Agent: The total amount for the order ID 18961346 is $23.94
User: Can we make a new column to hold that?

_Supporting Details_
Valid: OrderID, CustomerID, RestaurantID, OrderDate, OrderPrice, OrderFee, OrderStatus, DeliveryAddress, EstDeliveryTime, SpecialInstructions in CustOrders table
Predicted: none

_Output_
```json
{{
  "thought": "'total amount' is explicitly mentioned, so I can assign a high score. 'price and the fee' seem similar to 'OrderPrice' and 'OrderFee', but I am not completely certain so the score is a bit lower.",
  "source": [["OrderPrice", 4], ["OrderFee", 4]],
  "target": [["TotalAmount", 5]]
}}
```

#############
Now it's your turn. Think carefully about how to assign source and target columns and provide a certainty level for each assignment in well-formatted JSON output.
{history}

_Supporting Details_
Valid: {columns}
Predicted: {entities}

_Output_
"""

describe_facts_prompt = """Given the conversation history and the available table and columns, our task is to figure out which facts the user is requesting.
We are only dealing with descriptive statistics here, so anything requiring calculations beyond simple statistics is out of scope.
The possible facts to describe are:
  * statistics - summary statistics like mean, median, and standard deviation
  * existence - whether there exists a column related to a certain attribute
  * range - the minimum or maximum values of a column, or the difference between them
  * preview - common values or a sample of the data in a column
  * size - the number of rows or the number of columns in a table
  * count - the count of unique values in a column (does not query for actual unique values)

Start by constructing a concise thought concerning what facts the user is asking for. Then, generate a list of fact terms, choosing only from the six valid options.
We are fairly confident that the user is asking for at least one of these facts. However, if that is not the case, then please output an empty list.
Your entire response should be in well-formatted JSON with keys for a thought (string) and facts (list), with no further explanations after the JSON output.

For example,
#############
User: How many rows are in the data?

_Output_
```json
{{
  "thought": "number of rows is equivalent to size",
  "facts": ["size"]
}}
```

User: Where do our highest spending customers come from?
Agent: The states with the highest spending are New York and Florida.
User: What is the lowest and highest spending amount for users from Florida?

_Output_
```json
{{
  "thought": "calculating spend from a specific location requires filtering which goes beyond the scope of a simple range",
  "facts": []
}}
```

User: Do we have a column that calculates CPCs?

_Output_
```json
{{
  "thought": "the user is asking whether there is a column related to cost per click",
  "facts": ["existence"]
}}
```

User: Do we have a column that calculates CPCs?
Agent: We have a 'CostPerView' column, is that what you're looking for?
User: Close enough, what's the average?

_Output_
```json
{{
  "thought": "Given the 'CostPerView' column, the user is likely asking for the average",
  "facts": ["statistics"]
}}
```

User: Ok, let's explore the Purchase table now
Agent: Sure, what would you like to know?
User: What sort of data is in the returns column?

_Output_
```json
{{
  "thought": "we can get a sense of the data by looking at common values",
  "facts": ["preview"]
}}
```

User: Ok, go ahead.
Agent: No problem, I have removed them. See the table for details.
User: what are the names of all the unique brands?

_Output_
```json
{{
  "thought": "provided facts only covers the count of unique brands, not the actual brand names",
  "facts": []
}}
```

User: Do we know how many views we got from our email campaign?

_Output_
```json
{{
  "thought": "the user wants to know if there exists a column for views",
  "facts": ["existence"]
}}
```

User: Do we know how many views we got from our email campaign?
Agent: yes, we can measure that using the 'opened_count' column.
User: I'd like to know the center value, biggest value, and smallest value to get a sense of the spread.

_Output_
```json
{{
  "thought": "the user wants summary statistics regarding mean, median, max, and min",
  "facts": ["range", "statistics"]
}}
```

User: We advertised on Facebook too right?
Agent: Yes, we have campaigns from Facebook within the FB_ads_updated table.
User: How many ad groups are covered in that table?

_Output_
```json
{{
  "thought": "number of ad groups is probably referring to the number of unique values",
  "facts": ["count"]
}}
```

#############
Now it's your turn! If it's helpful, the available columns are:
{columns}

What facts are the user requesting in the following conversation snippet?
Please return the target facts as a list of single tokens, or an empty list if no facts are mentioned, without any other words.

{history}

_Output_
"""

split_symbol_prompt = """Given the the conversation history and supporting details, determine the most likely symbol(s) used for splitting the contents into multiple columns.
Supporting details includes the head of the source column and the resulting target column names. Sometimes, the target names may be unknown, in which case you should just focus on the source column.
Start by thinking briefly about the best way to divide up a list. Sometimes, this is a typical text-to-columns operation, but other times creating multiple binary columns is more appropriate.
Next, output the most probable splitting symbols in a dictionary where the key is the name of the symbol and the value is the symbol itself.
If the symbol is fairly obvious, then just return one symbol. If there are multiple possibilities, return at most three symbols. If the symbol is unclear, output 'unsure' as the key.

Your entire response should be well-formatted JSON with thought (string) and symbols (dict) as keys. There should be no further explanations after the JSON output.

For example,
#############
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

_Output_
```json
{{
  "thought": "The delivery date is in a standard date format, so splitting by '/' is the most likely approach.",
  "symbols": {{ "slash": "/" }}
}}
```

#############
_Conversation History_
User: Which city had the highest number of signups?
Agent: There isn't a city column, but I can create one by splitting the location column. How does that sound?
User: That works for me

_Supporting Details_
|    | location         |
|---:|:-----------------|
|  0 |  Los Angeles CA  |
|  1 |  New York, NY    |
|  2 |  Chicago IL      |
|  3 |  Miami FL        |
|  4 |  Seattle, WA     |
Target: <unknown>

_Output_
```json
{{
  "thought": "City and states are often split with a comma, but many of the examples use a space. I will include both as possible splitting symbols.",
  "symbols": {{
    "comma": ",",
    "space": " "
  }}
}}

```

#############
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

_Output_
```json
{{
  "thought": "The attributes are separated by an ampersand, so that is the most likely splitting symbol.",
  "symbols": {{ "ampersand": "&" }}
}}
```

#############
_Conversation History_
User: Let's see if there's a relationship between the origin of the lead and the conversion rate
Agent: It might help to split up the origin column into separate columns first. What do you think?
User: yea, go for it

_Supporting Details_
|     |  Origin               |
|----:|:----------------------|
|  0  |  google, email        |
|  1  |  email                |
|  2  |  facebook, instagram  |
|  3  |  google               |
|  4  |  word of mouth        |
Target: ['google search', 'facebook', 'instagram', 'email', 'conference/event', 'word of mouth']

_Output_
```json
{{
  "thought": "Based on the targets, it seems we should be creating binary columns for each source by dividing the string by commas.",
  "symbols": {{ "comma": "," }}
}}
```

#############
_Conversation History_
User: We should clean up the leads as well before moving forward.
Agent: Sure, what kind of cleaning are you looking for?
User: Start by splitting the outreach names into separate columns

_Supporting Details_
|     |  Outreach Name      |
|----:|:--------------------|
|  0  |  SpotOn             |
|  1  |  Hickies            |
|  2  |  Fennel Markets     |
|  3  |  Ava                |
|  4  |  Wellahead          |
Target: <unknown>

_Output_
```json
{{
  "thought": "It's not clear how to split the values since they are single words.",
  "symbols": {{ "unsure": "" }}
}}
```

#############
_Conversation History_
User: Let's take a look at the survey results for the ice cream flavors now.
Agent: Sure, I see a column for favorite_flavors, what would you like me to do with it?
User: Each participant ranked their top 3 favorite flavors, can you separate them out?

_Supporting Details_
|    | favorite_flavors              |
|---:|:------------------------------|
|  0 |  chocolate;vanilla;strawberry |
|  1 |  mint;caramel;coffee          |
|  2 |  rocky road;coffee;chocolate  |
|  3 |  vanilla;strawberry;caramel   |
|  4 |  chocolate;rocky road;coffee  |
Target: ['chocolate', 'vanilla', 'strawberry', 'mint', 'caramel', 'coffee', 'rocky road']

_Output_
```json
{{
  "thought": "The flavors are separated by semicolons, so that is the most likely splitting symbol.",
  "symbols": {{ "semicolon": ";" }}
}}
```

#############
_Conversation History_
User: Do you know what percentage of people found us through facebook?
Agent: Apologies, I don't see a column for facebook. Where should I be looking?
User: it's in the column for 'How Did Your Hear About Us?'

_Supporting Details_
|    | How Did You Hear?                                   |
|---:|:----------------------------------------------------|
|  0 |  [facebook, twitter, instagram, linkedin, youtube]  |
|  1 |  [snapchat, tiktok, instagram, pinterest]           |
|  2 |  [twitter, instagram, medium, linkedin]             |
|  3 |  [reddit, quora]                                    |
|  4 |  [facebook, twitter, youtube]                       |
Target: ['linkedin', 'snapchat', 'reddit', 'pinterest', 'tiktok', 'youtube', 'quora', 'facebook', 'instagram', 'medium', 'twitter']

_Output_
```json
{{
  "thought": "The channels are separated by commas within each list.",
  "symbols": {{ "comma": "," }}
}}
```

#############
_Conversation History_
{history}

_Supporting Details_
{source_markdown}
Target: {targets}

_Output_
"""

move_element_prompt = """Based on the conversation history, the user wants to move some data around the '{table}' table.
Your task is to review the details of the movement and verify their accuracy.

First, we want to check the type of movement being made. For our purposes, the different movement types are:
  * cell - move one or more cell values to a new location
  * row - reorder an entire row to a new location
  * column - cut and paste a column to a different position in the same table
  * table - move columns located in multiple tables
Note that 'table' does not cover moving columns across tables. Such an operation would violate row alignment, and is therefore is not allowed.
If the movement type is ambiguous or invalid, please output 'unsure' rather than making any assumptions.

Second, we believe the user is strictly cutting and pasting content, not copying. This means the original location should be empty after the move.

Third, we want to check if any column headers are being renamed as they are moved, and if so what the new name might be.
If nothing is being renamed, output an empty string for the new name. If multiple columns are being renamed, separate the names by semi-colons.

Please start by formulating a brief thought on the user's request. Then, provide the answer to the individual details in well-formatted JSON.
Specifically, your output should contain keys for thought (string), movement (string), do_copy (boolean), and new_name (string).
There should be no further reasoning or explanations after the JSON output.

For example,
#############
_Conversation History_
User: Do we have any data about when deliveries were made?
Agent: We have EstDeliveryTime and DeliveryStatus columns in the CustomerOrders table.
User: OK, can you move the delivery status to right after the order status?

_Output_
```json
{{
  "thought": "The user wants to move a single column in a single table.",
  "movement": "column",
  "do_copy": false,
  "new_name": ""
}}
```

_Conversation History_
User: How many users to we have that are active and also have a Twitter account?
Agent: There are 6423 active users who also have a Twitter account.
User: Let's bring all customers who are active to the top of the table.

_Output_
```json
{{
  "thought": "The user wants to reorder rows in a single table.",
  "movement": "row",
  "do_copy": false,
  "new_name": ""
}}
```

_Conversation History_
User: Calculate total amount by multiplying the price and quantity, and also taking into account the discount.
Agent: Certainly, the TotalAmount column has been created.
User: Can you duplicate that column and move it to the end of the table?

_Output_
```json
{{
  "thought": "The user wants to copy a column to a new location.",
  "movement": "column",
  "do_copy": true,
  "new_name": ""
}}
```

_Conversation History_
User: We can just forget out those for now.
Agent: Ok, I will ignore those concerns moving forward.
User: The CPCs for the bed frames should actually be for the eye frames, can you take care of that?

_Output_
```json
{{
  "thought": "The user wants to cut the cell values and paste them in a new location.",
  "movement": "cell",
  "do_copy": false,
  "new_name": ""
}}
```

_Conversation History_
User: How many campaigns have spend that went over the limit?
Agent: The budget is located in a separate table, but I do not see a clear key to join the tables. Any ideas?
User: Can we just move the budget column over to the ad campaign table?

_Output_
```json
{{
  "thought": "The user is moving a single column across tables, which is not allowed.",
  "movement": "unsure",
  "do_copy": false,
  "new_name": ""
}}
```

_Conversation History_
User: Can you show me any campaigns that were running before August?
Agent: Sure, I can filter the campaigns based on the launch_time. How does that sound?
User: Actually, let's put any columns related to dates at the beginning of the table.

_Output_
```json
{{
  "thought": "The user is moving columns located in multiple tables.",
  "movement": "table",
  "do_copy": false,
  "new_name": ""
}}
```

_Conversation History_
User: See how we have ship date column?
Agent: Yes, I see it. Would you like to calculate something with it?
User: Bring it right next to the StartDate and call it EndDate instead

_Output_
```json
{{
  "thought": "The user is moving a single column and renaming it along the way.",
  "movement": "column",
  "do_copy": false,
  "new_name": "EndDate"
}}
```
#############
Now it's your turn! Think about the user's request and provide the movement type, whether copying is involved, and the new column name if applicable.
Remember that JSON booleans are written in lowercase, and that no text should be generated after the JSON output.

For additional context, the relevant columns are:
{columns}

_Conversation History_
{history}

_Output_
"""

metric_name_prompt = """Given the conversation history, think carefully about what target metric or KPI is mentioned in the final turn. Then, output the name of the metric in short and long form.
More specifically, the long form is the full name of the metric, while the short form is the industry standard abbreviation. Common metrics include:
  * Abandonment Rate (Abandon)
  * Average Revenue per User (ARPU)
  * Average Order Value (AOV)
  * Attribution Modeling (Attribute)
  * Bounce Rate (Bounce)
  * Customer Churn Rate (Churn)
  * Customer Acquisition Cost (CAC)
  * Cost per Acquisition (CPA)
  * Cost per Click (CPC)
  * Cost per Mille (CPM)
  * Click-Through Rate (CTR)
  * Conversion Rate (CVR)
  * Daily Active Users (DAU)
  * Device Ratio (Device)
  * Engagement Rate (Engage)
  * Purchase Frequency (Freq)
  * Inactive Users (Inactive)
  * Customer Lifetime Value (LTV)
  * Monthly Active Users (MAU)
  * Monthly Recurring Revenue (MRR)
  * Net Promoter Score (NPS)
  * Email Open Rate (Open)
  * Net Profit (Profit)
  * Return on Ad Spend (ROAS)
  * Return on Investment (ROI)
  * Retention Rate (Retain)
  * Time to Resolution (TTR)

As seen above, not every metric has a standard acronym. In such cases, please select a single token that best represents the metric.
When deciding on the short form, make sure it is *short* as the name implies, which means no longer than seven characters.
If the user refers to calculating a metric, but does not explicitly mention the name, then output 'unsure' for both the short and long form.
Alternatively, if the user is not referring to a metric at all, but simply wants to perform a basic query, then output 'none' for short and long form.

Please start by formulating a brief thought on the user's request. Then, decide on the acronym and full name of the metric.
Your entire response should be in well-formatted JSON including keys for thought (string), long (string), and short (single token), with no further explanations after the JSON output.

For example,
#############
User: What was the total profit margin on GA for last week?
Agent: The total profit margin on GA for last week was $2,611.
User: What about for Bing?

_Output_
```json
{{
  "thought": "profit margin is abbreviated as Profit",
  "long": "Net Profit",
  "short": "Profit"
}}
```

User: What is our highest click-thru rate across all social media campaigns?
Agent: The highest click-thru rate is 3.2%.
User: What is the most common device used for these campaigns?

_Output_
```json
{{
  "thought": "user mentioned CTR, but the final turn is about Device",
  "long": "Device Ratio",
  "short": "Device"
}}
```

User: Show me all our active channels in the past six months.
Agent: Sure, here you go. See the table for details.
User: How have paid channels been doing in that time? Are they converting better than organic?

_Output_
```json
{{
  "thought": "conversion rate is abbreviated as CVR",
  "long": "Conversion Rate by Channel",
  "short": "CVR"
}}
```

User: What is the average revenue per user for these lost users?
Agent: In order to calculate ARPU, we need to know the total revenue. I see a column called UnrealizedRevenue, is that the right one?
User: Actually, you can calculate total revenue by summing the columns SubscriptionPayments and LateFees.

_Output_
```json
{{
  "thought": "user mentioned ARPU, but the final turn is about total revenue, which is not a metric",
  "long": "unsure",
  "short": "unsure"
}}
```

User: What is the average CPM for our paid channels?
Agent: The average CPM in the past month is 2.5%.
User: Can you show me the highest one?

_Output_
```json
{{
  "thought": "the highest one is a co-reference to CPM",
  "long": "Cost per Mille",
  "short": "CPM"
}}
```

User: How many conversions have we had from the security and privacy campaign?
Agent: The security and privacy campaigns has led to 1,405 conversions.
User: How have those users stayed with us over time?

_Output_
```json
{{
  "thought": "staying with us over time refers to user retention",
  "long": "Retention Rate",
  "short": "Retain"
}}
```

User: So we have all these new accounts coming in from LinkedIn
Agent: Yes, we have 1,405 new accounts from LinkedIn in the past month.
User: What is the average acquistition cost for these new accounts?

_Output_
```json
{{
  "thought": "acquisition cost translates to CAC",
  "long": "Customer Acquisition Cost",
  "short": "CAC"
}}
```

User: What if we break down the ROI by channel?
Agent: The channels with the highest ROI are Instagram, Facebook, and Snapchat.
User: How many clicks did we get from each of those channels?

_Output_
```json
{{
  "thought": "although conversation mentions ROI, the final turn is about clicks, which is just an aggregate query rather than a metric",
  "long": "none",
  "short": "none"
}}
```

User: How any total emails were viewed for the Bountiful Harvest campaign?
Agent: A total of 617 emails have been viewed.
User: How many views did we get on the Soft Touch drip campaign.

_Output_
```json
{{
  "thought": "email views are equivalent to open rate",
  "long": "Email Open Rate",
  "short": "Open"
}}
```

User: Interesting, how many people have actually enrolled in classes in that time?
Agent: According to the class_dates from the last three months, there are 1,023 people who have enrolled in classes.
User: How is that possible when there are only 574 active members?
Agent: Apologies for the confusion. I see that there are 1,023 enrollments, but many of those are double counting the same person. I will need to find unique enrollments somehow, any ideas?
User: Let's go a different route, let's find the members who joined in the past quarter, but have not enrolled in any classes.

_Output_
```json
{{
  "thought": "main goal is to find members who joined in the past quarter but have not enrolled in any classes",
  "long": "Active Members without Enrollments",
  "short": "Active"
}}
```

User: How many users are visiting our app each day?
Agent: We have 34,676 daily active users.
User: How about on a monthly basis?

_Output_
```json
{{
  "thought": "converting daily active users to monthly basis becomes monthly active users",
  "long": "Monthly Active Users",
  "short": "MAU"
}}
```

User: How many active campaigns do we have running in this account?
Agent: There are 12 active campaigns running in the Royal Diamond account.
User: Can we calculate the customer lifetime value for these campaigns?

_Output_
```json
{{
  "thought": "customer lifetime value is abbreviated as LTV",
  "long": "Customer Lifetime Value",
  "short": "LTV"
}}
```
#############
Please return the target metric in long form as a full name and short form as a single token. When in doubt, return 'unsure' for both.
In all cases, do not output any text other than the JSON object. For additional context, the available columns are:
{columns}

Now it's your turn! What is the target metric or KPI in the final user turn of the following conversation snippet?

{history}

_Output_
"""

segment_metric_prompt = """Given the conversation history, think carefully about what target metric or KPI is mentioned in the final turn. Then, output the name of the metric in short and long form.
More specifically, the long form is the full name of the metric, while the short form is the industry standard abbreviation. Common metrics include:
  * Abandonment Rate (Abandon)
  * Average Revenue per User (ARPU)
  * Average Order Value (AOV)
  * Attribution Modeling (Attribute)
  * Bounce Rate (Bounce)
  * Customer Churn Rate (Churn)
  * Customer Acquisition Cost (CAC)
  * Cost per Acquisition (CPA)
  * Cost per Click (CPC)
  * Cost per Mille (CPM)
  * Click-Through Rate (CTR)
  * Conversion Rate (CVR)
  * Daily Active Users (DAU)
  * Device Ratio (Device)
  * Engagement Rate (Engage)
  * Purchase Frequency (Freq)
  * Inactive Users (Inactive)
  * Customer Lifetime Value (LTV)
  * Monthly Active Users (MAU)
  * Monthly Recurring Revenue (MRR)
  * Net Promoter Score (NPS)
  * Email Open Rate (Open)
  * Net Profit (Profit)
  * Return on Ad Spend (ROAS)
  * Return on Investment (ROI)
  * Retention Rate (Retain)
  * Time to Resolution (TTR)

As seen above, not every metric has a standard acronym. In such cases, please select a single token that best represents the metric.
When deciding on the short form, make sure it is *short* as the name implies, which means no longer than seven characters.
If the user refers to calculating a metric, but does not explicitly mention the name, then output 'unsure' for both the short and long form.
Alternatively, if the user is not referring to a metric at all, but simply wants to perform a basic query, then output 'none' for short and long form.

Please start by formulating a brief thought on the user's request. Then, decide on the acronym and full name of the metric.
Our situation can be tricky because the user may request to filter the metric by a specific time period, segment it by a specific channel, or break it down by some other dimension.
We should ignore those details and focus on finding just the metric itself.
Your entire response should be in well-formatted JSON including keys for thought (string), long (string), and short (single token), with no further explanations after the JSON output.

For example,
#############
User: What was the total profit margin on GA for last week?
Agent: The total profit margin on GA for last week was $2,611.
User: What about for Bing?

_Output_
```json
{{
  "thought": "profit margin is abbreviated as Profit",
  "long": "Net Profit",
  "short": "Profit"
}}
```

User: What is our highest click-thru rate across all social media campaigns?
Agent: The highest click-thru rate is 3.2%.
User: What is the most common device used for these campaigns?

_Output_
```json
{{
  "thought": "user mentioned CTR, but the final turn is about Device",
  "long": "Device Ratio",
  "short": "Device"
}}
```

User: Show me all our active channels in the past six months.
Agent: Sure, here you go. See the table for details.
User: What are their conversion rates during that time?

_Output_
```json
{{
  "thought": "conversion rate is abbreviated as CVR",
  "long": "Conversion Rate",
  "short": "CVR"
}}
```

User: What is the average revenue per user for these lost users?
Agent: In order to calculate ARPU, we need to know the total revenue. I see a column called UnrealizedRevenue, is that the right one?
User: Actually, you can calculate total revenue by summing the columns SubscriptionPayments and LateFees.

_Output_
```json
{{
  "thought": "user mentioned ARPU, but the final turn is about total revenue, which is not a metric",
  "long": "unsure",
  "short": "unsure"
}}
```

User: What is the average CPM for our paid channels?
Agent: The average CPM in the past month is 2.5%.
User: Can you show me the highest one?

_Output_
```json
{{
  "thought": "the highest one is a co-reference to CPM",
  "long": "Cost per Mille",
  "short": "CPM"
}}
```

User: How many conversions have we had from the security and privacy campaign?
Agent: The security and privacy campaigns has led to 1,405 conversions.
User: How have those users stayed with us over time?

_Output_
```json
{{
  "thought": "staying with us over time refers to user retention",
  "long": "Retention Rate",
  "short": "Retain"
}}
```

User: So we have all these new accounts coming in from LinkedIn
Agent: Yes, we have 1,405 new accounts from LinkedIn in the past month.
User: What is the average acquistition cost for these new accounts?

_Output_
```json
{{
  "thought": "acquisition cost translates to CAC",
  "long": "Customer Acquisition Cost",
  "short": "CAC"
}}
```

User: What if we break down the ROI by channel?
Agent: The channels with the highest ROI are Instagram, Facebook, and Snapchat.
User: How many clicks did we get from each of those channels?

_Output_
```json
{{
  "thought": "although conversation mentions ROI, the final turn is about clicks, which is just an aggregate query rather than a metric",
  "long": "none",
  "short": "none"
}}
```

User: How any total emails were viewed for the Bountiful Harvest campaign?
Agent: A total of 617 emails have been viewed.
User: How many views did we get on the Soft Touch drip campaign.

_Output_
```json
{{
  "thought": "email views are equivalent to open rate",
  "long": "Email Open Rate",
  "short": "Open"
}}
```

User: those aren't a problem
Agent: OK, I will ignore those outliers moving forward.
User: What is the average order value for each campaign?

_Output_
```json
{{
  "thought": "average order value is abbreviated as AOV",
  "long": "Average Order Value",
  "short": "AOV"
}}
```

User: How many users are visiting our app each day?
Agent: We have 34,676 daily active users.
User: How about on a monthly basis?

_Output_
```json
{{
  "thought": "converting daily active users to monthly basis becomes monthly active users",
  "long": "Monthly Active Users",
  "short": "MAU"
}}
```

User: Which channels have the worst conversion rates?
Agent: Bing, CJ and Tiktok have the worst conversion rates recently.
User: Can we calculate the customer lifetime value from these channels?

_Output_
```json
{{
  "thought": "customer lifetime value is abbreviated as LTV",
  "long": "Customer Lifetime Value",
  "short": "LTV"
}}
```
#############
Please return the target metric in long form as a full name and short form as a single token. When in doubt, return 'unsure' for both.
In all cases, do not output any text other than the JSON object. For additional context, the available columns are:
{columns}

Now it's your turn! What is the target metric or KPI in the final user turn of the following conversation snippet?

{history}

_Output_
"""