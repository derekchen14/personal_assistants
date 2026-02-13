import json
from backend.components.engineer import PromptEngineer

class Clause(object):
  def __init__(self, aggregation, table, column, row='all', name=''):
    self.pytype = 'Clause'
    self.name = f'{table}.{column}' if len(name) == 0 else name
    self.aggregation = aggregation
    self.verified = False

    self.table = table
    self.row = row
    self.column = column

  @classmethod
  def from_entity(cls, entity):
    name = entity['name'] if 'name' in entity.keys() else ''
    aggregation = entity['agg']

    table = entity.get('tab', 'N/A')
    column = entity.get('col', 'N/A')
    row = entity['row'] if 'row' in entity.keys() else 'all'
    new_variable = cls(aggregation, table, column, row, name)

    if 'ver' in entity and entity['ver']:
      new_variable.verified = True
    return new_variable

  def as_dict(self, with_verify):
    entity = {'name': self.name, 'agg': self.aggregation, 'tab': self.table}
    if self.row != 'all':
      entity['row'] = self.row
    entity['col'] = self.column
    if with_verify:
      entity['ver'] = self.verified
    return entity

  def check_if_verified(self):
    return self.verified

  def display(self, style='json', with_verify=False, include_tab=False):
    if style == 'json':
      dict_format = self.as_dict(with_verify=with_verify)
      json_format = '{'
      for key, value in dict_format.items():
        json_format += f'"{key}": "{value}", '
      return json_format[:-2] + '}'
    elif style == 'sql':
      return self.display_as_sql()
    else:
      return self.display_as_line(include_tab)

  def display_as_sql(self):
    # return a SQL representation of the variable
    match self.aggregation:
      case 'all': line = f"{self.table}.{self.column}"
      case 'constant': line = f"{self.row}"
      case 'equals': line = f"{self.table}.{self.column} = {self.row}"
      case 'not': line = f"{self.table}.{self.column} NOT LIKE '%{self.row}%'"
      case 'greater_than': line = f"{self.table}.{self.column} > {self.row}"
      case 'less_than': line = f"{self.table}.{self.column} < {self.row}"
      case 'top': line = f"TOP {self.row} {self.table}.{self.column}"
      case 'bottom': line = f"TOP {self.row} {self.table}.{self.column} DESC"
      case _: line = f"{self.aggregation.upper()}({self.table}.{self.column})"
    return line

  def display_as_line(self, include_tab=False):
    # return a description of the variable, including whether the clauses are verified and their aggregation
    description = f"{self.aggregation} of "

    if include_tab:
      description += f"{self.table}."
    description += f"{self.column}"

    if self.verified:
      description += " (verified)"
    else:
      description += " (candidate)"
    return description

  def describe(self, level=0):
    """Generate a natural language description of the clause."""
    match self.aggregation:
      case 'sum': desc = f"{self.name} is the total of the {self.column} column in the {self.table} table"
      case 'count': desc = f"{self.name} is the number of unique values in the {self.column} column of the {self.table} table"
      case 'average': desc = f"{self.name} is the average of the {self.column} column in the {self.table} table"
      case 'top': desc = f"{self.name} is the largest {self.row} values in the {self.column} column of the {self.table} table"
      case 'bottom': desc = f"{self.name} is the smallest {self.row} values in the {self.column} column of the {self.table} table"
      case 'min': desc = f"{self.name} is the minimum value in the {self.column} column of the {self.table} table"
      case 'max': desc = f"{self.name} is the maximum value in the {self.column} column of the {self.table} table"
      case 'equals': desc = f"{self.name} is true when the {self.column} column in the {self.table} table equals {self.row}"
      case 'not': desc = f"{self.name} is false when the {self.column} column in the {self.table} table contains {self.row}"
      case 'less_than': desc = f"{self.name} is true when {self.table}.{self.column} is less than {self.row}"
      case 'greater_than': desc = f"{self.name} is true when {self.table}.{self.column} is greater than {self.row}"
      case 'filled' | 'empty': desc = f"{self.name} is true when the {self.column} column in the {self.table} table is {self.aggregation}"
      case 'constant': desc = f"{self.name} is a constant value of {self.row}"
      case 'all': desc = f"{self.name} keeps all the raw values in the {self.column} column in the {self.table} table"
      case _: desc = f"{self.name} is the {self.aggregation} of {self.column} in the {self.table} table"
    return desc

  def get_words(self, added=False):
    if self.verified:
      desc = f"We are already able to access the {self.name} by using "
      desc += f"the {self.column} column(s) in the {self.table} table."
    else:
      if added:
        desc = f"We also need to find a column that plays the role of {self.name}. "
      else:
        desc = f"We need to find a column that plays the role of {self.name}, "
        desc += "since it is not immediately apparent. "

      nl_alias = PromptEngineer.array_to_nl(self.aliases[:4])
      desc += f"For example, {self.name} may sometimes come from {nl_alias} columns."
    return desc

