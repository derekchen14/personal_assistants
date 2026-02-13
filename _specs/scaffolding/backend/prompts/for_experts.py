intent_prompt = """Given the utterance, predict the intent: Analyze, Visualize, Clean, Transform, Detect, Converse.
The intents are defined as follows:
  * Analyze - queries the spreadsheet for analysis without altering the underlying data. Common operations include filter, group, pivot table or sort. Analyze also includes calculation of metrics, such as LTV, CVR, retention, CPC, or CTR.
  * Visualize - covers creation and management of charts, graphs, or figures for reporting purposes. This also includes anything related to dashboards or any design elements of the spreadsheet.
  * Clean - relates to modifying the spreadsheet data by updating values. This includes resolving standardizing formats, validating content, setting datatypes, and removing duplicates. These typically operate on the data in-place.
  * Transform - changes the shape or structure of the spreadsheet by inserting or deleting data. This also includes splitting or merging columns, connecting data across tables, and generally moving data around.
  * Detect - inspects the data to uncover potential issues, insights, or integrations. Common issues include outliers, anomalies, typos, or null values. Usually more generic in nature, requiring the agent to gather metadata or propose a plan before proceeding. The context matters, where either user or agent can be raising issues to fix.
  * Converse - intent includes chit chat, informing the agent about preferences, ignoring or confirming agent suggestions. Also includes requesting clarification, positive reactions, and expressing dissatisfaction. Normally, the user is not trying to accomplish anything, and from the conversation history, no data work like fixing or transforming is needed.

Please think carefully about the user's intent and choose the most appropriate option from the six (6) options.
If the user's intent is to continue the previous intent, please output the same intent as the previous turn, which is {previous_intent}.
Your entire response should be in well-formatted JSON including a thought (a sentence or two) and target (single token), with no further explanations before or after the output.

For example,
#############
User: How many visitors came to the fall fashion landing page each day last week?
_Output_
```json
{{
  "thought": "Querying the data is clearly a type of analysis.",
  "target": "Analyze"
}}
```

User: Can we align the ads data from Google and Facebook together somehow?
_Output_
```json
{{
  "thought": "Connecting data from two ad platforms alters the structure of the data, so this is Transform.",
  "target": "Transform"
}}
```

User: Can you change all channels tagged as ga into Google Analytics?
_Output_
```json
{{
  "thought": "Changing the underlying values is Clean.",
  "target": "Clean"
}}
```

User: Show me a breakdown of traffic by channel and also by day, only from social media
_Output_
```json
{{
  "thought": "The user wants to see a graphical representation of the data, so this is Visualize.",
  "target": "Visualize"
}}
```

User: Get rid of all customer rows that don't have a valid last name.
_Output_
```json
{{
  "thought": "Removing invalid rows is a type of cleaning.",
  "target": "Clean"
}}
```

User: Is there any column related to revenue?
_Output_
```json
{{
  "thought": "The user is asking about the data without altering it, so this is Analyze.",
  "target": "Analyze"
}}
```

User: lemme see that as a bar chart instead, with the top 5
_Output_
```json
{{
  "thought": "The user wants to change the graphical representation, so this is Visualize.",
  "target": "Visualize"
}}
```

User: There are a bunch of empty cells in the data we need to take care
_Output_
```json
{{
  "thought": "Identifying issues, such as blank, null or empty values, is a type of detection.",
  "target": "Detect"
}}
```

User: The row is related to money, so there should be two decimals
_Output_
```json
{{
  "thought": "Updating the values is a type of cleaning.",
  "target": "Clean"
}}
```

User: Add a column that calculates the net profit by subtracting the payment processing fees from the account balance
_Output_
```json
{{
  "thought": "Adding a new column is a type of transformation.",
  "target": "Transform"
}}
```

User: Oh, that's wonderful!
_Output_
```json
{{
  "thought": "The data is not relevant to the task at hand, so we are conversing.",
  "target": "Converse"
}}
```

User: Can we connect the email campaign data with the social media data?
_Output_
```json
{{
  "thought": "Connecting two sources of data is a type of transformation.",
  "target": "Transform"
}}
```

User: How big is the orders table?
_Output_
```json
{{
  "thought": "The user is asking about the data without altering it, so this is Analyze.",
  "target": "Analyze"
}}
```

User: what anomalies are you talking about?
_Output_
```json
{{
  "thought": "Detecting issues, such as numeric outliers or textual anomalies, is a Detect operation.",
  "target": "Detect"
}}
```

User: our CRM is filled with few duplicates entries, it's a mess right now
_Output_
```json
{{
  "thought": "Removing duplicate entries is a type of cleaning.",
  "target": "Clean"
}}
```

User: Help me calcuate the ROAS for all Meta Ads campaigns
Agent: I notice there are Mta_ads, metta_ads, and meta_ads tables, should these typos be fixed or grouped together?
User: I think we should group them as meta_ads.
_Output_
```json
{{
  "thought": "Agent raised issues like typos and the users is confirming the agent's suggestions, which means this is a Detect operation as we are fixing detected issues.",
  "target": "Detect"
}}
```

User: I need to know the ROAS for our most recent campaign, the one with the flowers
_Output_
```json
{{
  "thought": "Calculating metrics does not change the underlying data, so this is Analyze.",
  "target": "Analyze"
}}
```

User: Give me an update to the numbers on this report once every two weeks.
_Output_
```json
{{
  "thought": "Requests related to reporting are all Visualize.",
  "target": "Visualize"
}}
```

User: What can you do? Who made you?
_Output_
```json
{{
  "thought": "FAQ questions are unrelated to the data, so this is a type of conversation.",
  "target": "Converse"
}}
```

User: Can we split by the dates by '/'?
_Output_
```json
{{
  "thought": "Splitting a column transforms the structure of the table, so this is Transform.",
  "target": "Transform"
}}
```

User: Which one of our A/B tests is performing the best so far?
_Output_
```json
{{
  "thought": "The user is asking about the data without altering it, so this is Analyze.",
  "target": "Analyze"
}}

User: Can you make a pivot table for the sales made in different age groups?
_Output_
```json
{{
  "thought": "The user want a pivot table, which does not change underlying data, so it is Analyze.",
  "target": "Analyze"
}}
```

User: Bread down the employee data by their department and job title?
_Output_
```json
{{
  "thought": "The user want a breaddown, which is a pivot table. It does not change underlying data, so it is Analyze.",
  "target": "Analyze"
}}
```

User: What do you think this dip in the graph means?
_Output_
```json
{{
  "thought": "The word 'graph' implies a visualization, so this is Visualize.",
  "target": "Visualize"
}}
```

User: Please join the first and last name columns into a new column
_Output_
```json
{{
  "thought": "Merging the first and last name columns changes the structure of the table, so this is Transform.",
  "target": "Transform"
}}
```

User: Please plot the best selling products from last quarter by gross margin
_Output_
```json
{{
  "thought": "The word 'plot' implies a visualization, so this is Visualize.",
  "target": "Visualize"
}}
```

User: they should actually all be in lowercase
_Output_
```json
{{
  "thought": "Changing the underlying values is Clean.",
  "target": "Clean"
}}
```

User: What interesting information can we gather from our website traffic data?
_Output_
```json
{{
  "thought": "Generic requests for insights within the data require creating a plan, so these are Detect.",
  "target": "Detect"
}}
```

User: That doesn't look good, let's go back a step
_Output_
```json
{{
  "thought": "Going back a step changes the values back to the previous state, so this is Clean.",
  "target": "Clean"
}}
```

User: I'm curious about the results of our customer surveys, but it's not very clean. Can you help me fix it?
_Output_
```json
{{
  "thought": "Generic requests to fix or connect data require creating a plan, so these are Detect.",
  "target": "Detect"
}}


User: Help me sort the prices by the highest to lowest.
Agent: Sure, I noticed there are some null values in the price column, should we fix them first?
User: Yes, please.
_Output_
```json
{{
  "thought": "Agent noticed there are some null values in the price column, and user is confirming the agent's suggestions. They are fixing the issue, so this is a Detect operation.",
  "target": "Detect"
}}
```

User: Let's just forget about those for now.
Agent: Ok, I will ignore those months with missing data.
User: Which campaigns have a conversion rate above 5%? And how many clicks did they get?
_Output_
```json
{{
  "thought": "I can see conversion rate (CVR) as part of the request as what the user want next, so I know this is a Analyze operation to return data.",
  "target": "Analyze"
}}
```

User: What was the total spend on GA for last week?
Agent: The total spend on GA for last week was $1,509.
User: Can we save these results for future reference?
_Output_
```json
{{
  "thought": "The user wants to save the data for future reference. This is a materialize operation, which belongs to Analyze.",
  "target": "Analyze"
}}
```

User: Can you graph the total clicks and impressions for each day last week?
Agent: Ok, done. How does this look?
User: yea, can I get these metrics pulled on a daily basis?
_Output_
```json
{{
  "thought": "After graphing, the user asks for a recurring report, so this is still part of the Visualize operation. I can cross reference {previous_intent} to confirm this.",
  "target": "Visualize"
}}
```

User: Can you give me a breakdown of our Boston user engagement?
Agent: In the data, I see 'Boston', 'boston', and 'Beantown'. Should these be treated as 'Boston'?
User: Yes, change to Boston.
_Output_
```json
{{
  "thought": "The user agreed with the agent's suggestion to merge similar terms, so this is a Clean operation.",
  "target": "Clean"
}}
```

User: Calculate the CLV for each customer.
Agent: In the data, I there are some null values in the customer_id column, should we fix them first?
User: No, we don't care about those for now.
_Output_
```json
{{
  "thought": "The user disagreed with the agent's suggestion to fix and want to continue with the operation which is Analyze. We can cross reference {previous_intent} to confirm this.",
  "target": "Analyze"
}}
```

User: Calculate the CLV for each customer.
Agent: In the data, I there are some null values in the customer_id column, should we fix them first?
User: Yes, let's delete those rows.
_Output_
```json
{{
  "thought": "The user agree with the agent's proposal to delete the rows with null values, so this is a Clean operation.",
  "target": "Clean"
}}
```

#############
Now it's your turn. Please rethink your answer to make sure the response is correct. Use the conversation context and focus on the last utterance from the user and refer the conversation history to understand what the user is trying to accomplish. Only output the JSON.

{history}
_Output_
"""

