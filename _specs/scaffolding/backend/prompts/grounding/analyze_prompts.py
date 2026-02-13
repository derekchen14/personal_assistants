# =============================================================================
# Grounding prompts for the "analyze" flow category.
# Trimmed to 3 representative templates out of 9 total.
# Removed templates: segment_analysis_prompt, pivot_flow_prompt,
#   describe_flow_prompt, check_existence_prompt, recommend_flow_prompt,
#   inform_metric_prompt, define_metric_prompt
# These followed the same few-shot pattern with scenario-based examples
# and a final "Current Scenario" block with {valid_tab_col}, {history},
# {prior_state}, and/or {current} placeholders.
# =============================================================================

query_flow_prompt = """Given the conversation history and supporting details, your task is to determine the relevant columns to query.
Supporting details includes the valid tables and columns, along with the previous dialogue state, written as the table name followed by a list of column names.

Start by constructing a concise thought concerning what information is useful for generating a SQL query regarding the final user utterance.
Then, choosing only from valid tables and columns, generate the list of relevant targets needed to create the query.
If it is unclear what tables are being discussed, output 'unsure'. If a column is confusing or uncertain, mark it as 'ambiguous'. If no columns are relevant, then just leave the list empty.
Current columns are often carried over from the previous state, so pay close attention since it provides useful context that may not be available from the conversation alone.
Your entire response should be in well-formatted JSON including keys for thought (string) and result (list) where each item is a dict, with no further explanations before or after the JSON output.
Each item in the list should be a dict with keys for 'tab' (string), 'col' (string), and optionally 'rel' (string) when the column is 'ambiguous'.

For example,
---
## Online Course Scenario
* Tables: BB_courses, BB_enrollments, Testimonials, CanvasOutreach
* Columns: CourseID, CourseTitle, InstructorID, CourseDescription, StartDate, EndDate, Duration, CourseFormat, Category, EnrollmentCount in BB_courses;
EnrollmentID, CourseID, StudentID, EnrollmentDate, CompletionStatus, Feedback, CertificateLink, PaymentStatus, ReferralSource in BB_enrollments;
TestimonialID, StudentID, CourseID, TestimonialText, DateProvided, Rating, Featured, ApprovalStatus, PhotoLink in Testimonials;
OutreachID, CampaignName, TargetAudience, Platform, ResponseRate, Collaborators in CanvasOutreach

_Conversation History_
User: how many of the students enrolled in the Biology course provided a testimonial?
Agent: 12 students enrolled in Biology provided an approved testimonial.
User: how about for the Chemistry course?

_Previous State_
BB_courses - [CourseID, CourseTitle, Category]
BB_enrollments - [CourseID, StudentID, EnrollmentDate]
Testimonials - [CourseID, StudentID, TestimonialText, ApprovalStatus]

_Output_
```json
{{
  "thought": "StudentID can be used to count number of students. BB_Courses info can match for Chemistry. TestimonialText should be checked to make sure it is not empty, and ApprovalStatus is useful to make sure it can be used. CourseID can be used to group by course and join tables.",
  "result": [
    {{"tab": "BB_courses", "col": "CourseID"}},
    {{"tab": "BB_courses", "col": "CourseTitle"}},
    {{"tab": "BB_courses", "col": "Category"}},
    {{"tab": "BB_enrollments", "col": "CourseID"}},
    {{"tab": "BB_enrollments", "col": "StudentID"}},
    {{"tab": "BB_enrollments", "col": "EnrollmentDate"}},
    {{"tab": "Testimonials", "col": "CourseID"}},
    {{"tab": "Testimonials", "col": "StudentID"}},
    {{"tab": "Testimonials", "col": "TestimonialText"}},
    {{"tab": "Testimonials", "col": "ApprovalStatus"}}
  ]
}}
```

## Restaurant Scenario
* Tables: customerContact, customerOrders, marketingOffers
* Columns: CustomerID, CustName, FavCuisineType, ShippingAddress, ContactNumber, IsActive, Twitter, Instagram, Yelp in customerContact;
OrderID, CustomerID, RestaurantID, OrderDate, TotalAmount, DeliveryAddress, OrderStatus, EstDeliveryTime, SpecialInstructions in customerOrders;
OfferID, OfferTitle, OfferDescription, OrderKey, StartDate, EndDate, DiscountAmount, ApplicableRestaurants, RedemptionCode in marketingOffers

_Conversation History_
User: ok, let's also check for the SEND40OFF code
Agent: The SEND40OFF redemption code was used by 23 customers.
User: What are their email addresses?

_Previous State_
customerOrders - [OrderID, CustomerID]
marketingOffers - [OrderKey, EndDate, RedemptionCode]

_Output_
```json
{{
  "thought": "RedemptionCode can be used to filter for SEND40OFF and I can group customers with CustomerID. EndDate matches the year with OrderID and OrderKey for joins. Although customerContact has a ShippingAddress column, this is likely a physical address and not an email address, so EmailAddress is ambiguous.",
  "result": [
    {{"tab": "customerOrders", "col": "OrderID"}},
    {{"tab": "customerOrders", "col": "CustomerID"}},
    {{"tab": "marketingOffers", "col": "OrderKey"}},
    {{"tab": "marketingOffers", "col": "EndDate"}},
    {{"tab": "marketingOffers", "col": "RedemptionCode"}},
    {{"tab": "customerContact", "col": "EmailAddress", "rel": "ambiguous"}}
  ]
}}
```

---
## Current Scenario
{valid_tab_col}

_Conversation History_
{history}

_Previous State_
{prior_state}

_Lesson_
Please choose the list of relevant tab and cols from the valid options, which means preserving all spacing, capitalization, and special characters. There should be no text or explanations after the JSON output.

_Output_
"""

