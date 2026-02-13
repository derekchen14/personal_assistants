from abc import ABC, abstractmethod
import os
import json
import pandas as pd
import time
from typing import Dict, List, Any, Optional, Tuple

class UserPreferences:
  """Unified API layer for managing user preferences with memory capabilities."""

  def __init__(self):
    self._user_prefs = {
      'goal': MajorGoalsPreference(),
      'timing': TimeHorizonPreference(),
      'caution': RiskTolerancePreference(),
      'special': SpecialAdjustmentsPreference(),
      'viz': VisualizationSettingsPreference(),
      'metric': CustomMetricsPreference(),
      'sig': BenchmarkSignificancePreference(),
      'search': SearchParametersPreference(),
    }
    self.user_id = 3 # TODO: get user_id
    self.feedback_history = []
    self.session_context = {}

  def get_pref(self, preference_name, top_ranking=True):
    if preference_name == 'all':
      # return all preferences in dict form for use in writing the system prompt
      return self._user_prefs
    else:
      if top_ranking:
        return self._user_prefs[preference_name].top_rank()
      else:
        return self._user_prefs[preference_name]

  def related_to_pref(self, utterance):
    # check if the utterance contains any of the preference triggers
    tokens = utterance.split()

    for name, preference in self._user_prefs.items():
      for trigger in preference.triggers:
        if trigger in tokens:
          return name
    return None

  def set_pref(self, pref_name, pref_value, pref_detail=''):
    user_preference = self._user_prefs[pref_name]
    user_preference.set_ranking(pref_value, pref_detail)
    # self.save_to_disk()
    return user_preference

  def possible_options(self):
    # check which preference names are available
    possible_prefs = list(self._user_prefs.keys())
    return possible_prefs

  def store_context(self, key: str, value: Any) -> None:
    """Store context information for the current session."""
    self.session_context[key] = {
      'value': value,
      'timestamp': time.time()
    }
    
  def get_context(self, key: str) -> Any:
    """Retrieve context information."""
    context_item = self.session_context.get(key)
    return context_item['value'] if context_item else None

  def clear_context(self) -> None:
    """Clear session context."""
    self.session_context = {}
    
  def record_feedback(self, insight_id: str, feedback: Dict[str, Any]) -> None:
    feedback_record = {
      'insight_id': insight_id,
      'feedback': feedback,
      'timestamp': time.time()
    }
    self.feedback_history.append(feedback_record)
    
    # Update preference confidence based on feedback
    if 'preferences' in feedback:
      for pref_name, feedback_value in feedback['preferences'].items():
        if pref_name in self.preferences:
          self.preferences[pref_name].update_confidence(feedback_value)          
    self.save_to_disk()  # Persist changes

  def save_to_disk(self) -> None:
    # In a real implementation, this would save to a database
    os.makedirs(f"./preferences", exist_ok=True)
    with open(f"./preferences/{self.user_id}.json", "w") as f:
      json.dump(self.to_dict(), f, indent=2)
      
  def load_from_disk(self) -> bool:
    file_path = f"./preferences/{self.user_id}.json"
    with open(file_path, "r") as f:
      data = json.load(f)
      
    # Restore preferences
    for name, pref_data in data.get('preferences', {}).items():
      if name in self.preferences:
        pref_class = self.preferences[name].__class__
        self.preferences[name] = pref_class.from_dict(pref_data)
        
    # Restore feedback history  
    self.feedback_history = data.get('feedback_history', [])
    return True