continuation_snippet = """Your first decision is simply whether the current turn is a continuation of previous analysis, or a new direction.
When the user is answering a clarification question posed by the agent, you should just carry over the existing target, which is '{dialog_act}'.
This is quite likely since a user rarely abandons a previous plan of action. With that said, the user may change their mind, so let's also discuss the other range of other options.
"""

analyze_prompt = """Given the conversation history, your task is to determine the target scope of the analysis presented in the user's request.
Specifically, there are nine (9) possible targets we could be facing: describe, exist, query, measure, pivot, segment, insight, materialize, or visualize.
{continuation}

Most of the time, you need to decide whether the request is for a simple query, pivot table, basic metric, multi-step analysis, or insight detection:
  * query: retrieve data from a table by filtering, grouping, sorting, or applying aggregation operations directly on existing columns
    - common aggregations include sum, count, average, min, max, or string_agg
  * pivot: reorganize data to show different views, which requires at least three operations, one of which must be grouping by some dimension
    - valid operations include filtering, grouping, or applying aggregations such as sum, count, average, or string_agg
    - notably, sorting and limiting rows (ie. top 3, bottom 10%, min/max) are not considered operations since they don't change data structure
    - if the phrase 'pivot table' is used or there is an explicit request to create a new table, then we are definitely dealing with 'pivot'
  * measure: calculate a new metric that involves subtracting, adding, multiplying, or dividing more than one column. Common examples include:
    - Marketing Efficiency: Return on Ad Spend (ROAS), Click-Through Rate (CTR), Cost Per Click (CPC), Cart Abandonment Rate, Cost per Mille (CPM)
    - User Engagement: Bounce Rate, Daily Active Users (DAU), Monthly Active Users (MAU), Device Statistics, Net Promoter Score (NPS), Churn Rate, Retention Rate (Retain)
    - Conversion: Conversion Rate (CVR), Signup Rate, Purchase Frequency (Frequency),  Email Open Rate (Open), Customer Acquisition Cost (CAC)
    - Revenue: Average Order Value (AOV), Average Revenue Per User (ARPU), Customer Lifetime Value (LTV), Monthly Recurring Revenue (MRR), Net Profit (Profit)
  * segment: perform analysis involving metric segmentation by inserting staging columns before reaching the final answer
  * insight: open-ended exploration of the data to identify patterns or trends, anything associated with calculating multiple metrics
    - also includes any generic requests for insights within the data, such as 'Anything interesting in this data?'

Additional scenarios include:
  * describe: summary statistics or characteristics of the data, such as number of rows or columns, average of the column, range of values in the column, or the most common values in a column
  * exist: checking if a specific column or value exists in the data
  * materialize: save a temporary table or view for future reference, typically after a complex query or metric calculation
  * visualize: create a figure, chart or diagram from the data in addition to the query. This includes any design elements or formatting of the spreadsheet.

Suppose you want to calculate the conversion rate (CVR) for an E-commerce website:
  * if we just wanted to know the number of rows in the table, then we are describing the data.
  * if we instead wanted to know if a 'conversion' column exists, then we are checking for existence.
  * if there already exist columns for 'conversions' and 'visits', then we can directly calculate CVR = conversions / visits, which is a simple query.
  * if we want conversions per day from FB Ads, then this requires grouping by day, filtering by channel, and aggregating the sum of conversions. Given three operations, we graduate from query to pivot.
  * if we need to calculate conversions by first pulling from other columns (ie. filter for the 'purchase' event type where 'purchase amount > 0'), then we are measuring a metric.
  * if we wanted to break down the conversion rate by day or segment it by IP address, then we are performing a segmentation analysis.
  * if we wanted to save the results for future reference, then we are materializing the data.
  * if our goal is to find the most effective channel, then we might consider CTR and CPC along with CVR. This is more than one metric, which implies insight detection.
  * if we wanted to create a chart or graph to visualize the conversion rate, then we are visualizing the data.

Other considerations:
  * By default, everything is a 'query', so we should only consider the other targets if the user request requires some intermediate calculations.
  * Generally speaking, 'pivot' is the next level of complexity after 'query' due to grouping, while 'segment' can be viewed as the next level after 'measure' due to segmentation
  * 'insight' comes into play when things have gotten so complicated that we need to form a plan involving multiple other targets to find the answer
  * If the prior thought or metric name are empty or TBD, do not panic! Just consider the conversation history and make an informed decision.

Please start by looking for the prior target. If it is not empty, then that is strong evidence that the current target is the same.
Moving on, consider whether the metric can be pulled from the table by aggregating the values in a single column. If so, then we are dealing with a 'query'.
Next, if the metric requires three or more operations where at least one is grouping, then we are dealing with a 'pivot'.
Alternatively, if the metric requires dividing or subtracting the values from multiple columns, then we are dealing with an 'measure'.
Then, consider if we need to categorize or bucket the metric based on along some dimension. If so, then we are dealing with a 'segment'.
Finally, consider if the there are actually multiple metrics being calculated or other vagueness. If so, then we are dealing with an 'insight'.
If we aren't querying from the table, we might be checking for existence, describing the data, or visualizing it.
Lastly, if we are saving the results for future reference, then we are materializing the data.
If none of the above apply, possibly because no metric can be inferred from the context, then we set the target to 'unsure'.
Your entire response should be in well-formatted JSON including keys for thought (string) and target (single token), with no further explanations after the JSON output.

For example,
---
Prior target: query
User: what's the average number of purchases made by users who bought something last week?
Agent: Out of 173 users who bought something recently, they have made 1.4 purchases on average.
User: Can we break this down by channel? I'd like to see if there are any differences.

_Output_
```json
{{
  "thought": "In the previous turn, we aggregated the purchase count, and filtered for recent users. We are now adding a grouping operation for channel, so this becomes a pivot.",
  "target": "pivot"
}}
```

Prior target: query
User: What was the revenue on our newsletter the last month?
Agent: The revenue from the newsletter the last month was $62,135.
User: How does that compare to our costs that month?

_Output_
```json
{{
  "thought": "Asking for just revenue is a query, but comparing to costs is ROAS or Profit, which requires multiple columns, so this is measuring a metric.",
  "target": "measure"
}}
```

Prior target: query
User: There's so many cities in this data, how many are there?
Agent: Sure, which cities are you interested in?
User: Show me a breakdown of the costs by city.

_Output_
```json
{{
  "thought": "A cost breakdown can be best visualized in a graph.",
  "target": "visualize"
}}
```

Prior target: describe
User: How big is the Marketo_Conversions table?
Agent: The Marketo_Conversions table has 34,127 rows and 12 columns.
User: Which ad sets have the highest conversion rates?

_Output_
```json
{{
  "thought": "Conversion rate is a metric, but we are also segmenting it by ad set, so this is segmentation analysis.",
  "target": "segment"
}}
```

Prior target: ignore
User: Let's just forget about those for now.
Agent: Ok, I will ignore those months with missing data.
User: Which campaigns have a conversion rate above 5%? And how many clicks did they get?

_Output_
```json
{{
  "thought": "I can see conversion rate (CVR) as part of the request, so I know this is a metric.",
  "target": "measure"
}}
```

Prior target: ignore
User: Let's just forget about those for now.
Agent: Ok, I will ignore those months with missing data.
User: Which campaigns have a conversion rate above 5%? And what is their return on ad spend?

_Output_
```json
{{
  "thought": "I can see return on ad spend (ROAS) and conversion rate (CVR) as part of the request, which is more than one metric, so this is an insight.",
  "target": "insight"
}}
```

Prior target: pivot
User: That's interesting, can we group by the location and see the total subscriptions for each region?
Agent: Yes, the results are in the table. What do you think?
User: Ok, let's group by a second dimension targeting just female users.

_Output_
```json
{{
  "thought": "Since we are adding a second dimension to the grouping, this is a pivot operation.",
  "target": "pivot"
}}
```

Prior target: chat
User: So our total ad spend just exploded all of a sudden then.
Agent: yes, it seems there is a 12% increase in clicks. Should we look into it?
User: i first want to know the highest number of clicks we have recorded

_Output_
```json
{{
  "thought": "Maximum counts are a summary statistic, so we are trying to describe the data.",
  "target": "describe"
}}
```

Prior target: chat
User: So our total ad spend just exploded all of a sudden then.
Agent: yes, it seems there is a 12% increase in clicks. Should we look into it?
User: i first want to know the highest clicks we have for each campaign last week

_Output_
```json
{{
  "thought": "We want to know the number of clicks after grouping by campaign, so this is a 'query' rather than 'describe'.",
  "target": "query"
}}
```

Prior target: N/A
User: Anything in this email data you can tell me about that's interesting?

_Output_
```json
{{
  "thought": "This is a generic request for insights or observations.",
  "target": "insight"
}}
```

Prior target: N/A
User: We've been spending too much on ads, do we have any columns related to costs?

_Output_
```json
{{
  "thought": "The user is checking whether a column related to costs exists in the data.",
  "target": "exist"
}}
```

Prior target: query
User: What was the total spend on GA for last week?
Agent: The total spend on GA for last week was $1,509.
User: Can we save these results for future reference?

_Output_
```json
{{
  "thought": "The user wants to save the view for future reference, so we are materializing the view.",
  "target": "materialize"
}}
```

Prior target: measure
User: What is the CTR from the security and privacy campaign?
Agent: The CTR is 9.8%
User: Let's compare the CTR against each step in the funnel, broken down by membership status

_Output_
```json
{{
  "thought": "This is a complex analysis involving the calculation of CTR metric. Given that are are segmenting by membership status, this graduates from 'measure' to a 'segment' analysis.",
  "target": "segment"
}}
```

Prior target: measure
User: What is the average time to purchase?
Agent: When calculating Time to Conversion, should we use the first site visit or the last interaction before purchase?
User: Use the first site visit

_Output_
```json
{{
  "thought": "The user provided information needed to continue with the measurement, thus we should carry over the prior target.",
  "target": "measure"
}}
```
---
Now it's your turn. Please rethink your answer to make sure the response is correct. Use the conversation context and focus on the last utterance from the user.
Predict the target dialogue act in well-formatted JSON. This is very important, the target must come from one of the nine valid options.

Prior target: {prior_target}
{history}

_Output_
"""

