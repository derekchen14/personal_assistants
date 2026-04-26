"""User-facing copy for the violation-vocabulary error codes.

RES consumes this when rendering an error frame — the `violation` key in `frame.metadata` maps to a
single-sentence user-facing description. Keep the copy short and neutral; technical detail belongs
in `frame.thoughts` (for the agent's voice) or `frame.code` (for payloads), not in this map."""


VIOLATION_COPY = {
    'failed_to_save':    "I couldn't save the change.",
    'scope_mismatch':    "I worked on the wrong scope.",
    'missing_reference': "I couldn't find what you referenced.",
    'parse_failure':     "I had trouble parsing the result.",
    'empty_output':      "I came up empty.",
    'invalid_input':     "A tool rejected the input.",
    'conflict':          "Two of your inputs conflict.",
    'tool_error':        "A tool returned an error.",
}


def describe(violation:str) -> str:
    return VIOLATION_COPY.get(violation, "Something went wrong.")
