---
title: "Using Multi-modal Models to Improve AI Agents"
---

## Motivation

Text-only agents operate on tokenized language alone, missing rich spatial and visual cues present in real-world environments.

UI navigation, chart interpretation, and image-heavy documents require visual grounding that LLMs cannot infer from alt-text alone.

Growing benchmark evidence shows multi-modal agents outperform text-only baselines on vision-dependent tasks.

Business case: reducing the human-in-the-loop burden for tasks involving screenshots, diagrams, and video frames.


## Process
Attach a vision encoder (e.g., CLIP or SigLIP) to the agent's planning backbone to produce image embeddings alongside text tokens.

Route incoming observations through a modality classifier so the planner selects the right encoder per input type.

Align image and text representations via a lightweight projection layer before feeding to the LLM.

Implement a perception-action loop: observe (image + text) → encode → plan → act → observe next frame.

Pick a vision encoder that matches your input distribution and latency constraints.

Wire it to the planner by connecting encoder outputs to the token stream the LLM already consumes.

Fine-tune on UI traces to ground the agent's visual understanding in realistic interaction data.

Evaluate on held-out workflows to measure generalisation before any wider rollout.

Ship behind a flag so the multi-modal path can be toggled off without disrupting the existing text-only agent.


## Ideas
Grounding bounding-box outputs to action coordinates for GUI agents (click, drag, scroll).

Using video frame sequences instead of single screenshots to capture temporal context.

Chaining a captioning model as an intermediate step to produce structured descriptions for a text-only planner.

Experimenting with mixture-of-encoders to handle heterogeneous inputs (PDFs, web pages, camera feeds).

Using video for temporal grounding, giving the agent a richer sense of state change across multi-step tasks.

Treating screenshots as a tool the agent can call on demand rather than piping every frame through the vision encoder.

Falling back to text-only when the latency budget is tight, preserving responsiveness without scrapping the multi-modal architecture entirely.


## Takeaways

Multi-modal inputs meaningfully reduce agent errors on vision-heavy tasks, but latency overhead is non-trivial.

Projection layer quality matters more than encoder size — a well-tuned small encoder beats a large misaligned one.

Caption-as-intermediary is a pragmatic fallback when full multi-modal fine-tuning is out of scope.

Next steps: evaluate on long-horizon tasks and measure performance vs. cost trade-offs across encoder choices.