visualize_prompt = """Given the recent conversation history, think carefully about what the user is trying to accomplish in the final turn. Then, choose from one of the following dialogue acts:
  1. plot - create a graph, chart, figure, or other visual diagram from the data
  2. trend - apply statistical inference to a figure or diagram, namely trendlines, correlation, or clustering
  3. explain - write out any text to summarize or present information within a chart or figure
  4. report - manage reports, such as pulling the latest numbers or setting a recurring report rhythm
  5. save - save a chart or figure to the dashboard, or saving it as an image to download
  6. design - apply design elements to a figure or chart, such as changing colors, title, fonts, or layout
  7. style - style a table (rather than a figure or chart), such as changing the boldness, background color, or alignment

If none of the above work, please output 'unsure'. In total, this offers 8 options that are exactly one word long.
Your final response should be in well-formatted JSON including a thought (a sentence or two) and target (single token), with no further explanations after the output.

For example,
#############
User: Show me a breakdown of the costs by city.
Agent: Sure, here you go.
User: Can you show that as a line chart?

_Output_
```json
{{
  "thought": "The user wants to visualize the cost breakdown by city, which is clearly plotting the results.",
  "target": "plot"
}}
```

User: Can you graph the total clicks and impressions for each day last week?
Agent: Ok, done. How does this look?
User: yea, can I get these metrics pulled on a daily basis?

_Output_
```json
{{
  "thought": "The user wants to run a recurring analysis on the daily metrics, so this is a 'report'.",
  "target": "report"
}}
```

User: Ok, it seems that the dip in traffic keeps occuring in the middle of each week.
Agent: yes, there is a meaningful drop in traffic during each Wednesday.
User: please write out the main insight below in bulletpoints

_Output_
```json
{{
  "thought": "The user wants to summarize the main insight from the plot.",
  "target": "explain"
}}
```

User: Plot how many pairs were sold in March, broken down by day.
Agent: OK, here's a graph for pairs sold in March.
User: Can you add a 5-day moving average to that?

_Output_
```json
{{
  "thought": "Adding a moving average is an example of trend analysis.",
  "target": "trend"
}}
```

User: So let's include the open rate as a line on the graph.
Agent: No problem, how does this look? 
User: The title is a bit hard to read, can you make it larger?

_Output_
```json
{{
  "thought": "Change the title font size is a design element.",
  "target": "design"
}}
```

User: The title is a bit hard to read, can you make it larger?
Agent: Ok, done. How does this look?
User: Looks great, let's download this chart for the presentation.

_Output_
```json
{{
  "thought": "Downloading the chart is saving the figure.",
  "target": "save"
}}
```

User: please add the ad spend amount to the graph as a red line
Agent: You got it. Please see the graph for details.
User: what is the correlation between ad spend and roas for this campaign?

_Output_
```json
{{
  "thought": "Calculating the correlation is an example of trend analysis.",
  "target": "trend"
}}
```

User: what's the total spend on GA for last week?
Agent: The total spend on GA for last week was $1,509.
User: This is good, can we save this as a permanent table?
Agent: Done. I have created a new table named 'GA_Spend'.
User: Let's make the header rows bold and change the background color to light blue.

_Output_
```json
{{
  "thought": "Changing the background color and bolding rows is styling the table, not the chart.",
  "target": "style"
}}
```


User: So our total clicks just dropped all of a sudden then.
Agent: yes, that seems right. Should we look into it?
User: please summarize these findings so we can share with the team

_Output_
```json
{{
  "thought": "Summarizing findings is asking to explain the results",
  "target": "explain"
}}
```

User: Can you graph the average order value for each campaign?
Agent: The average order value requires a total return column, I found these RankedRevenue and TotalSales columns. Do either of these look right?
User: RankedRevenue col should be good

_Output_
```json
{{
  "thought": "The user specified seeing a AOV as a graph, so this is a 'plot'.",
  "target": "plot"
}}
```

User: Can you display the click through rate for each of the copy variations.
Agent: Sure, here you go.
User: Those colors are terrible, let's go with a darker red for the Property Value line.

_Output_
```json
{{
  "thought": "Changing the color of a line is a design element.",
  "target": "design"
}}
```

#############
Follow the JSON format to predict the target dialogue act. This is very important, the target must come from one of the eight valid options.

{history}

_Output_
"""

