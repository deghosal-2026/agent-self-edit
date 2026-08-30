# AgentSelfEdit

An agent that rewrites its own system prompt from execution feedback — proposing edits, A/B testing them, and promoting only statistically-proven winners under guardrails.

## Why

Most production agents are prompt-tuned once by the human who wrote them, then never again. Every recurring failure is silently absorbed until a human manually tunes again. The agent that sees the most failure data is the least able to use it.

AgentSelfEdit turns prompt optimization into a self-sustaining, evidence-driven loop.

## How It Works

1. **Analyze** — After each task, an LLM reviews the execution trace and identifies what went wrong: the specific instruction that was missing, ambiguous, or wrong.
2. **Propose** — It proposes one or more concrete, minimal prompt edits, each with a stated hypothesis about why it should improve outcomes.
3. **Test** — Each candidate edit is A/B tested against the current prompt on a held-out task set, with confidence intervals, effect-size thresholds, and a minimum sample floor before any promotion decision.
4. **Promote or Archive** — The statistically-proven winner becomes the new baseline. The loser is archived with its full reasoning.
5. **Guard** — Frozen core sections, edit-distance limits, and drift detection keep the agent from rewriting itself into a worse version over hundreds of iterations.

## Status

🚧 **Pre-release.** Project scaffolded, architecture defined. First build in progress.

## License

MIT