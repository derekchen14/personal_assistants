# ------------------------------------------------------------------
# TRIMMED FOR SPEC BREVITY
# Original file: 6,329 lines with 27 prompt templates.
# Kept 2 representative prompts below (clarify_metric_prompt, query_to_visual_prompt).
# Removed 25 prompts: proactive_validation_prompt, exemplar_variables_prompt,
#   segment_exemplar_prompt, reasoning_variables_prompt, segment_reasoning_prompt,
#   variable_completion_prompt, variable_disagreement_prompt, check_existence_prompt,
#   pivot_table_prompt, empty_result_prompt, clarifying_thought_prompt,
#   operational_thought_prompt, metric_routing_prompt, metric_verification_prompt,
#   time_period_prompt, pivot_backfill_prompt, sufficient_info_prompt,
#   identify_segmentation_prompt, determine_buckets_prompt, metric_completion_prompt,
#   segment_completion_prompt, create_segmentation_prompt, metric_revision_prompt,
#   segment_revision_prompt
# ------------------------------------------------------------------

clarify_metric_prompt = """In accordance with the conversation history, we want to calculate the {expanded} metric.
However, there is ambiguity that needs to be resolved surrounding which columns should be used to represent the variables within the metric.
For more context, the formula is constructed as a tree of variables, starting with the root node which is the highest level Expression representing the metric.
The internal variables mix and match other Expressions until we reach the leaf nodes, which are constructed as Clause variables that reference specific columns in a table.

Expressions are composed of a name, variables, and relation, which conveys the relationship between those variables.
Valid relations include: add (+), subtract (-), multiply (*), divide (/), exponent (^), and (&), or (|), less_than (<), greater_than (>), equals (=), conditional (?), and placeholder.
The 'placeholder' relation is of particular interest since it indicates that we are unsure about how to structure the expression, and therefore serves as a great candidate for clarification.
Each Clause is composed of a name, aggregation (agg), table (tab), row, and column (col). They represent the data that is grounded to specific columns in a table.
Valid aggregations include: sum, count, average, top, bottom, min, max, greater_than, less_than, not, equals, empty, filled, constant, all.
For the aggregations of [top, bottom, greater_than, less_than, not, equals, constant], the 'row' field is used to specify the value of N.
The difference between top/bottom versus min/max is that top/bottom can be used to specify the number of values to return, while min/max only returns a single value.
Whereas not/equals are used to filter the column by a specific value, the empty/filled relations are used to filter for null or non-null values, respectively.
Both Expressions and Clauses contain a 'verified' field, which indicates whether the variable has been confirmed by the user. If a variable has already been verified, we don't need to ask about it again.

The different levels of ambiguity are:
  * general - high uncertainty about the user's intent; This is unlikely since we know the goal is to calculate a metric. We include this option only for completeness.
  * partial - we are unsure about which columns to use; Most often occurs when there are multiple options for a given column, and we need to ask the user which one to use.
  * specific - we are missing a specific piece of information such as an aggregation function, filter condition, or relationship between variables.
  * confirmation - we have a fairly complete candidate formula, but want to confirm that the structure and its details are correct.

To help with this task, you are also given:
  * Metric: the full name of the metric and short version
  * Thought: previous thought process, providing context for potential questions to ask
  * Formula: our current understanding of the formula, including the variables and their potential columns;
    When a variable is marked as verified, we already know the columns to use. Instead, focus your attention on variables that are unverified.

Start by constructing a concise thought concerning what information is still missing that prevents us from querying for the target metric.
Then, choose the level of ambiguity and generate a clarification question that will help us determine the correct columns to use and which variables they belong to.
To avoid overwhelming the user, your question response should be no longer than three (3) sentences at most.
Your entire response should be in well-formatted JSON including keys for thought (string), level (token), and question (string), with no further explanations after the JSON output.

For example,
---
_Conversation History_
User: Let's expand further. I want to look at the whole past year.
Agent: Certainly! To calculate the ROI for last year, we'll need to look at our revenue and costs. Which specific revenue streams and cost categories would you like me to consider?
User: The sum of expenses should cover the cost categories.

_Supporting Details_
  * Metric: Return on Investment (ROI)
  * Thought: There is no direct column for ROI, so we will need to calculate it ourselves. The cost variable is verified as the sum of expenses, so we no longer need to worry about it.
With that said, many reasonable options exist for 'revenue', including license_fee, service_charge, or maintenance_income.
We also need to filter for last year, which can be calculated using interact_date or visit_ts, so we might want to double check that as well.
  * Formula:
  {{
    "name": "Return on Investment", "verified": false, "relation": "and",
    "variables": [
      {{
        "name": "ROI", "verified": false, "relation": "divide",
        "variables": [
          {{
            "name": "total_revenue", "verified": false, "relation": "add",
            "variables": [
              {{"name": "license_revenue", "ver": false, "agg": "sum", "tab": "stripe_download", "col": "license_fee"}},
              {{"name": "service_revenue", "ver": false, "agg": "sum", "tab": "bookings", "col": "service_charge"}},
              {{"name": "income_revenue", "ver": false, "agg": "sum", "tab": "stripe_download", "col": "maintenance_income"}}
            ]
          }}, {{
            "name": "costs", "ver": true, "agg": "sum", "tab": "stripe_download", "col": "expenses"
          }}
        ]
      }}, {{
        "name": "past_year", "ver": false, "agg": "greater_than", "tab": "stripe_download", "col": "interact_date", "row": "12 months ago"
      }}
    ]
  }}

_Output_
```json
{{
  "thought": "There are multiple options for revenue and timing, so we need to clarify which ones to use.",
  "level": "confirmation",
  "question": "Is license fee, service charge, or maintenance income most appropriate to calculate revenue? Also, should I use interact_date or visit_ts to determine the past year?"
}}
```

_Conversation History_
User: What's the average time to close a deal for each stage?
Agent: The average time to close a deal for each stage is 39 days for 'New', 15 days for 'Qualified', and 11 days for 'Negotiation'.
User: So what does the final score look like if we count negotation stage as promoters?

_Supporting Details_
  * Metric: Net Promoter Score (NPS)
  * Thought: After removing the null values in the final_scores column, we can use the rest to determine the number of promoters and detractors.
The number of 'promoters' is the count of scores that are 9 or 10, while the number of 'detractors' is the count of scores that are 0 to 6.
We also need to avoid double counting, so we should use the DISTINCT keyword applied to either the lead_id or the survey_id.
  * Formula:
  {{
    "name": "Net Promoter Score", "verified": false, "relation": "and",
    "variables": [
      {{
        "name": "NPS", "verified": false, "relation": "subtract",
        "variables": [
          {{ "name": "promoters", "verified": false, "relation": "placeholder", variables: [] }},
          {{ "name": "detractors", "verified": false, "relation": "placeholder", variables: [] }}
        ]
      }}, {{
        "name": "unique_leads", "verified": false, "agg": "count", "tab": "pardot_report", "col": "lead_id"
      }}
    ]
  }}

_Output_
```json
{{
  "thought": "The user wants to rely on the stages to count promoters and detractors, but it is unclear how to do so.",
  "level": "specific",
  "question": "How does the Negotiation stage count towards a promoter score? I am using a formula where promoters are survey scores of 9 or 10, should we be doing something different?"
}}
```

_Conversation History_
User: I'm not sure, what options do we have for active customers?
Agent: Active users are often determined by the last time they logged in or when they last took some action, such as making a purchase or registering for an event.
User: Event registration and email signups are the activities we care most about. Let's focus on just last quarter like earlier.

_Supporting Details_
  * Metric: Retention Rate (Retain)
  * Thought: We should filter users who have been active in the last month, which is determined by their last_login date.
Filtering for the last month can be done by using the last_login column and the current date.
Additionally, we have already verified that we should use the count of unique user_ids to determine total customers.
We can use the registered_at column in the events table and the signup_date column in the users table to determine active customers.
  * Formula:
  {{
    "name": "Retention Rate", "verified": false, "relation": "divide",
    "variables": [
      {{
        "name": "active_customers", "verified": false, "relation": "and",
        "variables": [
          {{
            "name": "has_activity", "verified": false, "relation": "or",
            "variables": [
              {{"name": "event_registration", "ver": false, "agg": "filled", "tab": "events", "col": "registered_at"}},
              {{"name": "email_signup", "ver": false, "agg": "filled", "tab": "salesforce_June2021", "col": "signup_date"}}
            ]
          }},
          {{
            "name": "last_quarter", "ver": true, "agg": "greater_than", "tab": "events", "col": "last_login", "row": "3 months ago"
          }}
        ]
      }}, {{
        "name": "total_customers", "ver": true, "agg": "count", "tab": "salesforce_June2021", "col": "user_id"
      }}
    ]
  }}

_Output_
```json
{{
  "thought": "The remaining uncertainty concerns how to determine active customers. We have a reasonable idea, but we should confirm with the user that having a non-null value in either the registered_at or signup_date columns is sufficient.",
  "level": "confirmation",
  "question": "Ok, I will grab just the last month of data. I am considering a customer as active when either the registered_at or signup_date columns for that user are not null. Is this correct?"
}}
```
---
Now it's your turn! Please generate a concise thought followed by the ambiguity level and an insightful question to clarify the key points of uncertainty.

_Conversation History_
{history}

_Supporting Details_
  * Metric: {metric}
  * Thought: {thought}
  * Formula: {formula}

_Output_
"""