class BasePreference(ABC):

  def __init__(self, name, values):
    # examples of 'count' value include: subscriptions, downloads, visitors, conversions, sign-ups, etc.
    self.name = name
    self.endorsed = False
    self.triggers = []
    self.rankings = [{'value': val, 'detail': ''} for val in values]
    self.entity = {}

    self.last_updated = time.time()
    self.access_count = 0
    self.confidence = 0.5  # Default confidence

  def top_rank(self, include_detail=False):
    self.access_count += 1
    first_ranked = self.rankings[0]
    if include_detail:
      return first_ranked   # returns a dict with 'value' and 'detail' keys
    else:
      return first_ranked['value']

  def find_preference(self, pref_value):
    for pref in self.rankings:
      if pref['value'] == pref_value:
        return pref
    return None

  def assign_entity(self, tab, col, ver=False):
    table_name, column_name, verified = tab, col, ver
    self.entity = {'tab': table_name, 'col': column_name, 'ver': verified}

  def set_ranking(self, pref_value, pref_detail):
    pref = self.find_preference(pref_value)
    if pref:
      self.rankings.remove(pref)
    self.rankings.insert(0, {'value': pref_value, 'detail': pref_detail})
    self.endorsed = True
    self.last_updated = time.time()
  
  def update_confidence(self, feedback_value, learning_rate=0.2):
    # Simple weighted average with a default learning rate of 0.2
    prior = (1 - learning_rate) * self.confidence
    new = learning_rate * feedback_value
    self.confidence = prior + new

  # --- Memory Management Methods ---
  def to_dict(self):
    return {'name': self.name, 'endorsed': self.endorsed, 'triggers': self.triggers,
            'rankings': self.rankings, 'entity': self.entity, 'last_updated': self.last_updated,
            'access_count': self.access_count, 'confidence': self.confidence }

  @classmethod
  def from_dict(cls, data):
    instance = cls()
    instance.name = data['name']
    instance.endorsed = data.get('endorsed', False)
    instance.triggers = data.get('triggers', [])
    instance.rankings = data.get('rankings', [])
    instance.entity = data.get('entity', {})
    instance.last_updated = data.get('last_updated', time.time())
    instance.access_count = data.get('access_count', 0)
    instance.confidence = data.get('confidence', 0.5)
    return instance

  # --- Abstract Methods for Preference Application ---  
  @abstractmethod
  def apply_to_analysis(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    NotImplementedError("should return modified dataframe and analysis parameters")
    
  @abstractmethod
  def make_prompt_fragment(self) -> str:
    NotImplementedError("should return text fragment to inject into LLM prompt")

class MajorGoalsPreference(BasePreference):
  """Defines what constitutes success in data analysis. What does a good performance entail? What KPIs matter most?"""

  def __init__(self):
    values = ['amount', 'count', 'percent', 'time']
    # details = [revenue, conversions, CTR, earliest]
    super().__init__('goal', values)
    self.triggers = ['best', 'greatest', 'most', 'highest', 'top']

  def make_prompt_fragment(self) -> str:
    pref = self.top_rank(include_detail=True)
    if self.endorsed:
      description = f"Remember, the 'best' campaign or 'most popular' product refers to "
    else:
      description = f"If discussing the 'best' campaign or best ad, assume the user is looking for "

    if pref['detail'] == '<entity>':
      detail = f"the {self.entity['col']} column in the {self.entity['tab']} table"
    else:
      detail = pref['detail']

    if pref['value'] == 'amount':
      description += f"the highest dollar amount as measured by {detail}. "
    elif pref['value'] == 'count':
      description += f"the highest volume or count of {detail}. "
    elif pref['value'] == 'percent':
      description += f"the best percentage in terms of {detail}. "
    elif pref['value'] == 'time':
      description += f"the {detail} time. "

    if self.endorsed:
      description += f"Use {detail} in your query rather than deriving a new definition. "
    return description

  def apply_to_analysis(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    pref = self.top_rank(include_detail=True)
    analysis_params = {'priority_metric': pref['value']}

    if self.entity:
      analysis_params['target_column'] = self.entity['col']
      
    # Prioritize monetary columns and sort by highest values
    if pref['value'] == 'amount':
      monetary_cols = [col for col in df.columns if df[col].dtype in ['float64', 'int64']]
      analysis_params['target_columns'] = monetary_cols
      analysis_params['sort_order'] = 'descending'      
    # Prioritize frequency analysis and counts
    elif pref['value'] == 'count':
      analysis_params['analysis_type'] = 'frequency'
      analysis_params['sort_order'] = 'descending'
    # Prioritize percentage/ratio metrics
    elif pref['value'] == 'percent':
      analysis_params['analysis_type'] = 'percent_change'
    # Prioritize temporal analysis
    elif pref['value'] == 'time':
      analysis_params['analysis_type'] = 'temporal'
      
    return df, analysis_params

class TimeHorizonPreference(BasePreference):
  """ Defines what timeframe to consider for analysis.
      How far back should we look when we consider 'recent' performance? Which day represents the start of the week?"""

  def __init__(self):
    values = ['month', 'week', 'quarter', 'day']
    super().__init__('timing', values)
    self.triggers = ['recent', 'newest', 'latest', 'lately', 'recently']

  def make_prompt_fragment(self, details=False) -> str:
    if self.endorsed:
      description = "Remember, 'recent' performance on a campaign or channel refers to the "
    else:
      description = "If talking about a 'recent' time period, such as 'How did our email campaigns perform recently', assume the user means the "

    pref = self.top_rank(include_detail=True)
    description += f"{pref['detail']} {pref['value']}. "
    return description

  def apply_to_analysis(self, df, schema) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Filter data to the preferred time horizon."""
    pref = self.top_rank(include_detail=True)
    analysis_params = {'time_horizon': pref['value']}
    
    # Find datetime columns
    date_cols = [col for col in df.columns if schema.get_type_info(col)['type'] == 'datetime']
    if not date_cols:
      return df, analysis_params
      
    # Default to the first date column
    date_col = date_cols[0]
    analysis_params['date_column'] = date_col
    
    # Filter based on preferred time horizon
    if pref['value'] == 'month':
      latest_date = df[date_col].max()
      month_start = pd.Timestamp(year=latest_date.year, month=latest_date.month, day=1)
      filtered_df = df[df[date_col] >= month_start]
      
    elif pref['value'] == 'week':
      latest_date = df[date_col].max()
      week_start = latest_date - pd.Timedelta(days=7)
      filtered_df = df[df[date_col] >= week_start]
      
    elif pref['value'] == 'quarter':
      latest_date = df[date_col].max()
      quarter = (latest_date.month - 1) // 3 + 1
      quarter_start = pd.Timestamp(year=latest_date.year, month=((quarter-1)*3)+1, day=1)
      filtered_df = df[df[date_col] >= quarter_start]
      
    elif pref['value'] == 'day' and pref['detail'].isdigit():
      latest_date = df[date_col].max()
      days_start = latest_date - pd.Timedelta(days=int(pref['detail']))
      filtered_df = df[df[date_col] >= days_start]
      
    else:
      filtered_df = df      
    return filtered_df, analysis_params

class RiskTolerancePreference(BasePreference):
  """ Caution Levels:
  - ignore: User wants the agent to behave very independently in resolving any issues automatically.
  - warning: User wants the agent to be balanced between making too assumptions vs asking for too much permission.
  - alert: User wants the agent to be conservative in their approach to resolving issues, preferring to ask for permission.
  """
  def __init__(self):
    values = ['warning', 'ignore', 'alert']
    super().__init__('caution', values)

  def make_prompt_fragment(self):
    pref = self.top_rank(include_detail=True)
    if pref['value'] == 'alert':
      description = "User always wants to be alerted whenever there is an issue."
    elif pref['value'] == 'warning':
      # we define concerns and problems as blocking, while typos and blanks are non-blocking
      description = "User wants to be notified with a warning only when it blocks progress on the task."
    elif pref['value'] == 'ignore':
      description = "User does not want to be pro-actively alerted about any issues with the data."
    return description
  
  def apply_to_analysis(self, df, schema) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    pref = self.top_rank(include_detail=True)
    analysis_params = {'caution_level': pref['value']}
    return df, analysis_params

class SpecialAdjustmentsPreference(BasePreference):
  """what special factors do I need to consider before giving a final answer? Are there certain dates
  to ignore because they were test periods or otherwise not representative of normal business operations? """

  def __init__(self):
    values = ['seasonality', 'currency conversion', 'special circumstance', 'regulations']
    super().__init__('special', values)
    self.triggers = ['adjust', 'correct', 'fix', 'update', 'change']

  def make_prompt_fragment(self) -> str:
    if self.endorsed:
      description = "Remember, the user wants to account for "
    else:
      description = "If the user asks to 'adjust' or 'correct' the data, assume they want to account for "

    pref = self.top_rank(include_detail=True)
    match pref:
      case 'seasonality':
        description += "seasonal patterns in the data when identifying trends."
      case 'currency conversion':
        description += f"monetary values have been standardized to {pref['detail'] or 'USD'} for consistent analysis."
      case 'special circumstance':
        description += f"special circumstances, such as {pref['detail']}."
      case 'regulations':
        description += f"{pref['detail']} regulatory requirements."
    return description

  def apply_to_analysis(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Apply special adjustments to the analysis."""
    pref = self.top_rank(include_detail=True)
    analysis_params = {'adjustment_type': pref['value']}
    modified_df = df.copy()
    
    if pref['value'] == 'seasonality':
      # Apply seasonality adjustments
      analysis_params['apply_seasonality'] = True
      
      # Example seasonality adjustment (simplified)
      if 'date' in df.columns and pd.api.types.is_datetime64_any_dtype(df['date']):
        # Add month and day of week features
        modified_df['month'] = modified_df['date'].dt.month
        modified_df['day_of_week'] = modified_df['date'].dt.dayofweek
        
        # Flag seasonal peaks for retail (example)
        modified_df['is_holiday_season'] = modified_df['month'].isin([11, 12])
        
        analysis_params['seasonality_features'] = ['month', 'day_of_week', 'is_holiday_season']
    
    elif pref['value'] == 'currency conversion':
      # Apply currency conversion
      analysis_params['apply_currency_conversion'] = True
      base_currency = pref['detail'] if pref['detail'] else 'USD'
      analysis_params['base_currency'] = base_currency
      
      # Example conversion logic (simplified)
      monetary_cols = [col for col in df.columns if 'revenue' in col.lower() 
                       or 'price' in col.lower() or 'cost' in col.lower()]
      
      if monetary_cols and 'currency' in df.columns:
        # Mock conversion rates
        conversion_rates = {'EUR': 1.1, 'GBP': 1.3, 'JPY': 0.009}
        
        # Apply conversions
        for col in monetary_cols:
          # Make a copy to avoid SettingWithCopyWarning
          temp_df = modified_df.copy()
          for curr, rate in conversion_rates.items():
            mask = temp_df['currency'] == curr
            temp_df.loc[mask, col] = temp_df.loc[mask, col] * rate
          modified_df = temp_df
          
        analysis_params['converted_columns'] = monetary_cols
    
    elif pref['value'] == 'special circumstance':
      # Handle special circumstances
      analysis_params['exclude_special_circumstances'] = True
      circumstance_note = pref['detail']
      analysis_params['circumstance_note'] = circumstance_note
      
      # Example: exclude test data or outliers
      if 'is_test' in df.columns:
        modified_df = modified_df[~modified_df['is_test']]
        analysis_params['excluded_test_data'] = True
        
    return modified_df, analysis_params

class VisualizationSettingsPreference(BasePreference):
  """What are the default brand colors or other settings when creating a chart? """
  def __init__(self):
    values = ['chart type', 'color scheme', 'formatting', 'fonts', 'logo']
    super().__init__('viz', values)
    self.triggers = ['chart', 'color', 'format', 'interactive']

  def make_prompt_fragment(self):
    if self.endorsed:
      description = "Remember, the user wants the "
    else:
      description = "If the user asks about the 'chart' or 'color' or 'format' or 'interactive', assume they want the "

    pref = self.top_rank(include_detail=True)
    description += f"{pref['value']}. "
    return description
  
  def apply_to_analysis(self, df, schema) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    pref = self.top_rank(include_detail=True)
    analysis_params = {'visualization_setting': pref['value']}
    return df, analysis_params
  
class CustomMetricsPreference(BasePreference):

  def __init__(self):
    values = ['AOV', 'CAC', 'CPC', 'CTR', 'DAU', 'NPS', 'Email Open Rate', 'Profit', 'ROAS', 'CVR']
    super().__init__('metric', values)
    self.triggers = ['metric', 'calculate', 'derive', 'compute', 'analyze']

  def make_prompt_fragment(self):
    if self.endorsed:
      description = "Remember, the user wants to calculate "
    else:
      description = "If the user asks to 'calculate' or 'derive' or 'compute' or 'analyze' a metric, assume they want to calculate "

    pref = self.top_rank(include_detail=True)
    description += f"{pref['value']}. "
    return description

  def apply_to_analysis(self, df, schema) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    pref = self.top_rank(include_detail=True)
    analysis_params = {'custom_metric': pref['value']}
    return df, analysis_params
  
class BenchmarkSignificancePreference(BasePreference):
  """ the threshold for determining if something is deemed important, how much above (or below) the benchmark is considered significant?
  What is the baseline, and how much variation from the baseline is considered significant?
  """
  def __init__(self):
    values = ['absolute', 'relative', 'percentage', 'margin']
    super().__init__('sig', values)
    self.triggers = ['significant', 'important', 'matter', 'impact', 'difference']

  def make_prompt_fragment(self):
    if self.endorsed:
      description = "Remember, the user wants to consider something significant if it is "
    else:
      description = "If the user asks about something being 'significant' or 'important' or 'matter' or 'impact' or 'difference', assume they want to consider something significant if it is "

    pref = self.top_rank(include_detail=True)
    description += f"{pref['value']}. "
    return description

  def apply_to_analysis(self, df, schema) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    pref = self.top_rank(include_detail=True)
    analysis_params = {'significance_threshold': pref['value']}
    return df, analysis_params
  
class SearchParametersPreference(BasePreference):
  """How long should we let an automated search run before giving up?
  width - how many analyses do we consider in each round?
  depth - how many rounds do we run? coarse to fine granularity
  height - how long does each round last before timing out?
  """
  def __init__(self):
    values = ['width', 'depth', 'height']
    super().__init__('search', values)
    self.triggers = ['search', 'find', 'look', 'query', 'retrieve']

  def make_prompt_fragment(self) -> str:
    if self.endorsed:
      description = "Remember, the user wants to "
    else:
      description = "If the user asks to 'search' or 'find' or 'look' or 'query' or 'retrieve', assume they want to "

    pref = self.top_rank(include_detail=True)
    match pref['value']:
      case 'width': description += f"consider {pref['detail']} categories of analysis."
      case 'depth': description += f"run {pref['detail']} rounds of analysis at increasing levels of granularity."
      case 'height': description += f"allow {pref['detail']} minutes for each round of analysis."
    return description
    
  def apply_to_analysis(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Apply search parameter preferences to analysis."""
    pref = self.top_rank(include_detail=True)
    analysis_params = {'search_strategy': pref['value']}
    
    if pref['value'] == 'width':
      # Prioritize breadth of analysis
      analysis_params['num_categories'] = 5   # Analyze more categories
      analysis_params['insights_per_category'] = 2  # But fewer insights per category
      analysis_params['depth_limit'] = 1      # Limited drill-down
      
    elif pref['value'] == 'depth':
      # Prioritize depth of analysis
      analysis_params['num_categories'] = 2   # Focus on fewer categories
      analysis_params['insights_per_category'] = 5  # But more insights per category
      analysis_params['depth_limit'] = 3      # More drill-down levels
      
    elif pref['value'] == 'height':
      # Prioritize quality over quantity
      analysis_params['num_categories'] = 3   # Balance of categories
      analysis_params['insights_per_category'] = 3  # Balance of insights
      analysis_params['depth_limit'] = 2      # Moderate drill-down
      analysis_params['timeout'] = 60         # Longer computation time allowed
      
    return df, analysis_params

