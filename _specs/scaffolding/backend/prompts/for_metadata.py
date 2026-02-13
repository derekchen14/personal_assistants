exact_col_prompt = """The '{column}' column was originally labeled a {original} sub type from {orig_parent} data type.
However, we suspect that the column was miscategorized and may actually contain {proposed} type of data.

For more context, the datatypes with their subtypes are:
  * unique - each value holds a unique meaning. Includes IDs (often used as primary keys), pre-defined categories, set of statuses, and boolean values.
  * datetime - related to dates or times. Includes quarter, month, day, year, week, date, time, hour, minute, second, and timestamp.
  * location - the values are related to geographical locations or addresses. Includes streets, cities, states, countries, zip codes, and full addresses.
  * number - the values are numeric and can be used for calculations. Includes currency, percent, whole numbers, and decimals.
  * text - the values are textual and can include any characters. Includes email addresses, phone numbers, URLs, names, and general text.

Please review the examples carefully to decide which data type they represent.
Then, output your answer as either `{original}` or `{proposed}` without any additional text or explanations.
Your entire response should be in well-formatted JSON with keys for 'thought' and 'answer'.

For example,
#############
Column name - phone_number
Original - datatype: text, subtype: phone
Proposed - datatype: number, subtype: whole
Samples - ['(650)774-8901', '(650)595-2121', '(451)783-4412', '(650)494-1287', '(880)236-1554', '(650)616-3123', '(556)256-5686', '(650)903-0403']

_Output_
```json
{{
  "thought": "Even though the word 'number' is in the column name, the values are all text strings. This is a false positive.",
  "answer": "phone"
}}
```
#############
Column name - meeting_time
Original - datatype: datetime, subtype: timestamp
Proposed - datatype: datetime, subtype: time
Samples - ['1900-01-01 08:30:00', '1900-01-01 09:45:00', '1900-01-01 10:30:00', '1900-01-01 08:45:00', '1900-01-01 11:30:00', '1900-01-01 10:30:00', '1900-01-01 09:15:00', '1900-01-01 14:00:00']

_Output_
```json
{{
  "thought": "The values are technically timestamps, but they all share the same default date which is likely inaccurate. People are not setting up meetings 100 years in the past. This is a true positive.",
  "answer": "time"
}}
```
#############
Column name - validateParking
Original - datatype: unique, subtype: status
Proposed - datatype: datetime, subtype: date
Samples - ['pass', 'invalid', 'fail', 'pass', 'pass', 'invalid', 'fail', 'pass']

_Output_
```json
{{
  "thought": "Even though the word 'date' is in the column name, the values are different parking validation statuses. This is a false positive.",
  "answer": "status"
}}
```
#############
Column name - conversionRate
Original - datatype: number, subtype: decimal
Proposed - datatype: number, subtype: percent
Samples - ['1.14', '5.04', '7.20', '0.98', '1.25', '6.77', '11.00', '0.05']

_Output_
```json
{{
  "thought": "Although the values are outside the range of 0 to 1, they do represent values that should be seen as percentages. This is a true positive.",
  "answer": "percent"
}}
```
#############
Now, please decide whether the proposed {proposed} data type is more appropriate for our case:
Column name - {column}
Original - datatype: {orig_parent}, subtype: {original}
Proposed - datatype: {prop_parent}, subtype: {proposed}
Samples - {samples}

_Output_
"""

short_content_prompt = """The '{col_name}' column within a spreadsheet is made up of {true_desc}. Samples include:
{true_data}

However, some of the rows suggest that the column may be of '{suspect_type}' data type, representing {suspect_desc}.
In particular, the following cases are potentially problematic:
{suspect_data}

Please think carefully about your answer, and then say `yes` if the column contains a legitimate problem with mixed data types, or `no` otherwise.
Your entire response should be in well-formatted JSON including a thought and answer, with no further text or explanations.

For example,
#############
_Output_
```json
{{
  "thought": "Since most values are written as text like ['two', 'five', 'three'], I can see why someone included 4. However, this mixes text and numbers, so it is a problem.",
  "answer": "yes"
}}
```

#############
_Output_
```json
{{
  "thought": "DE could be a state, but given we are looking at the language column, it is more likely that DE represents German. This is an alternative spelling of a valid category, so it is not a problem.",
  "answer": "no"
}}
```

#############
_Output_
```json
{{
  "thought": "[3, 9, 5] could be hours in a day, but the OrdersPlaced column holds the count of orders, which naturally includes numbers. Thus, we are probably just looking at additional valid numbers, rather than mixing in a time data type.",
  "answer": "no"
}}
```

#############
_Output_
```json
{{
  "thought": "'8 PM' is indeed a time, but the values are mostly written in the HH:MM format. This mixes text strings with timestamps data types, which is a problem.",
  "answer": "yes"
}}
```

#############
Now it is your turn. Given the above information, does the column actually contain '{suspect_type}' data mixed with '{true_type}' data, or is this a false positive?

_Output_
"""

