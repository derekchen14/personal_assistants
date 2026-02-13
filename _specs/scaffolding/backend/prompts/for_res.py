query_response_prompt = """Given the conversation history, a related thought and the database output, generate a response that answers the current question.
When more than one utterance is given, pay attention to the previous utterances since they can be used to infer the user intention. Only answer the question in the final user utterance.
Remember to use the Thought to gain more context in interpreting the situation. Be sure to mention if the results are empty or contain nulls so the user is aware of the data's limitations.

It is incredibly important that you keep your response concise and to the point. If you are highlighting takeaways, only mention the 1 or 2 most insightful ones.
Even if the output from the database contains a long list of results, you should only mention the top N rows at most to remain concise, where by default N=3.
Staying focused is especially critical if the user has requested the 'best' of something or has filtered to a subset of the data, since the rest is not relevant.
If your answer is more than three (3) sentences, you should probably make it shorter.

Your answer should be written as if you are responding to the user directly. Simply reading results off the table is not helpful, instead focus on summarizing the key takeaways.
Accordingly, do not use a [introduction, list, and follow-up question] format. Just answer the user's question directly.
We will go over a few examples and then turn to the real scenario.

---
## Example 1
User: How much was the average subscription in that year?

Thought: The purchases table has a price column, which can be used to calculate average price. Orders has a order_timestamp column and I need to filter by year to 2022.
|    |  AVG(price)  |  Year  |
|---:|:-------------|-------:|
|  0 |     173.4    |  2021  |
|  1 |     166.5    |  2022  |
|  2 |     172.8    |  2023  |
|  3 |     176.0    |  2024  |
Answer: The amount of the average subscription in 2022 was $166.50, which is a dip compared to all prior and future years.

## Example 2
User: How many runners participated at the Track and Field Fun Run?
Agent: There were a total of 1014 participants at the Track and Field Fun Run event.
User: Let's drill down to each sub-event. Is there any one that people preferred more than the others?

Thought: The survey_tallies table can tell me about the number of participants in each sub-event. Since the user is further segmenting the data, I should also carry over the event name from the previous state.
|    | Sub_event     | Runner_count | Percentage |
|---:|:--------------|-------------:|-----------:|
|  0 | 5k            |         147  |     48.36% |
|  1 | full marathon |          91  |     29.93% |
|  2 | 10k           |          39  |     12.83% |
|  3 | half marathon |          27  |      8.88% |
Answer: The 5k sub-event was by far the most popular, with nearly half of the runners participating. The full marathon was the second most popular, followed by the 10k and half marathon. The results suggest that people preferred shorter distances over longer ones.

## Example 3
User: which ones had the highest spend then?

Thought: To determine the sectors where we spent the most on advertising, I need to group by the Sector column, sum the Dollars Spent column, and sort the results by the total spend amount.
|    | Sector                                     |   TotalSpend   |
|---:|:-------------------------------------------|---------------:|
|  0 | Construction, Housing                      |  nan           |
|  1 | Automotive                                 |  nan           |
|  2 | Healthcare, Beauty                         |  nan           |
|  3 | Cloud Computing, B2B Software              |  nan           |
|  4 | E-commerce, Retail                         |  nan           |
|  5 | Information Technology                     |    4.2e+07     |
|  6 | Sports, Entertainment                      |    3e+07       |
|  7 | Energy, Climate                            |    5.7e+07     |
|  8 | Finance, Banking                           |    1.93093e+07 |
Answer: The industries with the highest spend were Energy & Climate, Information Technology, and Sports & Entertainment. However, the spend for certain industries is not available so the final results may vary.

## Example 4
User: What channels have the worst win rates recently?
Agent: Pinterest, CJ and Twitter have the worst win rates recently.
User: Which ones have the best win rates?

Thought: The channels table has a win rate column, which can be used to find the best win rates and a channel column to group by. The previous state mentioned the worst win rates, so I should carry over the same time period and filter for the best win rates.
|    | channel   |   win_rate |
|---:|:----------|-----------:|
|  0 | Tiktok    |   0.68     |
|  1 | Yahoo     |   0.62     |
|  2 | Bing      |   0.53     |
|  3 | Facebook  |   0.43     |
|  4 | Instagram |   0.41     |
|  5 | Google    |   0.41     |
|  6 | Snapchat  |   0.25     |
|  7 | Twitter   |   0.19     |
Answer: The channels with the best win rates are Tiktok, Yahoo, and Bing.

## Example 5
User: What are all the brands that had an order in March 2023?

Thought: The products table has a brand column, which can be used to find all the brands. The orders table has a month and year column, which can be used to filter for March 2023.
|    | brand            |
|---:|:-----------------|
|  0 | Adidas           |
|  1 | ASICS            |
|  2 | Stella McCartney |
|  3 | Converse         |
|  4 | Brooks           |
|  5 | Dr. Martens      |
|  6 | New Balance      |
|  7 | Nike             |
|  8 | Reebok           |
|  9 | Timberland       |
| 10 | Vans             |
| 11 | Puma             |
| 12 | Nine West        |
| 13 | Rebook           |
| 14 | Cole Haan        |
| 15 | Sperry           |
| 16 | Steve Madden     |
Answer: In March, brands with orders included Adidas, ASCIS, and Stella McCartney. See the table for more.

## Example 6
User: Which month performed the best?

Thought: The channels table has a spend column, while the orders table contains month column.  Since the previous state mentioned filtering to the email channel, we carry that over to this turn as well.
|    |   month |        spend |
|---:|--------:|-------------:|
|  0 |       3 |           88 |
|  1 |       7 |          126 |
|  2 |      12 |          160 |
|  3 |       5 |          172 |
|  4 |       4 |          217 |
|  5 |       2 |          280 |
|  6 |       6 |          345 |
|  7 |       8 |          370 |
|  8 |      11 |          457 |
|  9 |       1 |          501 |
| 10 |      10 |          554 |
| 11 |       9 |          593 |
Answer: March had the lowest email spend at just $88.

## Example 7
User: Who from Delaware bought the most watches in 2018?

Thought: We need to join the orders and customers tables on customer_id and filter by state and year. We also need to aggregate by customer and count the number of watches bought.
| customer_id   | num_watches_bought  |
|---------------|---------------------|
Answer: There are no results from the database. It seems no customers from Delaware bought watches in 2018.

## Example 8
User: What channels had the best conversion rates in April?

Thought: The orders table has a channel column, and also a month column, so I can filter it for April. The activity table has a conversion column, which I can use to sort for highest conversion rate.
|    | channel           |  conversion_rate |
|---:|:------------------|-----------------:|
|  0 | Google            |             4.34 |
|  1 | email_new_user    |             4.12 |
|  2 | affiliate_display |             3.99 |
|  3 | email_existing    |             3.76 |
|  4 | search_google     |             3.52 |
|  5 | Bing              |             2.84 |
|  6 | social_fb         |             2.66 |
|  7 | Facebook          |             2.41 |
|  8 | search_bing       |             2.16 |
|  9 | social_tiktok     |             1.80 |
| 10 | search_yahoo      |             1.78 |
| 11 | Twitter           |             1.30 |
| 12 | social_twitter    |             1.06 |
| 13 | email_newuser     |             0.96 |
| 14 | affiliate_text    |             0.93 |
| 15 | GA                |             0.92 |
| 16 | Yahoo             |             0.81 |
Answer: Google, email_new_user, and affiliate_display had the best conversion rates in April. See the table for more.

## Example 9
User: How many were sold that day?
Agent: There were 414 shirts sold on Wednesday.
User: What about the previous day?

Thought: The orders table has a day_of_week column, which can be used to filter for the previous day.  The products table has a product column, which can be used to count the number of shirts sold.
|    | day_of_week |  shirts_sold |
|---:|------------:|-------------:|
|  0 | Tuesday     |          329 |
|  1 | Wednesday   |          414 |
Answer: There were 329 shirts sold on Tuesday.
---
## Real Scenario
{history}

Thought: {thought}
{frame}
"""

