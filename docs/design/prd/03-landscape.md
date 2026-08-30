# 03 — Landscape

> Sub-document of the [Design overview](../README.md). Competitive landscape, the gap, and our wedge.

## 3.1 The Landscape

| Category | Example | What they do | What they don't do |
|---|---|---|---|
| Prompt optimization frameworks | DSPy, TextGrad, SAMMO | Optimize prompts via gradient-free optimization, few-shot selection, or program synthesis | Don't run as a continuous loop on a live agent. Require offline datasets and retraining cycles |
| Agentic reflection | AutoGen reflect, LangGraph reflect, CrewAI reflection | Append a reflection step to context after execution | Prompt itself never changes. Context bloat without learning. Same failure repeats tomorrow |
| Prompt version control | PromptLayer, LangSmith, Agenta | Version, track, and evaluate prompts | Don't propose, test, or promote edits automatically. Human-driven change workflow |
| A/B testing frameworks | LaunchDarkly, Statsig | Feature flagging and experiment analysis | Not designed for prompt-level A/B testing. No understanding of prompt semantics |
| Manual prompt engineering | ChatGPT, Claude, Playground | Human writes prompt, iterates manually | No automation, no guardrails, no statistical rigor |

## 3.2 The Gap

No existing tool combines a **continuous self-improvement loop** with **statistical safety guarantees** and **prompt provenance**. The space has three disconnected clusters:

1. **Optimization frameworks** (DSPy, TextGrad) — powerful but offline. You run them on a dataset, get a better prompt, and deploy it. They don't run continuously on a live agent.

2. **Reflection mechanisms** (AutoGen, LangGraph) — built into agent frameworks but append context rather than modify the prompt. The prompt itself never changes. The same failure repeats.

3. **Prompt management** (PromptLayer, LangSmith) — version and evaluate prompts but require a human to propose and promote changes. No automation, no guardrails.

AgentSelfEdit sits in the intersection: a continuous loop that proposes, tests, and promotes prompt edits with statistical and safety guarantees.

## 3.3 Our Wedge

| Dimension | DSPy / TextGrad | AutoGen reflect | PromptLayer | AgentSelfEdit |
|---|---|---|---|---|
| Continuous loop | ❌ Offline | ❌ Per-task only | ❌ Human-driven | ✅ Continuous |
| Proposes edits | ✅ (programmatic) | ❌ (appends context) | ❌ (human writes) | ✅ (LLM proposes) |
| A/B tests edits | ✅ (offline dataset) | ❌ | ❌ | ✅ (held-out tasks) |
| Statistical gate | ✅ (metric-driven) | ❌ | ❌ | ✅ (CI, effect size, floor) |
| Safety guardrails | ❌ | ❌ | ❌ | ✅ (frozen core, drift, distance) |
| Prompt lineage | ❌ | ❌ | ✅ (versioned) | ✅ (versioned + rollback) |
| Live agent integration | ❌ | ✅ (in-loop) | ❌ | ✅ (sidecar) |

## 3.4 Why This Is Hard

1. **Evaluation safety** — a single fluke edit promoted on noise poisons the baseline for all future iterations. The guardrails must be as good as the optimization.

2. **Statistical rigor** — naive win-rate comparison on small samples is meaningless. Confidence intervals, effect sizes, and sample floors are non-negotiable.

3. **Drift prevention** — unconstrained self-editing optimizes toward the eval, not the task. Guardrails must resist this.

4. **Provenance and rollback** — a self-modifying system needs a clean, explainable way back.

5. **User trust** — the user must be able to see exactly what changed, why, and whether the guardrails held. Without this, they won't trust the system.

## 3.5 Grounded in (sources)

- DSPy: github.com/stanfordnlp/dspy
- TextGrad: github.com/zou-group/textgrad
- AutoGen: github.com/microsoft/autogen
- PromptLayer: promptlayer.com
- LangSmith: langchain.com/langsmith
- Self-correction blind spot (arXiv 2507.02778) — 64.5% same-model review failure rate
- Voyager (arXiv 2305.16291) — self-verification accumulates correct skills