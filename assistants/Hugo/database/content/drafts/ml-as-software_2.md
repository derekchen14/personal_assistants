---
title: "ML as Software 2.0"
tags: [thoughts, trends]
---

## Introduction
- ML as Software 2.0 (per Andrej Karpathy): what does it mean in practice?
- Frame the question: if a company wants to embrace this shift, what should they actually do?

## The Web Development Analogy
- Desktop-to-web transition as a parallel to traditional software-to-ML shift
- Early web: debates over frameworks and rigid structures dominated
- The real lesson: unit tests, version control, and rapid iteration won — not the framework choice
- Implication: the same pattern likely holds for ML

## The Framework Trap
- Today's ML community repeats the same mistake: PyTorch vs. TensorFlow vs. JAX debates
- Debating models and architectures is still debating the code layer
- The differentiator in ML is not the framework — it's the data fed into the model

## Data Strategy as the Core Differentiator
- Data is ML's equivalent of "iterative shipping" in web development
- Key open questions that warrant more research:
  - What types of data drive the best model performance?
  - How do you define and measure data quality at scale?
  - Given a fixed budget, what is the optimal trade-off between data quality and quantity?
- Gap: annotation is expensive, so the field defaults to unsupervised pre-training — but this sidesteps the problem
- Opportunity: annotation efficiency research is under-invested and under-published

## Conclusion
- **Stop debating frameworks** — your framework choice is unlikely to be your competitive edge
- **Audit your data strategy now** — map what data you have, what quality it is, and how it was labeled
- **Invest in annotation pipelines** — build or buy tooling that lets your team label data faster and more consistently
- **Treat data quality vs. quantity as an explicit budget decision** — document the trade-off rather than defaulting to "more data"
- **Build data as a moat** — proprietary, well-curated datasets are harder to replicate than model architectures
- **Make data strategy a first-class research priority** — if your team isn't asking "what data should we collect next?", you're optimizing the wrong thing