pivot_response_prompt = """Given the most recent utterances, a related thought and output from the database, generate a response that answers the current question.
When more than one utterance is given, pay attention to the previous utterances since they can be used to infer the user intention. Only answer the question in the final user utterance.
Remember to use the Thought to gain more context in interpreting the situation. Be sure to mention if the results are empty or contain nulls so the user is aware of the data's limitations.

It is incredibly important that you keep your response concise and to the point.
Even if the output from the database contains a long list of results, you should only mention the top N rows at most to remain concise, where by default N=3.
Staying focused is especially critical if the user has requested the 'best' of something or has filtered to a subset of the data, since the rest is not relevant.

For example,
---
## Example 1
User: How much was the average subscription in that year?
Thought: The purchases table has a price column, which can be used to calculate average price. Orders has a order_timestamp column and I need to filter by year to 2022.
Output from DB:
|    |  AVG(price)  |  Year  |
|---:|:-------------|-------:|
|  0 |     173.4    |  2021  |
|  1 |     166.5    |  2022  |
|  2 |     172.8    |  2023  |
|  3 |     176.0    |  2024  |
Answer: The amount of the average subscription in 2022 was $166.50.

## Example 2
User: Let's drill down to just kid's shoes
Thought: The products table can tell me about the type of shoes bought, such as kids shoes. Since the user is narrowing her search, I should also carry over the month and year from the previous state.  This also lets me know I need the total sum of price rather than average price.
Output from DB:
|    |  total_revenue |
|---:|---------------:|
|  0 |           845  |
Answer: Kids shoes produced $845 in total revenue for the same time period.

## Example 3
User: which ones had the highest spend then?
Thought: To determine the sectors where we spent the most on advertising, I need to group by the Sector column, sum the Dollars Spent column, and sort the results by the total spend amount.
Output from DB:
|    | Sector                                     |   TotalSpend   |
|---:|:-------------------------------------------|---------------:|
|  0 | Construction, Housing                      |  nan           |
|  1 | Automotive                                 |  nan           |
|  2 | Healthcare, Beauty                         |  nan           |
|  3 | Cloud Computing, B2B Software              |  nan           |
|  4 | E-commerce, Retail                         |  nan           |
|  5 | Information Technology                     |    4.2e+07     |
|  6 | Sports, Entertainment                      |    3e+07       |
|  7 | Energy, Climate                            |    5.7e+07     |
|  8 | Finance, Banking                           |    1.93093e+07 |
Answer: The industries with the highest spend were Energy & Climate, Information Technology, and Sports & Entertainment. However, the spend for certain industries is not available so the final results may vary.

## Example 4
User: What channels have the worst win rates recently?
Agent: Pinterest, CJ and Twitter have the worst win rates recently.
User: Which ones have the best win rates?
Thought: The channels table has a win rate column, which can be used to find the best win rates and a channel column to group by. The previous state mentioned the worst win rates, so I should carry over the same time period and filter for the best win rates.
Output from DB:
|    | channel   |   win_rate |
|---:|:----------|-----------:|
|  0 | Tiktok    |   0.68     |
|  1 | Yahoo     |   0.62     |
|  2 | Bing      |   0.53     |
|  3 | Facebook  |   0.43     |
|  4 | Instagram |   0.41     |
|  5 | Google    |   0.41     |
|  6 | Snapchat  |   0.25     |
|  7 | Twitter   |   0.19     |
Answer: The channels with the best win rates are Tiktok, Yahoo, and Bing.

## Example 5
User: What are all the brands that had an order in March 2023?
Thought: The products table has a brand column, which can be used to find all the brands. The orders table has a month and year column, which can be used to filter for March 2023.
Output from DB:
|    | brand            |
|---:|:-----------------|
|  0 | Adidas           |
|  1 | ASICS            |
|  2 | Stella McCartney |
|  3 | Converse         |
|  4 | Brooks           |
|  5 | Dr. Martens      |
|  6 | New Balance      |
|  7 | Nike             |
|  8 | Reebok           |
|  9 | Timberland       |
| 10 | Vans             |
| 11 | Puma             |
| 12 | Nine West        |
| 13 | Rebook           |
| 14 | Cole Haan        |
| 15 | Sperry           |
| 16 | Steve Madden     |
Answer: In March, brands with orders included Adidas, ASCIS, and Stella McCartney. See the table for more.

## Example 6
User: Which month performed the best?
Thought: The channels table has a spend column, while the orders table contains month column.  Since the previous state mentioned filtering to the email channel, we carry that over to this turn as well.
Output from DB:
|    |   month |        spend |
|---:|--------:|-------------:|
|  0 |       3 |           88 |
|  1 |       7 |          126 |
|  2 |      12 |          160 |
|  3 |       5 |          172 |
|  4 |       4 |          217 |
|  5 |       2 |          280 |
|  6 |       6 |          345 |
|  7 |       8 |          370 |
|  8 |      11 |          457 |
|  9 |       1 |          501 |
| 10 |      10 |          554 |
| 11 |       9 |          593 |
Answer: March had the lowest email spend at just $88.

## Example 7
User: Who from Delaware bought the most watches in 2018?
Thought: We need to join the orders and customers tables on customer_id and filter by state and year. We also need to aggregate by customer and count the number of watches bought.
Output from DB:
| customer_id   | num_watches_bought  |
|---------------|---------------------|
Answer: There are no results from the database. It seems no customers from Delaware bought watches in 2018.

## Example 8
User: What channels had the best conversion rates in April?
Thought: The orders table has a channel column, and also a month column, so I can filter it for April. The activity table has a conversion column, which I can use to sort for highest conversion rate.
Output from DB:
|    | channel           |  conversion_rate |
|---:|:------------------|-----------------:|
|  0 | Google            |             4.34 |
|  1 | email_new_user    |             4.12 |
|  2 | affiliate_display |             3.99 |
|  3 | email_existing    |             3.76 |
|  4 | search_google     |             3.52 |
|  5 | Bing              |             2.84 |
|  6 | social_fb         |             2.66 |
|  7 | Facebook          |             2.41 |
|  8 | search_bing       |             2.16 |
|  9 | social_tiktok     |             1.80 |
| 10 | search_yahoo      |             1.78 |
| 11 | Twitter           |             1.30 |
| 12 | social_twitter    |             1.06 |
| 13 | email_newuser     |             0.96 |
| 14 | affiliate_text    |             0.93 |
| 15 | GA                |             0.92 |
| 16 | Yahoo             |             0.81 |
Answer: Google, email_new_user, and affiliate_display had the best conversion rates in April. See the table for more.

## Example 9
User: How many were sold that day?
Agent: There were 414 shirts sold on Wednesday.
User: What about the previous day?
Thought: The orders table has a day_of_week column, which can be used to filter for the previous day.  The products table has a product column, which can be used to count the number of shirts sold.
Output from DB:
|    | day_of_week |  shirts_sold |
|---:|------------:|-------------:|
|  0 | Tuesday     |          329 |
|  1 | Wednesday   |          414 |
Answer: There were 329 shirts sold on Tuesday.
---
{history}
Thought: {thought}
Output from DB:
{frame}
"""

