import re, json
import pandas as pd
import numpy as np
from functools import partial
from pyisemail import is_email
from dateutil import parser
from datetime import datetime as dt
from math import ceil
from decimal import Decimal

from collections import Counter
from backend.assets.ontology import state_abbreviations, date_formats, time_formats, missing_tokens, default_tokens, exact_match_tokens
from backend.utilities.search import sample_from_series

class TypeCheck(object):
  @staticmethod
  def build_properties(column_name, series):
    properties = {'col_name': column_name, 'total': len(series),
                  'type': 'unknown', 'subtype': 'unknown', 'supplement': {},
                  'potential_problem': [], 'potential_concern': False }

    data = sample_from_series(series)
    types = [BlankType(), UniqueType(), DateTimeType(), LocationType(), NumberType(), TextType()]

    for type_class in types:
      properties = type_class.check(data, properties)
      if properties['type'] != 'unknown': break
    return properties

  def contains(self, cell, properties):
    column_name = properties['col_name'].replace(' ', '_').lower()
    for subtype in self.subtypes:
      if subtype.contains(cell, column_name):
        return True

  def check(self, data, properties):
    """ Standard method for detecting subtypes, returns the subtype in properties dict """
    column_name = properties['col_name'].replace(' ', '_').lower()
    type_limit = 0.95 if any(ti in column_name for ti in self.type_indicators) else 0.99

    type_match = 0
    for subtype in self.subtypes:
      subtype_match = 0
      for row in data:
        if subtype.contains(row, column_name):
          subtype_match += 1
          type_match += 1

      subtype_limit = subtype.limit if any(sti in column_name for sti in subtype.indicators) else type_limit
      is_done, properties = self.load_subtype_properties(properties, subtype, subtype_match, subtype_limit)
      if is_done: break

    type_ratio = type_match / properties['total']
    if type_ratio > type_limit and properties['type'] == 'unknown':
      properties['type'] = self.name
    return properties

  def load_subtype_properties(self, properties, subtype, subtype_match, subtype_limit):
    subtype_ratio = subtype_match / properties['total']

    if subtype_ratio > subtype_limit:
      properties['subtype'] = subtype.name
      properties['type'] = subtype.parent
      properties = self.post_check_for_form(properties, subtype)
      properties = self.post_check_for_id(properties)
      if subtype_ratio < 1:
        properties['potential_problem'].append(subtype.name)
      return True, properties
    elif subtype_match > 0:
      properties['potential_problem'].append(subtype.name)

    return False, properties

  def post_check_for_form(self, properties, subtype):
    if subtype.name in ['date', 'time', 'currency']:
      top_format = subtype.format_counter.most_common(1)
      if top_format:
        properties['supplement'][subtype.name] = top_format[0][0]
      subtype.format_counter.clear()
    return properties

  def post_check_for_id(self, properties):
    if properties['subtype'] == 'whole':
      column_name = properties['col_name'].replace(' ', '_')
      if column_name.startswith('id_') or column_name.endswith('_id') or column_name.endswith('ID'):
        properties['subtype'] = 'id'
        properties['type'] = 'unique'
    return properties

  def children(self):
    names = [subtype.name for subtype in self.subtypes]
    return names

class SubType(object):
  def __init__(self):
    # threshold if the subtype indicators are matched
    self.limit = 0.8

  @staticmethod
  def contains(cell, header='') -> bool:
    raise NotImplementedError

# ---------- Default and Empty Types -----------
class BlankType(TypeCheck):
  def __init__(self):
    super().__init__()
    self.name = 'blank'
    self.subtypes = [NullSubtype(), MissingSubtype(), DefaultSubtype()]

  def check(self, data, properties):
    """ Counts the blank rows rather than declaring a subtype """
    for subtype in self.subtypes:
      properties['supplement'][subtype.name] = 0

      for row in data:
        if subtype.contains(row):
          properties['supplement'][subtype.name] += 1
          properties['total'] -= 1

    # if sufficient number of rows exist, but the total is 0, then it means the entire column is blank
    if len(data) > 10 and properties['total'] == 0:
      max_subtype, max_count = '', 0
      for subtype in self.subtypes:
        if properties['supplement'][subtype.name] > max_count:
          max_subtype = subtype.name
          max_count = properties['supplement'][subtype.name]

      properties['type'] = self.name
      properties['subtype'] = max_subtype
    return properties