clean_prompt = """Given the recent conversation history, think carefully about what the user is trying to accomplish in the final turn. Then, choose from one of the following dialogue acts:
  1. validate - make sure all values belong to a predefined set. For example, all customer payment statuses are exactly 'paid', 'unpaid', or 'refunded' with no variations in spelling or capitalization.
  2. format - standardize the data within the column to conform to a specific format. For example, ensuring all dates are 'mm/dd/yyyy' or all phone numbers follow the 'xxx-xxx-xxxx' format.
  3. pattern - flash fill the cells within a column where each cell is dependent on the previous cell above it. For example, copying down the first non-empty value to fill any blank cells beneath it.
  4. dedupe - remove duplicates, such as merging duplicate users from a CRM or eliminating repeat entries from a log file.
  5. datatype - assign the data type of the column to a specific type or subtype, such as text, number, date or location.
  6. impute - fill in missing values based on a formula or mapping. Formula can include interpolation, taking the median, or a custom relationship. Mapping serves as static lookups, such as matching city to state.
  7. insert - adding a new column or row to a table that contains new data or a calculated formula
  8. update - changing existing cells, such as trimming whitespace, lowercasing, or find and replace operations.
  9. delete - removing or hiding rows or columns, often based on some filtering criteria
  10. undo - revert the most recent change(s) or going back a step

When choosing the dialogue act, prefer the option that is more specific over the more general one. For example, if the user is removing duplicates, choose 'dedupe' over 'delete'.
Similarly, if a user wants to set all the states to uppercase with exactly two letters, choose 'format' over 'update'.
Going even further, if the user has explicitly listed the list of valid states to choose from, choose 'validate' over 'format'.

If none of the above work, please output 'unsure'. In total, this offers 11 options that are exactly one word long.
Your final response should be in well-formatted JSON including a thought (a sentence or two) and target (single token), with no further explanations after the output.

For example,
---
User: we can rename the domain into 'Companies'
Agent: Ok, done.
User: Let's trim this down to unique companies only

_Output_
```json
{{
  "thought": "The user wants to clean up the data by removing duplicates.",
  "target": "dedupe"
}}
```

User: Was there any purchases from newsletter customers in the last week?
Agent: There were 74 purchases from newsletter customers.
User: Can we add a column for calculating the profit for these users?

_Output_
```json
{{
  "thought": "Adding a column for profit calculation is an 'insert'.",
  "target": "insert"
}}
```

User: I need to standardize the categories in the 'Product Category' column.
Agent: Sure, what kind of cleaning did you have in mind?
User: I want to change all instances of 'Electronics' to 'Electrical' and 'Clothing' to 'Apparel'.

_Output_
```json
{{
  "thought": "Standardizing values in the 'Product Category' column is akin to a find and replace operation, which involves updating existing values.",
  "scope": "update"
}}
```

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

User: What's in the sing-ups table?
Agent: The Sign-Ups table includes user_id, name, signup_date, email, is_verified, is_active, role, preferences, profile_image, social_id
User: Can we make sure that all signup dates follow MM/DD/YYYY

_Output_
```json
{{
  "thought": "The user wants to standardize the date format",
  "target": "format"
}}
```

User: yes, let's take a look.
Agent: Ok, as you can see. The 'Unnamed:0' column is mostly blank.
User: Please get rid of this Unnamed column

_Output_
```json
{{
  "thought": "The user wants to remove a column, so this is a 'delete'.",
  "target": "delete"
}}
```

User: Please remove all users which don't have a last name.
Agent: Certainly, I have removed all users without a last name.
User: Sorry, take that back, can I get a count of those users instead?

_Output_
```json
{{
  "thought": "The user wants to undo the deletion of users without a last name.",
  "target": "undo"
}}
```

User: Do we have customres who are from 5 miles of store? Based on street address.
Agent: I see a 'store address' and 'street address' column, but I do not see a 'distance' column. Am I missing something?
User: ok, so first, change all places ending with avenue or Ave. into Avenue

_Output_
```json
{{
  "thought": "The user wants to standardize the address format to be title-case and spelled out without abbreviations.",
  "target": "format"
}}
```

User: Show me all accounts with a late payment over $1000.
Agent: Apologies, I can't seem to find any accounts payment dates to determine lateness.
User: The overdue accounts column lets you know based on the binary value. They're not just strings.

_Output_
```json
{{
  "thought": "Verifying the type of the column as boolean values is a 'datatype'.",
  "target": "datatype"
}}
```

User: yes, that looks good.
Agent: Great, I have created the JointAttribution column.
User: Fill in the missing attribution methods using the last known value from above it

_Output_
```json
{{
  "thought": "Filling in missing values is a 'pattern' operation.",
  "target": "pattern"
}}
```

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
---
Follow the JSON format to predict the target dialogue act. This is very important, the target must come from one of the eleven valid options.

{history}

_Output_
"""

transform_prompt = """Given the recent conversation history, think carefully about how the user is trying to manipulate the data in the final turn. Then, choose from one of the following dialogue acts:
  1. update - change existing cells, such as trimming whitespace, interpolating new values, or find and replace operations.
  2. delete - removing or hiding rows or columns, often based on some filtering criteria
  3. transpose - transpose columns into rows, or vice versa, includes rotating an axis within a graph or figure
  4. move - cut and paste values (usually columns) in order to move them around from one place to another
  5. split - split a single column into multiple ones based on a delimiter (ie. text-to-columns) or splitting a list of values into a multiple boolean columns
  6. join - joining two tables together for data integration, likely involves cleaning along the way
  7. append - a special case of joining tables where both table share the same columns so they can be concatenated vertically
  8. merge - compare or concatenate multiple columns together. Always involves at least two or more source columns. The target often copies content directly from the source
  9. insert - add a target column or row through assignment or calculation. Unlike 'merge', the target values for 'insert' are derived from user specified rules or formulas
  10. call - call an external API to retrieve a content for a new table or view
  11. materialize - save a temporary view from a query into a permanent table for future reference

If none of the above work, please output 'unsure'. In total, this offers 12 options that are exactly one word long.
Your final response should be in well-formatted JSON including a thought (a sentence or two) and target (single token), with no further explanations after the output.

For example,
#############
User: Which tables do we have to work with?
Agent: The available tables in this spreadsheet are HubSpot, Salesforce, Mailchimp and Amplitude
User: Ok, we need to join together the Hubspot and Salesforce results

_Output_
```json
{{
  "thought": "joining together two tables is a 'join' operation.",
  "target": "join"
}}
```

User: Is there a column for address? I can't seem to find it.
Agent: Yes, there is a column called 'Address' in the Purchases table.
User: Please move the addresses into the Customers table instead.

_Output_
```json
{{
  "thought": "moving a column is obviously a 'move' operation.",
  "target": "move"
}}
```

User: Was there any purchases from newsletter customers in the last week?
Agent: There were 74 purchases from newsletter customers.
User: Can we add a column for calculating the profit for these users?

_Output_
```json
{{
  "thought": "The values are calculated from a basic formula, so this is an 'insert'.",
  "target": "insert"
}}
```

User: Can I take a look at the activities table?
Agent: Absolutely, here you go.
User: There should be no spaces in the columns, let's change them to underscores.

_Output_
```json
{{
  "thought": "Replacing spaces with underscores is a find and replace operation, which falls under 'update'.",
  "target": "update"
}}
```

User: yes, let's take a look.
Agent: Ok, as you can see. The 'Unnamed:0' column is mostly blank.
User: Please get rid of this Unnamed column

_Output_
```json
{{
  "thought": "Getting rid of a column is a 'delete' operation.",
  "target": "delete"
}}
```

User: Can you group these by city instead?
Agent: We don't seem to have an column for 'city'. Is there something I'm missing?
User: Divide the address column into street, city, state and zip

_Output_
```json
{{
  "thought": "Dividing the address into multiple columns is splitting the column.",
  "target": "split"
}}
```

User: So there are three columns for shopping, called HasArrived, HasBought, HasReturned.
Agent: Yes, here they are.
User: Let's combine together them into a single column called ShoppingState. So if the user HasArrived and HasBought, then the column will include 'arrived, bought'.

_Output_
```json
{{
  "thought": "Combining the content of multiple columns is a 'merge' operation.",
  "target": "merge"
}}
```

User: This column has first name, last name, payment amount and customer status every four rows.
Agent: Ok.
User: Can we stack every four rows new entry into four new columns?

_Output_
```json
{{
  "thought": "Stacking rows into columns will transpose the data.",
  "target": "transpose"
}}
```

User: What's the breakdown of the sign-ups per month for users who saw the Hall of Fame campaigns?
Agent: There were 614 sign-ups in January, 541 in February, and 689 in March. See table for more details.
User: Can we keep this to view later?

_Output_
```json
{{
  "thought": "Saving a table is a 'materialize' operation.",
  "target": "materialize"
}}
```

User: And how many rows does the CRM data include?
Agent: The Hubspot table includes 26,169 rows while the Salesforce table includes 24,512 rows.
User: Let's create a 360 customer profile with all these rows combined.

_Output_
```json
{{
  "thought": "Assuming the two tables have the same columns, creating a joint table by combining rows is an 'append' operation.",
  "target": "append"
}}
```

User: Do we have customres who are from 5 miles of store? Based on street address.
Agent: I see a 'store address' and 'street address' column, but I do not see a 'distance' column. Am I missing something?
User: ok, so first, change all places ending with Avenue into Ave. instead

_Output_
```json
{{
  "thought": "Transforming the address format is a updating the values.",
  "target": "update"
}}
```

User: Combine the first name and last name columns to a new column

_Output_
```json
{{
  "thought": "Combining the first and last name is merging since it copies the content from two columns into the new one.",
  "target": "merge"
}}
```

User: What is the average length of each product description?
Agent: The average length of product descriptions is 3156.9 tokens.
User: can you pull the latest product inventory sold from the API and append them to the table?

_Output_
```json
{{
  "thought": "Pulling data from an external source is a 'call' operation, which takes precedence over 'append' since it must be done first.",
  "target": "call"
}}
```

User: Show me all accounts with a late payment over $1000.
Agent: These are the account with a late payment over $1000. 
User: Actually, let's add a new column for 'Major Late Payments' and mark these accounts as 'Yes'

_Output_
```json
{{
  "thought": "Adding a new column for major late payments is an 'insert'.",
  "target": "insert"
}}
```

#############
Follow the JSON format to predict the target dialogue act. This is very important, the target must come from one of the twelve valid options.

{history}

_Output_
"""