describe_response_prompt = """Given the conversation history, generate a concise response that describes the current state of the data.
Your answer should be simple and brief, containing one or two sentences at most. Do not include any explanations or additional information.
Remember that you are responding directly to the user, so your response should be in the form of a direct answer to their question.

For example,
---
_Conversation History_
User: How big is this table?

Answer: The CustomerSupport table contains 2,411 rows and 10 columns.

_Conversation History_
User: Do we have a column that calculates CPMs?
Agent: We have a 'CostPerView' column, is that what you're looking for?
User: Close enough, what's the average?

Answer: The average cost per view is $0.25.

_Conversation History_
User: What sort of data is in the subscriptions table?
Agent: The subscriptions table contains information about user subscriptions, including subscription name and billing cycle.
User: How many unique plans are there?

Answer: There are 14 unique plans to choose from. Is there anything specific about the plans you would like to know?

_Conversation History_
User: Where do our highest spending customers come from?
Agent: The states with the highest spending are New York and Florida.
User: What is the lowest and highest spending amount for users from Florida?

Answer: The lowest spending amount is $0.99, while the highest amount is $414.77.

_Conversation History_
User: Do we know how many views we got from our email campaign?
Agent: yes, we can measure that using the 'opened_count' column.
User: I'd like to know the center value and the variance around it to get a sense of spread.

Answer: The mean number of views from the email campaign is 1.97, with a median of 1.0 and a standard deviation of 0.232.

_Conversation History_
User: We advertised on Facebook too right?
Agent: Yes, we have campaigns from Facebook within the FB_ads_updated table.
User: How many ad groups are covered in that table?

Answer: There are 7 unique ad groups in the FB_ads_updated table.

_Conversation History_
User: Ok, let's explore the Purchase table now
Agent: Sure, what would you like to know?
User: What sort of data is in there?

Answer: The purchases table covers items that were bought by username (email) along with their order_time (timestamp) and order_amount (currency). Other important columns include product_name, order_quantity, and total_price.

_Conversation History_
User: Did you see any data regarding AOV?

Answer: I don't see a column for AOV, but I do see a avg_order_size column. Would that work?

_Conversation History_
User: What kind of data is in the returns column?

Agent: The returns column contains 'yes' and 'no' string values, likely indicating whether a purchase was returned. There are also some null values.

_Conversation History_
User: How many redemptions have we received in the past week?
Agent: There have been 23 redemptions in the past week.
User: Do we have any data regarding revenue from those redemptions?

Answer: The package_price column and a membership_fee column both contain dollar amounts. Either of these could be considered as revenue.
---
For our real case, here are some pertinent facts you should find useful:
{details}

Please note, the pertinent facts were collected *after* the conversation history, so they are already up to date.
Also, here is a preview of some rows in the most pertinent columns:
{preview}

_Conversation History_
{history}

"""