class NullSubtype(SubType):
  def __init__(self):
    super().__init__()
    self.name = 'null'
    self.parent = 'blank'

  @staticmethod
  def contains(cell):
    return pd.isnull(cell)

class MissingSubtype(SubType):
  def __init__(self):
    super().__init__()
    self.name = 'missing'
    self.parent = 'blank'

  @staticmethod
  def contains(cell):
    return str(cell).strip().lower() in missing_tokens

class DefaultSubtype(SubType):
  def __init__(self):
    super().__init__()
    self.name = 'default'
    self.parent = 'blank'

  @staticmethod
  def contains(cell):
    cell_value = str(cell).strip().lower()

    for def_tok in default_tokens:
      if def_tok in cell_value:
        return True
    if cell_value in exact_match_tokens:
      return True
    return False

# ----- Special Types with Fixed Format --------
class UniqueType(TypeCheck):
  """ Semantically meaningful to ask for percentage of rows containing a given value """
  def __init__(self):
    super().__init__()
    self.name = 'unique'
    # num unique values     T/F           2 to 4             3 to 16            all
    self.subtypes = [BooleanSubtype(), StatusSubtype(), CategorySubtype(), IDSubtype()]

  def contains(self, cell, properties):
    if properties['type'] == 'unique':
      return True
    return False

  def check(self, data, properties, check_category=False):
    column_name = properties['col_name'].replace(' ', '_').lower()
    data_copy = data.copy()
    if properties['supplement']['missing'] > 0:
      data_copy.replace(missing_tokens, np.NaN, inplace=True)
    if properties['supplement']['default'] > 0:
      data_copy.replace(exact_match_tokens, np.NaN, inplace=True)
      for row in data:
        for def_tok in default_tokens:
          if def_tok in str(row).strip().lower():
            data_copy.replace(row, np.NaN, inplace=True)
    num_unique = data_copy.nunique()
    data_copy = data_copy.dropna()
    threshold = 0.9 if properties['col_name'].lower().endswith('id') else 0.95
    majority = ceil(threshold * len(data))

    if num_unique <= 2 and BooleanSubtype.contains(data_copy):
      properties['subtype'] = 'boolean'
    elif num_unique <= 4 and StatusSubtype.contains(data_copy, column_name):
      properties['subtype'] = 'status'
    elif num_unique <= 16 and len(data_copy) > 16 and check_category:
      properties['subtype'] = 'category'
    elif num_unique >= majority and IDSubtype.contains(data):
      properties['subtype'] = 'id'

    if properties['subtype'] != 'unknown':
      properties['type'] = 'unique'
    return properties

class BooleanSubtype(SubType):
  def __init__(self):
    super().__init__()
    self.name = 'boolean'
    self.parent = 'unique'

  @staticmethod
  def contains(data):
    unique_values = data.unique()
    binary_pairs = [{True, False}, {'True', 'False'}, {'TRUE', 'FALSE'}, {'true', 'false'}, {'T', 'F'}, {0,1}]

    if len(unique_values) == 0:  # All are NaNs
      return False
    if any(set(unique_values).issubset(pair) for pair in binary_pairs):
      return True
    if len(unique_values) == 1 and '' in data.unique():
      return True
    return False

