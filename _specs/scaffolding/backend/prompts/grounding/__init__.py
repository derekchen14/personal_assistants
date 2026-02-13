from backend.prompts.grounding.analyze_prompts import *
from backend.prompts.grounding.visualize_prompts import *
from backend.prompts.grounding.clean_prompts import *
from backend.prompts.grounding.transform_prompts import *
from backend.prompts.grounding.detect_prompts import *

grounding_prompts = {
  'Analyze': {
    '001': query_flow_prompt,
    '01A': pivot_flow_prompt,
    '002': measure_flow_prompt,
    '02D': segment_analysis_prompt,
    '014': describe_flow_prompt,
    '14C': check_existence_prompt,
    '248': inform_metric_prompt,
    '268': define_metric_prompt,
  },
  'Visualize': {
    '003': plot_flow_prompt,
    '023': trend_flow_prompt,
    '038': explain_flow_prompt,
    '23D': manage_report_prompt,
    '38A': save_to_dashboard_prompt,
    '136': design_chart_prompt,
    '13A': style_table_prompt,
  },
  'Clean': {
    '006': update_flow_prompt,
    '36D': validate_flow_prompt,
    '36F': format_flow_prompt,
    '0BD': pattern_fill_prompt,
    '06B': impute_flow_prompt,
    '06E': assign_datatype_prompt,
    '06F': undo_flow_prompt,
    '068': persist_preference_prompt,
    '7BD': remove_duplicates_prompt
  },
  'Transform': {
    '005': insert_flow_prompt,
    '007': delete_flow_prompt,
    '056': transpose_flow_prompt,
    '057': cut_and_paste_prompt,
    '5CD': split_column_prompt,
    '58A': materialize_view_prompt,
    '05A': join_tables_prompt,
    '05B': append_flow_prompt,
    '05C': merge_columns_prompt,
    '456': call_external_api_prompt,
  },
  'Detect': {
    '46X': identify_issues_prompt,   # special prompt for all resolve flows
    '46B': blanks_prompt,
    '46C': concerns_prompt,
    '46D': connect_flow_prompt,
    '46E': typos_prompt,
    '46F': problems_prompt,
    '468': resolve_flow_prompt,
    '146': insight_flow_prompt,
  }
}