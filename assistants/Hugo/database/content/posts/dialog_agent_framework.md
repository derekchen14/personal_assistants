---
layout: post
title: Dialog Agent Framework
date: '2018-01-04 18:09:00'
---

(aka. How the technical part of the building a intelligent agent might work)

Drawing upon the insights from traditional dialog state tracking and newer models, a proposed framework includes the following key ideas:

  - Break down the problem into modules (similar to DMN): this is so that components can be analyzed individually, and optimized immediately when new algorithms come out.  Also, this is just good programming practice.
  - System should be end-to-end differentiable: take advantage of the magic of SGD
  - Focuses on user intents: research from Stanford NLP has shown that rule-based agents can perform on par with neural-based agents by focusing on modeling user beliefs which significantly limits the amount of calculation required by the model.
  - Closed domain: each bot handles some small section of related tasks to make the problem tractable.  Don't try to make one bot that does everything at once.

The model takes in user input:

  1. Perform NLU to infer user beliefs:
      - tokenization and vocab embedding lookup
      - lexer to find relevant entities
      - parser to identify user intent
      - reformulate as user query
      - *Best Candidate*: Bi-LSTM encoder with attention
  2. Model query as probabilistic factor in a Bayes Net:
      - user belief modeled as (hidden) state, so solution must go beyond reflexive machine learning algorithms
      - not a binary factor since the prediction of user intent was a probability distribution
      - to the extent that user intent is an indicator variable (ie. did or did not click a button declaring explicit preference), then add laplace smoothing
      - not a Markov Network or CRF since turns within a dialogue have order, and thus direction (i.e. we can't look into the future to perform smoothing)
      - process and store query as continuous vector embedding to allow for gradients
      - *Best Candidate*: Dynamic Memory Network or EntNet
  3. Performance Module:
      - Receive reward if proper API is called.  Reward signal in the form of task completion accuracy.
      - *Best Candidate*: AC3 or TRPO
  4. Understanding Module:
      - Different from most models, we explicitly try to model whether or not we have a high confidence of the user intent.
      - If low confidence, ask for follow up (i.e. "What did you mean by that?") just like in real life, rather than setting user intent state as "unknown"
      - Receive reward if properly predict user intent.  Reward signal in the form of positive signals.
 (i.e. "Thanks!")
      - Allows model to never return generic (non-useful) answer.
  5. GAN for generating agent response:
      - Discriminator measures coherency of agent output
      - Humanlike-ness and interesting-ness are secondary
      - Generator probably a GRU Decoder with beam search

As a first pass, if a rule-based method or IR can find answers, use that rather than passing to neural-based agent which may take time.  Additionally, fallbacks need to be implemented in case nothing useful is found. Attach speech recognition and TTS modules if desired.

Critically, limiting usage to small domains allows agent to tractably approximate full state space of user intents.  Scalability comes from connecting multiple such agents together rather than having one agent that can do it all.  Consequently, the process for building (and training and KBP) for many agents must be incredibly simple.  Furthermore, this implies that each agent should be able to work independently of all other agents.

In conjunction, similar to how ensembles always win data science competitions, all the smaller agents form a super-agent with superior capabilities.