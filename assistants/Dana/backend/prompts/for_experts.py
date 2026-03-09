INTENT_INSTRUCTIONS = (
    'Classify the user utterance into exactly one intent.\n\n'
    'Available intents:\n'
    '- Clean: modify cell values, fix data types, remove duplicates, '
    'validate values against allowed options, format values into correct form\n'
    '- Transform: insert/delete rows or columns, join/append tables, '
    'reshape, merge/split columns, define formulas\n'
    '- Analyze: run SQL queries, look up metric definitions, pivot, '
    'describe datasets, compare variables, segment (drilldown analysis), '
    'check data existence\n'
    '- Report: create charts (bar, line, pie), plot trends, '
    'build dashboards, summarize data/results, style tables, design charts\n'
    '- Converse: greetings, preferences, recommendations, '
    'explain what the agent did or plans to do (analysis process), '
    'undo, approve/reject suggestions. '
    'Note: summarize (Report) is grounded to a specific chart or table; '
    'explain (Converse) is about the analysis process in general\n'
    '- Plan: complex insights requiring multiple steps, ETL pipelines, '
    'issue detection, data validation, find blanks\n\n'
    'Do NOT predict "Internal" — that intent is system-only '
    '(includes retrieve for FAQs/reference info).\n\n'
    'Think step-by-step about the user\'s goal, then classify.'
)

INTENT_OUTPUT_SHAPE = (
    '```json\n'
    '{{"thought": "<reasoning>", "intent": "<Intent>"}}\n'
    '```'
)

INTENT_EXEMPLARS = '''
---
User: "change the value in row 5 to 100"
_Output_
```json
{{"thought": "User wants to modify a cell value in place.", "intent": "Clean"}}
```
---
User: "cast the date column to datetime"
_Output_
```json
{{"thought": "User wants to fix a column data type.", "intent": "Clean"}}
```
---
User: "remove duplicate rows"
_Output_
```json
{{"thought": "Deduplication is a cleaning operation.", "intent": "Clean"}}
```
---
User: "join sales and inventory on product"
_Output_
```json
{{"thought": "User wants to combine two tables.", "intent": "Transform"}}
```
---
User: "rename the column to total_cost"
_Output_
```json
{{"thought": "User wants to rename a column.", "intent": "Transform"}}
```
---
User: "add a new column called profit"
_Output_
```json
{{"thought": "Adding a column is a transformation.", "intent": "Transform"}}
```
---
User: "what's the average revenue?"
_Output_
```json
{{"thought": "User wants to compute a metric — but first needs to know what 'average revenue' means in context.", "intent": "Analyze"}}
```
---
User: "filter rows where region is North"
_Output_
```json
{{"thought": "User wants to subset rows by a condition — handled via query.", "intent": "Analyze"}}
```
---
User: "describe the sales dataset"
_Output_
```json
{{"thought": "User wants structure, types, and stats for a dataset.", "intent": "Analyze"}}
```
---
User: "group by region and sum revenue"
_Output_
```json
{{"thought": "Group-by summarization is an analysis operation — handled via query.", "intent": "Analyze"}}
```
---
User: "compare revenue between Q1 and Q2"
_Output_
```json
{{"thought": "Comparing two groups is an analysis operation.", "intent": "Analyze"}}
```
---
User: "Break down MAU by platform"
_Output_
```json
{{"thought": "Breaking down a metric by a dimension is a drilldown analysis.", "intent": "Analyze"}}
```
---
User: "What's driving the revenue drop? Drill down by region"
_Output_
```json
{{"thought": "Drilling down by region to diagnose a metric change is analysis.", "intent": "Analyze"}}
```
---
User: "make a bar chart of revenue by region"
_Output_
```json
{{"thought": "User wants to create a chart.", "intent": "Report"}}
```
---
User: "plot the trend of sales over time"
_Output_
```json
{{"thought": "User wants a trend visualization.", "intent": "Report"}}
```
---
User: "hello"
_Output_
```json
{{"thought": "Simple greeting.", "intent": "Converse"}}
```
---
User: "what does standard deviation mean?"
_Output_
```json
{{"thought": "Asking about a statistical concept — summarize interprets data grounded to a chart or table.", "intent": "Report"}}
```
---
User: "I prefer dark charts"
_Output_
```json
{{"thought": "Setting a display preference.", "intent": "Converse"}}
```
---
User: "What did you just do?"
_Output_
```json
{{"thought": "User wants to know what action the agent took — process explanation.", "intent": "Converse"}}
```
---
User: "Why did you choose that analysis?"
_Output_
```json
{{"thought": "User wants to understand the agent's reasoning — process explanation.", "intent": "Converse"}}
```
---
User: "What does this chart mean?"
_Output_
```json
{{"thought": "User wants a summary of a chart.", "intent": "Report"}}
```
---
User: "Highlight cells above 1000 in red"
_Output_
```json
{{"thought": "Styling table cells is a reporting operation.", "intent": "Report"}}
```
---
User: "Change the bar chart colors to blue"
_Output_
```json
{{"thought": "Changing chart design is a reporting operation.", "intent": "Report"}}
```
---
User: "Check this data for problems"
_Output_
```json
{{"thought": "Validating data quality is a cleaning operation.", "intent": "Clean"}}
```
---
User: "Normalize the date formats"
_Output_
```json
{{"thought": "Normalizing formats is a formatting/cleaning operation.", "intent": "Clean"}}
```
---
User: "Format the phone numbers correctly"
_Output_
```json
{{"thought": "Formatting values into correct form is a cleaning operation.", "intent": "Clean"}}
```
---
User: "Interpolate the missing temperature readings"
_Output_
```json
{{"thought": "Estimating missing values from surrounding data is a cleaning operation.", "intent": "Clean"}}
```
---
User: "Make sure all emails are valid entries"
_Output_
```json
{{"thought": "Checking values against valid options is a cleaning operation.", "intent": "Clean"}}
```
---
User: "Are there any data quality issues?"
_Output_
```json
{{"thought": "Diagnosing data quality issues is a multi-step plan.", "intent": "Plan"}}
```
---
User: "find all the issues in the price column"
_Output_
```json
{{"thought": "Issue detection is a multi-step diagnosis.", "intent": "Plan"}}
```
---
User: "check for missing values"
_Output_
```json
{{"thought": "Finding blanks is a multi-step diagnosis.", "intent": "Plan"}}
```
---
User: "create a pipeline to clean and analyze this data"
_Output_
```json
{{"thought": "Multi-step pipeline planning.", "intent": "Plan"}}
```
'''


