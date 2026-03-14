---
layout: post
title: Top 10  Secrets to Building Effective Dialogue Agents
tags: [dialogue]
date: '2019-01-11 19:11:28'
---

Some notes to remember when building intelligent task oriented dialogue agents:

<!--kg-card-begin: markdown-->
1. Modularity is important. While E2E response generation is good, intepretability is better.
  - There is a draw to simply use a Seq2Seq approach with an encoder for reading user input and decoder for generating output. However, the output becomes more of a language model, and fails to perform reasoning.
  - Moreover, the hidden state is not human readable. Instead, this should be broken down into Intent Tracking, Policy Management and Text Generation, which allows for better interpretability.
  - Additionally, modularity is easier to maintain and easier to delegate duties when operating in a realistic industry setting.
2. Important not to forget about optimizing auxiliary components
  - Intent tracker should include context embedder in addition to utterance embedder
  - Intent tracker includes memory cells, likely formulated as a Recurrent Entity Network or Neural Process Network
  - Policy manager includes soft knowledge base query mechanism
  - Evaluation and data processing should be optimized
3. Intent tracking is a set of binary predictors
  - Multi-intent utterances occur often, even multiple slots of the same dialogue act are fairly common, such as "I would like to eat Chinese or Korean food."
  - The model actually works better since each task is now much simpler (watch for if the user wants Chinese food, rather than watch for what the user wants)
  - This has been shown to work well in practice (from start-up)
4. Intent output should be act(slot-relation-value):
  - for example: inform(food = korean), request(address = the\_missing\_sock), inform(rating \> 3), accept(offer = the\_missing\_sock), inform(date \> today), answer(confirm = yes)
  - between two values (such as price range) can be written as inform(price \> 3) and inform(price \< 6)
  - this is all possible because the binary predictors allow for arbitrary combinations
  - semantic parsing is overly complex (hard for machines to perform and hard for people to interpret), also does not necessarily give better information to the policy manager
5. Dialogue Acts are five pairs of items which constitutes a MECE set
  - request/inform
  - open/close
  - accept/reject
  - question/answer
  - acknow/confuse
  - MECE = mutually exclusive, collectively exhaustive
6. Full Dialogue State (to be fed into RL agent) includes
  - Five items:
    - previous agent actions
    - current user intent
    - full frame of possible slots-value pairs
    - turn count
    - KB results
  - Context vector is stored for Intent Tracker, but not for Policy Manager
  - Markov property that previous information, such as the order of past "informs" is not needed
7. In order to measure uncertainty, distributed soft approximation of dialogue state is necessary
  - memory stored as neural embedding
  - a pure softmax has been shown to be overly confident, more research is needed on how to better measure "uncertainty"
8. In order to increase accuracy, model should ask for clarification:
  - **conventional** clarification request (question paraphrase) - what did you want?
  - **partial** clarification requests (ask for relevant knowledge) - what was the area you mentioned?
  - **confirmation** through mention of alternatives (knowledge verification) - did you say the north part of town?
  - **reformulation** of information (question verification) - so basically you want asian food, right?
9. Good dialogue models have the following attributes
  - works across multiples turns, which distinguishes it from QA bots
  - works with a knowledge base, which distinguishes it from chatbots
  - knows whether to clarify and what type of clarification to employ using expected entropy maximization objective (ie. it does not ask irrelevant questions and annoy the user)
10. Covers majority of real world scenarios through use of user simulator capable of generating novel examples
  - user simulator allows for fast training, since real users are expensive in time and money
  - user simulator should be dynamic, meaning it should be trainable itself
  - user simulator should output realistic user utterance through use of a GAN which discriminates against model generated text
  - user simulator should be smart about switching between offering real text vs generated text as training progresses
<!--kg-card-end: markdown-->