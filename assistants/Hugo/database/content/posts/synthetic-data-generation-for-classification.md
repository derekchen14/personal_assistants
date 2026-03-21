---
title: "Synthetic Data Generation for Classification"
---

## Motivation
Labeling data is expensive, slow, and unforgiving. Before a model learns anything useful, annotators must read, interpret, and tag thousands of examples — and the costs stack up fast. At small scale, it's manageable. At product scale, it's a bottleneck that kills roadmaps.

We hit that wall head-on while building an intent classification chatbot for a customer support platform. The premise was straightforward: users type a message, the model identifies their intent, and the system routes them to the right response flow. Simple in concept, brutal in practice.

The chatbot needed to distinguish between more than 40 discrete intents — things like "track my order," "request a refund," "update billing info," and "speak to a human." Some of those intents are easy to tell apart. Others are deceptively close. A user saying *"I need to fix my payment"* could mean they want to update a card on file, dispute a charge, or resolve a failed transaction. Getting the model to reliably separate these required a training set that wasn't just large — it had to be diverse, covering the full range of ways real users phrase each intent, including misspellings, abbreviations, and the kind of fragmented, mid-thought messages people actually type when they're frustrated.

So we scoped the labeling effort. To hit acceptable accuracy across all 40+ intents, our ML lead estimated we needed at least 300–500 labeled examples per intent. That's upward of 20,000 annotations before we'd even trained a first meaningful model. We brought in a team of annotators, built a labeling guide, and started grinding through the queue.

The first wave went fine. Then the product team updated the intent taxonomy.

Three intents were merged. Two new ones were added. One was split into four. Overnight, a significant portion of our labeled data was either wrong, orphaned, or insufficient for the new categories. The labeling queue reset almost from scratch. We'd spent weeks and real budget to get to a place we could no longer use.

That cycle — label, ship, update, re-label — happened three times in two months. Each iteration cost us time we didn't have and money we hadn't budgeted for. Worse, it created a perverse incentive: the product team started hesitating to make intent changes they believed in because they knew it would blow up the data pipeline. The labeling burden was actively shaping product decisions in ways that had nothing to do with what users needed.

That's when we started asking a harder question: what if we didn't rely on human annotation as the primary source of training data? What if we could *generate* labeled examples — fast, cheaply, and in whatever quantity the model actually needed? That question is what led us to synthetic data generation, and it changed how we think about the entire classification pipeline.
## Breakthrough Ideas
The first set of ideas we explored were classical augmentation techniques: paraphrasing, back-translation, and noise injection. These methods transform existing labeled examples into new ones, expanding the training set without requiring additional human annotation. They work well as a baseline, but they're limited by the diversity of the original data.

The bigger unlock came from using large language models to generate utterance variations from scratch. Instead of augmenting what we had, we could prompt an LLM to produce a wide range of realistic phrasings for each intent.

One technique stood out above the rest: reversing the generation direction. Rather than starting with an utterance and asking what intent it represents, we started from the label and asked the model to generate a plausible conversation. This label-to-conversation approach gave us fine-grained control over class coverage. After generation, we applied a denoising step to filter out low-quality or ambiguous examples before they reached the training set.
## Process
Our synthetic data pipeline follows a structured sequence that moves from design to clean, ready-to-train examples. The first decision is choosing the right base model or template for generation. A capable instruction-tuned LLM works well here, though smaller fine-tuned models can be more cost-effective when you have some seed data to work with.

The pipeline then moves through five concrete steps. First, design the scenarios: define the intent classes and the realistic contexts in which each might appear. Second, assign labels to each scenario before generation begins, so every output has a ground-truth class from the start. Third, generate conversations by prompting the model with the scenario and label, producing a batch of candidate training examples. Fourth, review a sample of the outputs to catch systematic errors or prompt drift early. Fifth, denoise at scale using a classifier or heuristic filters to remove examples that are off-topic, ambiguous, or too similar to one another.

Sampling strategy matters throughout. Varying temperature, prompt phrasing, and scenario diversity prevents the model from generating repetitive outputs. Quality control checks at each stage keep noise from compounding downstream.
## Best Practices
## Best Practices
## Takeaways
Applying synthetic data to classification taught us several lessons we didn't expect. The biggest one: quality control is not optional. A pipeline that generates thousands of examples quickly can also flood your training set with noise just as fast. Denoising and review steps are what separate a useful dataset from a harmful one.

Synthetic data shines when you need coverage across many classes, when labeled data is scarce for a specific domain, or when your intents evolve faster than annotators can keep up. It falls short when the real-world distribution is highly nuanced, when edge cases matter more than volume, or when your base model lacks the domain knowledge to generate realistic examples.

For teams hitting labeling bottlenecks, the practical recommendation is to start small. Generate synthetic data for one or two underrepresented classes, measure the impact on model performance, and build confidence before scaling the pipeline. The approach works, but it rewards patience and iteration over bulk generation.