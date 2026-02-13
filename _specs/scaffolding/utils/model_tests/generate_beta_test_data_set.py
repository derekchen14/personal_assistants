import json
import ast

# Define the valid DAX codes
VALID_DAX_CODES = ["001", "002", "01A","02D", "003", "014", "14C", "005", "006", "007"]

def is_valid_dax(turn):
    """Check if a turn has a valid DAX code"""
    return "dax" in turn and turn["dax"] in VALID_DAX_CODES


def process_conversation(conversation):
    """Process a single conversation according to the rules"""
    turns = conversation["turns"]
    if not turns:
        return None

    # Get all user turns and their indices
    user_turns = [
        (i, turn) for i, turn in enumerate(turns) if turn["speaker"] == "User"
    ]

    if not user_turns:
        return None

    # Check if the first user utterance is invalid
    if not is_valid_dax(user_turns[0][1]):
        # If the first user utterance is invalid, remove the entire conversation
        return None

    # Check if any non-first user utterance is invalid
    has_invalid_later_turn = any(not is_valid_dax(turn) for idx, turn in user_turns[1:])

    # Initialize list to track which turns to keep
    keep_turns = [True] * len(turns)

    # Process each user turn
    for i, (turn_idx, user_turn) in enumerate(user_turns):
        # Get next user turn index if it exists
        next_user_idx = user_turns[i + 1][0] if i + 1 < len(user_turns) else len(turns)

        # If user turn has invalid DAX
        if not is_valid_dax(user_turn):
            # Mark current user turn for deletion
            keep_turns[turn_idx] = False

            # Mark all turns until next user turn for deletion
            for j in range(turn_idx + 1, next_user_idx):
                keep_turns[j] = False

    # If any non-first user utterance is invalid, we need to check if we would still have
    # a valid conversation context after removing invalid turns
    if has_invalid_later_turn:
        # If after removal we'd have only user utterances after the first one,
        # we need to keep the full conversation or remove it entirely
        # Check if we have at least one valid turn after the first user turn
        valid_after_first = False
        first_user_idx = user_turns[0][0]
        for i in range(first_user_idx + 1, len(turns)):
            if keep_turns[i]:
                valid_after_first = True
                break

        if not valid_after_first:
            # No valid turns after the first user utterance, so remove the entire conversation
            return None

    # If no turns are kept, return None
    if not any(keep_turns):
        return None

    # Keep only marked turns and renumber utt_ids
    new_turns = []
    new_utt_id = 1
    for i, turn in enumerate(turns):
        if keep_turns[i]:
            turn = dict(turn)  # Create a copy of the turn
            turn["utt_id"] = new_utt_id
            new_turns.append(turn)
            new_utt_id += 1

    # Only keep turns up to the last user turn
    last_user_idx = -1
    for i in range(len(new_turns) - 1, -1, -1):
        if new_turns[i]["speaker"] == "User":
            last_user_idx = i
            break

    if last_user_idx >= 0:
        new_turns = new_turns[: last_user_idx + 1]
        # Renumber utt_ids again
        for i, turn in enumerate(new_turns):
            turn["utt_id"] = i + 1

    return {**conversation, "turns": new_turns} if new_turns else None


def main():
    # Read input file
    input_path = "nlu_dacts.py"
    output_path = "nlu_beta_dacts.py"

    with open(input_path, "r") as file:
        content = file.read()
        # Extract just the list part by removing the "test_set = " prefix
        list_content = content.replace("test_set = ", "")
        # Convert string representation of list to actual list
        data = ast.literal_eval(list_content)

    # Process each conversation
    processed_data = []
    for conversation in data:
        processed_conv = process_conversation(conversation)
        if processed_conv:  # Only add non-None results
            processed_data.append(processed_conv)

    # Write to output file
    with open(output_path, "w") as file:
        # Write in the same format as input
        file.write("beta_test_set = ")
        # Format the output to match the input style
        output_str = repr(processed_data)
        # Make it more readable with proper indentation
        formatted_output = output_str.replace("], [", "],\n [")
        file.write(formatted_output)


if __name__ == "__main__":
    main()
