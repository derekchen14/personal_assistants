---
layout: post
title: Dialog State Tracking Models
tags: [dialogue]
date: '2018-06-16 21:41:16'
---

Thoughts on some of the latest and greatest as of mid-2018.  

1) [Towards E2E RL of Dialogue Agents for Information](https://arxiv.org/abs/1609.00777) _aka. KB-Infobot_ (Dhingra et al.)
    a. **Process:** Follows the format of many traditional DST systems.  In particular, this includes a belief tracker, policy manager, database operator and text generator. This paper focuses on the database querying portion by introducing a soft KB-lookup mechanism that selects items across a probability distribution rather than a hard KB-lookup which is non-differentiable.
    It assumes access to a domain-specific entity-centric knowledge base (EC-KB) where all items are split intro triples of (h,r,t) which stands for head, relation, tail.  This is very similar to querying based on Key-Value Pair as in [Key-Value Retrieval Networks for Task-Oriented Dialogue](https://arxiv.org/abs/1705.05414).  
    The belief state is the set of all _p_ and _q_ outputs.  P is a multinomial distribution over the slot values _v_  (and thus are vectors of size V), and each Q is a scalar probability of the user knowing the value of slot _j_. Each slot is summarized into an entropy statistic over a distribution, with final size 2M + 1, where the first M is the summary of all previous _p_, M is all the _q_ values (which are unchanged since they are already scalar), and 1 is the summary of the current _p_ distribution.
    b. **Strengths:** Good job in building out the system from end-to-end, with different experiments comapred to handcrafted systems.  They also test across different KB sizes.
    c. **Weaknesses:** Final performance is not yet exciting with only 66% success rate for small KBs.  They also achieve 83%, 83% and 68% for medium, large and extra large KBs respectively, which looks better but it is odd we don't see consistent trends, but rather a bump in the middle.
    d. **Notes:** Easy to criticize (ie. multiple networks used for belief tracking), but to be fair, that is not the goal of their paper.  As far as database operation is concerned, this is a great contribution!

2) [E2E Task-Completion Neural Dialogue Systems](https://arxiv.org/abs/1703.01008) with a novel [User Simulator](https://arxiv.org/abs/1612.05688) (Li et al.)
    a. **Process:** Lays down a full framework for end-to-end dialogue. The first half is a user simulator that starts by randomly generating an agenda, and then uses a NLG module to translate that into natural language.  The agenda explicitly outlines a user's goal, like which movie they want to watch and what requirements they have (i.e. at 3PM, about comedy), so the user model behaves in a consistent, goal-oriented manner. Separately, this concept is extended further in [Building a Conversational Agent Overnight with Dialogue Self-Play](https://arxiv.org/abs/1801.04871) where the authors (a) add the ability of varying user personality through a temperature mechanism and (b) greatly expand the diversity of the user dialogue by introducing Turkers paraphrasing the original text to inject human-likeness.
    The second half of the framework is actual dialogue agent which includes an language understanding module to parse utterances into a semantic frame.  This is then passed into the state tracker which accumulates the semantics from each utterance, and policy learner for generating the next system action.  It is assumed that the output of the dialogue agent is simply the next action, rather than natural text, which is acceptable because the "user" is actually the simulator which operates under the assumption it is able to perfectly understand the agent.
    b. **Strengths:**  The other major contribution is a method of gathering data with a User Simulator so that there are enough examples for training an RL agent. By tweaking the parameters of the simulator, the auuthors are able to show that slot-level errors have a greater impact on the system performance than intent-level ones, and that slot value replacement degrades the performance most.
    To understand what this means, let's start by defining the possible intent-level errors:
     - _Within Group Error_: noise is from the same group of the real intent, where groups are either (a) inform intents (b) request intents or (c) other intents.  For example, the real intent is `request_theater`, which calls into the request group, but the predicted intent from LU module might be `request_moviename`.
     - _Between Group Error_: noise is from the different group. For example, a real intent `request_moviename` might be predicted as the intent `inform_moviename`.
     - _Random Error_: any mixture of the two above
   
   Similarly, let's also define the possible slot-level errors:
     - _Slot Deletion_: slot is not recognized by the LU module
     - _Incorrect Slot Value_: slot name is correctly recognized, but the slot value is wrong
     - _Incorrect Slot_: both the slot and its value are incorrectly recognized
     - _Random Error_: any mixture of the three above
    Then the conclusion is that "Incorrect Slot Value" causes the biggest performance drop of all options.

    c. **Weaknesses:** While the idea sounds promising, the RL agents were asked to explore a limited number of dialogue acts. Looking at actual dialogues, it feels like the entire system can be solved using a competent rule-based system.
    d. **Notes:** The framework itself and the results are not particularly interesting, but the many experiments analyzing model succeess are quite insightful.  They find predicting the wrong intent or slot is recoverable, but choosing the wrong value is not.  This actually makes a lot of intuitive sense because if as a listener, you recieve a mismatched signal (intent implies one thing, but slot-value pair imply another), you ask for clarification.  However, if you only get a wrong value, then you actually think you're correct, so you never bother to inquire further!

3) [Network-based E2E Trainable Task-oriented Dialogue System](https://arxiv.org/abs/1604.04562) (Wen et al.)
    a. **Process:** Generally follows traditional DST framework and includes five main components:
    - _Intent Detection_: maps parsed utterance into user-defined intents using LSTM, output is a hidden state vector
    - _Belief Tracker_: maps parsed utterance (and previously predicted beliefs) into a distribution of beliefs for current timestep.  This consists of a **different tracker for every possible slot**. There is also a distinction between inform slots (food type, area, price range) vs. request slots (address, phone number).  A CNN is used to extract features, along with n-gram embeddings surrounding the delexicalized keywords.  The key slots and values are "special", so they get their part of the embedding.
    - _Database Operator_: takes in probability distribution of slots to calculate a binary truth vector that is 1 if the value is predicted to be important and 0 otherwise.  Rules are written to make sure that a value is 1, only if that value is compatible with the query. For example, if the query is "food type", then values like "Japanese" and "Indian" are allowed, but values like "3-star rating" and "expensive" are not allowed.
    - _Policy Management_: maps slot probability distribution, database entities, and intent hidden vector into agent actions.  This part makes very little sense because it seems to be trained as a linear transform with SGD, rather than a reinforcement learning module.  The output is a single vector _o_, but seems to be in a vector format with no interpretable meaning, as an actual action.  Most critically, there is little justification for why the policy manager has the structure that it does.
    - _Text Generation_: uses an LSTM to generate words one-by-one until EOS.  (Can be replaced by a retrieval model for more human-like, but less generalizable responses).  Then fills in the slots based on return values of the database entity pointer.

    b. **Strengths**: This paper is among the first to develop an end-to-end neural system within the traditional DST framework.  In doing so, they strike a good balance between imposing too much structure (ie. rule-based systems of the past) and not enough structure (ie. pure neural models). Also proposes a new way of collecting dialogue data based on a Wizard-of-Oz framework.

    c. **Weaknesses**: Despite new dataset, the topic is still restaurant booking, so its really not that novel.  Also, the method is just having person A (acting as the agent) label person B's utterance (acting as the customer) while also providing the agent output.  This just sounds like a lot of work (and room for error) on the part of Person A.
    Different belief trackers for each slot mean lots of data is needed.  Does not allow room for agent to confirm any ambiguity.  Slots are hard to identify when creating training data (and thus hard to delexicalize) which means placing a lot of confidence in the Turker to get it right. Not sure how this would perform with ambiguities found in real world data. Would have really liked to see how well the belief tracker module alone compares to hand-crafted lexicon.

    d. **Notes**: Not sure why belief tracking (ie. semantic parsing into slot-value pairs) needs to be distinguished from intent detection.  Feels like two separate networks are trained when they should be combined for weight sharing purposes.
     Overall, data collection method is improved, but the lack of data issue remains largely unresolved.  Also, the architecture seems overly complicated, and finally, attention helps, as always.

![wen_e2e](/content/images/2018/06/wen_e2e.png)

4) [Neural Belief Tracker](https://arxiv.org/abs/1606.03777) (Mrkšić et al.)
    a. **Process:** Encodes three inputs using either a deep NN or a convolutional NN.  It is a bit odd that an LSTM is not considered:
     - Agent Utterance (ie. System Ouput) - the previous sentence, spoken by the agent.
     - User Utterance: the current sentence, spoken by the user.
     - Candidate Pairs: a list of all possible slot-value pairs, either inform (food type, area, price range) or request (address, phone number)
    These 3 items are then passed into another layer:
     - Semantic Decoding: calculates a similarity score between the user utterance and the candidate pair.  Checks is the user explicitly offered/requested a specific piece of information that turn.
     - Context Modeling: uses the interaction between agent utterance and candidate pair to decide if (a) system request or (b) system confirm occured.  If the candidate pair passes this gating portion, then another similarity score is calculated to determine the impact of the user's answer.
         - System request: "What price range would you like?", then area and food are not relevant.
         - System confirm: "How about Turkish food?", then any user response is referring to food type, and not price range or area.
    Finally, these two outputs are mashed together in a final network to calculate the binary (yes/no) decision about whether this candidate-pair occurred in the current timestep.

    b. **Strengths**: Delexicalization is a process where "slots and values mentioned in the text are replaced with generic labels."  However, this introduces a hidden dependency of identifying slot/value mentions in text.  The authors then hit the nail on the head when they state "For toy domains, one can manually construct semantic dictionaries which list the potential rephrasings for all slot value pairs ... although, this will not scale to the rich variety of user language or to general domains." User utterances are unlabeled in real world scenarios, so slot-filling becomes impossible since we don't know which slots exist, much less which values belong to them.  The solution proposed is to use dense vectors embeddings which encode meaning, and thus have a sense of semantic similarity baked in.
    c. **Weaknesses**: Only uses n-grams, rather than full sentence encoding.  Does not use attention or other means of long-term tracking.  Makes Markovian assumption about influence of previous system dialogue acts.  Does not report final impact on task completion rate, only performs intrinsic evaluation on belief tracking.
    d. **Note**: This paper only deals with the belief tracking component, so evaluation is performed on predicting inform-slots and request-slots, ignoring policy manangement and dialog generation.
    While GloVE performed admirably, a different set of vectors Paragram-SL999 actually did best, since these embeddings are trained on paraphrases and are specifically optimized for semantic similarity, as opposed to GloVE or Word2vec which are optimized for window-context similarity.  The latter maps antonyms to similar vector spaces since the words are highly related, despite the opposing semantics.

[//]: # (/content/images/2018/06/nbt_cnn.png)
![nbt_model](/content/images/2018/06/nbt_model.png)

5) [Global-Locally Self-Attentive Dialogue State Tracker](https://arxiv.org/abs/1805.09655) (Zhong, Xiong, Socher)
    a. **Process:** Past DST models perform poorly when predicting on rare slot-value pairs since each slot requires its own tracker.  Thus, this paper uses global modules to share parameters between estimators for each slot and local modules to learn slot-specific feature representations.  The overall process is _very_ similar to the NBT model above, where both include encoders for agent utterance, user utterance, and candidate slot-value pairs.  Both also produce a similarity score based on user text (semantic decoder) and based on agent's utterance (context decoder), which are then fed into a final binary-decision mixture model.  The key differences are
    - _Global-Local Encoding_: rather than using a deep neural network or CNN, the three encoders operate with a two step LSTM/attention process. In more detail, given the input of a tokenized utterance _X_, the encoder performs a mapping of f(X) -> H, c where _H_ which is the result of a BiLSTM encoder and _c_ is the result of a self-attention on the encoding.
    - _Mixture model_: What makes this unit special is that rather than just one encoder with attention, as typically found in [Learning End-to-End Goal-Oriented Dialog](https://arxiv.org/abs/1605.07683), the encoder operates on two levels.  Namely, there is one encoder for the global level where the weights are shared across slots, and an encoder for the local level, where the weights are retrained for each slot.  The results of these two encoders are then combined in an interpolation mechanism where the mixture strength, beta, is a hyperparameter to be tuned on the dev set.

    b. **Strengths**: The model takes into account global context so that weights can be shared across different slots. Uses an RNN as the encoder which makes sense.
    c. **Weaknesses**: No clear explanation of where proposed slot-value pairs come from. I think the assumption is that the model cycles through all possible pairs.
    d. **Notes**: Would be interesting to encode with hierarchical encoders and to also see how the model performs on extrinsic measures.  Given the resources of the group, it would have been nice for them to release a new dataset.
![GLAD_model](/content/images/2018/06/GLAD_model.png)