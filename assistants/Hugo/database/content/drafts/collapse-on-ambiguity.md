---
title: "Collapse On Ambiguity"
---

## What Is Ambiguity, Really?
- Define ambiguity in the context of language, communication, and AI systems
- Distinguish between lexical, syntactic, and pragmatic ambiguity with concrete examples
- Explain why ambiguity is not a bug but an inherent feature of natural language
- Set up the core tension: humans navigate ambiguity intuitively, but systems struggle

## How Ambiguity Breaks Conversations
- Walk through real-world failure cases where unresolved ambiguity derails a dialogue
- Explore the cascade effect: one ambiguous turn poisons downstream context
- Discuss the cost of ambiguity in high-stakes domains (customer support, medical, legal)
- Highlight why silence or confident wrong answers are both dangerous responses

## Catching Ambiguity Early: The Pipeline Approach
- Introduce the concept of an ambiguity detection layer at the input stage
- Outline a practical pipeline: detect → classify → resolve or escalate
- Cover techniques: slot-filling, confidence thresholds, clarifying question generation
- Show how early detection reduces recovery cost versus catching ambiguity late

## Designing for Uncertainty
- Reframe the goal: instead of eliminating ambiguity, design systems that are robust to it
- Introduce patterns like graceful degradation, hedged responses, and explicit confirmation loops
- Discuss how UX and copy choices can reduce ambiguity at the source
- Close with a call to treat uncertainty as a first-class design constraint, not an edge case