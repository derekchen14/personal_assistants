---
title: "Making AI Agents Reliable"
---

## Teaser
* Is it possible to increase the reliability of an agent to an acceptable level if each component probabilistic?

## Core Idea

### Yes, this is possible. Look to a company building as an analogy
* Note that this parallels running an organization
* a. redundancy - hire multiple people to do the same job
* b. specialization - hire people who are individually more responsible than average
* c. coordination -  recognize that something is hard or unknown
  - try harder, think deeper, look for documentation
  - ask for help from a manager, ask for clarification
  - hand off to someone else to handle, route to someone who can handle
* d. getting unstuck - retry the task, loop for documentation, ask your manager for help

### Applied to an agent this means
* a. redundancy - many modules that do the same thing
  - same with hamming codes
* b. specialization - fine-tuning with SFT or RL rather than prompting
* c. getting unstuck - ability to recognize uncertainty, and then think deeper/ retry, or ask for clarification

## Going Beyond

### Best practices should apply first
* Set up telemetry to capture model unit behavior, observability traces, and E2E agent evals
* These are standard and should not be skipped

### some other techniques for strong acceptance
* programs are deterministic - depend on code and pre-defined instructions
* Multiple retries are possible - sometimes able have 5 judges rather than just running once.
* Even able to try all options - instead of sampling, there are even cases where we can brute force by literally just trying all the things. It's not possible to write all code to query a DB, but it is possible to search individually through every column to see if the answer is available.
  - With 25 tables and 40 columns with each having 10,000 rows
  - this 1 million cells which might take a human a month to go through, but a model can handle that in minutes

## Conclusion
* will this be perfect? No, but recall that humans are also imperfect.
* We already have much better, there is no need to depend on a giant LLM-wrapper if we are will to break down the task and focus on improving each part.