id_examples = """
Column 'primary_id' with values: ['20500P', '20501P', '20502P', '20503P', '20504P']
Answer: yes

Column 'purchaseid' with values: ['pc_68001', 'pc_68002', 'pc_68003', 'pc_68004', 'pc_68005']
Answer: yes

Column 'indicator_id' with values: [00, 00, 01, 10, 10]
Answer: no

Column 'account_id' with values: ['lucy01', 'kathy00', 'xinyi', 'david97', 'jason0201']
Answer: no
"""

timestamp_examples = """
Column 'Timestamp' with values: [1970-01-01 00:00:00, 1970-01-01 00:00:00, 1970-01-01 00:00:00, 1970-01-01 00:00:00, 1970-01-01 00:00:00]
Answer: yes

Column 'created_timestamp' with values: [2022-01-01 , 1970-01-01 00:00:00, 2022-01-05 04:00:00, 2022/01/02, 2022_1_4]
Answer: no
"""

city_examples = """
Column 'City_NJ' with values: [NJ_Newark, NJ_Jersey City, NJ_Paterson, NJ_Elizabeth, NJ_Edison]
Answer: yes

Column 'city' with values: [NJ, NY, CA, TX, FL]
Answer: no
"""

state_examples = """
Column 'state_eastern' with values: [New Jersey, New York, Connecticut, Pennsylvania, Delaware]
Answer: yes

Column 'state' with values: [Newark, Jersey City, Paterson, Elizabeth, Edison]
Answer: no
"""

price_examples = """
Column 'price_discounted' with values: [$0.10, €0.20, €20,00, ¥69.99, $2.99]
Answer: yes

Column 'price' with values: [0.07, 0.0875, 0.07, 0.07, 0.0875]
Answer: no
"""

email_examples = """
Column 'secondary_email' with values: [lulugmail.com, emily99@gmail.com, 9175281234@hotmail.com, 10027lily@gmail.com, david123!@gmail.com]
Answer: yes

Column 'email' with values: [lucy01, kathy00, xinyi, david97, jason0201]
Answer: no
"""

detect_blank_prompt = """Given the column contents and currently detected missing and default values, decide if we can accept the detected blanks or if they need to be revised.

The detected missing terms are: {missing_terms}
The detected default terms are: {default_terms}

Please review the context of the column and determine if these detected blanks are correct given the rest of the data.
Your entire response should be in well-formatted JSON with keys for 'accept' (boolean), 'missing_terms' (list), and 'default_terms' (list).
If accept is True, then the missing_terms and default_terms lists can be empty.
If accept is False, provide the corrected lists of terms that should be considered missing or default values.
There should be no additional text or explanations before or after the JSON output.

For example,
---
_Sample Data_
Column: Age
Under 18 - 75 instances
18 to 24 - 124 instances
35 to 44 - 150 instances
25 to 34 - 229 instances
N/A - 13 instances <--
45 to 54 - 17 instances
55 to 64 - 58 instances
65 and older - 30 instances

Detected missing terms: N/A
Detected default terms:

_Output_
```json
{{
  "accept": true,
  "missing_terms": [],
  "default_terms": []
}}
```

_Sample Data_
Column: Hobby
reading - 613 instances
running - 230 instances
swimming - 211 instances
cycling - 198 instances
hiking - 177 instances
fill in later - 19 instances <--
dancing - 156 instances
cooking - 143 instances

Detected missing terms:
Detected default terms: fill in later

_Output_
```json
{{
  "accept": true,
  "missing_terms": [],
  "default_terms": []
}}
```

_Sample Data_
Column: Status
active - 450 instances
inactive - 230 instances
pending - 180 instances
test - 15 instances <--
suspended - 125 instances

Detected missing terms:
Detected default terms: test

_Output_
```json
{{
  "accept": false,
  "missing_terms": [],
  "default_terms": ["test", "pending"]
}}
```
---
Now for the current case:
_Sample Data_
Column: {column}
{samples}

Detected missing terms: {missing_terms}
Detected default terms: {default_terms}

_Output_
"""