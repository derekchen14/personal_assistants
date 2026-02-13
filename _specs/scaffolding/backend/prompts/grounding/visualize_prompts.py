# =============================================================================
# Grounding prompts for the "visualize" flow category.
# Trimmed to 2 representative templates out of 7 total.
# Removed templates: trend_flow_prompt, explain_flow_prompt,
#   manage_report_prompt, save_to_dashboard_prompt, design_chart_prompt,
#   style_table_prompt
# The removed prompts were shorter "placeholder" style templates with a
# single placeholder scenario and a "Current Scenario" block. They all
# shared the same structure: {valid_tab_col}, {history}, and {current}.
# =============================================================================

plot_flow_prompt = """Given the conversation history and supporting details, your task is to determine the relevant columns for visualizing the user's request.
Supporting details includes the valid tables and columns, along with the previous dialogue state, written as the table name followed by a list of column names.

Start by constructing a concise thought concerning what information is useful for generating a plot or figure.
Then, choosing only from valid tables and columns, generate the list of relevant targets needed to create the visualization.
If it is unclear what tables are being discussed, output 'unsure'. If a column is confusing or uncertain, mark it as ambiguous. If no columns are relevant, then just leave the list empty.
Your entire response should be in well-formatted JSON including keys for thought (string) and result (list) where each item is a dict. There should be no further explanations after the JSON output.
Let's consider six example scenarios, and then tackle the current case.

## 1. Straightforward Scenario
Suppose the valid tables and columns are:
* Tables: mq_leads, product_launches, subscriptions, user_activity
* Columns: lead_id, first_name, last_name, email, organization, lead_source, contact_date, status, notes, follow_up_date in mq_leads;
launch_id, is_secure, provenance, version, features, documentation_link in data_sources;
subscription_id, user_id, plan_name, sub_timestamp, billing_cycle, payment_status, renewal_notice in subscriptions;
activity_id, user_id, activity_type, timestamp, duration, data_source, outcome, error_log in user_activity

_Conversation History_
User: How many leads do we have from the brightline account?
Agent: I do not see any organizations named brightline in our leads database.
User: Which accounts have the most leads then?

_Previous State_
mq_leads - [lead_id, organization]

_Output_
```json
{{
  "thought": "I can count the number of leads using lead_id. I will then group by organization to find the number of leads per account.",
  "result": [
    {{"tab": "mq_leads", "col": "organization"}},
    {{"tab": "mq_leads", "col": "lead_id"}}
  ]
}}
```

## 2. Carrying over from prior state
Suppose the valid tables and columns are:
* Tables: BB_courses, BB_enrollments, Testimonials, CanvasOutreach
* Columns: CourseID, CourseTitle, InstructorID, CourseDescription, StartDate, EndDate, Duration, CourseFormat, Category, EnrollmentCount in BB_courses;
EnrollmentID, CourseID, StudentID, EnrollmentDate, CompletionStatus, Feedback, CertificateLink, PaymentStatus, ReferralSource in BB_enrollments;
TestimonialID, StudentID, CourseID, TestimonialText, DateProvided, Rating, Featured, ApprovalStatus, PhotoLink in Testimonials;
OutreachID, CampaignName, TargetAudience, Platform, ResponseRate, Collaborators in CanvasOutreach

_Conversation History_
User: how many of the students enrolled in the Biology course provided a testimonial?
Agent: 12 students enrolled in Biology provided an approved testimonial.
User: can you show me the number of students who provided testimonials for each course?

_Previous State_
BB_courses - [CourseID, CourseTitle, Category]
BB_enrollments - [CourseID, StudentID, EnrollmentDate]
Testimonials - [CourseID, StudentID, TestimonialText, ApprovalStatus]

_Output_
```json
{{
  "thought": "StudentID can be used to count number of students. BB_Courses is used to group by courses. TestimonialText should be checked to make sure it is not empty, and ApprovalStatus is useful to make sure it can be used. CourseID can be used to group by course and join tables.",
  "result": [
    {{"tab": "BB_courses", "col": "CourseID"}},
    {{"tab": "BB_courses", "col": "CourseTitle"}},
    {{"tab": "BB_enrollments", "col": "StudentID"}},
    {{"tab": "Testimonials", "col": "CourseID"}},
    {{"tab": "Testimonials", "col": "StudentID"}},
    {{"tab": "Testimonials", "col": "TestimonialText"}},
    {{"tab": "Testimonials", "col": "ApprovalStatus"}}
  ]
}}
```

_Lesson_
Pay close attention to the full conversation history since current columns are often carried over from the previous state. CourseTitle is not strictly necessary but can be useful for labeling the plot.

## Current Scenario
For our current case, start with a concise thought followed by JSON output. there should be no explanations or lessons after the JSON output. As reference, the valid tables and columns are:
{valid_tab_col}

_Conversation History_
{history}

_Output_
"""

trend_flow_prompt = """Given the valid tables and columns along with the conversation history, your task is to identify a pattern or trend in the data by running some chart-based analysis.
Start by constructing a concise thought concerning what information is useful for generating a SQL query regarding the final user utterance.
Then, choosing only from valid tables and columns, generate the list of relevant targets needed to create the query.
If it is unclear what tables are being discussed, output 'unsure'. If a column is confusing or uncertain, mark it as ambiguous. If no columns are relevant, then just leave the list empty.

Your entire response should be in well-formatted JSON with keys for thought (string) and result (list) where each item is a dict. There should be no further explanations after the JSON output.
Let's consider six example scenarios, and then tackle the current case.

## 1. Placeholder Scenario
Suppose the valid tables and columns are:
* Tables: BB_courses, BB_enrollments, Testimonials, CanvasOutreach

## Current Scenario
For our current case, start with a concise thought followed by a result list of tabs and cols. There should be no explanations or lessons after the JSON output. As reference, the valid tables and columns are:
{valid_tab_col}
* Current table: {current}

_Conversation History_
{history}

_Output_
"""

# -----------------------------------------------------------------------------
# The following 5 prompts were removed for brevity. Each was a short
# "placeholder" style template with minimal examples, sharing the same
# structure as trend_flow_prompt above: a single placeholder scenario
# followed by a "Current Scenario" block with {valid_tab_col}, {history},
# and {current} placeholders.
#
# Removed prompts:
#   - explain_flow_prompt: Generate explanation/summary of chart
#   - manage_report_prompt: Manage dashboard settings (recurring reports)
#   - save_to_dashboard_prompt: Save visualization to dashboard/file
#   - design_chart_prompt: Design dashboard layout and appearance
#   - style_table_prompt: Style appearance of a permanent derived table
# -----------------------------------------------------------------------------