class Expression(object):
  relation_mapping = {'+': 'add',       '-': 'subtract',     '*': 'multiply',   '/': 'divide',
                      '&': 'and',       '|': 'or',           '^': 'exponent',   '?': 'conditional',
                      '<': 'less_than', '>': 'greater_than', '=': 'equals',     '#': 'placeholder'}

  def __init__(self, name, relation='', symbol='', variables=[]):
    self.pytype = 'Expression'
    self.name = name
    self.verified = False
    self.aliases = []
    self.variables = variables    # list of Expression or Clause objects

    if relation == '' and symbol == '':
      raise ValueError("Must specify either a symbol or relation")
    if relation == '' and symbol != '':
      relation = self.relation_mapping[symbol]
    elif symbol == '' and relation != '':
      relation, symbol = self._get_symbol(relation)

    self.relation = relation
    self.symbol = symbol

  def _get_symbol(self, relation):
    symbol_mapping = {v: k for k, v in self.relation_mapping.items()}
    symbol = symbol_mapping.get(relation, '#')
    if symbol == '#':
      relation = 'placeholder'
    return relation, symbol

  def add_alias(self, alias, multiple=False):
    if multiple:  # then alias is a list
      self.aliases.extend(alias)
    else:
      self.aliases.append(alias)
    return self.aliases

  def add_variable(self, variables):
    for variable in variables:
      # Prevent adding the same variable twice
      if not any(var.name == variable.name for var in self.variables):
        self.variables.append(variable)
    return self.variables

  def get_name(self, plural=False):
    if plural:
      return self.name
    else:
      return self.name[:-1] if self.name[-1] == 's' else self.name

  def as_dict(self, with_verify):
    expression = {
      'name': self.name,    'rel': self.relation,  'sym': self.symbol,
      'vars': [var.as_dict(with_verify) for var in self.variables]
    }
    return expression

  def check_if_verified(self) -> bool:
    """ Recursively checks if this expression and all its variables are verified. """
    # 1. Must have at least one variable
    if not self.variables:
      self.verified = False
      return False

    self.verified = True
    for var in self.variables:
      # 2. Recursively check child variables
      var.check_if_verified()
      self.verified = self.verified and var.verified

      # 3. All leaf variables must be Clauses (and not Expressions)
      if var.pytype == 'Expression' and not var.variables:
        self.verified = False

    return self.verified

  def drop_unverified(self) -> bool:
    """
    Recursively removes unverified variables in-place.
    Returns True if any variables were dropped, False otherwise.
    """
    any_dropped = False
    index = 0
    while index < len(self.variables):
      var = self.variables[index]
      if not var.verified:
        any_dropped = True
        self.variables.pop(index)
        continue

      if var.pytype == 'Expression':
        if var.drop_unverified():
          any_dropped = True
        if not var.variables:  # Remove expression if it has no variables left
          self.variables.pop(index)
          any_dropped = True
          continue
      index += 1

    return any_dropped

  def _get_prefix(self, index, total_vars):
    """Get the appropriate prefix based on position and number of variables."""
    prefixes = ['In turn', 'Next', 'Then', 'Additionally']
    if index == total_vars - 1 and total_vars >= 2:
      return 'Finally'
    return prefixes[index % len(prefixes)]

  def _get_relation_template(self, level=0):
    templates = {
      'verbose': {
        'add': "{name} is calculated by taking the sum of {vars}",
        'subtract': "{name} is calculated by taking the difference of {vars[0]} minus {vars[1]}",
        'multiply': "{name} is calculated by taking the product of {vars}",
        'divide': "{name} is calculated by taking the ratio of {vars[0]} to {vars[1]}",
        'and': "{name} occurs when {vars} are all true",
        'or': "{name} happens when at least one of these is true: {vars}",
        'exponent': "{name} is calculated by raising {vars[0]} to the power of {vars[1]}",
        'less_than': "{name} checks if {vars[0]} is less than {vars[1]}",
        'greater_than': "{name} checks if {vars[0]} is greater than {vars[1]}",
        'equals': "{name} checks if {vars[0]} equals {vars[1]}",
        'conditional': "{name} takes the value of {vars[1]} when {vars[0]} is true, otherwise {vars[2]}",
        'placeholder': "{name} is currently ambiguous so we need to clarify"
      },
      'concise': {
        'add': "{name} adds {vars} together",
        'subtract': "{name} subtracts {vars[1]} from {vars[0]}",
        'multiply': "{name} multiplies {vars}",
        'divide': "{name} divides {vars[0]} by {vars[1]}",
        'exponent': "{name} is {vars[0]} to the power of {vars[1]}",
        'and': "{name} occurs when {vars} are {all_true}",
        'or': "{name} happens when at least one of these is true: {vars}",
        'less_than': "{name} is less than {vars[0]} than {vars[1]}",
        'greater_than': "{name} is greater than {vars[0]} than {vars[1]}",
        'equals': "{vars[0]} equals {vars[1]}",
        'conditional': "returns {vars[1]} or {vars[2]} depending on {vars[0]}",
        'placeholder': "{name} is unknown"
      }
    }
    template = templates['verbose'] if level == 0 else templates['concise']
    return template.get(self.relation, "{name} with {vars}")

  def _get_special_conditional(self):
    first_var = self.variables[0]
    phrase = self.relation.replace('_', ' ')
    table, row, column = '', '', ''
    is_special = False

    if all(var.pytype == 'Clause' for var in self.variables):
      table, column = first_var.table, first_var.column
      tables = {var.table for var in self.variables}
      columns = {var.column for var in self.variables}
      if len(tables) == 1 and len(columns) == 1:
        aggs = {v.aggregation for v in self.variables}
        # Example: one clause is "equals" and the other "greater_than"
        if "greater_than" in aggs and "equals" in aggs:
          row = next(v.row for v in self.variables if v.aggregation in ["greater_than", "equals"])
          phrase = "greater than or equal"
        elif "less_than" in aggs and "equals" in aggs:
          row = next(v.row for v in self.variables if v.aggregation in ["less_than", "equals"])
          phrase = "less than or equal"
        elif "less_than" in aggs and "greater_than" in aggs:
          row = next(v.row for v in self.variables if v.aggregation == "in between")
          phrase = "in between"
        is_special = True

    return phrase, table, row, column, is_special

  def _collect_descriptions(self, level=0):
    """Collect all descriptions in a flat list, starting with self."""
    if level == 1:
      var_descs = [f"the {var.name}" for var in self.variables]
    else:
      var_descs = [var.name for var in self.variables]

    # Handle special case for conditionals
    if self.relation in ['and', 'or']:
      relation_text, table, row, column, is_special = self._get_special_conditional()
      if is_special:
        return [f"{self.name} measures when {table}.{column} is {relation_text} to {row}"]

    # Get the appropriate template and format it
    template = self._get_relation_template(level)

    # Handle special case for binary operations
    if self.relation in ['divide', 'subtract']:
      desc = template.format(name=self.name, vars=[var_descs[0], var_descs[1]])
    elif self.relation == 'exponent' and var_descs[1] in ['2', 'two']:
      desc = f"{self.name} is square of {var_descs[0]}"
    else:
      match self.relation:
        case 'and': connector = 'and'
        case 'add': connector = 'and'
        case 'multiply': connector = 'by'
        case _: connector = 'or'
      vars_text = PromptEngineer.array_to_nl(var_descs, connector=connector)

      if self.relation == 'and':
        truthy = "both true" if len(var_descs) == 2 and level > 0 else "all true"
        desc = template.format(name=self.name, vars=vars_text, all_true=truthy)
      else:
        desc = template.format(name=self.name, vars=vars_text)

    # Collect descriptions from itself, and then children
    descriptions = [desc]
    if level >= 3:
      return descriptions

    for var in self.variables:
      if var.pytype == 'Expression':
        descriptions.extend(var._collect_descriptions(level + 1))
      elif var.pytype == 'Clause':
        descriptions.append(var.describe(level + 1))
    return descriptions

  def describe(self, level=0):
    """Generate a natural language description of the expression."""
    descriptions = self._collect_descriptions(level)
    descriptions = list(dict.fromkeys(descriptions))  # Remove duplicates while preserving order

    if level == 0 and len(descriptions) > 1:
      # Add prefixes to all but the first description
      prefixed_descriptions = [descriptions[0]]
      remaining = descriptions[1:]

      for i, desc in enumerate(remaining):
        prefix = self._get_prefix(i, len(remaining))
        prefixed_descriptions.append(f"{prefix}, {desc}")

      desc_str = ". ".join(prefixed_descriptions) + "."
    else:
      desc_str = descriptions[0]
    return desc_str

  def display(self, style='json', with_verify=False):
    if style == 'json':
      return self.display_as_json(with_verify=with_verify)
    else:
      return self.display_as_sql()

  def display_as_json(self, with_verify):
    # Return the JSON representation of the expression
    json_format = {'name': self.name}
    if with_verify:
      json_format['verified'] = self.verified
    json_format.update({
      'relation': self.relation,
      'variables': [var.display('json', with_verify) for var in self.variables]
    })
    return json_format

  def display_as_sql(self):
    var1 = self.variables[0].display('sql')
    var2 = self.variables[1].display('sql') if len(self.variables) >= 2 else None
    var3 = self.variables[2].display('sql') if len(self.variables) >= 3 else None

    match self.symbol:
      case '+': return f"{var1} + {var2}" + (f" + {var3}" if var3 else "")
      case '-': return f"{var1} - {var2}"
      case '*': return f"{var1} * {var2}" + (f" * {var3}" if var3 else "")
      case '/': return f"{var1} * 1.0 / NULLIF({var2}, 0)"
      case '^': return f"POWER({var1}, {var2})"
      case '&': return f"{var1} AND {var2}" + (f" AND {var3}" if var3 else "")
      case '|': return f"{var1} OR {var2}" + (f" OR {var3}" if var3 else "")
      case '<': return f"{var1} < {var2}"
      case '>': return f"{var1} > {var2}"
      case '=': return f"{var1} = {var2}"
      case '?': return f"CASE WHEN {var1} THEN {var2} ELSE {var3} END"
      case _:   return f"[Unknown Operation]"


