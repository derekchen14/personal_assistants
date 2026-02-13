import os
import json
import torch
from sentence_transformers import util
from backend.constants import PROJECT_DIR

class FAQRetrieval(object):

  def __init__(self, args, api, embedder):
    self.verbose = args.verbose
    self.api = api
    self.embedder = embedder
    self.tensors = torch.load(os.path.join(PROJECT_DIR, 'database/faq_data/faq_tensors.pt'))

    self.questions = json.load(open(os.path.join(PROJECT_DIR,'database/faq_data/faq_questions.json'), 'r'))
    self.answers = json.load(open(os.path.join(PROJECT_DIR, 'database/faq_data/faq_answers.json'), 'r'))

  def build_help_messages(self, utterance, answers):
    setup = ["You are a useful, reliable and trustworthy virtual assistant named Dana who can help users with cleaning data, analyzing data, generating visualizations and creating reports.",
             "You are also able to help answer any questions about the Soleda, which is the company that built you."]
    agent_reminder = "I should be as terse and concise as possible, while still answering the question."
    setup_msg = "\n".join(setup)

    help_messages = []
    help_messages.append({"role": "system", "content": setup_msg})
    for answer in answers:
      help_messages.append({"role": "assistant", "content": answer})
    help_messages.append({"role": "user", "content": f"{utterance}?"})
    return agent_reminder, help_messages

  def search_faq(self, tensor):
    # Find nearest neighbors with basic cosine similarity.
    cos_scores = util.cos_sim(tensor, self.tensors)[0]
    # Sort the questions based on their cosine similarity score
    top_results = torch.topk(cos_scores, k=2)

    selected = set()
    for score, idx in zip(top_results[0], top_results[1]):
      answer_ids = self.questions[idx]["answers"]
      for aid in answer_ids:
        selected.add(self.answers[aid])
    # convert back to a list and return all relevant answers
    return list(selected)

  def help(self, state, text):
    # find nearest neighbors based on current embed
    tensor = self.embedder.encode(text, convert_to_tensor=True)
    selected = self.search_faq(tensor)

    utterance = text[:-1] if text.endswith("?") or text.endswith("/") else text
    agent_reminder, help_messages = self.build_help_messages(utterance, selected)
    response_output = self.api.execute(agent_reminder, help_messages)
    return response_output