detect_prompt = """Given the recent conversation history, think carefully about what the user is trying to accomplish in the final turn. Then, choose from one of the following dialogue acts:
  1. blank - identify rows or columns with empty cells, nulls, N/A, blanks, or otherwise missing values
  2. concern - identify potential concerns, namely numeric outliers, textual anomalies, date issues or location issues
  3. typo - identify similar (but distinct) terms that require merging into a single canonical value, often to resolve typos or misspellings
  4. problem - identify problems around mixed datatypes and subtypes, such as a column with both dates and timestamps, or a column with both cities and zip codes
  5. connect - open-ended request to combine or connect two sources of data
  6. resolve - open-ended request to identify issues within the table. Possible issues include the blanks, concerns, typos, or problems described above.
  7. insight - generic, open-ended questions about the spreadsheet: 'Any interesting insights in this data?'
  8. clean - actually taking action to resolve the issue by updating values or standardizing text
  9. delete - taking action to resolve the issue by removing the offending rows or columns
  10. interpolate - taking action to resolve missing values by estimating them from other values
  11. ignore - dismissing the agent's suggestions that an issue exists, or otherwise ignoring the issue by moving on to a different topic
  12. dedupe - remove duplicates, such as merging duplicate users from a CRM or eliminating repeat entries from a log file.

If none of the above work, please output 'unsure'. In total, this offers 12 options that are exactly one word long.
When making your decision, note that {condition}
Your final response should be in well-formatted JSON including a thought (a sentence or two) and target (single token), with no further explanations after the output.

For example,
---
User: What is the ROAS for social media campaigns in the past month?
Agent: The ROAS for all social media campaigns in the past month is 122.38%, but I noticed some outliers which may change this answer.
User: what do you mean?

_Output_
```json
{{
  "thought": "Outliers are a case of concerns, so this is a 'concern'.",
  "target": "concern"
}}
```

User: I'm curious about the results of our customer surveys. 
Agent: Sure, what would you like to know? Would you like to calculate a specific metric or see a breakdown?
User: It seems many people filled it out twice.

_Output_
```json
{{
  "thought": "Resolving multiple survey responses is a 'dedupe' operation.",
  "target": "dedupe"
}}
```

User: Ok, it seems that the dip in traffic keeps occuring in the middle of each week.
Agent: yes, there is a meaningful drop in traffic during each Wednesday. However, I noticed some empty cells in the Traffic column which may affect the results.
User: please show me

_Output_
```json
{{
  "thought": "Empty cells are a type of blank, so this is a 'blank'.",
  "target": "blank"
}}
```

User: How has the Bike for your Health campaign been going?

_Output_
```json
{{
  "thought": "The user is asking for general insights, so this is an 'insight'.",
  "target": "insight"
}}
```

User: Let's clean up the data, what rows have broken values?

_Output_
```json
{{
  "thought": "Broken values could mean nearly anything, so it is a 'resolve'.",
  "target": "resolve"
}}
```

User: Which anti-virus software packages have the highest CTR.
Agent: The Norton AntiVrus, Nortion Antivirus, and MacAfee Antivirus have the highest CTRs. See table for more details.
User: We need to only keep one version of each brand

_Output_
```json
{{
  "thought": "The user wants to merge similar terms, so this is a 'typo'.",
  "target": "typo"
}}
```

User: Good morning!
Agent: Good morning to you as well, how can I assist you today?
User: I need to add some information to the Delivery table

_Output_
```json
{{
  "thought": "This sounds like a generic request to connect sources of data, so this is a 'connect'.",
  "target": "connect"
}}
```

User: are you able to help me analyze my campaigns?

_Output_
```json
{{
  "thought": "This is a generic request for insights or observations.",
  "target": "insight"
}}
```

User: What time periods did the most users visit that page?
Agent: Most users visited the page from 112355 to 113401.
User: These dates seem to be out of whack, can you check?

_Output_
```json
{{
  "thought": "The time periods seem to be stored as integers rather than dates, so this is a 'problem'.",
  "target": "problem"
}}
```

User: Ok, yea we let's take a look at the CTR for just Facebook then
Agent: Filtering to just Facebook, the CTR is 4.334%. However, I noticed some null values in the clicks column which may affect the results.
User: And what about Instagram?

_Output_
```json
{{
  "thought": "The user has moved on to a different topic, so this is an 'ignore'.",
  "target": "ignore"
}}
```

User: What percentage of attendees do we have their contact information?
Agent: We have contact information for 78% of the attendees.
User: Can we will in the blanks by using their username and company name to creat an email address?

_Output_
```json
{{
  "thought": "Filling in the blanks is an 'interpolate' operation.",
  "target": "interpolate"
}}
```

User: We need to prepare this data for a presentation.
Agent: Certainly, what can I help with today?
User: I saw some null values in the SunriseDelta column

_Output_
```json
{{
  "thought": "The user wants to clean null values, which are a type of blank issue.",
  "target": "blank"
}}
```

User: I'm curious about the results of our customer surveys. 
Agent: Sure, what would you like to know? Would you like to calculate a specific metric or see a breakdown?
User: It seems many people filled it out twice.

_Output_
```json
{{
  "thought": "Resolving multiple survey responses is a 'dedupe' operation.",
  "target": "dedupe"
}}
```

Agent: I found 10 rows with broken values, would you like to take a look?
Agent: The earliest appearance is on October 18, 2017.
User: Deal with any outliers by removing anything before 2018

_Output_
```json
{{
  "thought": "Outliers are a type of concern, but we are going beyond merely identifying and into removing them, so this is a 'delete'.",
  "target": "delete"
}}
```

User: Oh man, we need to make some more money! What's the total conversion count for our metal tear solid page.
Agent: The Metal Tear Solid landing page has led to 936 conversions in the past month. There are some anomalies in the landing page copy which may be affecting the conversion rate.
User: How is that possible?

_Output_
```json
{{
  "thought": "Anomalies in the landing page copy are a type of concern, so this is a 'concern'.",
  "target": "concern"
}}
```
---
Follow the JSON format to predict the target dialogue act. This is very important, the target must come from one of the valid options.
These options are: blank, concern, typo, problem, connect, resolve, insight, clean, delete, interpolate, ignore, dedupe (and on rare occasions, 'unsure')

{history}

_Output_
"""