class StatusSubtype(SubType):
  def __init__(self):
    self.name = 'status'
    self.parent = 'unique'

  @staticmethod
  def contains(data, header=''):
    status_symbols = [('yes', 'no'), ('on', 'off'), ('new', 'old'), ('men', 'women', 'kids', 'youth'),
      ('red', 'yellow', 'green'), ('beginner', 'intermediate', 'advanced'), ('black', 'white', 'gray'),
      ('bronze', 'silver', 'gold'), ('small', 'medium', 'large', 'xl'), ('search', 'social', 'referral'),
      ('poor', 'good', 'great', 'excellent'), ('past', 'present', 'future'), ('in stock', 'out of stock'),
      ('visible', 'hidden'), ('public', 'private'), ('cold', 'warm', 'hot'), ('man', 'woman', 'unisex') ]
    status_patterns = [
      r'(in)?valid', r'(in)?complete', r'start(ed)?|stop(ped)?', r'(un)?subscribed', r'(on|off)line',
      r'(un)?paid', r'(un)?read', r'low|med(ium)?|high', r'up[- ]?sell|cross[- ]?sell|new( sale)?',
      r'promoter(s)?|passive(s)?|detractor(s)?', r'(en|dis)abled', r'(un)?locked', r'(un)?available',
      r'pass(ed)?|fail(ed)?', r'open(ed)?|close(ed)?', r'(in)?active', r'approve(d)?|reject(ed)?' ]

    if header == 'status': return True
    string_data = data.astype(str).str.lower()
    for symbol_set in status_symbols:
      if all(string_data.isin(symbol_set)):
        return True
    for pattern in status_patterns:
      if all(string_data.astype(str).str.match(pattern)):
        return True

    unique_values = np.array([str(x) for x in data.unique()])
    for val in unique_values:
      if f'not {val}' in unique_values:
        return True
    return False

class CategorySubtype(SubType):
  def __init__(self):
    super().__init__()
    self.name = 'category'
    self.parent = 'unique'

  @staticmethod
  def contains(data):
    if len(data) < 16:
      return False

    num_unique = 0
    for unique_value in data.dropna().unique():
      if isinstance(unique_value, (int, float)):
        return False
      num_unique += 1
    return num_unique <= 16

class IDSubtype(SubType):
  def __init__(self):
    super().__init__()
    self.name = 'id'
    self.parent = 'unique'

  @staticmethod
  def contains(data):
    id_lengths = set()
    if data.isna().any():
      return False

    for val in data.dropna().unique():
      if pd.api.types.is_integer(val):
        id_lengths.add(len(str(val)))
        continue
      elif isinstance(val, str):
        id_lengths.add(len(val))
        if re.fullmatch(r'\d+', val):
          continue
        elif re.fullmatch(r'[A-Za-z-_]{0,3}\d{4,}', val):
          continue
        else:
          return False
      else:
        return False

    if len(id_lengths) > 2:    # Length of IDs should be largely consistent
      return False
    return True

# -------------- Dates and Times --------------
class DateTimeType(TypeCheck):
  """ Semantically meaningful to ask for earliest and latest """
  def __init__(self):
    super().__init__()
    self.name = 'datetime'    # order of subtypes matters
    self.subtypes = [QuarterSubtype(), MonthSubtype(), DaySubtype(), YearSubtype(),
                    WeekSubtype(), DateSubtype(), TimeSubtype(),
                    HourSubtype(), MinuteSubtype(), SecondSubtype(), TimestampSubtype()]
    self.type_indicators = ['date_', '_date', 'datetime', '_time', 'duration']
  
class YearSubtype(SubType):
  def __init__(self):
    super().__init__()
    self.name = 'year'
    self.parent = 'datetime'
    self.indicators = ['year', 'term', 'annual']

  @staticmethod
  def contains(cell, header=''):
    if header == 'year': return True
    year_pattern = re.compile(r'^\d{4}$')
    min_year, max_year = 1950, 2150  # Adjust range if needed
    if year_pattern.match(str(cell)):
      return min_year <= int(cell) <= max_year
    return False

class QuarterSubtype(SubType):
  def __init__(self):
    super().__init__()
    self.name = 'quarter'
    self.parent = 'datetime'
    self.indicators = ['quarter', 'qtr']

  @staticmethod
  def contains(cell, header=''):
    cell_value = str(cell).strip().lower()
    if header.startswith('q'):
      if cell_value.isdigit():
        return 1 <= int(cell_value) <= 4
    else:
      quarter_pattern = re.compile(r'^(q-?[1-4]|[1-4](st|nd|rd|th)|(first|second|third|fourth))$')
      return bool(quarter_pattern.match(cell_value))

