export const rowStyleDetails = {
  // Shared for all Schemas
  order:  { title: 'Order of Appearance',     type: 'radio_btn',      choices: {
    'first': "Keep the value from the row that appeared higher in the table.",
    'last': "Keep the value from the row that appeared lower in the table."},       icon: 'signpost'},
  time:   { title: 'Time Period',             type: 'radio_btn',      choices: {
    'earlier': "Keep the row which occurred earlier according to the '<COL>' column.",
    'later': "Keep the row which occurred later according to the '<COL>' column."}, icon: 'calendar'},
  binary: { title: 'External Binary Column',  type: 'radio_btn',      choices: {
    'positive': "Keep the row if the '<COL>' column has a 'True' value.",
    'negative': "Keep the row if the '<COL>' column has a 'False' value."}, icon: 'halfstar'},
  contains: { title: 'Contains a Substring',  type: 'input_box',      choices: {
    'description': "Prefer the row when it matches or contains the given text string.",
    'input box': 'Text:'},                                            icon: 'substring'},
  question: { title: "I'm Not Sure",          type: 'desc_only',       choices: {
    'description': "Show me some examples of potential conflicts before deciding what do to."},
    example: 'N/A',                                                   icon: 'question'},
  automatic: { title: "Automatic Merge",      type: 'desc_only',       choices: {
    'description': "Dana can decide how to resolve all remaining merge conflicts for me."},
    example: 'N/A',                                                   icon: 'automatic'},

  // Number Schema
  add:    { title: 'Addition',                type: 'desc_exp',       choices: {    
    'description': "Add the values in the two rows together."},
    example: '15 + 6 = 21',                                           icon: 'plus'},
  subtract: {title: 'Subtraction',            type: 'radio_exp',      choices: {
    'first': "Subtract the second row from the first row.",
    'second': "Subtract the first row from the second row."}, 
    example: '15 - 6 = 9',                                            icon: 'minus'},
  multiply: {title: 'Multiplication',         type: 'desc_exp',       choices: {
    'description': "Multiply the values in the two rows together."},
    example: '15 * 6 = 90',                                           icon: 'times'},
  divide: { title: 'Division',                type: 'radio_exp',      choices: {
    'numerator': "Divide the first row by the second row.",
    'denominator': "Divide the second row by the first row."},
    example: '15 / 6 = 2.5',                                          icon: 'divider'},
  mean:   { title: 'Average',                 type: 'desc_exp',       choices: {        
    'description': "Take the average of the values in the rows."},
    example: 'avg(9, 15, 6) = 10',                                    icon: 'balance'},
  size:   { title: 'Number Size',             type: 'radio_btn',      choices: {
    'minimum': "Keep the value that is smaller.",
    'maximum': "Keep the value that is larger."},                     icon: 'comparison'},
  power:  { title: 'Exponentiation',          type: 'radio_btn',      choices: {
    'base': "Raise the first row to the power of the second row.",
    'exponent': "Raise the second row to the power of the first row."},             icon: 'superscript'},
  log:    { title: 'Logarithm',               type: 'radio_btn',      choices: {
    'base': "Calculate the log of the first row with second row as the base.",
    'exponent': "Calculate the log of the second row with first row as the base."}, icon: 'squareroot'},

  // Text Schema
  length: { title: 'Text Length',             type: 'radio_btn',      choices: {
    'longer': "Keep the text from the row with longer content.",
    'shorter': "Keep the text from the row with shorter content." },  icon: 'ruler'},
  alpha:   { title: 'Alphabetical',           type: 'radio_btn',      choices: {
    'A to Z': "Keep the text which comes earlier in the alphabet.",
    'Z to A': "Keep the text which comes later in the alphabet." },   icon: 'sort'},
  concat: { title: 'Concatenate',             type: 'desc_exp',       choices: {
    'description': "Combine the text together directly, with no space in between."},
    example: 'socialmedia',                                           icon: 'concat'},
  space:   { title: 'Join w/ Space',          type: 'desc_exp',       choices: {
    'description': "Join the text of the two rows with an empty space."},
    example: 'social media',                                          icon: 'space'},
  underscore: {title: 'Join w/ Underscore',   type: 'desc_exp',       choices: {
    'description': "Join the text of the two rows with an underscore."},
    example: 'social_media',                                          icon: 'underscore'},
  period: { title: 'Join w/ Period',          type: 'desc_exp',       choices: {
    'description': "Join the text of the two rows with a period."},
    example: 'social.media',                                          icon: 'period'},
  comma:  { title: 'Join w/ Comma',           type: 'desc_exp',       choices: {
    'description': "Join the text of the two rows with a comma."},
    example: 'social,media',                                          icon: 'comma'},
  separator: {title: 'Choose a Separator',    type: 'input_box',      choices: {
    'description': "Join the text of the two rows with a custom separator.", 
    'input box': 'Sep:'},                                             icon: 'keyboard'},

  place:  {title: 'Placeholder',              type: 'desc_exp',      choices: {
    'description': "Lorem ipsum dolor sit amet, consectetur adipiscing elit."},
    exaple: 'other text here',                                       icon: 'placeholder'},
};

