---
layout: post
title: Building User Simulators for Scalable Dialogue Systems
tags: [modeling, rl, dialogue]
color: purple
excerpt_separator: <!--more-->
---

Training dialogue agents for real-life use cases is immensely difficult since manual data annotation quickly hits scaling issues.  One way around this is to build a user simulator which can theoretically then generate tons of examples for the agent to learn from.  However, to build a system representing the user, you would need a model that understands how to react and respond to agents.  But to train such a user model you would then need some dialogue system that acts as an agent.  So we have a chicken-and-egg problem, right?  Well, not quite.  There is at least one key distinction between a user simulator and a dialogue agent.
 <!--more-->

Note that while a dialogue agent takes in a natural language, follows some policy (often to make API calls), and then generates a natural language response, the simulator does not have to complete all those steps.  In particular, the user simulator can avoid the NLU component and go straight into policy management.  Furthermore, the number of user actions is inherently limited by the number of APIs that the product or service can provide.  To be clear, a real life user engages in a countless number of actions, but only a small subset of those actions are expected to be handled by the agent anyway — in all other cases, the agent can simply abstain.

Armed with these two facts, how can we go about designing a practical user simulator? Our first insight tells us that unlike a dialogue agent, what we want to build is a system that can handle reasonably complex actions followed by extremely sophisticated NLG component for producing responses.  Framed in this way, we see that such a system already exists: open-domain chat bots.  In fact, a large part of building task-oriented chatbots is that users often break out of script and engage in chit-chat.  If our user simulator already produced such outputs, in addition to directed information, then our dialogue agent would naturally be more robust to such variations.

Our second insight is that our user simulator does not need a terribly complex policy manager.  Instead, we can enumerate them with a set of rules to produce all combinations of user intents.  We can then sample from this set to produce plausible scenarios.  To see how this works, let's look at an example.  Suppose we are dealing with the a flight domain.  A user may want to book a flight, cancel a flight, check on an existing flight or ask about some FAQs.  In reality, there are maybe a dozen more actions that user would want to take, but not that much more.

What makes emulating and/or understanding the user difficult is the number of values they provide and the way in which they provide them.  For example, when booking a flight, the user may choose from thousands of (departure/destination) locations and times.  This can lead to millions of values, but there are only four possible slot combinations.  Taking into account edge cases such as price requirements, seating requests and airline preferences, we might expand this into a total of 100 slots for a given domain.  Ultimately though, the number of slots is relatively small compared to the number of values.[^1]  We separately mentioned that the way the user's express a preference have lots of variation: there are a hundred ways to say that you want to "Fly from San Diego to Miami on Saturday morning".  What all these permutations have in common though is that all the complexity is in how to express the exact request.

In other words, with a limited number of domains, slots and intents it is not particularly hard to design a policy which can scale to as many combinations as you want since the heavy lifting is actually within the text generation component.  And what existing models are great at generating text given a context?  Open-domain chatbots.  Such models can already directly query the internet and read through millions of Wikipedia pages.  Trying to parse a few dozen parameters before generating a natural language response should be a walk in the park.


---

[^1]: Further notice that the slots in a given domain are often re-used across intents which dramatically simplifies the task.