class MonthSubtype(SubType):
  def __init__(self):
    super().__init__()
    self.name = 'month'
    self.parent = 'datetime'
    self.indicators = ['month']

  @staticmethod
  def contains(cell, header=''):
    if any(conflict in header for conflict in ['monday', 'mountain', 'moment', 'man', 'minute', 'manage']):
      return False

    cell_value = str(cell).strip()
    if (header.startswith('m') and 'n' in header) or ('month' in header):
      if cell_value.isdigit():
        return 1 <= int(cell_value) <= 12

    month_pattern = re.compile(
      r'^(jan(uary)?|feb(ruary)?|mar(ch)?|apr(il)?|may|jun(e)?|jul(y)?|aug(ust)?|sep(tember)?|oct(ober)?|nov(ember)?|dec(ember)?)$',
      re.IGNORECASE
    )
    return bool(month_pattern.match(cell_value))

class WeekSubtype(SubType):
  def __init__(self):
    super().__init__()
    self.name = 'week'
    self.parent = 'datetime'
    self.indicators = ['week']

  @staticmethod
  def contains(cell, header=''):
    if header == 'day_of_week': return True
    
    cell_value = str(cell).strip().lower()
    if 'week' in header:
      if cell_value.isdigit():
        return 1 <= int(cell_value) <= 7
    else:
      week_pattern = re.compile(r'mon(day)?|tue(sday)?|wed(nesday)?|thu(rsday)?|fri(day)?|sat(urday)?|sun(day)?$')
      return bool(week_pattern.match(cell_value))

class DaySubtype(SubType):
  def __init__(self):
    super().__init__()
    self.name = 'day'
    self.parent = 'datetime'
    self.indicators = ['day']

  @staticmethod
  def contains(cell, header=''):
    if any(conflict in header for conflict in ['month', 'week', 'hour']):
      return False

    cell_value = str(cell).strip()
    if 'day' in header:
      if cell_value.isdigit():
        return 1 <= int(cell_value) <= 31
    return False

class HourSubtype(SubType):
  def __init__(self):
    super().__init__()
    self.name = 'hour'
    self.parent = 'datetime'
    self.indicators = ['hour', 'hr']

  @staticmethod
  def contains(cell, header=''):
    if any(conflict in header for conflict in ['second', 'sec', 'minutes', 'min']):
      return False

    cell_value = str(cell).strip()
    if 'hour' in header:
      if cell_value.isdigit():
        return 0 <= int(cell_value) <= 23
    else:
      hour_pattern = re.compile(r'^(?:[0-1]?[0-9]|2[0-3])[-\s]?(?:hr|hrs|hour)$', re.IGNORECASE)
      return bool(hour_pattern.match(cell_value))

class MinuteSubtype(SubType):
  def __init__(self):
    super().__init__()
    self.name = 'minute'
    self.parent = 'datetime'
    self.indicators = ['minute', 'min']

  @staticmethod
  def contains(cell, header=''):
    if any(conflict in header for conflict in ['second', 'sec', 'hour', 'hr']):
      return False

    cell_value = str(cell).strip()
    if 'min' in header:
      if cell_value.isdigit():
        return 0 <= int(cell_value) <= 59
    else:
      minute_pattern = re.compile(r'^(?:[0-5]?[0-9])[-\s]?(?:min|minutes)$', re.IGNORECASE)
      return bool(minute_pattern.match(cell_value))

class SecondSubtype(SubType):
  def __init__(self):
    super().__init__()
    self.name = 'second'
    self.parent = 'datetime'
    self.indicators = ['second', 'sec']

  @staticmethod
  def contains(cell, header=''):
    if any(conflict in header for conflict in ['minute', 'min', 'hour', 'hr']):
      return False

    cell_value = str(cell).strip()
    if 'sec' in header:
      if cell_value.isdigit():
        return 0 <= int(cell_value) <= 59
    else:
      second_pattern = re.compile(r'^(?:[0-5]?[0-9])[-\s]?(?:sec|seconds)$', re.IGNORECASE)
      return bool(second_pattern.match(cell_value))

class DateSubtype(SubType):
  def __init__(self):
    super().__init__()
    self.name = 'date'
    self.parent = 'datetime'
    self.indicators = ['date', 'day', 'month', 'year']
    self.format_counter = Counter()

  def contains(self, cell, header=''):
    # removes extra spaces as well as ordinal suffixes, such as 1st, 2nd or 3rd
    str_date = re.sub(r'(?<=\d)(st|nd|rd|th)', '', str(cell).strip())

    if str_date.endswith('+00:00'):     # order matters here, we get rid of the timezone first
      str_date = str_date[:-6].strip()  # get rid of the extra '+' sign
    if str_date.endswith('T00:00:00'):
      str_date = str_date[:-9].strip()  # get rid of the extra 'T' for time
    if str_date.endswith('00:00:00'):
      str_date = str_date[:-8].strip()

    for date_format in date_formats:
      try:
        if dt.strptime(str_date, date_format):
          self.format_counter[date_format] += 1
          return True
      except ValueError:
        continue
    return False

