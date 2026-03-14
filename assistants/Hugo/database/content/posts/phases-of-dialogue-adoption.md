---
layout: post
title: Phases of Dialogue Adoption
date: '2019-06-04 14:55:16'
---

Dialogue systems and chatbots are going through the same cycle of adoption seen in previous technology growth curves. &nbsp;As a quick primer, we note that mobile experienced the same four phases as it has expanded from technical oddity to ubiquitous usage. &nbsp;In particular, in the first phase, you had a limited number of forerunners who used large brick phones. &nbsp;This certainly didn't live up the promise of mobile, but it was also certainly distinct from its predecessor of the corded phone. In the second phase, there was a shift to enterprise with Palm Pre, Blackberry and other PDAs. &nbsp;In the third phase, we had the original iPhone which lacked an App Store and other key functionality, but at this point you knew mobile was going to take over the world. &nbsp;Finally, in the fourth phase, there was also Android, long-lasting phones with giant screens, and all the bells and whistles we expect today.

Moving our focus on dialogue systems, it seems the same pattern is playing out again:

<!--kg-card-begin: markdown-->
1. 

Phase One: recognize basic intents to execute actions

  - Alexa, Siri, Cortana (2015 - 2019)
  - This is mainly characterized by taking a single utterance as input an resulting in the desired response
  - On the enterprise side: schedule a meeting or call, manage a todo list, transcribe meeting notes
  - On the consumer side: turn on the lights, set an alarm, what is the weather
2. 

Phase Two: responds to requests, asks for clarification, access to KB

  - Interface to apps and services (2019 - 2023)
  - The agent is now able to handle multi-turn conversation and hold onto context over many exchanges. The size of the ontology also becomes largely unbounded, with the structure focused only on the dialogue acts.
  - On the enterprise side: suggested phrases for customer service or call centers, automated scripts for sales teams, resolving helpdesk tickets for IT
  - On the consumer side: purchasing tickets for an event or movie, ordering food for common menu items, make a flight booking or restaurant reservation
3. 

Phase Three: makes recommendations and pushes notifications, proactive nature

  - Virtual Assistant (2023 - 2027)
  - The agent remembers your context from past conversations and has a basic understanding of who you are and your preferences. It is thus able to make simple recommendations without being too annoying.
  - On the enterprise side: onboarding for new employees, read and compose short emails, we noticed everyone in your department signed up for X, would you like to as well?
  - On the consumer side: recommend what news to read or shows to watch, give suggestion on what place to eat taking into account previously stated dietary preferences
4. 

Phase Four: converses based on personalized context

  - Executive Assistant (2027 - ?), timeline on this could be way off
  - The agent is able to handle more high level tasks and has low level commonsense baked into everything it does. It is able to infer from context what is the most likely intent for high performance in zero-shot learning settings.
  - On the enterprise side: research a subject online to generate a summary, intuitive interaction for booking a flight, almost like talking to a co-worker
  - On the consumer side: user no longer needs to adapt when giving instructions and can converse in natural language. This is reading into the future, so I will leave this vague ...
<!--kg-card-end: markdown-->

Sometimes, the best way to understand is with an example. &nbsp;So, on a more concrete level, the way this might play out:

<!--kg-card-begin: markdown-->

_Phase 1:_

- \<Turn on TV\>
- I'd like to watch the game.
- Got it, the Game Portal is on channel 312. Would you like to go there?
- No
- OK, what would you like me to do?
- Watch basketball game.
- OK, switching to channel 253. \<Shows a replay of NCAA FInal Four game.\>
- Argh, not that one!
- I'm sorry, I didn't get that.
- \<Manually flips through TV guide\>
- Please go to channel 261
- OK, switching to channel 261.

_Phase 2:_

- \<Turn on TV\>
- I'd like to watch the game.
- Which game?
- Basketball
- Did you mean the NBA playoffs?
- Yes
- There are two series currently playing: Bucks vs Raptors and Warriors vs Blazers, which one do you prefer?
- Umm, the Warriors and Blazers
- Ok, switching to channel 261

_Phase 3:_

- \<Turn on TV\>
- I'd like to watch the game.
- You mean the Warriors game?
- Yes, that's perfect!
- Ok, switching to channel 261

_Phase 4:_

- \<Turn on TV\>
- Would you like to watch the Warriors game?
- Oh, that'd be great!
- Ok, switching to channel 261
<!--kg-card-end: markdown-->

Open to thoughts and comments below!