export const colStyleDetails = {
  // Shared for all Schemas
  order:  { title: 'Order of Appearance',     type: 'radio_btn',      choices: {
    'first': "Keep the value from the column that appeared further to the left.",
    'last': "Keep the value from the column that appeared further to the right."},    icon: 'signpost'},
  time:   { title: 'Time Period',             type: 'radio_btn',      choices: {
    'earlier': "Keep the column which occurred earlier according to the '<COL>' column.",
    'later': "Keep the column which occurred later according to the '<COL>' column."}, icon: 'calendar'},
  binary: { title: 'External Binary Column',  type: 'radio_btn',      choices: {
    'positive': "Keep the column if the '<COL>' column has a 'True' value.",
    'negative': "Keep the column if the '<COL>' column has a 'False' value."},        icon: 'halfstar'},
  contains: { title: 'Contains a Substring',  type: 'input_box',      choices: {
    'description': "Prefer the column when it matches or contains the given text string.",
    'input box': 'Text:'},                                            icon: 'substring'},

  // Number Schema
  add:    { title: 'Addition',                type: 'desc_exp',       choices: {    
    'description': "Add the values in the two columns together."},
    example: '15 + 6 = 21',                                           icon: 'plus'},
  subtract: {title: 'Subtraction',            type: 'radio_exp',      choices: {
    'first': "Subtract the second column from the first column.",
    'second': "Subtract the first column from the second column."}, 
    example: '15 - 6 = 9',                                            icon: 'minus'},
  multiply: {title: 'Multiplication',         type: 'desc_exp',       choices: {
    'description': "Multiply the values in the two columns together."},
    example: '15 * 6 = 90',                                           icon: 'times'},
  divide: { title: 'Division',                type: 'radio_exp',      choices: {
    'numerator': "Divide the first column by the second column.",
    'denominator': "Divide the second column by the first column."},
    example: '15 / 6 = 2.5',                                          icon: 'divider'},
  mean:   { title: 'Average',                 type: 'desc_exp',       choices: {        
    'description': "Take the average of the values in the columns."},
    example: 'avg(9, 15, 6) = 10',                                    icon: 'balance'},
  size:   { title: 'Number Size',             type: 'radio_btn',      choices: {
    'minimum': "Keep the value that is smaller.",
    'maximum': "Keep the value that is larger."},                     icon: 'comparison'},
  power:  { title: 'Exponentiation',          type: 'radio_btn',      choices: {
    'base': "Raise the first column to the power of the second column.",
    'exponent': "Raise the second column to the power of the first column."},         icon: 'superscript'},
  log:    { title: 'Logarithm',               type: 'radio_btn',      choices: {
    'base': "Calculate the log of the first col with second col as the base.",
    'exponent': "Calculate the log of the second col with first col as the base."},   icon: 'squareroot'},

  // Text Schema
  length: { title: 'Text Length',             type: 'radio_btn',      choices: {
    'longer': "Keep the text from the column with longer content.",
    'shorter': "Keep the text from the column with shorter content." },  icon: 'ruler'},
  alpha:   { title: 'Alphabetical',           type: 'radio_btn',      choices: {
    'A to Z': "Keep the text which comes earlier in the alphabet.",
    'Z to A': "Keep the text which comes later in the alphabet." },   icon: 'sort'},
  concat: { title: 'Concatenate',             type: 'desc_exp',       choices: {
    'description': "Combine the text together directly, with no space in between."},
    example: 'socialmedia',                                           icon: 'concat'},
  space:   { title: 'Join w/ Space',          type: 'desc_exp',       choices: {
    'description': "Join the text of the two columns with an empty space."},
    example: 'social media',                                          icon: 'space'},
  underscore: {title: 'Join w/ Underscore',   type: 'desc_exp',       choices: {
    'description': "Join the text of the two columns with an underscore."},
    example: 'social_media',                                          icon: 'underscore'},
  period: { title: 'Join w/ Period',          type: 'desc_exp',       choices: {
    'description': "Join the text of the two columns with a period."},
    example: 'social.media',                                          icon: 'period'},
  comma:  { title: 'Join w/ Comma',           type: 'desc_exp',       choices: {
    'description': "Join the text of the two columns with a comma."},
    example: 'social,media',                                          icon: 'comma'},
  separator: {title: 'Choose a Separator',    type: 'input_box',      choices: {
    'description': "Join the text of the two columns with a custom separator.", 
    'input box': 'Sep:'},                                             icon: 'keyboard'},
};