class TimeSubtype(SubType):
  def __init__(self):
    super().__init__()
    self.name = 'time'
    self.parent = 'datetime'
    self.indicators = ['time', 'hour', 'minute', 'second']
    self.format_counter = Counter()

  def contains(self, cell, header=''):
    if HourSubtype.contains(cell) and MinuteSubtype.contains(cell) and SecondSubtype.contains(cell):
      return True

    str_time = str(cell).strip()
    for time_format in time_formats:
      try:
        if dt.strptime(str_time, time_format):
          self.format_counter[time_format] += 1
          return True
      except ValueError:
        continue
    return False

class TimestampSubtype(SubType):
  def __init__(self):
    super().__init__()
    self.name = 'timestamp'
    self.parent = 'datetime'
    self.indicators = ['time', 'timestamp', 'datetime']

  @staticmethod
  def contains(cell, header=''):
    cell_value = str(cell).replace('T', ' ').replace('+', ' ').replace('Z', '').strip()
    date_subtype, time_subtype = DateSubtype(), TimeSubtype()
    date_match = any(date_subtype.contains(part) for part in cell_value.split())
    time_match = any(time_subtype.contains(part) for part in cell_value.split())

    if date_match and time_match:
      return True
    # date separated by T, followed by time, followed by timezone as per ISO 8601 standard
    timestamp_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[+-]\d{2}:\d{2}|Z)$")
    return bool(timestamp_pattern.match(cell_value))

# -------------- Places and Locations --------------
class LocationType(TypeCheck):
  """ Semantically related to place, locations and addresses """
  def __init__(self):
    super().__init__()
    self.name = 'location'
    self.subtypes = [StreetSubtype(), CitySubtype(), StateSubtype(), ZipSubtype(), CountrySubtype(), AddressSubtype()]
    self.type_indicators = ['location_', 'place_', 'area_',]

class StreetSubtype(SubType):
  def __init__(self):
    super().__init__()
    self.name = 'street'
    self.parent = 'location'
    self.indicators = ['street']

  @staticmethod
  def contains(cell, header=''):
    street_signs = ['road', 'avenue', 'boulevard', 'blvd', 'drive', 'lane', 'highway', 'pkwy', 'court']
    if header == 'street': return True

    if isinstance(cell, str):
      if re.fullmatch(r'\d{1,5} [a-zA-Z0-9\s]+', cell):
        return True
      else:
        for ss in street_signs:
          if ss in cell:
            return True
    return False

class CitySubtype(SubType):
  def __init__(self):
    super().__init__()
    self.name = 'city'
    self.parent = 'location'
    self.indicators = ['city', 'town', 'village', 'municipality', 'borough', 'capital', 'district', 'region']
    self.limit = 0.8

  @staticmethod
  def contains(cell, header=''):
    common_cities = ['new york', 'los angeles', 'chicago', 'houston', 'phoenix', 'philadelphia', 'san antonio',
        'san diego', 'dallas', 'san jose', 'austin', 'jacksonville', 'fort worth', 'columbus', 'charlotte',
        'san francisco', 'indianapolis', 'seattle', 'denver', 'washington', 'boston', 'el paso', 'nashville',
        'detroit', 'oklahoma city', 'portland', 'las vegas', 'memphis', 'louisville', 'baltimore', 'milwaukee',
        'albuquerque', 'tucson', 'fresno', 'sacramento', 'atlanta', 'kansas city', 'colorado springs', 'miami',
        'raleigh', 'omaha', 'long beach', 'reno', 'oakland', 'tulsa', 'arlington', 'tampa', 'new orleans',
        'wichita', 'bakersfield', 'cleveland', 'anaheim', 'honolulu', 'santa ana', 'riverside', 'lexington',
        'stockton', 'saint paul', 'st. louis', 'cincinnati', 'pittsburgh', 'anchorage', 'newark', 'lincoln',
        'toledo', 'orlando', 'chula vista', 'irvine', 'jersey city', 'durham', 'st. petersburg', 'buffalo',
        'madison', 'scottsdale', 'minneapolis', 'glendale', 'norfolk', 'chesapeake', 'fremont', 'baton rouge',
        'richmond', 'boise', 'san bernardino', 'spokane', 'birmingham', 'des moines', 'rochester', 'tacoma']

    if header == 'city': return True
    if str(cell).lower() in common_cities: return True
    return False

