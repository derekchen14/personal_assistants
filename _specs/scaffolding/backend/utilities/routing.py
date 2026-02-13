def style_sql_message(query):
  show_msg = True
  if "SELECT *" in query:
    sql_msg = "return all the data"
    show_msg = False
  elif "\n" in query:
    sql_msg = query.replace("\n", "<br>")
    sql_msg = sql_msg.replace("  ", "&nbsp;&nbsp;")
  else:
    try:
      from_position = query.index("FROM")
      partial = query[:from_position] + "<br>" + query[from_position:]
      if "JOIN" in partial:
        join_position = partial.index("JOIN")
        partial = partial[:join_position] + "<br>" + partial[join_position:]
      if "WHERE" in partial:
        where_position = partial.index("WHERE")
        partial = partial[:where_position] + "<br>" + partial[where_position:]
      if "AND" in partial:
        and_position = partial.index("AND")
        partial = partial[:and_position] + "<br>" + partial[and_position:]
      if "GROUP" in partial:
        group_position = partial.index("GROUP")
        partial = partial[:group_position] + "<br>" + partial[group_position:]
      sql_msg = partial
    except:
      sql_msg = query

  sql_message = f"<em>SQL Query</em>:<br>{sql_msg}"
  return sql_message, show_msg

def style_pandas_message(code):
  code = code.replace("\n", "<br>")
  code = code.replace("self.db.tables", "df")
  code = code.replace(", inplace=True", "")
  html_msg = f"<em>Pandas Code</em>:<br>{code}"
  return html_msg

def style_issues_message(query, issue_type):
  mapping = {'concern': 'Concerns', 'blank': 'Empty Values', 'problem': 'Problems'}
  nl_issue = mapping[issue_type]
  query = query.replace("\n", "<br>")
  html_msg = f"<em>Potential {nl_issue}</em>:<br>{query}"
  return html_msg

def build_json_response_for_frame(knowledge):
  frame, show_msg, flow_type = knowledge, True, 'Default(flow)'
  if frame.source == 'pandas':
    frame_msg = style_pandas_message(frame.code)
  elif frame.source == 'sql':
    frame_msg, show_msg = style_sql_message(frame.code)
    flow_type = 'Analyze(query)'
  elif frame.source == 'plotly':
    frame_msg, show_msg = style_sql_message(frame.code)
  elif frame.source in ['concern', 'blank', 'problem']:
    frame_msg = style_issues_message(frame.code, frame.source)
  elif frame.source in ['typo', 'interaction', 'default', 'error', 'change']:
    frame_msg, show_msg = '', False

  frame_json = {'tabType': frame.tab_type, 'interaction': {
    'content': frame_msg, 'format': 'html', 'show': show_msg, 'flowType': flow_type,
  }}
  if frame.tab_type == 'derived':
    tab_name = '(stage_' + frame.raw_table + ')'
    frame_json['frame'] = {'tabs': [tab_name], 'data': frame.get_data('json')}
    if hasattr(frame, 'properties'):
      raw_properties = frame.properties
      properties = {k.split('.')[-1]: v for k, v in raw_properties.items()}
      frame_json['properties'] = {tab_name: properties}
  else:
    frame_json['frame'] = frame.get_data('define')
  return frame_json

def build_json_response_for_state(knowledge):
  html_thought = knowledge.thought.replace("\n", "<br>")
  thought_json = {'interaction': {
    'content': html_thought, 'format':'html', 'show':True, 'flowType': 'Default(thought)',
  }}
  return thought_json
