# ------------------------------------------------------------------
# TRIMMED FOR SPEC BREVITY
# Original file: 3,730 lines with 22 prompt templates.
# Kept 3 representative prompts below (issue_redirection_prompt, concern_type_prompt, typo_type_prompt).
# Removed 19 prompts: problem_type_prompt, resolve_routing_prompt,
#   insight_routing_prompt, proposal_confirmation_prompt, blank_plan_prompt,
#   concern_plan_prompt, problem_plan_prompt, typo_plan_prompt,
#   insight_plan_prompt, automatic_plan_prompt, revise_plan_prompt,
#   revise_hypothesis_prompt, adjust_plan_prompt, convert_to_flow_prompt,
#   summarize_results_prompt, interesting_enough_prompt, focus_metric_prompt
# ------------------------------------------------------------------

issue_redirection_prompt = """When interacting with the {column} column, we encountered {description}.
Given the final turn in the conversation history, decide how the user wants to address the issue. Possible methods include:
  * update - change the values to a new value based on user specification, including interpolating new values
  * remove - delete the rows with the issues
  * ignore - do nothing, leave the issues as they are
  * recommend - suggest a course of action to the user
  * unsure - the user has not given a clear resolution, potentially because they are exploring alternatives

Start by thinking carefully about what the user is saying in the last utterance, and then output the appropriate resolution.
Your entire response should only contain well-formatted JSON including the thought (string) and method (string), with no further explanations after the JSON output.

For example,
#############
_Conversation History_
User: Yes, please show me.
Agent: The email column has 3 missing values. We can fill in the values, remove the rows, or just ignore the problem.
User: This is fine, not much we can do

_Output_
```json
{{
  "thought": "the user is dismissing the missing emails as not an issue",
  "method": "ignore"
}}
```

_Conversation History_
Agent: Agent: I found 3 outliers in the DiscountAmount column. Would you like to investigate?
User: Sure, what are the values?
Agent: The outliers are 50, 75, and 100. What should I do with them?
User: Divide by 10 so they are in the correct range

_Output_
```json
{{
  "thought": "Calculating new values is an update action",
  "method": "update"
}}
```

_Conversation History_
User: So what's the most popular city then?
Agent: I found 4 missing values in the ResolvedStatus column. Please see the table for details.
User: I guess those weren't resolved then.

_Output_
```json
{{
  "thought": "the user has not made a clear decision",
  "method": "unsure"
}}
```

_Conversation History_
User: What does that mean?
Agent: I found 6 default values in the OrderDeliveryName column. We can update the values, remove the rows, or just ignore the problem.
User: Dunno, what do you think?

_Output_
```json
{{
  "thought": "the user is asking the agent to recommend a course of action",
  "method": "recommend"
}}
```

_Conversation History_
User: Are there any issues with the enrollment data?
Agent: I found 3 textual anomalies in the Enrollment Status column. Please see the table for more.
User: Let's just drop the ones that are misspelled

_Output_
```json
{{
  "thought": "The user wants to remove some subset of the anomalies",
  "method": "remove"
}}
```

_Conversation History_
User: How many clicks is that in total?
Agent: The total is 5,486 clicks. However, I found some concerns which may affect the answer. See the table for more.
User: What exactly are the concerns?
Agent: There are 7 numeric outliers in the Impressions column. How would you like to proceed?
User: We should compare with the average to see if they are significantly different

_Output_
```json
{{
  "thought": "the user is conducting some preliminary analysis before deciding on a resolution",
  "method": "unsure"
}}
```
#############
Please think about how the user wants to deal with the problem and output the appropriate JSON. Remember to only choose a method from one of the four valid options.

_Conversation History_
{history}

_Output_
"""

