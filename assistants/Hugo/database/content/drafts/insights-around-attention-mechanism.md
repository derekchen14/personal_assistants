---
title: "Insights around Attention Mechanism"
tags: [machine_learning]
---

## Introduction
- Brief history of sequence models before attention (RNNs, LSTMs)
- The core problem: information bottleneck in encoder-decoder architectures
- What attention promises: dynamic, context-aware focus
- Thesis: attention doesn't just help models — it fundamentally changes how they "think"

## Attention Vector Replaces the Input Vector
- What the input vector represents in a standard model
- How the attention vector is computed as a weighted sum of encoder hidden states
- Side-by-side comparison: static input vector vs. dynamic attention vector
- Why this substitution is the key architectural shift
- Intuition: the model "chooses" what to read at each step

## Importance of Attention Weights
- What attention weights are and how they are calculated (softmax over scores)
- How weights distribute focus across different parts of the input
- Visualizing attention weights: what the heatmaps tell us
- The role of alignment: matching decoder queries to encoder keys
- Why "soft" attention weights are differentiable and trainable end-to-end

## Where the Magic Really Lives
- Stacking attention layers: multi-head attention in Transformers
- Self-attention vs. cross-attention — different roles, same mechanism
- How attention enables parallelization (unlike RNNs)
- Emergent capabilities: long-range dependencies, coreference resolution
- Why attention became the backbone of modern LLMs (BERT, GPT, etc.)