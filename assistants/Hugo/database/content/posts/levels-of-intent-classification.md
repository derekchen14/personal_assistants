---
layout: post
title: Label Formats for Intent Classification
date: '2019-05-13 17:53:21'
tags: [lists, research]
---

When trying to understand user belief, a NLU model attempts to track the intent over the length of the conversation. &nbsp;However, what format should this intent be represented? &nbsp;Is it continuous or discrete? &nbsp;It it directly passed into the Policy Manager or should it be augmented first? &nbsp;Hundreds of hours and effort will be spent finding labels for training such a model, so it seems reasonable we should agree on what format this label should take. &nbsp;But considering the issue in any depth will show trade-offs in different label formats, so the answer is not immediately obvious.

To be more concrete, let's first observe the spectrum of options, ranging from more structured to less structured:

_\<Most direct and interpretable, but less generalizable. &nbsp;Has more structure. \>_

<!--kg-card-begin: markdown-->
1. Output is from a rule-based model. Classifier is rules-based or works by statistical inference, so it is largely deterministic. It is directly based on structure infused by the expert.
2. Output is a semantic or syntactic parse, which is very still highly structured. There is a pre-defined set of logical predicates to choose from, so building such a system is heavily dependent on an expert. Gives highly interpretable results.
3. Output is a intent made up of dialogue act, slot, relation, value, such as `inform(price < $100)` or `accept(restaurant=the golden wok)` or `open(text=good morning)`. This has a flat structure, rather than a complex hierarchical parse tree, so it is less structured than before. This has a pre-defined expert labeled ontology, and much easier to label.
4. Output is a generic natural language tag. It is human interpretable, but largely unrestricted. This gets very messy quickly because the lexicon is only determined after the fact, if at all. So there can be many tags that are very similar to each other.
5. Output of classifier is some latent continuous vector that is then passed to a separate memory module, decoder, or other network. Great for back-propagation and end-to-end learning, really poor for human interpretability. Most powerful representation of user intent. Would need to build tools to understand its hidden structure, which arises from data rather than expert labels.
<!--kg-card-end: markdown-->

_\<Least direct and interpretable. &nbsp;Has no predefined structure.\>_

Implied in the spectrum is a shift from rule-based methods to more neural-based methods. &nbsp;While it may seem inevitable that everything moves into a deep learning direction, there is certainly the case to be made that we aren't there yet and also that human-interpretability matters more in certain situations than just high accuracy. As with many decisions involving trade-offs, I don't think there's a right answer overall, but there might be a right answer for your problem – so take the time to choose wisely.

