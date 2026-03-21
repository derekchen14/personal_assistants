# Proposed Components

1. Human-in-the-loop controls: Agents pause at critical decisions. Delete database? Charge card? Send customer emails? Harness requires approval. Replit’s agent generates code but requires human confirmation before deployment.

2. Filesystem access management: Harnesses define accessible directories, allowed operations, and conflict resolution. Never touch system files.

3. Tool call orchestration. Bad orchestration creates infinite loops and cascading failures. Vercel’s 80% tool reduction reveals harness thinking. Right tools (not too many or too few) in the right trajectory.

4. Sub-agent coordination. Complex tasks need specialized agents. One researches, another writes, a third reviews. Harnesses manage communication, merge outputs, resolve conflicts. LangChain’s Deep Research coordinates multiple research sub-agents.

5. Prompt preset management. Different tasks need different instructions. Code review versus code generation. Bug fixing versus feature development. Harnesses maintain prompt libraries.

6. Lifecycle hooks. Initialize context. Run task. Save state. Handle failures. Retry logic. Logging. Harnesses implement reliable workflows.