class StateSubtype(SubType):
  def __init__(self):
    super().__init__()
    self.name = 'state'
    self.parent = 'location'
    self.indicators = ['state', 'province', 'region', 'territory', 'district', 'division', 'zone']
    self.limit = 0.8

  @staticmethod
  def contains(cell, header=''):
    if header == 'state': return True
    state_names = list(state_abbreviations.values())
    cell_value = str(cell).strip().lower()
    if cell_value in state_names or cell_value in state_abbreviations:
      return True
    return False

class ZipSubtype(SubType):
  def __init__(self):
    super().__init__()
    self.name = 'zip'
    self.parent = 'location'
    self.indicators = ['zip', 'code', 'postal']  # code covers zip_code, post_code and mailing_code
    self.limit = 0.8

  @staticmethod
  def contains(cell, header=''):
    if header == 'zip_code': return True
    if 'id' in header: return False
    zip_pattern = re.compile(r"^\d{5}(?:[-]\d{4})?$")
    return bool(zip_pattern.match(str(cell)))

class CountrySubtype(SubType):
  def __init__(self):
    super().__init__()
    self.name = 'country'
    self.parent = 'location'
    self.indicators = ['country', 'nation', 'nationality', 'territory', 'republic', 'kingdom']
    self.limit = 0.8

  @staticmethod
  def contains(cell, header=''):
    common_countries = ['united states', 'usa', 'canada', 'mexico', 'united kingdom', 'britain', 'argentina',
        'france', 'spain', 'italy', 'russia', 'china', 'japan', 'india', 'australia', 'brazil', 'venezuela',
        'south africa', 'egypt', 'saudi arabia', 'philippines', 'turkey', 'indonesia', 'thailand', 'germany',
        'south korea', 'malaysia', 'singapore', 'new zealand', 'sweden', 'norway', 'denmark', 'finland', 'uk',
        'poland', 'netherlands', 'belgium', 'switzerland', 'austria', 'greece', 'ireland', 'portugal', 'peru',
        'israel', 'pakistan', 'bangladesh', 'nigeria', 'kenya', 'vietnam', 'iran', 'colombia', 'chile']
    if header == 'country': return True
    if str(cell).lower() in common_countries: return True
    return False

class AddressSubtype(SubType):
  def __init__(self):
    super().__init__()
    self.name = 'address'
    self.parent = 'location'
    self.indicators = ['address']
    self.limit = 0.8

  @staticmethod
  def contains(cell, header=''):
    if header == 'address': return True
    contains_digits = len(re.findall(r'\d', str(cell))) >= 3
    includes_street = StreetSubtype.contains(cell)
    likely_city = CitySubtype.contains(cell)
    likely_state = StateSubtype.contains(cell)
    return contains_digits and includes_street and (likely_city or likely_state)

# -----------  Numeric Types ----------------
class NumberType(TypeCheck):
  """ semantically meaningful to ask for min, max and average """
  def __init__(self):
    super().__init__()
    self.name = 'number'
    self.subtypes = [CurrencySubtype(), PercentSubtype(), WholeSubtype(), DecimalSubtype(),]
    self.type_indicators = ['number', 'num_', '# of', 'count']