exist_response_prompt = """Given the conversation history, generate a concise response that lets the user know if the data they are looking for exists within the available tables.
Your answer should be simple and brief, containing one or two sentences at most. Do not include any explanations or additional information.
Let's go through a number of examples so you can see the style of an appropriate response, and then you can tackle the task at hand.

For example,
#############
For the following scenarios, suppose the relevant columns are provided to you.

_Conversation History_
User: Do we have any time series data within subscriptions?
Agent: Yes, the sub_timestamp column in subscriptions contains time series data.
User: What about within the leads table?

Answer: We have contact_date and follow_up_date columns that can be considered time series data.

_Conversation History_
User: Is there any data about error rates connected to user sign-ups?

Answer: Cross-referencing activity type and error log columns might provide information about error rates.

_Conversation History_
User: What is our conversion rate last month?
Agent: In order to calculate the conversion rate, I would need to know what you consider as a conversion. Could you clarify that?
User: Not sure, can you provide some options?

Answer: Sure, there is a subscribe_count column in the search_results table that could count as a conversion. Would you like to use that?

_Conversation History_
User: Do we have a column that calculates CPCs?

Answer: There isn't any specific column referencing CPCs, but the spendInDollars and clickCount columns can likely be used to calculate CPC. Should I add a new costPerClick column?

_Conversation History_
User: What data do we have about conversions?

Answer: Conversions can be interpreted as the number of sign-ups, number of subscriptions, or number of installations. Which definition would you like to use?
#############
For our real case, the valid columns are:
{columns}

Furthermore, here is a preview of some rows in the most pertinent columns:
{preview}

_Conversation History_
{history}

"""

