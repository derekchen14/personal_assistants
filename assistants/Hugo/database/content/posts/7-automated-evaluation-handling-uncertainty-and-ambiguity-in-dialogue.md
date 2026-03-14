---
layout: post
title: '7) Automated Evaluation: Handling uncertainty and ambiguity in dialogue'
date: '2018-10-08 15:29:45'
---

Problem: Training function is imprecise (i.e. BLEU score)

- Training is imperfect because current evaluation metrics (i.e. BLEU Score) measure neither conversation fluency nor task-completion.
  - Labels are often inadequate since there are often many valid methods of answering the same query, where the gold label serves as only one such method.
  - Training set is incomplete since you they cover only a subset of possible acceptable responses
  - LMs train the network to be grammatically coherent, but not necessarily relevant
- Instead, a good method should be able to more closely mimic user satisfaction
  1. evaluate based on semantic similarity
  2. take context into account
<!--kg-card-end: markdown--><!--kg-card-begin: markdown-->

What does it mean to have high user satisfaction?

- Sentence-level fluency - sentence in isolation is valid and grammatically correct
- Turn-level appropriateness - sentence is natural and makes sense given the user input
- Dialogue-level fluency - sentence is strategically correct in getting the agent towards goal completion
- Overall Variation - sufficient diversity in agent responses

How do we measure the satisfaction?

- Ask the user for feedback after each dialogue --\> Very inefficient/annoying
- Hand-craft a “user satisfaction” estimator (e.g. success/length trade-off) --\> We usually need to know the user goal to succeed
- Train a “user satisfaction” estimator using user feedback --\> We ask for user feedback only when we are uncertain about it
<!--kg-card-end: markdown--><!--kg-card-begin: markdown-->

Quantitative Metrics

- Perplexity
- BLEU Score
- METEOR
- ROUGE
- ADEM
<!--kg-card-end: markdown-->