concern_type_prompt = """Given a sample of the data and rows containing potential concerns, determine the type of issues found in the column, if any.
Rows with potential concerns will be highlighted with an arrow (<--). The possible issue types are:
  * outlier - a numeric value that is significantly different from the rest of the data
  * anomaly - a textual value that is unexpected or inconsistent with the rest of the data
  * date_issue - a datetime that is inconsistent or set to some meaningless default
  * loc_issue - a location or address that is inconsistent or set to some meaningless default

Based on our understanding of the column's data type, the only issue is a '{main_type}', but this is exactly what we want to review.
Please start by constructing a concise thought concerning why the highlighted rows might be considered concerns.
After deciding whether the concern is legitimate or not, output the most likely concern types in a list.
If the detected issues are actually reasonable given the context, then they are not real concerns, so the output should be an empty list.
Your entire response should be in well-formatted JSON with thought (string) and issues (list) as keys. There should be no further explanations after the JSON output.

For example,
#############
_Sample Data_
Column: Total Spend
$3.45 - 2 instances
$2.67 - 5 instances
$2.34 - 1 instance
$300.00 - 1 instance <--
$1.23 - 3 instances
$2.01 - 3 instances
$2.92 - 2 instances
$2.30 - 4 instances
(1641 other unique values ...)

_Output_
```json
{{
  "thought": "The value of $300.00 is significantly higher than the rest of the data.",
  "issues": ["outlier"]
}}
```

_Sample Data_
Column: Projected Profit
$1,000 - 2 instances
$3,000 - 5 instances
$2,000 - 4 instance
$3,500 - 9 instance
-$1,500 - 3 instances <--
$2,500 - 3 instances
-$2,500 - 2 instances <--
$4,000 - 1 instances
(5 other unique values ...)

_Output_
```json
{{
  "thought": "A negative value is unusual, but can be interpreted as a loss, so this is not an outlier.",
  "issues": [ ]
}}
```

_Sample Data_
Column: arrival_date
May 12, 2023 - 2 instances
May 15, 2023 - 5 instances
May 17, 2023 - 4 instance
May 16, 2023 - 9 instance
May 0, 2023 - 1 instances <--
May 14, 2023 - 3 instances
May 13, 2023 - 3 instances
May 11, 2023 - 2 instances
(236 other unique values ...)

_Output_
```json
{{
  "thought": "The date of May 0, 2023 is not a valid date.",
  "issues": ["date_issue"]
}}
```

_Sample Data_
Column: Drop-off Location
Philadelphia - 24 instances
Lancaster - 18 instances
Harrisburg - 15 instances
Allenstown - 12 instances
Pittsburgh - 17 instances
Scranton - 13 instances
PA - 9 instances <--
Bethlehem - 7 instances
(8 other unique values ...)

_Output_
```json
{{
  "thought": "The location 'PA' is not a specific city and is likely a concern.",
  "issues": ["loc_issue"]
}}
```

_Sample Data_
Column: Product Name
Radiant Glow Liquid Foundation - 1 instance
Rejuvenating Face Oil - 2 instances
Soothing Chamomile Eye Cream - 1 instance
Deep Moisture Hair Mask - 1 instance
Calming Chamomile Sleep Spray - 1 instance
Jasmine Joy Perfume - 1 instance
Brightening Under-Eye Cream - 1 instance
Protect your skin from harmful UV rays with our lightweight, non-greasy sun cream. Just spray on before heading out for a healthy protection. - 1 instance <--
Detangling Silk Protein Hair Spray - 1 instance
(227 other unique values ...)

_Output_
```json
{{
  "thought": "It seems a product description was mistakenly added to the product name.",
  "issues": ["anomaly"]
}}
```
#############
Now it's your turn! Think carefully about the highlighted rows and provide the most likely issue type in well-formatted JSON output.
For reference, we have the following conversation history and supporting details:

_Conversation History_
{history}

_Sample Data_
Column: {column}
{samples}

_Output_
"""