fix_eval_prompt = """I am trying to evaluate a plotly figure with 'figure = eval(fig_code)'.
However, I get the following error:
{selected_tb}
Keep in mind that the dataframe 'df' is already available in the global scope, and should not be modified.
Please revise the fig_code so that it can be evaluated, perhaps by removing extra lines.
No explanations are needed; just return valid code that can be directly evaluated.

For example,
#############
_Original_
```python
px.bar(df, x='brand', y='num_cars_sold',
  labels={{
    'car_brand': 'Brand',
    'num_cars_sold': 'Cars Sold (#)'
  }},
  title='Number of Cars Sold')
```

_Error_
The label 'car_brand' was not found in the dataframe.

_Revised_
```python
px.bar(df, x='car_brand', y='num_cars_sold',
  labels={{
    'car_brand': 'Brand',
    'num_cars_sold': 'Cars Sold (#)'
  }},
  title='Number of Cars Sold')
```
#############
Now it's your turn. Please revise the fig_code so that it can be evaluated.

_Original_
```python
{pred_figure}
```

_Error_
{selected_tb}

_Revised_
"""

clarify_prompt = """You are given an ambiguous data question that cannot be answered from a data schema, possibly because there are no tables or columns that can answer the question.
Generate a clarifying question to resolve the ambiguity. Think carefully about the observation, but only output the final question. 

For example,
#############
Ambiguous utterance: How are the channels doing?
* Table: orders
* Columns: channel in orders
* Aggregation: None
* Operations: unsure
Observation: From the orders table, I see that there is the option to choose from price to represent revenue.  I could also consider costs from the products table or just total sales volume.
Output: How do you define channel performance?

#############
Ambiguous utterance: {utterance}
{state}
Observation: {observation}
Output:"""

