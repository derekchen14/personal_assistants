---
title: "Why No One is Building AI Agents"
---

## The Vendor Moat Reframe
- First-person motivation: building AF, wanted to know the landscape
- Surveyed ~14 harnesses across four families
- The Cognitive Dissonance: vendor "agents" look nothing like Claude Code or Cursor
- The Reframe: vendors aren't building agents; they are defending data planes (Salesforce, Snowflake, Microsoft)
- Moat Defense: Trust layers and hardwired topology keep data inside the security boundary

## The Agent SDK Landscape
- The blind spot: everyone debates models, but nobody talks about loop shape (topology)
- Four canonical topologies:
  - Free loop: model picks tools and termination (Claude Code, Pi)
  - Graph: dev picks DAG, model fills nodes (ADK, Strands, Semantic Kernel)
  - Flow set: dev picks N topologies, model navigates within and across (AF)
  - Vendor singleton: vendor picks one shape, customer fills tools
- Why topology is sticky: it constrains state, evals, and failure modes

## Where the Independent Market Wins
- Identifying the "Losers": Why graph-shaped scaffolding fails free-loop tasks
- Case studies: Cognition, Magic/Augment vs. Cursor
- Analysis of ServiceNow and Microsoft's dual-lane strategy

## Strategic Implications
- Buyers: You are buying a security boundary, not agent quality
- Builders: Independent and platform markets are not actually competing
- Model labs: Anthropic’s unique position with Computer Use/Claude Code

## The Field Guide (Appendix)
- Brief overview of the 14 harnesses grouped by family
- Final Reframe: Choosing your topology before your model