typo_type_prompt = """Given a sample of the data and rows containing potential typos, determine the type of issue found in the column.
The potential typos will be highlighted with an arrow (<--). The possible issue types are:
  * replacement: the word or phrase has meaning, but is likely incorrect as inferred from the context
    - suppose the values in the column are 'apple', 'pear', 'grape', 'orange', 'great', and 'banana'. Then 'great' should be replaced with 'grape'.
    - suppose the values in the column are 'LinkedIn', 'Facebook', 'Twitter', 'tiktok', 'Snapchat', and 'TikTok'. Then 'tiktok' should be replaced with 'TikTok'.
  * misspelled: the word is not found in a standard dictionary
    - suppose the values in the column are 'apple', 'pear', 'grape', 'ornage', 'banana', and 'kiwi'. Then 'ornage' is likely a misspelling of 'orange'.
    - suppose the values in the column are 'LinkedIn', 'Facebook', 'Twitter', 'TikToc', 'Snapchat', and 'TikTok'. Then 'TikToc' is likely a misspelling of 'TikTok'.
  * none: detected issues are not really typos, they are actually spelled correctly given the context

Please start by constructing a concise thought concerning why the highlighted rows might be considered a typo.
After deciding whether the typo is legitimate or not, output the most likely typo type as a single token.
If multiple issue types are present, then output the option which seems to appear most frequently.
Your entire response should be in well-formatted JSON with thought and issues as keys. There should be no further explanations after the JSON output.

For example,
#############
_Sample Data_
Column: first_contact_source
LinkedN - 18 instances <--
Phone - 19 instances
Salesforce - 15 instances
Direct Mail - 2 instances
LinkedIn - 23 instances
In Person - 7 instances
linkedin - 3 instances <--
Phone call - 11 instances <--
(12 other unique values ...)

_Output_
```json
{{
  "thought": "There are many typos, but the most prevalent is 'LinkedN' instead of 'LinkedIn'.",
  "issue_type": "misspelled"
}}
```

_Sample Data_
Column: Supplier
Radiant Revival Remedies - 135 instances
CrownGlow Creations - 98 instances
SilkenStrand Solutions - 126 instances
HydraHeal Holistics - 103 instances
Made You Blush - 152 instances
Radiant Revival Remedy - 3 instances <--
BellaCanvas Colors - 87 instances
Pure Touch Therapeutics - 112 instances
(6 other unique values ...)

_Output_
```json
{{
  "thought": "Although 'Remedy' is a valid word, it should be 'Remedies' to match the other values.",
  "issue_type": "replacement"
}}
```

_Sample Data_
Column: topline metrics
CVR - 21 instances
CPC - 18 instances
CPM - 15 instances
CAC - 12 instances
retention - 3 instances <--
CTR - 7 instances
CPA - 11 instances
ROI - 9 instances
(7 other unique values ...)

_Output_
```json
{{
  "thought": "While retention isn't an acronym, it is a valid metric, so it is not a typo.",
  "issue_type": "none"
}}
```

_Sample Data_
Column: paymentMethod
Paypal - 98 instances
Credit Card - 135 instances <--
Debit Card - 126 instances
Apple Pay - 103 instances
Credit - 152 instances

_Output_
```json
{{
  "thought": "It's unclear if 'Credit' or 'Credit Card' is correct, but they are likely the same thing.",
  "issue_type": "replacement"
}}
```

_Sample Data_
Column: final_mp_loc
Los Angeles - 135 instances
San Francisco - 126 instances
Santa Monica - 103 instances
Riverside - 98 instances
San Diego - 152 instances
Pasadena - 39 instances
San Deigo - 4 instances <--
Santa Barbara - 112 instances
(19 other unique values ...)

_Output_
```json
{{
  "thought": "The city 'San Deigo' is a common misspelling of 'San Diego'.",
  "issue_type": "misspelled"
}}
```

_Sample Data_
Column: EmailAddress
portofauthoritay12@gmail.com - 1 instance
tommorrow_never_dies1@hotmail.com - 1 instance <--
jacksonbaby44@gamesville.com - 1 instance
licence_to_drill@gmail.com - 1 instance <--
customerservice@beautyshop.com - 1 instance
contemplatingdeeply@gmail.com - 1 instance
brugers4life@gmail.com - 1 instance
johnsonalert99@yahoo.com - 1 instance
(514 other unique values ...)

_Output_
```json
{{
  "thought": "Although 'tomorrow' and 'license' are common typos, this is part of an email address where anything goes.",
  "issue_type": "none"
}}
```
#############
Now it's your turn! Think carefully about the highlighted rows and provide the most likely issue type in well-formatted JSON output.
For reference, we have the following conversation history and supporting details:

_Conversation History_
{history}

_Sample Data_
Column:
{samples}

_Output_
"""