FLOW_INSTRUCTIONS = (
    'Given the predicted intent and conversation context, detect the most '
    'specific flow for the user utterance.\n\n'
    'Each flow has a dax code, description, and slots. Pick the flow that '
    'best matches what the user wants to accomplish.\n\n'
    'If multiple flows could match, prefer:\n'
    '1. The flow whose description most closely matches the user\'s goal\n'
    '2. The flow with slots that match extractable information\n'
    '3. The simpler/more common flow over the specialized one\n\n'
    'Also extract any slot values you can identify from the utterance.'
)

FLOW_OUTPUT_SHAPE = (
    '```json\n'
    '{{\n'
    '  "thought": "<reasoning about which flow matches>",\n'
    '  "flow_name": "<flow_name>",\n'
    '  "confidence": <0.0-1.0>,\n'
    '  "slots": {{"<slot_name>": "<value>", ...}}\n'
    '}}\n'
    '```'
)

FLOW_EXEMPLARS = '''
---
Intent: Converse
User: "hello"
_Output_
```json
{{"thought": "Simple greeting.", "flow_name": "chat", "confidence": 0.95, "slots": {{}}}}
```
---
Intent: Report
User: "what does this chart show?"
_Output_
```json
{{"thought": "User wants a summary of a specific chart artifact.", "flow_name": "summarize", "confidence": 0.90, "slots": {{"dataset": "sales", "chart": "bar chart"}}}}
```
---
Intent: Converse
User: "What did you just do?"
_Output_
```json
{{"thought": "User wants to know what the agent did — process explanation.", "flow_name": "explain", "confidence": 0.90, "slots": {{}}}}
```
---
Intent: Converse
User: "Why that approach?"
_Output_
```json
{{"thought": "User asks about reasoning behind the chosen analysis.", "flow_name": "explain", "confidence": 0.90, "slots": {{}}}}
```
---
Intent: Converse
User: "I prefer larger fonts"
_Output_
```json
{{"thought": "Setting a preference.", "flow_name": "preference", "confidence": 0.85, "slots": {{"key": "font_size", "value": "large"}}}}
```
---
Intent: Internal
User: "what are our shipping FAQs?"
_Output_
```json
{{"thought": "User wants to pull business reference info.", "flow_name": "retrieve", "confidence": 0.90, "slots": {{"topic": "shipping FAQs"}}}}
```
---
Intent: Clean
User: "change the value in cell B3 to 500"
_Output_
```json
{{"thought": "User wants to update a cell value. Update also handles renaming columns (e.g., 'Rename the qty column to quantity').", "flow_name": "update", "confidence": 0.90, "slots": {{"column": "B", "row": "3", "value": "500"}}}}
```
---
Intent: Clean
User: "remove duplicate rows"
_Output_
```json
{{"thought": "Removing duplicates.", "flow_name": "dedupe", "confidence": 0.90, "slots": {{}}}}
```
---
Intent: Clean
User: "cast the date column to datetime"
_Output_
```json
{{"thought": "Fixing a column data type.", "flow_name": "datatype", "confidence": 0.90, "slots": {{"column": "date", "type": "datetime"}}}}
```
---
Intent: Transform
User: "join sales and inventory on product"
_Output_
```json
{{"thought": "Joining two tables.", "flow_name": "join", "confidence": 0.95, "slots": {{"left": "sales", "right": "inventory", "key": "product"}}}}
```
---
Intent: Transform
User: "delete the cost column"
_Output_
```json
{{"thought": "Removing a column.", "flow_name": "delete", "confidence": 0.90, "slots": {{"target": "cost"}}}}
```
---
Intent: Analyze
User: "describe the sales dataset"
_Output_
```json
{{"thought": "User wants structure, types, and stats.", "flow_name": "describe", "confidence": 0.95, "slots": {{"dataset": "sales"}}}}
```
---
Intent: Analyze
User: "what does 'churn rate' mean in our metrics?"
_Output_
```json
{{"thought": "Looking up a metric definition.", "flow_name": "lookup", "confidence": 0.90, "slots": {{"term": "churn rate"}}}}
```
---
Intent: Analyze
User: "show rows where revenue > 5000"
_Output_
```json
{{"thought": "Filtering by condition — handled via query.", "flow_name": "query", "confidence": 0.90, "slots": {{"query": "SELECT * WHERE revenue > 5000"}}}}
```
---
Intent: Analyze
User: "group by region and sum revenue"
_Output_
```json
{{"thought": "Group-by summarization — handled via query.", "flow_name": "query", "confidence": 0.90, "slots": {{"query": "SELECT region, SUM(revenue) FROM data GROUP BY region"}}}}
```
---
Intent: Analyze
User: "run SELECT * FROM sales WHERE region = 'North'"
_Output_
```json
{{"thought": "Explicit SQL query.", "flow_name": "query", "confidence": 0.95, "slots": {{"query": "SELECT * FROM sales WHERE region = 'North'"}}}}
```
---
Intent: Analyze
User: "cross-tabulate product by region"
_Output_
```json
{{"thought": "Pivot table request.", "flow_name": "pivot", "confidence": 0.85, "slots": {{"row_dim": "product", "col_dim": "region"}}}}
```
---
Intent: Analyze
User: "compare revenue vs cost by quarter"
_Output_
```json
{{"thought": "Comparing two variables across groups.", "flow_name": "compare", "confidence": 0.90, "slots": {{"column_a": "revenue", "column_b": "cost"}}}}
```
---
Intent: Analyze
User: "Break down monthly active users by platform"
_Output_
```json
{{"thought": "Drilldown of a metric by dimension.", "flow_name": "segment", "confidence": 0.95, "slots": {{"dataset": "users", "metric": "MAU", "dimension": "platform"}}}}
```
---
Intent: Analyze
User: "Drill into revenue by region"
_Output_
```json
{{"thought": "Drilldown of revenue segmented by region.", "flow_name": "segment", "confidence": 0.90, "slots": {{"metric": "revenue", "dimension": "region"}}}}
```
---
Intent: Report
User: "make a bar chart of revenue by product"
_Output_
```json
{{"thought": "Creating a bar chart.", "flow_name": "plot", "confidence": 0.95, "slots": {{"chart_type": "bar"}}}}
```
---
Intent: Report
User: "show the sales trend over time"
_Output_
```json
{{"thought": "Time series trend.", "flow_name": "trend", "confidence": 0.90, "slots": {{"column": "revenue"}}}}
```
---
Intent: Plan
User: "Find outliers and typos in this column"
_Output_
```json
{{"thought": "Multi-step issue detection.", "flow_name": "issue", "confidence": 0.90, "slots": {{"column": "price"}}}}
```
---
Intent: Plan
User: "check for missing values in the dataset"
_Output_
```json
{{"thought": "Null detection diagnosis.", "flow_name": "blank", "confidence": 0.90, "slots": {{}}}}
```
---
Intent: Plan
User: "what insights can you find about revenue trends?"
_Output_
```json
{{"thought": "Complex question requiring multi-step analysis.", "flow_name": "insight", "confidence": 0.85, "slots": {{"question": "revenue trends"}}}}
```
---
Intent: Report
User: "Highlight rows where revenue > 1000"
_Output_
```json
{{"thought": "Conditional formatting on table cells.", "flow_name": "style", "confidence": 0.90, "slots": {{"condition": "revenue > 1000"}}}}
```
---
Intent: Report
User: "Make the chart legend bigger"
_Output_
```json
{{"thought": "Adjusting chart visual design.", "flow_name": "design", "confidence": 0.90, "slots": {{"element": "legend", "adjustment": "bigger"}}}}
```
---
Intent: Report
User: "Change chart colors to a blue palette"
_Output_
```json
{{"thought": "Changing chart color scheme.", "flow_name": "design", "confidence": 0.90, "slots": {{"palette": "blue"}}}}
```
---
Intent: Clean
User: "Validate the email column format"
_Output_
```json
{{"thought": "Checking column values against valid options.", "flow_name": "validate", "confidence": 0.90, "slots": {{"column": "email"}}}}
```
---
Intent: Clean
User: "Format phone numbers to (xxx) xxx-xxxx"
_Output_
```json
{{"thought": "Formatting values into correct form.", "flow_name": "format", "confidence": 0.90, "slots": {{"dataset": "data", "column": "phone", "pattern": "phone_us"}}}}
```
---
Intent: Clean
User: "Standardize the email addresses"
_Output_
```json
{{"thought": "Formatting values into consistent form.", "flow_name": "format", "confidence": 0.90, "slots": {{}}}}
```
---
Intent: Clean
User: "Interpolate missing values in the price column"
_Output_
```json
{{"thought": "Estimating missing values from surrounding data.", "flow_name": "interpolate", "confidence": 0.90, "slots": {{"column": "price"}}}}
```
---
Intent: Plan
User: "1. Clean the data 2. Join with inventory 3. Plot sales by region"
_Output_
```json
{{"thought": "Multi-step plan from numbered instructions.", "flow_name": "outline", "confidence": 0.90, "slots": {{"instructions": "1. Clean the data 2. Join with inventory 3. Plot sales by region"}}}}
```
'''