measure_flow_prompt = """Based on the conversation history, we currently want to calculate a marketing metric or KPI.
Please start by identifying the metric the user wants to calculate, and which columns need to be aggregated to produce the metric.
In all likelihood, the relationship may not be entirely obvious, in which case you should select _potentially_ relevant columns to form variables, and then combine these variables to calculate the metric.
Furthermore, consider whether there are any global filters, groupings, or other transformations might be applicable to the calculation as a whole.
Finally, note whether there are any complications or uncertainties that need to be resolved before proceeding.

When you predict the metric, be sure to includes its short form as `(acronym)` where the name is surrounded by parentheses. Common examples include: ARPU, AOV, CTR, CVR, ROAS, ROI, CPA, CPC, CPM, DAU, MAU, NPS, etc.
Some other not-so-standard short forms we also recognize include: Bounce, Churn, Device, Engage, Retain, Abandon, Open, and Profit.
These stand for Bounce Rate, Customer Churn Rate, Device Ratio, Engagement Rate, Retention Rate, Abandonment Rate, Email Open Rate, and Net Profit, respectively.
Of course, it is entirely possible that the user is not referring to any of these metrics, in which case you should generate a metric name that best captures the user's intent, matching industry standards where possible.
If the metric is not clear or not mentioned, then label it as `unsure`. For example, you could say: 'I am (unsure) what metric the user wants to calculate.'

Whenever a column is mentioned, (whether for aggregation, filtering, or variable formation) be sure to write it as `<column_name>` where the name is surrounded by angle brackets.
Also, please keep a bit of white space outside of the angle brackets to make it easier to read and parse.
If there are no obviously matching columns or conversely, multiple conflicting columns that could be used, then note these issues in your thoughts.
Critically, in all cases, do *not* mention any invalid columns. This is very important to my career, only choose from valid columns!

Your goal at the moment is to simply produce a well formed thought -- there is no need to write any code yet!
To give a sense of an ideal thought process, we will go through some sample scenarios, and then tackle the final real scenario.
Notice that the generated thoughts are only a few sentences long, so please avoid any unnecessary details.

For example,
---
## Enterprise Data Security Scenario
For our first sample spreadsheet, suppose the valid options are:
* Tables: HubspotCRM; TransactionHistory; InteractionLogs
* Columns: cust_id, signup_date, cust_name, email, region, tracking_id, channel, acct_status in HubspotCRM;
trans_id, cust_id, trans_date, product_id, amount, trans_type, license_fee, service_charge, maintenance_income in the TransactionHistory;
interaction_id, cust_id, interact_date, interact_type, interact_duration, issue_resolved, expenses in the InteractionLogs

_Conversation History_
User: How many new customers did we get in the past month from the west coast?
Agent: We acquired 2,398 new customers in the past month in the west coast.
User: Can you help me figure out how many of them are still around?

_Output_
A likely metric is retention rate (Retain) , which is the number of active customers divided by the total number of customers.
We should start by filtering for the west coast, likely using the <region> column. <signup_date> is likely the best way to determine if a customer is acquired.
Grouping by customer id <cust_id> will allow us to form the base of total customers.
The last interaction date <interact_date> or the last transaction date <trans_date> are both ways to determine if a customer is active in the last month, so we should clarify before proceeding.

## E-commerce Online Advertiser Scenario
For our second sample spreadsheet, suppose the valid options are:
* Tables: GoogleAds_Q3, SalesRecord_Shopify_0812, Product_Details
* Columns: gAd_ID, spend(Dollars), clickCount, campaignInitDate, campaignTermDate, adBounceRate, audienceFocus, adContentCode in GoogleAds_Q3;
orderRef, prodSKU, saleDate, acquisitionCost, buyerID, gAdRef, revenueGenerated, unitsMoved, fulfillmentStatus, customerNotes in SalesRecord_Shopify_0812;
SKU, itemName, itemCategory, retailPrice, totalCost, stockLevel in Product_Details

_Conversation History_
User: What is the CPC for our ads?
Agent: Sure, I will need to verify the cost and clicks first. Does this look right?
User: Yea, clickCount looks good.

_Output_
Continuing the calculation of (CPC) , the user has confirmed that <clickCount> is the correct column for clicks, but we still need to verify the column used to derive cost.
Both <spend(Dollars)> and <totalCost> are plausible options for cost, but I will choose <spend(Dollars)> because it comes from the same table as <clickCount> .
When performing calculations, we should limit cost to only those that are directly attributable to clicks.

---
## Current Scenario
For our real case, the available data includes:
{valid_tab_col}
The currently active table is '{current}'.

_Conversation History_
{history}

Now it's your turn! Please generate a thought process that highlights the important considerations when calculating the target metric, making sure to note any surprising or nuanced interpretations.
Remember to use angle brackets ('<' and '>') to denote column names, and to keep your response concise.

_Output_
"""

