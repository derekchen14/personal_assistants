from sentence_transformers import SentenceTransformer
from database.tables import ConversationItem, UtteranceItem
from sqlalchemy import select, and_
from backend.db import get_db
from backend.components.context import Context

model = SentenceTransformer("all-MiniLM-L12-v2")  #let's hope this is re-entrant. Could not find any documentation.

# Used within agent.py as:
"""
  def load_data(self, spreadsheet, details={}):
    self.convo_subject = None # convo_subject of the conversation to store in the database
    if len(details) > 0:
      self.convo_subject = details['ssName']
      if self.loader.source in ['ga4', 'hubspot']:
        succeeded, output = self.loader.process_details(spreadsheet, details)
      else:  # for CSVs and non-vendor APIs
        succeeded, output = self.loader.process_details(spreadsheet, self.context.available_data, details)
    else:
      dir_name, table_names = spreadsheet.ssName.strip(), spreadsheet.tabNames
      self.convo_subject = dir_name
    ...
"""

def persist(subject: str, user_id: int, context: Context):
    """
    Stores the conversation with all its utterances in the database. If there was already a convo
    on this subject for this user, reuses the id. (Re)generates the embeddings for the convo. Obviously, this is going
    to fail if two saves to the same user/subject happen at the same time. Either use housekeeping to clean later or
    add a lock if needed.
    :param subject: the subject of the conversation. Used to find if there already has been a convo on this subject
    :param user_id: the user we've been talking to
    :param context: where we get Turns to analyze
    :return: nothing. Throws an exception if the save didn't work
    """
    convo_utterances = context.full_conversation(as_dict=True)
    for i in range(len(convo_utterances)):
        print(convo_utterances[i])
    if not convo_utterances:
        # print(f"no utterances for subject {subject} and User {user_id}. Not saving the convo.")
        return
    #let's see if we have an existing convo for the same user and subject
    stmt = select(ConversationItem).filter(and_(ConversationItem.user_id == user_id,
                                                ConversationItem.subject == subject))
    db = get_db()
    row = db.execute(stmt).first()
    turn = None
    convo_history = "\n".join(f"{u['speaker']}: {u['text']}" for u in convo_utterances)
    if row is None:
        # no existing convo, will create one
        for utt in reversed(convo_utterances):
            #looking for an utterance by a User
            if utt['speaker'] == 'User':
                turn = context.find_turn_by_id(utt['turn_id'])
                break
        if turn is None:
            print(f"conversation for subject {subject} and User {user_id} has no utterances by the User, not saving.")
            return
        print(f"working on turn gold:{turn.gold_dacts} distro:{turn.dact_distribution}")
        vector = model.encode(convo_history)
        if turn.dact_distribution:
            # currently dact_distribution is NOT set in code. Should be likely done in nlu.predict_intent_dact
            dact_id = turn.dact_distribution[0]
            conversation = ConversationItem(
                short_embed=vector, dact_id=dact_id, user_id=user_id, subject=subject
            )
        else:
            conversation = ConversationItem(
                short_embed=vector, user_id=user_id, subject=subject
            )
            db.add(conversation)
            print(f"added a conversation for user {user_id}, subject {subject}")
    else:
        # existing conversation, calc new vectors, add new utterances
        conversation = row[0]
        print(f"found an existing conversation {conversation}")
        for u in conversation.utterances:
            convo_history = convo_history + f"{u.speaker}: {u.text}\n"
        vector = model.encode(convo_history)
        conversation.short_embed = vector
    for nu in convo_utterances:
        persistent_utt = UtteranceItem(
            speaker=nu['speaker'], text=nu['text']
        )
        print(f"about to add utt {persistent_utt}")
        conversation.utterances.append(persistent_utt)
        print(f"about to db.add() same")
        db.add(persistent_utt)
    print("commiting")
    db.commit()