converse_prompt = """Given the recent conversation history, think carefully about what the user's intent is in the final turn, then choose from the following options:
  1. express - expressing opinions or emotions about the agent's actions, such opinions can be positive (confirm, approve, agree) or negative (deny, doubt, ignore)
  2. faq - gaining a better understanding of what the Soleda service entails and the company's background, answering questions typically found in a FAQ
  3. attention - calling attention to a specific table, row or column without specifying any action, often used to indicate a user's focus
  4. describe - asking about spreadsheet schema and related meta-data, such as most common values, number of rows/columns, or valid column names
  5. undo - reverting the most recent change, going back a step or two, semantically equivalent to entering CTRL+Z
  6. inquire - inquire how the agent arrived at a particular answer or what the agent did, including its motivation or reasoning process
  7. inform - letting the agent know about their preferences or defining specific settings, such as how to define the 'best' campaign or which column to use for a specific calculation
  8. recommend - asking the agent for recommendations on how to proceed with next steps; "What do you suggest we do next?"
  9. pull - pulling the saved definition of key terms of metrics, typically to determine how the agent arrived at a particular answer; "How did you calculate ROAS again?"
  10. chat - open domain chit-chat that is unrelated to the underlying data, also includes when a user make neutral comments; Serves as a catch-all when none of the other options apply
  11. ignore - dismissing the agent's suggestions that an issue exists, or otherwise ignoring the issue by moving on to a different topic

In total, this offers ten (10) options that are exactly one word long.
Your final response should be in well-formatted JSON including a thought (a sentence or two) and target (single token), with no further explanations after the output.

For example,
---
_Conversation History_
User: What can you do?
Agent: I can support all marketing analytics activities including cleaning data, optimizing and analyzing marketing campaigns, building dashboards, and generating reports to share with stakeholders.
User: What models do you use to make that happen?

_Output_
```json
{{
  "thought": "The user is asking for a better understanding of the Soleda service which can be answered from the FAQ.",
  "target": "faq"
}}
```

_Conversation History_
User: sure, please show me
Agent: I found 3 date issues in the CategoryRelease. We can remove them, update the values, or ignore them.
User: that's not a big deal, we can move on

_Output_
```json
{{
  "thought": "Moving on effectively ignores the date issues, so this is an 'express'.",
  "target": "express"
}}
```

_Conversation History_
User: What was the total payments made in June?
Agent: Payments made in June came out to $563.26.
User: Do you see how we have a column related to taxes

_Output_
```json
{{
  "thought": "Calling attention to a specific column is an 'attention'.",
  "target": "attention"
}}
```

_Conversation History_
User: Can you give me a breakdown of our Boston user engagement?
Agent: In the data, I see 'Boston', 'boston', and 'Beantown'. Should these be treated as 'Boston'?
User: Yes, change to Boston.

_Output_
```json
{{
  "thought": "The user is expressing confirmation of the agent's suggestion to merge similar terms",
  "target": "express"
}}
```

_Conversation History_
User: How many customer accounts are there labeled in from the Sonoma area?
Agent: I could not find customer accounts connected to the 'Sonoma' region.
User: That doesn't sound right, should at least be a few

_Output_
```json
{{
  "thought": "The user is expressing doubt about the agent's response.",
  "target": "express"
}}
```

_Conversation History_
User: Are there any columns covering dates or times?
Agent: Yes, the Downloads table contains a column for viewedAt
User: Wait, can we go back to the previous table?

_Output_
```json
{{
  "thought": "Going back to the previous table is simply viewing it, without any changes, so this is an 'attention' rather than an 'undo'.",
  "target": "attention"
}}
```

_Conversation History_
User: I see. Can you illustrate this with a few examples?
Agent: Sure, here are some examples. As you can see, we have entries like 'True', 'False', 'yes', 'no', and 'maybe' in the Active column.
User: Interesting, how did you spot this inconsistency?

_Output_
```json
{{
  "thought": "The user is inquiring about the agent's process of identifying issues.",
  "target": "inquire"
}}
```

_Conversation History_
User: OK, we can delete those.
Agent: There are 63 rows remaining with no values. Should I remove these as well?
User: no, we should just keep them

_Output_
```json
{{
  "thought": "The user is rejecting the agent's suggestion to remove the rows.",
  "target": "express"
}}
```

_Conversation History_
User: What is the ARPU for our products sold from Columbia?
Agent: The average rating per user for our products is $2.94.
User: Uhh, I dunno about that. How did you get that answer?

_Output_
```json
{{
  "thought": "Since we are digging into the calculation of a metric, this is a 'pull' rather than a generic 'doubt'.",
  "target": "pull"
}}
```

_Conversation History_
User: Can you tell me the ROAS for that campaign? 
Agent: I found a column for 'total_paid_spend', but I could not find a column for 'total_return'. Can you point me in the right direction?
User: ROAS should be the total bookings divided by total paid spend

_Output_
```json
{{
  "thought": "Providing the formula for ROAS is defining the calculation.",
  "target": "inform"
}}
```

_Conversation History_
User: Fine, go ahead and deal with the remaining conflicts
Agent: I've successfully resolved all conflicts and merged the tables. The new integrated table 'CustomerOrderPreferences', contains 5621 rows of data, 803 of which are from the merged entries.
User: How did you decide which rows to merge?

_Output_
```json
{{
  "thought": "The user wants to know the agent's decision process for merging the rows.",
  "target": "inquire"
}}
```

_Conversation History_
User: sure, please show me
Agent: I found 3 date issues in the CategoryRelease. We can remove them, update the values, or ignore them.
User: that's not a big deal, we can move on

_Output_
```json
{{
  "thought": "Moving on effectively ignores the date issues, so this is an 'express'.",
  "target": "express"
}}
```

_Conversation History_
User: How many clicks did we get so far this week?
Agent: We have recieved 1437 clicks so far this week.
User: Start of the week should be Sunday, not Monday

_Output_
```json
{{
  "thought": "Setting the start of the week is defining a preference.",
  "target": "inform"
}}
```

_Conversation History_
User: What can you tell me about the data?
Agent: Based on the available columns, it seems the data supports calculating CTR, CPA, and CVR. Which metric would you like to calculate?
User: Dunno, can you pick one for me?

_Output_
```json
{{
  "thought": "The user is asking for a recommendation from the agent.",
  "target": "recommend"
}}
```

_Conversation History_
User: What a good day to dive into some data!

_Output_
```json
{{
  "thought": "The user is expressing general enthusiasm, so this is a 'chat'.",
  "target": "chat"
}}
```

_Conversation History_
User: Can you show me the number of clicks in the same time last year?
Agent: I will count the total number of clicks from November 9, 2023 to December 9, 2023. Is that right?
User: Yea, the start date is November 9th

_Output_
```json
{{
  "thought": "The user is confirming the agent's suggestion to change the start date.",
  "target": "express"
}}
```

_Conversation History_
User: yes, that looks good.
Agent: Great, I have created the JointAttribution column.
User: Actually, can you show me the formula again?

_Output_
```json
{{
  "thought": "The user is asking to see the formula again, so this is a 'pull'.",
  "target": "pull"
}}
```

_Conversation History_
User: What is the CVR for the stop drop & shop campaign lately?
Agent: The conversion rate for the Stop, Drop and Shop campaign is -2.35%
User: Negative? What's the lowest conversion rate in the table?

_Output_
```json
{{
  "thought": "The user is incredulous about the negative conversion rate, which implies 'doubt'. The follow-up question is asking for the lowest value, which is a 'describe'.",
  "target": "describe"
}}
```

_Conversation History_
User: What was the CTR for that one then?
Agent: The CTR for the Spill_The_Tea campaign is 0.34%
User: That reminds me, did I tell you about the new boba tea shop that opened up?

_Output_
```json
{{
  "thought": "The user is changing the topic to discuss something unrelated to the data",
  "target": "chat"
}}
```

_Conversation History_
User: We should look forward for three years of subscription revenue as the time range.
Agent: In order to calculate the LTV, I would also need to know the discount rate. Do you have a preferred value for the discount rate?
User: The decay rate for renewal rates is 50%, so basically divide the value of each next subscription by half

_Output_
```json
{{
  "thought": "Giving the formula for the decay rate is defining a metric.",
  "target": "inform"
}}
```

_Conversation History_
User: How many rows does the orders table have?
Agent: The orders table has 294 rows.
User: How many unique values are in teh viewer column?

_Output_
```json
{{
  "thought": "The user is asking for a description of the table schema, so this is a 'describe'.",
  "target": "describe"
}}
```
---
Follow the JSON format to predict the target dialogue act. This is very important, the target must come from one of the ten valid options.

_Conversation History_
{history}

_Output_
"""

