---
title: "Reliable Agents from Unreliable Parts"
tags: [agents, reliability, ai, trustworthy, product-strategy, ideas]
color: green
---

## _hidden_section_title

* Is it possible to increase the reliability of an agent to an acceptable level if each component is probabilistic?
* Reliability compounds across steps
  - A 95%-reliable component sounds fine until you chain ten of them and end up at 60% end-to-end
  - This is why naive approaches hit a wall: per-step gains have to fight exponential decay. A bigger model or better prompt is not enough. 
  - The techniques below all work by either raising per-step reliability or by adding recovery paths so failures don't propagate.
 <!--more-->

## Reliability Through Actor Capability

### Yes, this is possible. Look to a company building as an analogy

Note that this parallels running an organization
* a. redundancy - hire multiple people to do the same job
* b. specialization - hire people who are individually more responsible than average
* c. coordination -  recognize that something is hard or unknown
  - try harder, think deeper, look for documentation
  - ask for help from a manager, ask for clarification
  - hand off to someone else to handle, route to someone who can handle
* d. getting unstuck - retry the task, loop for documentation, ask your manager for help

### Reasoning
* notice how a company itself is exactly this organizational unit
* Each human employee is unreliable
  - (makes mistakes, goes on vacation, gets sick)
* But the structure of the company allows you to absorb these mistakes and keep producing good work
  - however, we’ve developed logical org structures that improve the reliability & capabilities of the higher-level unit. 
  - Similarly, every LLM is unreliable and not particularly capable; but if researchers figure out how to arrange LLMs into a reliable organizational unit, that unit becomes usable with extremely minimal oversight. 
  - This also seems much easier than using training-time compute to achieve reliability (bigger model, etc.), due to the diminishing returns per dollar to scaling.

### Applied to an agent this means

* a. redundancy - many modules that do the same thing
  - same with hamming codes
* b. specialization - fine-tuning with SFT or RL rather than prompting
* c. getting unstuck - ability to recognize uncertainty, and then think deeper/ retry, or ask for clarification
* talk about the idea of how to _increase_ reliability of an organizational unit as a whole, despite each individual actor being a mistake

## Reliability Through Environmental Constraints
Companies don't just hire better people; they also design processes that make mistakes harder to make

* The org analogy isn't just about better employees — companies also use forms, approval workflows, and standardized processes to reduce the reliability burden on any individual.
* The agent analog: structured outputs (JSON schemas), scoped tool whitelists per step, guardrails that reject malformed actions before execution, state machines that only expose valid next-actions.
* A model picking from 3 valid tools is more reliable than one picking from 50 — not because the model got better, but because the space of possible mistakes shrank.
* This composes with everything in the previous section. A specialized, redundant, retry-capable agent operating in a constrained environment is more reliable than the sum of those techniques in an unconstrained one.
* Connects forward to the determinism point in your next section: constraints are how the surrounding system stays deterministic even when the model isn't.

## Going Beyond

### Operational Best practices should apply first

* Set up telemetry to capture model behavior, observability traces, and E2E agent evals
  - model unit tests: behavior of single model outputs, such as intent classification, hand-off accuracy, entity extraction and sub-agent routing
  - traces: covers tool-call trajectories, retrieval accuracy, and 
* These are standard and should not be skipped
* Telemetry pairs with graceful degradation
  - Budget caps on tokens, tool calls, and wall-clock time prevent runaway loops
  - Checkpoints let multi-step workflows roll back rather than corrupt state
  - Confidence thresholds can trigger human handoff before the agent commits to an irreversible action
  - A 95%-reliable agent that fails loudly and safely is more useful than a 98%-reliable one that fails silently with side effects

### some other techniques for strong acceptance

* programs are deterministic - depend on code and pre-defined instructions
* Multiple retries are possible - sometimes able have 5 judges rather than just running once.
* Even able to try all options - instead of sampling, there are even cases where we can brute force by literally just trying all the things. It's not possible to write all code to query a DB, but it is possible to search individually through every column to see if the answer is available.
  - With 25 tables and 40 columns with each having 10,000 rows
  - this 1 million cells which might take a human a month to go through, but a model can handle that in minutes
* LLM as a Judge is a good start

## Conclusion

* will this be perfect? No, but recall that humans are also imperfect.
* We already have much better, there is no need to depend on a giant LLM-wrapper if we are will to break down the task and focus on improving each part.