class CurrencySubtype(SubType):
  def __init__(self):
    super().__init__()
    self.name = 'currency'
    self.parent = 'number'
    self.limit = 0.8
    self.indicators = ["price", "cost", "amount", "charge", "fee", "tariff", "expense", "payable",
                      "dollar", "currency", "euro", "usd", "cents", "gbp", "yen", "rate", "rent",
                      "budget", "revenue", "income", "expenditure", "spend", "purchase", "wage",
                      "salary", "tuition", "payment", "profit", "deposit", "tax", "vat", "toll"]
    self.format_counter = Counter()

  def contains(self, cell, header=''):
    if isinstance(cell, (int, float, Decimal)):
      price_indicators = ["price", "cost", "amount", "charge", "fee", "tariff", "expense", "payable",
                      "dollar", "currency", "euro", "usd", "cents", "gbp", "yen", "budget", "revenue",
                      "income", "spend", "purchase", "salary", "payment", "profit", "deposit"]
      for indicator in price_indicators:
        if indicator in header and cell < 10000000:
          return True
    else:
      # Starts with one of the currency symbols $, €, £, or ¥ (or ends with a $)
      # Followed by one or more digits.
      # Optionally has groups of three digits separated by a comma or period.
      # Optionally ends with a decimal part consisting of exactly 2 digits.
      # Potentially with space between the currency symbol and the number
      currency_pattern = re.compile(r"^[\$€£¥]\d+([,.]\d{3})*(\.\d{2})?$|^[0-9,]+(\.\d{2})?\$$")
      is_currency = bool(currency_pattern.match(str(cell).replace(' ', '').strip()))
      if is_currency:
        for symbol in ['$', '€', '£', '¥']:
          if symbol in str(cell):
            self.format_counter[symbol] += 1
        return True
    return False

class PercentSubtype(SubType):
  def __init__(self):
    super().__init__()
    self.name = 'percent'
    self.parent = 'number'
    self.indicators = ['percent', 'portion', 'fraction', '_ratio', '_rate', '_pct', 'roas', 'ctr', 'cvr']

  @staticmethod
  def contains(cell, header=''):
    if isinstance(cell, (int, float, Decimal)):
      for ind in ['percent', 'portion', 'fraction', '_ratio', '_rate', '_pct', 'roas', 'ctr', 'cvr', 'tax']:
        if ind in header and -100 <= cell <= 100:
          return True
      if header.endswith('rate') and 0 <= cell <= 100:
        return True
    else:
      percent_pattern = re.compile(r"^-?\d+(\.\d{1,2})?%$")
      return bool(percent_pattern.match(str(cell)))
    return False

class WholeSubtype(SubType):
  def __init__(self):
    super().__init__()
    self.name = 'whole'
    self.parent = 'number'
    self.indicators = ['visitors', 'conversions', 'transactions', 'subscriptions', 'subscribers', 'milestones',
                  'clicks', 'impressions', 'leads', 'customers', 'orders', 'units', 'sessions', 'pageviews',
                  'hits', 'downloads', 'signups', 'registrations', 'shares', 'likes', 'followers', 'comments',
                  'retweets', 'posts', 'tickets', 'products', 'searches', 'accounts', 'logins', 'engagements',
                  'views', 'segments', 'levels', 'steps', 'tasks', 'reviews', 'ratings', 'referrals']

  @staticmethod
  def contains(cell, header=''):
    appropriate_datatype = isinstance(cell, (int, float, np.int64, np.float64))
    if appropriate_datatype:
      seems_whole = cell >= 0 and cell == round(cell)
      return appropriate_datatype and seems_whole
    else:
      # Handle string representations with commas and spaces
      if isinstance(cell, str):
        try:
          cleaned_value = str(cell).replace(',', '').replace(' ', '')
          if cleaned_value.isdigit():
            numeric_value = int(cleaned_value)
            return numeric_value >= 0
          # Also try to handle float representations that are whole numbers
          numeric_value = float(cleaned_value)
          return numeric_value >= 0 and numeric_value == round(numeric_value)
        except (ValueError, TypeError):
          pass
      return False

class DecimalSubtype(SubType):
  def __init__(self):
    super().__init__()
    self.name = 'decimal'
    self.parent = 'number'
    self.indicators = ['average', 'avg', 'mean', 'median', 'mode', 'std', 'range', 'max', 'min']

  @staticmethod
  def contains(cell, header=''):
    if pd.isna(cell):
      return False
    if isinstance(cell, (int, float)):
      return True
    number_pattern = re.compile(r'^-?\d+(\.\d+)?$')
    return bool(number_pattern.match(str(cell).strip()))
  
