NATURALIZE_INSTRUCTIONS = (
    "Smooth this filled template into natural language by making it flow within the conversation so far.\n\n"
    "Rules:\n"
    "- Keep the same information, but do not add or remove facts\n"
    "- Match the persona's tone and style\n"
    "- If a visual block accompanies the response, consider referencing it ('how does this look', or 'as seen on the right')"
    "rather than repeating its content. Only do this every few utterances, rather than every turn\n"
    "- Maximum 2 sentences unless the content genuinely requires more\n"
    "- Do not use markdown formatting unless the content is code\n"
    "- Respond with ONLY the rewritten text, nothing else"
)

def get_naturalize_prompt(raw_text:str, convo_history:str, block_desc:str) -> str:
    parts = [NATURALIZE_INSTRUCTIONS, '\n\n']
    if block_desc != 'default':
        msg = f"A visual block ({block_desc}) will accompany this response. Reference it rather than repeating its content.\n\n"
        parts.append(msg)
    if convo_history:
        parts.append(f'Recent conversation:\n{convo_history}\n\n')
    parts.append(f'Raw response:\n{raw_text}')
    return ''.join(parts)
