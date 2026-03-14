---
layout: post
title: Focus of Dialogue Agents
date: '2018-11-11 01:12:34'
---

What exactly is the task we are trying to solve in task-oriented dialogue modeling? &nbsp; Is there a different goal for academic research vs industry application? &nbsp;First, note that I am already segmenting into chit-chat vs. goal-oriented dialogue. Despite this, even with the realm of goal-oriented chat, there seems to be different categories. &nbsp;

Specifically, there seems to be at least 3 different categorizations:

<!--kg-card-begin: markdown-->
1. _Information Retrieval_ (IR)
  - Goal: better search by allowing for natural language queries, acts as internal Google engine
  - Value-add: helps users find information when they don't know where to look, or too many places to look
  - Use cases: Look up the company policy on X, lookup X within the customer account
  - Examples: Does the restaurant have any vegan options? What is the status of my purchase?
  - Downsides: Often requires access to KB which can be difficult to query
  - Best Method: Embed all questions into some vector space (perhaps sentence embeddings, perhaps autoencoder). Then, given a new user query, find the closest question already in the database (perhaps cosine similarity, perhaps a small FF Network). Then return the answer associated with the known question.
2. _Command and Control_ (CC)
  - Goal: report the status of event, execute pre-determined action
  - Value-add: faster than typing or tapping through mobile app
  - Use cases: this is what Siri and Alexa are capable of doing now
  - Examples: Weather in Milwaukee. Driving directions to Los Angeles. Music events near me on Oct 20th.
  - Downsides: dialogue is very unnatural, certainly not multi-turn conversation
  - Best Method: Parse input using rules and then return highest ranking action. Frankly, it's hard to imagine neural-baesd methods working better in this task.
3. _Recommendation System_ (Rec)
  - Goal: offer a solution based on user constraints
  - Value-add: offer insight into a new domain customer is unfamiliar with
  - Use cases: shopping for clothes, shoes, handbags, restaurant recommendation
  - Examples: Help me find a expensive hotel for last week of July. I would like some Indian food for 4 people on the South side of town.
  - Downsides: Really difficult to enumerate all possible options a user might want.
  - Best Method: a framework with RNN-based belief tracker, RL-based policy manager and slot-filled templates for text generation.
<!--kg-card-end: markdown-->

What's really interesting is that we actually study Task 3 in academia but we treat it as if it were Task 2. &nbsp;The datasets assume the user knows what he/she wants when in reality it should be more of a conversation to uncover a need, rather than &nbsp;series of utterances to extract a known desire. &nbsp;Otherwise, the most straightforward interface would be a single screen where users can tap on the options they want (area=south, price=cheap, food=Korean), all in a couple of seconds with no loss in fidelity. &nbsp;Additionally, most real-world users care about Task 1, but we lack datasets for it. &nbsp;Then again, datasets could always be better.

What can be done to build systems that survive in the real world? &nbsp;It seems clear that we need to tackle recommendation and move away from limiting ourselves to thinking that virtual assistants are only capable of command execution.