class Formula(object):
  def __init__(self, acronym, expanded, expression=None, description=''):
    self.pytype = 'Formula'
    self.acronym = acronym
    self.expanded = expanded

    self.aliases = []
    self.description = description
    self.expression = expression

    self.open_for_revision = False
    self.verified = False

  def get_name(self, size='full', case='title'):
    """
    sizes - [full, long, short] which return the full name, expanded, and acronym, respectively
    cases - lower, title, snake, which will change the case of the name
    """
    if size == 'full':
      return f"{self.expanded} ({self.acronym})"
    elif size == 'long':
      long_name = self.expanded
      if case == 'lower':
        return long_name.lower()
      elif case == 'title':
        return long_name.title()
      elif case == 'snake':
        return long_name.lower().replace(' ', '_')
    elif size == 'short':
      return self.acronym

  def describe_target(self, X_var):
    """ Return phrases based on the number of degrees
    unary - we want to focus on the X_var
    binary - X_var, and will deal with the Y_var separately
    ternary - we want to focus on the X_var, and will deal with Y_var and Z_var separately
    """
    other_vars = []
    for variable in self.expression.variables:
      if variable.name != X_var:
        other_vars.append(variable.name)

    phrase = f"we want to focus on the {X_var}"
    if len(other_vars) == 1:
      phrase += f", and will deal with the {other_vars[0]} separately"
    elif len(other_vars) == 2:
      phrase += f", and will deal with the {other_vars[0]} and {other_vars[1]} separately"
    return phrase

  def initialize_template(self):
    # Create raw template for divide and conquer analyze flow
    formula_sql = self.expression.display('sql')
    metric_name = self.get_name(size='long', case='snake')

    template = "WITH "
    for variable in self.expression.variables[::-1]:
      var_name = variable.name.replace(' ', '_')
      template += f"<{var_name}_alias> AS (\n  <{var_name}_SQL_code>\n),\n"
    template += f"SELECT\n"
    for variable in self.expression.variables:
      var_name = variable.name.replace(' ', '_')
      template += f"<{var_name}_result>,\n"
    template += f"  COALESCE({formula_sql}, 0) AS {metric_name}\n"
    template += f"FROM <CTE_alias>;"
    return template

  def build_template(self, code_snippets, previous_variables):
    if len(code_snippets) != len(previous_variables):
      raise ValueError("Number of code snippets does not match the number of variables")
    template = self.initialize_template()

    for snippet, var_name in zip(code_snippets, previous_variables):
      lines = snippet.split('\n')
      var_name = var_name.replace(' ', '_')

      # replace the calculated column alias
      alias_candidate = lines[0]
      if ':' in alias_candidate:
        alias = alias_candidate.split(':')[1].strip()
      else:
        alias = alias_candidate.strip()
      alias_marker = f'<{var_name}_alias>'
      template = template.replace(alias_marker, alias)

      # replace the generated SQL code
      code_marker = f'  <{var_name}_SQL_code>'
      query_lines = [line for line in lines[1:] if not line.startswith('```')]
      tabbed_query = '\n'.join(['  ' + line.strip() for line in query_lines])
      template = template.replace(code_marker, tabbed_query)
    return template

  def add_aliases(self, aliases):
    if isinstance(aliases, str):
      self.aliases.append(aliases)
    elif isinstance(aliases, list):
      self.aliases.extend(aliases)

  def add_clause(self, variable_name, tab_name, col_name, relation='', verification=False):
    for variable in self.expression.variables:
      if variable.name == variable_name:
        variable.add_clause(tab_name, col_name, relation, verification)

  def variable_names(self, all_vars=False):
    # Helper function to recursively collect variable names
    def collect_names(expr, recursive):
      names = []
      for var in expr.variables:
        names.append(var.name)
        if recursive and var.pytype == 'Expression':
          names.extend(collect_names(var, recursive=True))
      return names

    # Collect all variable names first
    var_names = collect_names(self.expression, recursive=all_vars)
    # Format the names into a string only once at the end
    var_str = PromptEngineer.array_to_nl(var_names, connector='and')
    return var_str

  def display(self, with_verify=False):
    """ output a formula view of the expression, including whether the variables are verified """
    def format_element(element, indent=0):
      spaces = ' ' * indent

      if element.pytype == 'Clause':
        # Format Clauses as a single line (leaf nodes)
        return f'{spaces}{element.display(with_verify=with_verify)}'

      elif element.pytype == 'Expression':
        # Format Expressions with proper indentation and line breaks
        result = f"{spaces}{{\n"
        result += f"{spaces}  \"name\": \"{element.name}\",\n"
        if with_verify:
          result += f"{spaces}  \"verified\": {str(element.verified).lower()},\n"
        result += f"{spaces}  \"relation\": \"{element.relation}\",\n"
        result += f"{spaces}  \"variables\": [\n"

        # Process each variable
        for i, var in enumerate(element.variables):
          comma = "," if i < len(element.variables) - 1 else ""
          var_str = format_element(var, indent + 4)
          result += f"{var_str}{comma}\n"

        result += f"{spaces}  ]\n"
        result += f"{spaces}}}"
        return result

    return format_element(self.expression)

  def verify_variables(self, variables: list) -> bool:
    # Marks the variables as verified if they are present in the list, then checks if the entire formula is verified
    def _cascade_verification(expr):
      expr.verified = True
      if expr.pytype == 'Expression':
        for var in expr.variables:
          _cascade_verification(var)

    def _verify_recursively(expr):
      # Handle leaf nodes (Clauses)
      if expr.pytype == 'Clause':
        if expr.name in variables:
          expr.verified = True
        return

      # Handle Expression nodes
      for var in expr.variables:
        if var.name in variables:
          _cascade_verification(var)
        elif var.pytype == 'Expression':
          _verify_recursively(var)

    if self.expression.name in variables:
      _cascade_verification(self.expression)
    else:
      _verify_recursively(self.expression)

    return self.expression.check_if_verified()
