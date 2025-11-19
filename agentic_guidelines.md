1. Architecture

Keep agents small and specialized.

Control what goes into the LLM (minimal, relevant context).

Route tasks to the model that fits cost + complexity.

Add simple logs/traces early; expand later.

2. Behavior & Planning

For multi-step tasks, force the agent to plan before acting.

Check the whole action sequence, not just the answer.

Use a critic/reflection loop only for important accuracy moments.

Parallelize independent tasks.

3. Memory

Use Session = short-term, MemoryService = long-term.

Keep memory small; summarize often.

Run heavy memory processing async.

4. Tools

Each tool = one clear action.

Document tool names/descriptions well.

Store large outputs outside context; return references only.

Use MCP for clean integrations.

5. Safety

Grant the agent minimal permissions.

Use input/output filters for obvious risks.

Check tool calls before execution when needed.

Sanitize LLM output shown in any UI.

6. Monitoring

Log prompts, tool calls, and important state changes.

Track basic metrics (latency, cost, success rate).

Capture full traces when users dislike the result.

7. Deployment

Test with a small, curated eval set before shipping.

Version prompts and tools.

Keep the runtime agent stateless; externalize data.

Make tools safe to retry.