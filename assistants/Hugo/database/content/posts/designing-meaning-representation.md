---
layout: post
title: Designing Meaning Representations for Dialogue Systems
tags: [data-strategy, explainer, dialogue]
excerpt_separator: <!--more-->
---

In order for a virtual assistant to be useful, the agent should do more than just information retrieval and basic chit-chat.  Rather than pattern recognition on the response level, the agent should be able to perform pattern recognition on the discourse level so it can mimic human-reasoning (even as true understanding remains an elusive goal).  If a model were to reason about an utterance, it must have been trained to do so.  Furthermore, we argue that such training must be explicitly performed through (weakly) supervised learning, rather than implicitly extracted from a large pre-trained LM (eg. through careful prompting).
<!--more-->
This article aims to show explicit training is indeed necessary and that such training is possible through well-designed meaning representations of dialogue.

# Necessity of Fine-tuning

The explosion of Foundation Models such as BART, GPT, DeBERTa, and others may make it seem like the solutions to all our NLP problems are right around the corner.  However, any serious investigation into the matter will quickly dissuade us of any such illusions.  These gigantic models are hard to train, hard to control and hard to deploy into real-world environments.  Moreover, while large language models generate realistic sounding text, even the creators of such models would likely hesitate to claim that those same models *comprehend* the text they are generating.  Indeed, the standard practice is to pre-train a large LM and then fine-tune it on the task of your choosing.

Given our core task is dialogue systems, how far can we go using only a PLM?

### Lemma 1: Dialogue semantics is not sufficiently modeled by Language modeling.
Language models predict next tokens to minimize perplexity.  Dialogue also contains an element of this skill since knowing what the speaker will say next is indicative of understanding, implying you are following along with the conversation.  However, we believe that dialogues are not captured by language modeling in a proof by induction:
  1. Starting with individual tokens, note that specific values are impossible to predict because they vary for each new interaction (ie. aleatoric uncertainty).  If a customer mentions "My name is X" or "You can call me at Y" that name or phone number is different for each person.  Some names may be more likely than others (ie. John), but for the most part, names are not shared.
  2. Sequences of tokens also follow this general pattern.  Certain phrases have higher probability than others, but conversations overall do not follow a predictable flow.  For example, there exist numerous generic phrases such as "there are plenty of fish in the sea", "dancing in the moonlight", or "distance makes the heart grow fonder".  Given the first few tokens, it's not hard to fill in the rest.  However, dialogues are not always so predictable.  Not only is it possible to tweak these phrases, but folks will occasionally do so precisely for the impact of the unexpected twist: "I would visit, but distance makes the heart grow tired since I don't like running."
Expanding this from phrases to sentence, from sentences to multi-turn utterances, and so on, we see that semantics are not so easy to capture by language modeling alone.

For further proof, consider the Nucleus Sampling paper (Holtzmann, 2019) which showed that true natural language has much higher perplexity than machine generated output.  We also don't want to forget about co-reference, ellipsis and anaphora.  Finally, consider that most common sense reasoning is left unstated.  Overall, if so much of communication is never explicitly stated, then merely being good at predicting what will be said is not enough to understand what is being said.

### Lemma 2: Conversational outcomes are subject to interpretation
Even when something is explicitly stated, the meaning of such utterances may be ambiguous.  "Yea, we'll get there around 8."  Is that 8 AM or 8 PM?  You didn't mention if your arrival was later today or tomorrow.  Is 8:30 still "around 8" or would that be considered too late?  All this makes dialogue complicated.  As another example, consider "That sounds sooo bad."  Does that mean the activity is actually bad, or did the speaker mean that ironically the activity is actually quite good. Is the activity wrong to some folks but debatably acceptable to others?

Language is too complicated to understand without full context.  And even with that, only training on target labels can help guide a model towards meaningful (ie. practically useful) understanding.  Encoding an utterance into a embedding through a language model or auto-encoder misses out on the critical human-in-the-loop validation. Foundation Models only perform language modeling, and thus are not sufficient for capturing the complexities for dialogue semantics.  In order to capture dialogue, extra supervision is necessary.

