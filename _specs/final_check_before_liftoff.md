Phase 1 — User Requirements
  1. First domain is sort of meta. It is an assistant (named Kalli) that collects information from the user to help build all the other assistant.
  The name of the domain is Onboarding. Blogger will come right after.
  The main tasks are to:
    - gather the user requirements for the next assistant to be built, 
    - answer questions about the 'personal assistants' repo
    - keep track of learnings and patterns encountered while building the repo so we can improve the system over time
  The key entities are:
    - config: which holds the partially filled out user requirements
    - lesson: which holds the learnings and patterns encountered while building the repo
    - components: which holds references to the different components, modules, and utilities used in the repo

  2. shared/shared_defaults.yaml should be created from the 16-section reference in configuration.md

  Phase 2 — Flow Selection
  1. For this first domain, we will generate them together. After Kalli is up and running, the next domain (blogger) will be designed by Kalli, with human in the loop approval.
  2. Derive from the flows once designed?

  Phase 3 — Tool Design
  1. We don't need external APIs for Kalli. Let's keep it simple for now.
  2. We can do direct execution using python's exec() function. Again, keep it quick and dirty for now.

  Phase 4 — Foundation
  1. Copy it as a starting point and adapt. We should generalize the code to make it more dynamic and less specific to the data analysis domain.
  2. Just need Anthropic for now.

  Phase 5 — Core Agent
  1. Just implement one. If we need to use Gemini, then just have it return a random selection for the list of valid flows.
  2. We will use in-memory FAISS for v3. In fact, we will not have any documents to put in the business context for v1, so this is a moot point for now.

  Phase 6 — Policies
  1. You should generate them, then share with me for review and approval.
  2. No flows within Kalli will have a reflection loop.

  Phase 7 — Prompt Writing
  1. use the 10 utterances per flow as seed data for the NLU exemplars.
  2. No template engine. We just use Svelte. Close this open question.

  Phase 8 — Deployment
  1. Build fresh following the checklist spec since this is a totally new domain.
  2. No evaluation for Kalli. We just want to get it up and running.