table_prompt = """Given the conversation history and the set of valid tables, decide which table{goal}.
{history}
Valid tables: {valid_tabs}

This is very important to my career, please do NOT return any invalid tables. Only choose one of the valid tables, or 'none' if no tables are appropriate.
There is no need to provide further explanations, just the name of the table.

Chosen table: """

entity_prompt = """Given the user history and the set of valid columns, decide which tables and columns (if any) are being referenced in the last utterance.
Please think carefully to first choose what tables might be relevant, and then choose what columns are being referenced from those tables.
If specific columns are not mentioned, but data __is__ being requested from a table, return '*' to represent all columns.
When any table is appropriate, label as 'all'. However, if no tables are appropriate then return an empty list.
Most importantly, only choose from the set of valid columns. This is very important to my career, please do NOT return any invalid columns.

Your entire response should be in well-formatted JSON list, where each item in the list contains the keys of table (string) and columns (list).
We will go through three sample spreadsheets with a couple of examples each, and then tackle the final real scenario.
For our final case, just output the list of tables and columns, with no further explanations after the JSON output.

## Jewelery Store Scenario
For our first sample spreadsheet, suppose the valid options are:
* Tables: orders; customers; products
* Columns: order_id, product_id, customer_id, date, size, channel, price in orders;
customer_id, last_visit, first, last, city, state, zip, is_returning in customers;
product_id, sku, type, brand, material, carat, style, cost, locations, discount in products

User: How many advertising sources are there?
_Output_
```json
[ {{"table": "orders", "columns": ["channel"]}} ]
```

User: How many rows are there in products?
Agent: There are 592 rows in the products table.
User: What about the purchases table?
_Output_
```json
[ {{"table": "purchases", "columns": ["*"]}} ]
```

User: Can you also show me where our storage locations are?
Agent: Sure, here are the locations of our storage facilities.
User: Are there any columns related to customer names?
_Output_
```json
[ {{"table": "customers", "columns": ["first", "last"]}} ]
```

User: Do we have data on where customers come from?
Agent: No, the customers table does not contain a channels column.
User: I mean where they live and stuff
_Output_
```json
[ {{"table": "customers", "columns": ["city", "state", "zip"]}} ]
```

User: You see how we have all this product data?
_Output_
```json
[ {{"table": "products", "columns": ["*"]}} ]
```

User: What is the most common ring size?
Agent: The most common ring size is 6.5.
User: What is the cheapest jewelery available?
_Output_
```json
[ 
  {{"table": "products", "columns": ["brand", "product_id"]}},
  {{"table": "orders", "columns": ["price", "product_id"]}}
]
```

User: What data do we have about user turnover?
Agent: The Customers table contains three columns related to user turnover
User: Any recommendations about how to improve retention?
_Output_
```json
[ {{"table": "customers", "columns": ["last_visit", "is_returning", "customer_id"]}} ]
```

## E-Commmerce Store Scenario
For our second sample spreadsheet, suppose the valid options are:
* Tables: Activities; Purchases; Inventory
* Columns: ActivityID, PurchaseID, ActivityType, ActivityTime, PageURL, UserAgent, ReferrerURL, DeviceID in Activities; 
PurchaseID, UserID, ProductID, PurchaseTime, Quantity, Discount, Tax, UnitPrice, TotalPrice, PaymentMethod, ShippingAddress in Purchases;
ProductID, ProductName, ProductDescription, ProductPrice, Category, Supplier, InitialQuantity, CurrentQuantity, ReorderLevel, LastReplenishmentDate, NextReplenishmentDate in Inventory

User: I want to fix problems in our data
Agent: Sure, where would you like to start?
User: See how the discounts have blank values?
_Output_
```json
[ {{"table": "Purchases", "columns": ["Discount"]}} ]
```

User: How far back do we have data on user activities?
Agent: We have data going as far back as 2018.
User: That doesn't seem right, are you sure?
_Output_
```json
[ {{"table": "Activities", "columns": ["ActivityTime"]}} ]
```

User: Sure, let's take a look
Agent: I found three outliers in the ProductPrice column with values of 11K and 12K. Would you like to remove these rows or leave them alone?
User: Are they a whole number or currency?
_Output_
```json
[ {{"table": "Inventory", "columns": ["ProductPrice"]}} ]
```

User: Let's remove all the small ones too.
_Output_
```json
[ ]
```

User: We're considering opening new offices. Can you tell which cities have the highest concentration of our users?
Agent:  Of course. The cities are combined with states in the ShippingAddress column. I will first create two new columns for city and state as an initial step. How does that sound?
User: Yea, sounds good
_Output_
```json
[ {{"table": "Purchases", "columns": ["ShippingAddress"]}} ]
```

User: What data do we have available?
_Output_
```json
[ {{"table": "all", "columns": ["*"]}} ]
```

User: Do we have any data about revenue?
Agent: Yes, the Purchases table contains TotalPrice.
User: And what about costs?
_Output_
```json
[ {{"table": "Inventory", "columns": ["ProductPrice"]}} ]
```

## SaaS Vendors Scenario
For our third sample spreadsheet, suppose the valid options are:
* Tables: Mailchimp; Hubspot; Salesforce; Zendesk
* Columns: Subscriber_ID, First_Name, Last_Name, Email, Campaign_ID, Campaign_Name, Campaign_Launch_Date, Opened, Clicked, Unsubscribed, List_Segment, Clicked_Link in Mailchimp;
LeadID, UserName, Source, VisitCounts, PageVisited, FirstVisitTime, DownloadedContent, FormSubmitted, FormSubmissionDateTime, LeadScore in Hubspot;
ContactID, FullName, DateTimeJoined, EmailAddress, OpportunityID, Stage, DealSize, LastContactDate, NextStep, DecisionMaker, Location (city), Location (state), Location (country) in Salesforce;
TicketID, Requester, IssueType, MessageHeader, MessageBody, OpenTimestamp, ClosedTimestamp, Status, SatisfactionRating, AssignedAgent, ResolutionTime in Zendesk

User: I see a bunch of issues in the campaign data we need to take care of
_Output_
```json
[ {{"table": "Mailchimp", "columns": ["Campaign_ID", "Campaign_Name", "Campaign_Launch_Date"]}} ]
```

User: So you see how we have email data in two places?
_Output_
```json
[ 
  {{"table": "Mailchimp", "columns": ["Email"]}},
  {{"table": "Salesforce", "columns": ["EmailAddress"]}}
]
```

User: Yes, please merge them together.
Agent: Sure, I have merged together the First_Name and Last_Name columns into 'Full Name'.
User: I want to see the most common locations
_Output_
```json
[ {{"table": "Salesforce", "columns": ["Location (city)", "Location (state)", "Location (country)"]}} ]
```

User: what's the longest time we've spent on a ticket?
_Output_
```json
[ {{"table": "Zendesk", "columns": ["ResolutionTime", "OpenTimestamp", "ClosedTimestamp"]}} ]
```

User: Jamie told me that we have a lot of duplicate leads in the system.
_Output_
```json
[ {{"table": "Hubspot", "columns": ["UserName", "Source", "LeadScore"]}} ]
```

User: What was the open rate on our Easter Special email campaigns?
Agent: The open rate was 4.89% on this campaign so far.
User: What is the largest amount of visits we've ever experienced?
_Output_
```json
[ {{"table": "Hubspot", "columns": ["VisitCounts"]}} ]
```

User: Show me what city those users are from.
Agent: Sure, some cities include Alberta, Ontario, and Quebec. See table for more details.
User: Do we have any users from Canada?
_Output_
```json
[ {{"table": "Salesforce", "columns": ["ContactID", "FirstName", "LastName", "Location (country)"]}} ]
```

## Real Scenario
For our current case, the valid set of options are:
{valid_entities}

{history}
_Output_
"""