The proof up to this point is not fully satisfying because we have only really shown that pre-training is insufficient with high probability.  Alternate forms of dialogue pre-training are still theoretically possible.  To tackle this in a more complete manner, we also offer some theoretical evidence.  We argue that language exists for communication and such communication is for achieving shared goals.  Since unsupervised pre-training does not have a labeled target, it does not have a clear goal, and therefore can never mimic this aim.  We are confident additional linguistic theory can be added to further support this claim.  In any case, despite the incomplete logic, the overall intuition should be clear: language models alone are not enough to build powerful dialogue models, and explicit training targets are needed.  We hope the reader finds this point convincing enough, so we now move onto discussing how such targets can be formed.

# Meaning Representations as Supervision

Since dialogues are so complex, one could convincingly argue that even defining a comprehensive schema is impossible since enumerating all options is beyond the capabilities of any organization.  We actually agree with this claim, and yet we still believe that a useful meaning representation (MR) of dialogue exists and can be obtained in cost effective manner.

To see how, let us first define what we mean by a "meaning representation".  A meaning representation is a way of defining the conversational semantics that can be concretely expressed and therefore can be used as a training signal for a model to learn. Many such expressions already exist, most commonly through the dialogue states as seen in Dialogue State Tracking benchmarks or policy states in dialogue-based reinforcement learning.  They have also been referred to as abstract meaning representations (AMRs) when used in the context of structured prediction.  Traditionally, these representations are also the target programs of semantic parsing.

### What are the desiderata for a good MR?
Given that many meaning representations are possible, what would a "good" meaning representation look like?  For our purposes, the ideal label set would strike a balance between being:
  - easy enough to annotate at scale
  - complex enough to faithfully capture the details of a conversation
Let's study these trade-offs in more detail.

What does it mean to be easy to annotate? Scalable annotation means that a "commodity" annotator can perform the job without excessive training and at reasonable cost. This can be achieved by making the annotation task simple.  For example, you can make the process a matter of verifying a model's predictions, rather than requiring the annotators to come up with the labels from scratch.  (How to bootstrap this process from a cold start is the topic for future discussion.)  Separately, we can also limit the scope of annotation to a single domain when starting out. Finally, we can limit the size of the ontology so not every variation is covered, which greatly simplifies the annotation task.  Suffice to say, there are a number of ways to design the annotation task such that annotators can move quickly, yet still produce accurate labels.

The simplifications introduced in the previous paragraph beg the question: if the ontology is so restricted, how can we hope for a model to learn all the desired details within a dialogue.  Well, what do we want from a complex ontology?  Which details are actually necessary to be captured?  We refer back to Lemma 1, which implies that all we want to capture are specific slot-values (ie. tokens) as well as the semantics of longer sequences (ie. phrases).  Training large PLMs towards these two targets is entirely possible given sufficient training data, which itself is possible since the annotation task has been simplified tremendously.

Critically, note what we do *not* capture within our ontology.  (1) Beyond semantics, we can safely assume that a Foundation model can capture the syntax of dialogue, meaning this is not something we need to annotate.  Along those lines, (2) we assume our problem is scoped such that we do not require capturing pragmatics either.  Finally, while we care about slot-values, (3) we assume that slots themselves are pre-defined by an API, not something a model needs to predict.  Overall, we rely heavily on the capabilities of pre-trained LMs so the amount of explicit supervision required is actually quite minimal.

### Corollary: Manfacturing cars required standardization
As a slight tangent, let us draw a parallel from designing MRs to producing cars during the Industrial Revolution.
In order to manufacture a large number of cars, you first had to simplify and standardize the process of building a car.
Similarly, in order to label a large number of conversations, you have to first reduce and standardize the meaning representation of an utterance.  All car parts were joined together within an assembly line.  All conversations are labeled in succession by crowdworkers.  Automation helps turn each individual's task into something extremely simple.  You transform each job from "can you build this car part" into "can you verify this car part was added correctly".  Alternatively, you transform each annotation from "can you annotate this example" into "can you verify this proposed label is correct."  In the end, you complete many labels/cars in a quick, yet high quality manner.

In conclusion, we are able to capture the important details of a conversation by considering the key entities and semantics of a conversation.  We are able to annotate this quickly by concurrently not considering anything else, as well as making the process itself quite efficient.  Finally, we spend time designing the form of the meaning representation to be easy to manage.  This allows us to train powerful dialogue systems at scale.

*Authors Note: This post is clearly not a formal proof, just having a bit of fun with the idea :)*