import json
import logging
import numpy as np
import pandas as pd

from backend.prompts.mixins.for_internal import * # Assuming prompts like think_prompt exist here
from backend.utilities.pex_helpers import *
from backend.components.engineer import PromptEngineer
from backend.components.frame import Frame
from utils.help import dax2flow, dax2dact, flow2dax

class InternalMixin:
  """ Methods that are called internally by the agent to support completing other flows """

  def think_carefully(self, context, state, world):
    """ Generates a thought or calls a stronger model to think deeper about a problem {089} """
    flow = state.get_flow(flow_type='think')
    frame = world.frames[-1] if world.has_data() else self.default_frame(state, state.entities)

    if flow.slots['topics'].filled or flow.slots['operation'].filled:
      source_info = PromptEngineer.array_to_nl(flow.slots['source'].values) if flow.slots['source'].filled else "the current context"
      topic_info = flow.slots['topics'].get_description() if flow.slots['topics'].filled else "the ongoing task"
      operation_info = flow.slots['operation'].get_description() if flow.slots['operation'].filled else "general reasoning"

      prompt = think_prompt.format(history=context.compile_history(), source=source_info, topics=topic_info,
                                   operation=operation_info, current_thought=state.thought)
      prediction = PromptEngineer.apply_guardrails(self.api.execute(prompt), 'json')

      if 'thought' in prediction and prediction['thought']:
        state.thought = prediction['thought']
        frame.message = "Okay, I've thought about it. " + state.thought
      flow.completed = True
    else:
      self.actions.add('CLARIFY')
      state.thought = "I need more specific information or context to think effectively about this."
      frame.message = state.thought
    return frame, state

  def peek_at_data(self, context, state, world):
    """ Peeks at data, formats it, and uses it with the task description to inform the next step {39B}"""
    flow = state.get_flow(flow_type='peek')
    frame = world.frames[-1] if world.has_data() else self.default_frame(state, state.entities)

    if flow.is_filled():
      entity_dict = state.entity_to_dict(flow.slots['source'].values)
      main_table = flow.slots['source'].values[0]['tab']
      style = flow.slots['style'].value
      size = flow.slots['size'].value if flow.slots['size'].filled else 32
      task_desc = '\n'.join(flow.slots['task'].values)

      if len(entity_dict) > 1:  # if there are multiple tables involved
        preview_md = multi_tab_display(entity_dict, self.database.db.tables)
      else:
        columns = [entity['col'] for entity in flow.slots['source'].values]
        main_df = self.database.db.tables[main_table]
        match style:
          case 'head': preview_md = PromptEngineer.display_preview(main_df, columns=columns, max_rows=size)
          case 'tail': preview_md = PromptEngineer.display_preview(main_df[::-1], columns=columns, max_rows=size, signal_limit=False)
          case 'sample': preview_md = PromptEngineer.display_samples(main_df, columns=columns, num_samples=size)

      match flow.origin:
        case '01A': task = 'querying the data'
        case '02D': task = 'calculating a metric'
        case '146': task = 'generating insights from the data'
        case '468': task = 'fixing issues in the data'
        case '46D': task = 'connecting data from different sources'
        case _: task = 'analyzing the data'

      # backfill the original flow
      convo_history = context.compile_history()
      prev_flow_name = dax2flow(flow.origin)
      prev_flow = state.get_flow(flow_type=prev_flow_name)

      if prev_flow_name == 'join':
        prev_entities = state.entity_to_dict(prev_flow.slots[prev_flow.entity_slot].values)
        target_cols = [entity['col'] for entity in flow.slots['source'].values]
        prev_ent_slot = prev_flow.entity_slot

        prompt = peek_backfill_prompt.format(history=convo_history, target=target_cols, previous=prev_entities[main_table])
        raw_output = self.api.execute(prompt)
        prediction = PromptEngineer.apply_guardrails(raw_output, 'json')
        for pair in prediction['mapping']:
          prev_flow.slots[prev_ent_slot].replace_entity(main_table, pair['old'], main_table, pair['new'])

      elif prev_flow_name == 'insight':
        prompt = peek_prompt.format(task=task, history=convo_history, data_preview=preview_md, task_desc=task_desc)
        raw_output = self.api.execute(prompt)
        prediction = PromptEngineer.apply_guardrails(raw_output, 'json')

        if 'error' in prediction.keys():
          self.actions.add('CLARIFY')
          state.ambiguity.declare('partial', flow='peek', slot='source table or column')
        else:
          for summary_text in prediction['summary']:
            summary_point = {'flow_name': flow.name(full=True), 'text': summary_text}
            prev_flow.scratchpad.append(summary_point)
          state.thought = prediction['thought']
          prev_flow.slots['plan'].mark_as_complete(flow.name(full=False))

      state.flow_stack.pop()  # remove the stack_on flow
      state.store_dacts(dax=flow.origin)  # point back to the underlying flow
      state.keep_going = True
      flow.completed = True

    else:
      self.actions.add('CLARIFY')
      state.ambiguity.declare('partial', flow='peek', slot='source table or column')

    return frame, state

  def search_meta_data(self, context, state, world):
    """ Searches meta-data like schema or issues before moving forward {149} """
    flow = state.get_flow(flow_type='search')
    frame = world.frames[-1] if world.has_data() else self.default_frame(state, state.entities) # Informational frame

    if flow.slots['target'].filled:
      search_target = flow.slots['target'].value
      source_entities = flow.slots['source'].values if flow.slots['source'].filled else None
      target_tables = list(set([e.table for e in source_entities])) if source_entities else None

      results = "No relevant metadata found." # Default message
      try:
        match search_target:
          case 'schema':
            # Assuming get_schema can handle None or list of tables
            schema_info = self.database.get_schema(target_tables)
            results = f"Schema information:\n{schema_info}"
            state.thought = f"Searched for schema related to {target_tables or 'all tables'}."
          case 'problems' | 'concerns' | 'typos' | 'blanks':
            # Needs access to stored issues, potentially in world or a metadata store
            # Placeholder: Accessing world.issues which might need filtering
            if hasattr(world, 'issues') and world.issues:
              # TODO: Implement more sophisticated filtering based on source_entities and issue type (search_target)
              relevant_issues = world.issues # Simple placeholder
              results = f"Found potential {search_target}:\n{relevant_issues}" # Format appropriately
              state.thought = f"Searched for {search_target} related to {source_entities or 'current context'}."
            else:
              results = f"No recorded {search_target} found."
              state.thought = f"Searched for {search_target}, but none were recorded."
          case 'convo':
            results = f"Conversation History:\n{context.compile_history(lines=10)}" # Show recent history
            state.thought = "Reviewed the recent conversation history."
          case 'docs':
            # This likely requires an external knowledge base or RAG system
            # Placeholder implementation
            # results = self.knowledge_base.search(query=f"Documentation related to {source_entities or 'general usage'}")
            results = "Accessing external documentation is not fully implemented yet."
            state.thought = "Attempted to search external documentation."
          case _:
            results = f"Unknown metadata target: {search_target}"
            state.thought = f"Unsure how to search for metadata target: {search_target}"

        frame.message = results
      except Exception as e:
        error_msg = f"An error occurred while searching metadata: {str(e)}"
        frame.signal_failure('metadata_error', error_msg)
        state.thought = "An unexpected error occurred when I tried to search metadata."
        logging.error(f"SearchFlow exception: {error_msg}", exc_info=True)

      flow.completed = True
    else:
      # Metadata target not specified
      self.actions.add('CLARIFY')
      state.ambiguity.declare('specific', flow='search', slot='target metadata type')
      frame.message = "What type of metadata should I search for (e.g., schema, problems, docs)?"
      state.thought = "I need to know what kind of metadata to search for."
    return frame, state

  def compute_action(self, context, state, world):
    """ Performs calculations or data science operations {129} """
    flow = state.get_flow(flow_type='compute')
    frame = world.frames[-1] if world.has_data() else self.default_frame(state, state.entities)

    if flow.slots['question'].check_if_filled():
      question = flow.slots['question'].values[0]
      convo_history = context.compile_history()
      tab_col_str = PromptEngineer.tab_col_rep(world)

      if flow.slots['task'].filled:
        task = flow.slots['task'].value

        if task in ['correlation', 'comparison']:
          df_message = "To aid you on this task, you will be given access to dataframes as 'db' followed by a table name: `db.table_name`."
          main_tab_name = flow.slots['source'].table_name()
          table_df = self.database.db.tables[main_tab_name]
          columns = [ent['col'] for ent in flow.slots['source'].values if ent['tab'] == main_tab_name]
          related_data = PromptEngineer.display_preview(table_df, columns, max_rows=16)

        elif task in ['calculator', 'classification']:
          df_message = "It should be noted that we do not believe you need to use any dataframes for this task."
          related_data = 'None'

        out_type = 'number' if task in ['correlation', 'calculator'] else 'string'
        prompt = computation_prompt.format(output_type=out_type, df_message=df_message, df_names=self.database.table_desc,
                                            history=convo_history, question=question, related_data=related_data)
        custom_params = {'data_preview': related_data, 'max_tokens': 512}
        result, python_code = self.database.generate_artifact(context, prompt, state, custom_params)

        if python_code == 'error':
          frame.signal_failure('code_execution', python_code)
          self.actions.add('CLARIFY')
        else:
          frame.set_data([], python_code, 'pandas')
          summary_text = "I executed the following code to perform the necessary computation:\n\n```" + python_code
          summary_text += f"```\n\nThe result is: {result}"

          if state.has_plan:
            prev_flow = state.get_flow(flow_type='insight')
            summary_point = {'flow_name': flow.name(full=True), 'text': summary_text}
            prev_flow.scratchpad.append(summary_point)
            prev_flow.slots['plan'].mark_as_complete(flow.name(full=False))
          else:
            if (out_type == 'number' or len(result) < 8) and len(python_code) < 32:
              state.command_type = 'direct_response'
              state.thought = f"The answer is {result}."
            else:
              state.thought = summary_text
              state.thought += "\nI should try to steer the conversation back data cleaning and analysis."
          flow.completed = True

      else:
        prompt = compute_type_prompt.format(history=convo_history, question=question, valid_tab_col=tab_col_str)
        prediction = PromptEngineer.apply_guardrails(self.api.execute(prompt), 'json')

        if flow.fill_slot_values(state.current_tab, prediction):
          frame, state = self.compute_action(context, state, world)
        else:
          self.actions.add('CLARIFY')
          state.ambiguity.declare('specific', flow='compute', slot='task')
    else:
      flow.completed = True
      state.flow_stack.pop()  # remove the compute flow
    return frame, state

  def stage_action(self, context, state, world):
    """ Creates a temporary derived table for further analysis {19A} """
    flow = state.get_flow(flow_type='stage')
    frame = world.frames[-1] if world.has_data() else self.default_frame(state, state.entities)

    # Staging requires both a source definition (like a query) and a target table name
    if flow.slots['source'].filled and flow.slots['target'].filled:
      target_table_name = flow.slots['target'].get_target_name() # Assumes TargetSlot has this method

      try:
        prompt = stage_prompt.format(df_tables=self.database.table_desc, history=context.compile_history(),
                                      target_table=target_table_name, source_query=flow.slots['source'].value)
        status_msg, sql_query = self.database.manipulate_data(self.api, context, state, prompt, world.valid_tables)

        if status_msg == 'success':
          # Update world state to recognize the new temporary table
          world.add_temporary_table(target_table_name) # Assuming world object has this capability
          frame.message = f"Successfully staged data into temporary table '{target_table_name}'."
          state.thought = f"Created temporary table '{target_table_name}' based on the specified source and filters."
          flow.completed = True
        else:
          # Staging failed, status_msg contains the error
          frame.signal_failure('staging_error', status_msg)
          state.thought = f"Failed to stage data into '{target_table_name}'. Reason: {status_msg}"
      except Exception as e:
        error_msg = f"An error occurred during staging: {str(e)}"
        frame.signal_failure('execution_error', error_msg)
        state.thought = f"An unexpected error occurred when trying to stage data into '{target_table_name}'."
        logging.error(f"StageFlow exception: {error_msg}", exc_info=True)

    elif not flow.slots['source'].filled:
      self.actions.add('CLARIFY')
      state.ambiguity.declare('partial', flow='stage', slot='source data for staging')
      frame.message = "What data should be included in the staged table?"
      state.thought = "I need to know the source data or query for staging."

    return frame, state

  def consider_preferences(self, context, state, world):
    """ Considers user preferences before taking the next action {489} """
    flow = state.get_flow(flow_type='consider')
    frame = world.frames[-1] if world.has_data() else self.default_frame(state, state.entities) # Informational

    if flow.slots['preference'].filled:
      pref_type = flow.slots['preference'].value
      task_desc = flow.slots['task'].get_description() if flow.slots['task'].filled else "the current task"
      source_context = flow.slots['source'].values if flow.slots['source'].filled else None

      # Access preferences (assuming stored in world or fetched)
      # Placeholder: Accessing world.preferences
      relevant_prefs = []
      if hasattr(world, 'preferences'):
         # TODO: Implement logic to filter world.preferences based on pref_type and source_context
         # Example: Find 'timing' pref, or 'caution' relevant to source_context tables/cols
         relevant_prefs = world.get_relevant_preferences(pref_type, source_context) # Assumed method

      if relevant_prefs:
        prefs_str = "; ".join([f"{p['name']}: {p['value']}" for p in relevant_prefs]) # Example format
        state.thought = f"Considering preference(s) '{pref_type}' for task '{task_desc}'. Found: {prefs_str}. Applying these to my next steps."
        frame.message = f"Okay, considering relevant preference(s): {prefs_str}"
      else:
        state.thought = f"Considered preference type '{pref_type}' for task '{task_desc}', but found no specific setting relevant right now."
        frame.message = f"Checked for '{pref_type}' preferences, none seem directly applicable here."

      flow.completed = True
    else:
      # Preference type not specified
      self.actions.add('CLARIFY')
      state.ambiguity.declare('specific', flow='consider', slot='preference type')
      frame.message = "Which user preference should I consider (e.g. goals, timing, caution)?"
      state.thought = "I need to know which user preference to look up."
    return frame, state

  def handle_uncertainty(self, context, state, world):
    """ Clarifies user intent when uncertainty is detected {9DF} """
    flow = state.get_flow(flow_type='uncertain')
    frame = world.frames[-1] if world.has_data() else self.default_frame(state, state.entities)

    # This flow's purpose IS to handle ambiguity already detected.
    # It uses its slots to structure the clarification question.
    metric_info = flow.slots['metric'].value if flow.slots['metric'].filled else None
    source_info = flow.slots['source'].values if flow.slots['source'].filled else None
    settings_info = flow.slots['settings'].value if flow.slots['settings'].filled else None

    # Construct clarification based on what's known/unknown from the flow's slots
    # This logic depends heavily on *why* uncertainty was triggered and routed here.
    # Assuming it relates to ambiguity about how to proceed with a potential metric/action.

    clarification_question = "I'm a bit unsure how to proceed. Could you please clarify?" # Default

    if metric_info and not source_info:
      clarification_question = f"To calculate '{metric_info}', which specific tables or columns should I use?"
      state.ambiguity.declare('partial', flow='uncertain', slot='source for metric ' + metric_info)
    elif source_info and not metric_info:
      cols_str = PromptEngineer.array_to_nl(source_info)
      clarification_question = f"What specifically should I calculate or do with {cols_str}?"
      state.ambiguity.declare('specific', flow='uncertain', slot='metric or action')
    elif metric_info and source_info:
      # Maybe settings are ambiguous?
      cols_str = PromptEngineer.array_to_nl(source_info)
      setting_str = f" with settings {settings_info}" if settings_info else ""
      clarification_question = f"I understand you want '{metric_info}' using {cols_str}{setting_str}. Is there anything specific I should focus on or any parameters I'm missing?"
      state.ambiguity.declare('general', flow='uncertain', slot='confirmation or parameters')
    else:
      # General uncertainty if little is known
       state.ambiguity.declare('general', flow='uncertain', slot='intent')


    self.actions.add('CLARIFY')
    frame.message = clarification_question
    state.thought = f"Handling uncertainty: Asking for clarification: {clarification_question}"

    # Do NOT mark flow completed - it requires user response.
    return frame, state