# If any ambiguity arises, rather than making assumptions, instead note the uncertainty and consider what clarification is needed.
segment_analysis_prompt = """As seen in the conversation history, the user wants to perform complex analysis that likely takes multiple steps.
Before diving into a calculation, it's important to fully understand the situation and the data we need to access in order to avoid embarrassing mistakes.
However, this is not be straightforward because the final result requires deriving accurate intermediate results, which in turn necessitates careful planning.

Let's start by considering how we can manage the scope of the analysis, focusing on three key areas:
  1. Grounding to existing data
    * Can we identify specific tables or columns to focus our attention?
    * Is it possible to limit the scope by filtering to rows containing certain values?
    * Are there any time-based constraints that can help us narrow down the range?
  2. Staging intermediate results
    * What groupings or aggregations are needed in our query when pulling the data?
    * Should we create temporary tables or columns to store the derived metrics?
    * What validation checks can we put in place to confirm calculation accuracy?
  3. Disambiguating underspecified requests
    * Are we making any unwarranted assumptions about the user's intent?
    * What steps might contain branching logic that require clarification?
    * What information is still missing before we can proceed with the analysis?

When formulating your thoughts, whenever a column is referenced, be sure to write it as <column_name> where the name is surrounded by angle brackets: < and >.
These thoughts will set the foundation of our plan, which is tackled later on the process.
To reiterate, we are *not* writing any code or producing a plan at this stage, just outlining the key considerations.
Consequently, your entire response should be contained within a single paragraph that spans no longer than 5-7 sentences.

For example,
---
## Initial Request
For our first example, suppose the tables and columns are:
* Tables: CodePathCourses, StudentProgress, LearnerSuccess, MarketingCampaigns
* Columns: CourseID, TrackName, LeadMentorID, TechStackJSON, CohortStartDate, CohortEndDate, WeeklyCommitmentHrs, DeliveryFormat, DifficultyLevel, CurrentEnrollment, MaxCapacity, PreReqSkills, GitHubTemplateURL in CodePathCourses;
ProgressID, CourseID, LearnerUUID, EnrollmentDate, MilestoneStatus, LastSubmissionURL, PeerReviewScore, TuitionPlanType, EmploymentStatus, MentorNotes, ActiveStatus in StudentProgress;
SuccessID, LearnerUUID, CourseID, CareerOutcome, SalaryIncrease, TestimonialBody, DateSubmitted, NPSScore, CompanyPlaced, ShowcasePermission in LearnerSuccess;
CampaignID, InitiativeName, CareerSegment, LinkedInAudience, ConversionMetrics, PartnershipType, BudgetAllocated, LeadSource in MarketingCampaigns

_Conversation History_
User: What is the range of peer review scores for all students in the last cohort?
Agent: Using CohortStartDate to determine the last cohort, the peer review scores range from 60 to 95.
User: Ok, taking a broader view, does increased student activity lead to better outcomes?

Since the user has just begun to make a request, limited information is available to guide our analysis.
Thus, our focus should be enumerating the missing details we need to proceed, such as specific columns or time constraints.

_Output_
To analyze if increased student activity leads to better outcomes, we need to first ground our analysis using <LastSubmissionURL>, <MilestoneStatus>, and <ActiveStatus> from StudentProgress as activity indicators,
linking to outcome metrics like <CareerOutcome>, <SalaryIncrease>, and <NPSScore> from LearnerSuccess through the common <LearnerUUID> identifier.
Given so many options, we will need clarification on which combination of indicators is used to define 'activity', and also how to measure which outcomes are 'better'.
Since the conversation previously referenced the last cohort, we should consider using <CohortStartDate> and <CohortEndDate> to place constraints on the time period for analysis.
For staging, we should consider creating intermediate metrics that aggregate activity levels per student while accounting for different <PreReqSkills> and <DifficultyLevel> variations across courses,
as these could confound our analysis. Several critical pieces remain ambiguous and require user input: whether to control for factors like <TechStackJSON>, whether to segment by <DeliveryFormat>,
and how exactly should we determine what constitutes a 'better' outcome?

---
For our real case, the available data includes:
{valid_tab_col}
The currently active table is '{current}'.

_Conversation History_
{history}

Now it's your turn! Please generate a thorough thought process that hits upon (1) grounding, (2) staging, and (3) disambiguation.
Remember to use angle brackets (< and >) to denote column names, and to keep your response concise.

_Output_
"""

# -----------------------------------------------------------------------------
# The following 6 prompts were removed for brevity. Each followed the same
# pattern as the templates above: few-shot scenario examples with JSON output,
# ending with a "Current Scenario" block using {valid_tab_col}, {history},
# {prior_state}, and/or {current} placeholders.
#
# Removed prompts:
#   - pivot_flow_prompt: Pivot table column selection (6 scenarios)
#   - describe_flow_prompt: Table/column reference identification (2 spreadsheets)
#   - check_existence_prompt: Table/column existence checking (2 spreadsheets)
#   - recommend_flow_prompt: Action recommendation (placeholder + current)
#   - inform_metric_prompt: Metric information (placeholder + current)
#   - define_metric_prompt: Metric definition (placeholder + current)
# -----------------------------------------------------------------------------