def build_intent_prompt(user_text: str, history_text: str) -> str:
    parts = [
        f'## Conversation History\n\n{history_text}\n' if history_text else '',
        f'## Instructions\n\n{INTENT_INSTRUCTIONS}\n',
        f'## Output Format\n\n{INTENT_OUTPUT_SHAPE}\n',
        f'## Examples\n{INTENT_EXEMPLARS}\n',
        f'## Current Utterance\n\nUser: "{user_text}"\n\n',
        '_Output_',
    ]
    return '\n'.join(p for p in parts if p)


def build_flow_prompt(user_text: str, intent: str | None, history_text: str,
                      candidate_flows: str) -> str:
    parts = [
        f'## Conversation History\n\n{history_text}\n' if history_text else '',
    ]
    if intent:
        parts.append(f'## Predicted Intent: {intent}\n')
    parts.extend([
        f'## Candidate Flows\n\n{candidate_flows}\n',
        f'## Instructions\n\n{FLOW_INSTRUCTIONS}\n',
        f'## Output Format\n\n{FLOW_OUTPUT_SHAPE}\n',
        f'## Examples\n{FLOW_EXEMPLARS}\n',
        f'## Current Utterance\n\nUser: "{user_text}"\n\n',
        '_Output_',
    ])
    return '\n'.join(p for p in parts if p)