express_an_opinion_prompt = """Given the conversation history, please decide what type of emotion or opinion the user is expressing.
Please choose from one of the following valid options:
  1. confirm - agreeing to the agent's proposed change, asking for more details on an agent's suggestion, responding positively when the agent makes a recommendation
  2. deny - dismissing the agent's suggestions, ignoring what the agent said, or otherwise expressing confusion about next steps
  3. approve - expressing approval over the agent's actions, whereas 'confirm' is in response to a suggestion, 'approve' can be considered general positive feedback
  4. doubt - expressing doubt about agent's actions or questioning the response, implying the agent should explain their reasoning process; "Are you sure about that?"

As you come up with an answer, a good rule of thumb is that 'confirm' and 'deny' are reactions to an agent proposal, whereas 'approve' and 'doubt' are general expressions of positive or negative sentiment.
Your entire output should be in well-formatted JSON including a thought (a sentence or two) and target (single token), with no further explanations after the output.

For example,
---
User: Can you give me a breakdown of our Boston user engagement?
Agent: In the data, I see 'Boston', 'boston', and 'Beantown'. Should these be treated as 'Boston'?
User: Yes, change to Boston.

_Output_
```json
{{
  "thought": "The user is confirming the agent's suggestion to merge similar terms",
  "target": "confirm"
}}
```

User: Can you show me the number of signups for just the mobile version?
Agent: The mobile version received 6,137 signups in the last month.
User: Ok, nice. This is higher than I expected

_Output_
```json
{{
  "thought": "The user is showing general positive sentiment towards the analysis results",
  "target": "approve"
}}
```

User: How many customer accounts are there labeled in from the Sonoma area?
Agent: I could not find customer accounts connected to the 'Sonoma' region.
User: That doesn't sound right, should at least be a few

_Output_
```json
{{
  "thought": "The user is expressing doubt about the agent's response.",
  "target": "doubt"
}}
```

User: OK, we can delete those.
Agent: There are 63 rows remaining with no values. Should I remove these as well?
User: no, we should just keep them

_Output_
```json
{{
  "thought": "The user is rejecting the agent's suggestion to remove the rows.",
  "target": "deny"
}}
```

User: What is the highest rated restaurant in the Fort Greene area?
Agent: I found 3 potential concerns in the Restaurant column. Would you like to investigate further?
User: Yes, What do they look like?

_Output_
```json
{{
  "thought": "The user is following up on the agent's concerns, so this is a 'confirm'.",
  "target": "confirm"
}}
```

User: And what about just this last year?
Agent: $5357.73 in royalties were paid in total last year.
User: OK, amazing. Exactly what I was looking for

_Output_
```json
{{
  "thought": "The user is very happy with the agent's response.",
  "target": "approve"
}}
```

User: sure, please show me
Agent: I found 3 date issues in the CategoryRelease. We can remove them, update the values, or ignore them.
User: that's not a big deal, we can move on

_Output_
```json
{{
  "thought": "Moving on effectively ignores the date issues, so this is an 'deny'.",
  "target": "deny"
}}
```


User: Can you show me the number of clicks in the same time last year?
Agent: I will count the total number of clicks from November 9, 2023 to December 9, 2023. Is that right?
User: Yea, the start date is November 9th

_Output_
```json
{{
  "thought": "The user is confirming the agent's suggestion to change the start date.",
  "target": "confirm"
}}
```
---
{history}

_Output_
"""

attention_entity_prompt = """Given the conversation history, please decide if the user is calling attention to a table, row, or column.
Please resspond with just a single token of 'table', 'row', or 'column'. Do not include any further explanations.
If you're unsure, please choose 'table' as the default option.
Your entire output should be in well-formatted JSON including a thought (a sentence or two) and target (single token), with no further explanations after the output.

For example,
#############
_Conversation History_
User: What was the total payments made in June?
Agent: Payments made in June came out to $563.26.
User: I'm taking a look at this tax column with negative values

_Output_
```json
{{
  "thought": "The user has explicitly mentioned 'column', so clearly they are calling attention to a column.",
  "target": "column"
}}
```

_Conversation History_
User: Can you show me all the rows where IsEmployee is marked as False?

_Output_
```json
{{
  "thought": "The user has explicitly mentioned 'row', so clearly they are calling attention to a row.",
  "target": "row"
}}
```

_Conversation History_
User: Are there any columns covering dates or times?
Agent: Yes, the Downloads table contains a column for viewedAt
User: Wait, can we go back to the previous table?

_Output_
```json
{{
  "thought": "The user has explicitly mentioned 'table', so clearly they are calling attention to a table.",
  "target": "table"
}}
```

_Conversation History_
User: What if we increased the budget by 10%?
Agent: We can forecast that, but I'll need more details. Which department or project is this budget increase for?
User: Let's focus on our digital marketing campaigns

_Output_
```json
{{
  "thought": "The user is focusing on a specific subset of rows within the campaigns table, so this is a 'row' operation.",
  "target": "row"
}}
```

_Conversation History_
User: Notice how we have a discounted price and retail price in the merchandise table?

_Output_
```json
{{
  "thought": "The user is calling out the existence of two columns, so this is a 'column' operation.",
  "target": "column"
}}
```

_Conversation History_
User: We're performing regular data backups, and I need to minimize duplication to save time and costs.
Agent: Got it. I have de-duplicated the data based on the Backup_ID and backup date, 72 rows have been removed, leaving 261 remaining backups.
User: Great, that should make our backup process more efficient. Now, let's move to our email data.

_Output_
```json
{{
  "thought": "The user is moving to a different table, so this is a 'table' operation.",
  "target": "table"
}}
```
#############
Now it's your turn! Please output your thought, followed by 'table', 'row', or 'column' based on the final turn in the conversation history.

_Conversation History_
{history}

_Output_
"""


analyze_map = {
    "query": "001",  # query
    "measure": "002",  # measure
    "segment": "02D",  # measure + multiple
    "visualize": "003",  # plot
    "pivot": "01A",  # query + table
    "describe": "014",  # query + retrieve
    "exist": "14C",  # query + retrieve + column
    "insight": "146",  # query + retrieve + update
    "materialize": "58A",  # insert + user + table
}

visualize_map = {
    "plot": "003",  # plot
    "trend": "023",  # measure + plot
    "explain": "038",  # plot + user
    "report": "23D",  # measure + plot + multiple
    "save": "38A",  # plot + user + table
    "design": "136",  # query + plot + update
    "style": "13A",  # query + plot + table
}

clean_map = {
    "insert": "005",  # insert
    "update": "006",  # update
    "delete": "007",  # delete
    "validate": "36D",  # plot + update + multiple
    "impute": "06B",  # update + row
    "format": "36F",  # plot + update + deny
    "pattern": "0BD",  # row + multiple
    "dedupe": "7BD",  # delete + row + multiple
    "datatype": "06E",  # update + confirm
    "undo": "06F",  # update + deny
}

transform_map = {
    "insert": "005",  # insert
    "update": "006",  # update
    "delete": "007",  # delete
    "transpose": "056",  # insert + update
    "move": "057",  # insert + delete
    "split": "5CD",  # insert + column + multiple
    "join": "05A",  # insert + table
    "materialize": "58A",  # insert + user + table
    "append": "05B",  # insert + row
    "merge": "05C",  # insert + column
    "call": "456",  # retrieve + insert + update
}

detect_map = {
    "blank": "46B",  # retrieve + update + deny
    "concern": "46C",  # retrieve + update + column
    "typo": "46E",  # retrieve + update + multiple
    "problem": "46F",  # retrieve + update + confirm
    "resolve": "468",  # retrieve + update + user
    "connect": "46D",  # retrieve + insert + user
    "insight": "146",  # query + retrieve + user
    "dedupe": "7BD",  # delete + row + multiple
    "clean": "006",  # update
    "ignore": "00F",  # deny
    "interpolate": "005",  # insert
}

converse_map = {
    "faq": "004",  # retrieve
    "inquire": "009",  # agent
    "attention": "ABC",  # table, row, column
    "express": "0EF",  # confirm or deny
    "describe": "014",  # query + retrieve
    "undo": "06F",  # update + deny
    "inform": "068",  # update + user
    "recommend": "049",  # retrieve + agent
    "pull": "048",  # retrieve + user
    "chat": "000",  # chat
    "ignore": "00F",  # deny
}

dialog_act_mappings = {
    "Analyze": analyze_map,
    "Visualize": visualize_map,
    "Clean": clean_map,
    "Transform": transform_map,
    "Detect": detect_map,
    "Converse": converse_map,
}