query_to_visual_prompt = """Based on the conversation history, we have executed a query on the database for some data.
Given a preview of the data, please determine if it is appropriate to visualize the results.
Please start by thinking about the context of the conversation and whether the query output can be visualized.
Then respond in well-formatted JSON including keys for thought (string) and convert (boolean), with no further explanations after the JSON output.

For example,
---
_Conversation History_
User: How many visitors did we get in the past month coming from email?
Agent: Email visitors this month comes to 121,975
User: I meant broken down by day.

_Preview_
| date       | page_views |
|:-----------|:-----------|
| 2024-09-14 | 10,229     |
| 2024-09-15 | 8,756      |
| 2024-09-16 | 5,811      |
| 2024-09-17 | 1,908      |
| 2024-09-18 | 4,020      |
| 2024-09-19 | 2,876      |
| 2024-09-20 | 3,732      |
| 2024-09-21 | 5,993      |

_Output_
```json
{{
  "thought": "The date can serve as the x-axis and page_views as the y-axis.",
  "convert": true
}}
```

_Conversation History_
User: What's the latest release candidate that is considered stable?
Agent: That would be 72.6.1
User: Are we still getting a lot of downloads for it?

_Preview_
| firmware_version | downloads |
|------------------|-----------|
| 72.6.1           | 3146      |

_Output_
```json
{{
  "thought": "Since there is only one row of data, visualizing as a graph would not add much value.",
  "convert": false
}}
```

_Conversation History_
User: I want to flag high-value customers who have not logged in for a long time.
Agent: How do you define high-value customers?
User: Customers who have spent more than $1,000 with us.

_Preview_
| customer_id   | days_since_last_login | total_purchase_value |
|---------------|-----------------------|----------------------|
| 192837465728  | 29                    | $15,780              |
| 129384756473  | 8                     | $12,875              |
| 928374561029  | 25                    | $7,489               |
| 847362910293  | 52                    | $4,199               |
| 463728192837  | 2                     | $2,450               |
| 384756291038  | 31                    | $1,917               |
| 582947102938  | 15                    | $1,450               |
| 756382910274  | 7                     | $1,250               |

_Output_
```json
{{
  "thought": "Comparing login frequency to purchase value does not tell us anything interesting. Moreover, the scale of the values makes it difficult to display the data in a single graph.",
  "convert": false
}}
```

_Conversation History_
User: So how much did she generate?
Agent: Maria generated $1,181,700 in invoices last month.
User: Who are the top sales reps across all dealerships?

_Preview_
| dealership       | sales_rep       |
|------------------|-----------------|
| AutoMax Downtown | Maria Rodriguez |
| CarWorld East    | Yuki Tanaka     |
| Honda DriveTime  | Diego Lopez     |
| Elite Motors     | Hassan Ahmed    |
| Luxury Wheels    | Aisha Patel     |
| BMW of San Jose  | James Wilson    |
| Sunset Motors    | Michael Nguyen  |
| Toyota of LA     | Sophia Chu      |

_Output_
```json
{{
  "thought": "There are no numeric values to plot, so a visualization is not appropriate.",
  "convert": false
}}
```

_Conversation History_
User: Yes, subscriptions is what we're looking for.
Agent: Is there any specific time range you want to consider?
User: No, let's look at all the results

_Preview_
| variant               | conversion_rate |
|-----------------------|-----------------|
| No Change (control)   | 2.32%           |
| Dark Mode Support     | 2.86%           |
| Team Collaboration    | 2.26%           |
| Dark Mode + Collab    | 3.39%           |

_Output_
```json
{{
  "thought": "The variants can serve as the x-axis and conversion_rate as the y-axis",
  "convert": true
}}
```
---
Now it's your turn to decide whether the query results can be visualized.

_Conversation History_
{history}

_Preview_
{preview}

_Output_
"""