# ------------ Textual Types ---------------  
class TextType(TypeCheck):
  """ Makes sense to ask for values that start with 'X', will frequently have empty or default values """
  def __init__(self):
    super().__init__()
    self.name = 'text'
    self.subtypes = [EmailSubtype(), PhoneSubtype(), URLSubtype(), NameSubtype(), GeneralSubtype()]
    self.type_indicators = ['email_address', 'phone_number', 'full_name', 'website_url']

  @staticmethod
  def contains(cell, properties):
    if properties['type'] == 'unique':
      return True
    else:
      return super().contains(cell, properties)

  def check(self, data, properties):
    if CategorySubtype.contains(data):
      properties['subtype'] = 'category'
      properties['type'] = 'unique'
    else:
      properties = super().check(data, properties)
    return properties

class EmailSubtype(SubType):
  def __init__(self):
    super().__init__()
    self.name = 'email'
    self.parent = 'text'
    self.indicators = ['email', 'e-mail', 'e_mail']

  @staticmethod
  def contains(cell, header=''):
    if isinstance(cell, str):
      return is_email(cell)
    return False
  
class PhoneSubtype(SubType):
  def __init__(self):
    super().__init__()
    self.name = 'phone'
    self.parent = 'text'
    self.indicators = ['phone', 'cell', 'mobile', 'tel', 'telephone']

  @staticmethod
  def contains(cell, header=''):
    cleaned_item = re.sub(r'[-+()\' ]', '', str(cell))
    # Ensure that the cleaned item only contains digits
    if not re.match(r"^\d+$", cleaned_item):
      return False

    match len(cleaned_item):
      case 7:  result = True      # Local number (e.g., 555-1234)
      case 10: result = True      # Standard US number (e.g., 555-123-4567)
      case 11: result = cleaned_item[0] == '1'  # Must start with country code 1
      case _:  result = False
    return result

class NameSubtype(SubType):
  def __init__(self):
    super().__init__()
    self.name = 'name'
    self.parent = 'text'
    self.indicators = ['name']

  @staticmethod
  def contains(cell, header=''):
    if header in ['username', 'first_name', 'last_name', 'full_name', 'surname']:
      return True
    name_pattern = re.compile(r"^[A-Z][a-z]+([ '-][A-Z][a-z]+)*$")
    return bool(name_pattern.match(str(cell)))

class URLSubtype(SubType):
  def __init__(self):
    super().__init__()
    self.name = 'url'
    self.parent = 'text'
    self.indicators = ['url', 'link', 'webpage', 'website', 'uri']

  @staticmethod
  def contains(cell, header=''):
    # ^(?:https?://)?                             # http or https
    # (?:[\w]+(?::[\w]*)?@)?                      # username:password (optional)
    # (?:[\w.-]+\.)                               # sub-domain or domain and a period
    # [a-zA-Z]{2,4}                               # TLD
    # (?:/[\w&%./-]+)?                            # path
    # (?:\?[a-zA-Z0-9!-'\*\.;:=\+\$/%#\[\]@&]*)?  # query string
    # (?:#[a-zA-Z0-9!-'\*\.;:=\+\$/%#\[\]@&]*)?$  # fragment
    url_pattern = re.compile(r'^(?:https?://)?(?:[\w]+(?::[\w]*)?@)?(?:[\w.-]+\.)[a-zA-Z]{2,4}(?:/[\w&%./-]+)?(?:\?[a-zA-Z0-9!-\'\*\.;:=\+\$/%#\[\]@&]*)?(?:#[a-zA-Z0-9!-\'\*\.;:=\+\$/%#\[\]@&]*)?$')
    return bool(url_pattern.match(str(cell)))
 
class GeneralSubtype(SubType):
  def __init__(self):
    super().__init__()
    self.name = 'general'
    self.parent = 'text'
    self.indicators = []

  @staticmethod
  def contains(cell, header=''):
    # Rather than checking for membership, instead reject if something is a NaN, list, tuple or dict
    if pd.isna(cell):
      return False
    if isinstance(cell, (list, tuple, dict)):
      return False
    if isinstance(cell, str):
      try:
        json_value = json.loads(cell)
        if isinstance(json_value, dict):
          return False
      except json.JSONDecodeError:
        pass
    return True