noun_prompt = """The user is calling attention to a certain table or set of columns. Given the available table and column names, either:
1. Assure the user you have noticed the item of interest, and ask what they would like to do next. For example,
  - Yes, I see the post_content_0318 table. What would you like to know?
  - Yea, what would you like to do with those columns?
  - Sure, here you go. Is there anything in particular from this table you'd like to know?
  - We have an 'incremental spend' column related to revenue. Would you like to calculate something with that?

2. Inform the user that the table or columns are not found, and ask for clarification. For example,
  - Unfortunately, I do not see a table related to blog post content. Maybe the table has not yet been uploaded?
  - I'm not sure if those columns are available. Could you provide more information about them?
  - Hmm, I couldn't find that table. Perhaps it has a different name?
  - I do not see a column related to revenue. The closest I could find was Economic Value. Is that right?

Available table and columns:
{valid_content}

User Request: {utterance}

Remember to be concise and to the point. Only return your final response and no explanations.
"""

insight_response_prompt = """We have just completed a multi-step plan involving {analysis_name}, so your task now is to summarize the key findings.
To aid you in this task, you are provided with the user's original request, followed by a series of observations gathered throughout the analysis.
You will also be given the recent conversation history and a preview of the likely relevant data to provide additional context.
Based on this information, please generate a response that highlights the most insightful aspects of the analysis.

Please start by thinking carefully about the user's underlying intention and which observations are most relevant to satisfying that goal.
Your value is in distilling the complex analysis into a few key takeaways, so do NOT discuss every single observation.
Instead, pick up to three (3) key takeaways from the analysis that are most relevant to the user's goal. Good takeaways are:
  * directly related to what the user originally asked for
  * not already satisfied by the conversation history
  * uncover unexpected or surprising insights
  * do not overlap with each other
  * should consist of a short paragraph at most, preferably just one or two sentences

Finally, write an "Output" response that contains the key takeaways. Your response should:
  * Start with a brief introduction that sets the stage.
  * There should be no titles or headers. We are responding in a chat, so avoid generating a whole report.
  * Do NOT force your answer to exactly three takeaways. Only include each point if it is sufficiently useful in it's own right.
  * End with a short conclusion of specific and actionable recommendations.

Your entire response should written in well-formatted Markdown, starting with a "Thoughts" section followed by an "Output" section.
There should be no text or explanations after the Output.

For example,
---
## Average Deal Velocity Example
_Original Request_
On average, how long does it take for a deal to close?

_Observations_
  * Marketing to Sales contains compares the outreach_date to first_contact_date with roughly 1200 rows.
  * Sales Qualification compares the first_contact_date to discovery_date with roughly 1100 rows.
  * Technical Validation compares the discovery_date to demo_date with roughly 250 rows.
  * Contract Negotiation compares the demo_date to contract_sent with roughly 150 rows.
  * Closing Period compares the contract_sent to close_date with roughly 100 rows.
  * The close_date contains numerous null values, indicating many deals that have not yet closed.
  * The average deal velocity is 1.4 (marketing to sales) + 2.5 (sales qualification) + 3.2 (technical validation) + 5.1 (contract negotiation) + 2.7 (closing period) = 14.9 days.
  * The marketing to sales handoff takes the shortest on average, at 1.4 days.
  * The contract negotiation stage takes the longest on average, at 5.1 days.

_Conversation History_
User: The last two stages are contract negotiation, and finally closing period.
Agent: Just to be clear, I will be using the demo_date to contract_sent to calculate the Contract Negotiation stage, and the contract_sent to close_date to mark the Closing Period. Is that right?
User: yea, that sounds right

_Table Preview_
| Stage                | Avg Days |
|--------------------- |----------|
| Marketing to Sales   |  1.4     |
| Sales Qualification  |  2.5     |
| Technical Validation |  3.2     |
| Contract Negotiation |  5.1     |
| Closing Period       |  2.7     |

_Thoughts_
To answer the user's original question, we must sum to get total deal velocity to get 14.9 days. In order to stay concise, we will focus on the longest and shortest stages, rather than talking about every single stage.

_Output_
The average deal velocity is almost exactly 15 days:
  * More precisely, adding the 5 stages together, we get 1.4 + 2.5 + 3.2 + 5.1 + 2.7 = 14.9 days.
  * Marketing to Sales handoff is the fastest at just 1.4 days, while the contract negotiation takes the longest, at 5.1 days.
  * The major drop-off point occurs at technical validation, which only has ~250 rows, compared to 1000+ for the other earlier stages.
Streamlining the contract negotiation process could help significantly increase deal speed. However, Technical Validation may actually be the main bottleneck, so we should dig those areas to see if there are common causes for delay.

## Significance Testing Example
_Original Request_
Is the Knock Your Socks Off campaign doing ok?

_Observations_
  * The average open rate for all campaigns is 19.8%, while the average CTR is 2.7%, and the average unsubscribe rate is 0.3%
  * The average open rate for the Knock Your Socks Off campaign is 27.6%, while the average CTR is 4.1%, and the average unsubscribe rate is 0.2%
  * Since 2.3% < 5%, the Knock Your Socks Off campaign has a statistically significant higher open rate than the average campaign
  * Since 1.8% < 5%, the Knock Your Socks Off campaign has a statistically significant higher CTR than the average campaign
  * Since 14.2% > 5%, the Knock Your Socks Off campaign performs similarly to the average campaign in terms of unsubscribe rate

_Conversation History_
User: Yes, that sounds good.
Agent: Just to clarify, I will set a threshold of 5% for statistical significance. Is that right?
User: Sure, we can go with that.

_Table Preview_
Completing the fifth step results in the table:
| Metric                       | ClickThroughRate | ConversionRate | AbandonmentRate |
|------------------------------|------------------|----------------|-----------------|
| mean (all campaigns)         | 0.198            | 0.027          | 0.003           |
| std_dev (all campaigns)      | 0.042            | 0.008          | 0.001           |
| num_campaigns (all campaigns)| 27               | 27             | 27              |
| Knock Your Socks avg.        | 0.276            | 0.041          | 0.002           |
| p-value                      | 0.023            | 0.018          | 0.142           |

_Thoughts_
To answer the user's original question, we must look at the p-values to see if the Knock Your Socks Off campaign is doing statistically significantly better than the average campaign.

_Output_
The Knock Your Socks Off campaign is doing statistically significantly better than the average campaign in terms of CTR and CVR, but basically on par in terms of abandonment rate.
  * The campaign has a 27.6% CTR, which is 7.8% higher than the average of 19.8%.
  * The campaign has a 4.1% CVR, which is 1.4% higher than the average of 2.7%.
Overall, the campaign is doing well overall, and we should consider running it again in the future.

## Customer Segmentation Example
_Original Request_
Does it matter which device type people use to view our content?

_Observations_
  * The only ad groups with over 1000 views are within the Student_Resources and Professional_Finance categories.
  * The highest view-through rate is for student content on mobile iOS devices.
  * The highest download rate is for student content on mobile iOS devices.
  * There is consistently better performance on iOS vs Android, although the difference is not huge.
  * The trend in View-through rates are very highly correlated with download rates.
  * Desktop has higher view-throughs and downloads when it comes to Professional content, but not for Student content, where mobile is actually better.
  * The average difference in view-through rates between iOS and Android is 8.66%, while the average difference in download rates is 16.8%.
  * The average difference in view-through rates between Desktop and Mobile is 15.3%, while the average difference in download rates is 21.5%.
  * The average view-through rates for each device type is - Mobile iOS: 5.90%, Mobile Android: 5.43%, Desktop Mac: 5.95%, Desktop Windows: 5.16%
  * The average download rates for each device type is - Mobile iOS: 3.10%, Mobile Android: 2.66%, Desktop Mac: 3.07%, Desktop Windows: 2.56%

_Conversation History_
User: We can consider content based on the Ad group.
Agent: Do you want to compare all ad groups, or just filter to certain ones? Also, is there a specific time period you want to focus on?
User: Let's go with anything with over 1000 views.

_Table Preview_
| Device         | AdGroup              | ViewThroughRate | DownloadRate |
|----------------|----------------------|-----------------|--------------|
| Mobile_iOS     | Professional_Finance | 0.0423          | 0.0186       |
| Mobile_Android | Professional_Finance | 0.0387          | 0.0142       |
| Desktop_Mac    | Professional_Finance | 0.0612          | 0.0324       |
| Desktop_Windows| Professional_Finance | 0.0534          | 0.0267       |
| Mobile_iOS     | Student_Resources    | 0.0756          | 0.0434       |
| Mobile_Android | Student_Resources    | 0.0698          | 0.0389       |
| Desktop_Mac    | Student_Resources    | 0.0578          | 0.0298       |
| Desktop_Windows| Student_Resources    | 0.0498          | 0.0245       |

_Thoughts_
To answer the user's original question, we must segment the KPIs by device type. In order to stay concise, I will focus primarily on Desktop and Mobile since it has the largest gap, rather than reporting on everything.

_Output_
Device type seems to have a small, but measurable impact on engagement:
  * iOS and Mac devices are essentially tied in terms of view-through and download rates, but they consistently outperform Android and Windows devices.
  * The average difference in view-through rates between Desktop and Mobile is 15.3%, while the average difference in download rates is 21.5%.
  * Student-focused content generally outperforms professional content in terms of both view-through and download rates.
Although differences between each device type are minimal, Desktop dominates over Mobile across views and downloads. Therefore, the mobile experience likely contains the most low-hanging fruit for improvement.

## Email Performance Example
_Original Request_
How are our email campaigns doing in the last quarter?

_Observations_
  * Many of the campaigns have very low delivery rates, leading to no data for clicks and unsubscribes
  * The delivery, open, and click columns can be used to calculate the relevant rates for each campaign
  * The New Year's Eve Sale has the highest delivery rate at 98.2%, while the Mother's Day Sale has the lowest at 27.2%.
  * Spring Clearance Sale has the highest open rate at 30.2%, while Party Like It's 2024 has the lowest at 14.2%.
  * Spring into Savings has the highest click-through rate at 5.2%, while Party Like It's 2024 has the lowest at 1.1%.
  * New Year's Eve Sale has the highest unsubscribe rate at 0.12%, while Party Like It's 2024 has the lowest at 0.05%.

_Conversation History_
User: I'm mainly concerned about the click-through rates, and maybe unsubscribe rates as well.
Agent: No problem. Just to be clear, would like like to calculate click-through rate as the number of clicks divided by the number of delivered emails?
User: No, CTR should be clicks divided by opens.

_Table Preview_
| Campaigns                 | Delivery Rate | Open Rate | Click-Through Rate | Unsubscribe Rate |
|---------------------------|---------------|-----------|--------------------|------------------|
| Spring into Savings       | 29.1%         | 28.7%     | 5.2%               | 0.08%            |
| Spring Clearance Sale     | 91.4%         | 30.2%     | 4.5%               | 0.06%            |
| March Madness Special     | 96.7%         | 25.1%     | 3.9%               | 0.07%            |
| New Year's Eve Sale       | 98.2%         | 22.4%     | 3.8%               | 0.12%            |
| Mother's Day Sale         | 27.2%         | 23.5%     | 3.6%               | N/A              |
| Party Like It's 2024      | 94.8%         | 14.2%     | 1.1%               | 0.05%            |
| Friends & Family Discount | 32.6%         | 19.0%     | 0.0%               | N/A              |
| Just in Time for Summer   | 19.8%         | 20.2%     | 0.0%               | N/A              |
[11 other rows ...]

_Thoughts_
To answer the user's original question, we should focus on the campaigns with the highest click-through rates since that is the primary KPI of interest according to the conversation.

_Output_
Our top email campaigns have high CTR and low unsubscribe rates, but there may be some deliverability issues:
  * The 'Spring into Savings' campaign has the highest click-through rate at 5.2%, but it also has a surprisingly low delivery rate of 29.1%.
  * While most campaigns enjoy a 90+% delivery rate, a handful of others are hovering around 30% or lower. This leads to very low CTRs and not enough data to even calculate unsubscribe rates for certain campaigns.
We should investigate why the delivery rates are so low for some campaigns before we launch any new ones.
---
## Real Scenario: {analysis_name}
_Original Request_
{utterance}

_Observations_
{observations}

_Conversation History_
{history}

_Table Preview_
{table_md}

"""