# Real Traces Corpus

Real execution traces from various sources, organized by usability for the improvement loop.

## Directory Structure

```
field-test/corpus/real-traces/
├── usable/           ← Traces with real inputs, real outputs, and failures (35 traces)
├── telemetry/        ← Traces with generic/placeholder outputs (642 traces)
├── labeled/          ← Gold corpus with human-labeled failure clusters (30 traces)
└── README.md         ← This file
```

## usable/ — Traces that can drive the improvement loop

These traces have:
- Real task inputs (actual customer questions)
- Real model outputs (full LLM-generated responses)
- Concrete failures (success=False with deviation reasons)

| File | Traces | Source | Domain |
|------|--------|--------|--------|
| `hf-open-agent-traces.jsonl` | 26 | HuggingFace open-agent | Customer support triage |
| `hf-customer-support-traces.jsonl` | 9 | HuggingFace customer support | Customer support triage |

**Limitation:** Expected outputs are vague ("Successful customer-support-triage task") — these are suitable for analyzer quality evaluation but not for A/B test scoring.

**Use with runner:**
```bash
python3 field-test/scripts/run_improvement_loop.py --iterations 10 \
  --real-traces field-test/corpus/real-traces/usable/hf-open-agent-traces.jsonl
```

## telemetry/ — Traces with placeholder outputs (not usable for loop)

These traces have real metadata but generic/placeholder outputs:

| File | Traces | Problem |
|------|--------|---------|
| `agent-observatory-traces.jsonl` | 336 | Outputs are "N chars produced" — telemetry metadata only |
| `evalforge-failures.jsonl` | 34 | Outputs are "Agent X failed scenario Y" — no agent behavior |
| `hf-pi-coding-agent-traces.jsonl` | 200 | Outputs are "Completed 0 tool calls" — agent didn't execute |

**Do not use with the improvement loop.** The analyzer cannot produce meaningful proposals from these traces.

## labeled/ — Gold corpus for analyzer quality evaluation

| File | Traces | Description |
|------|--------|-------------|
| `gold-corpus.jsonl` | 30 | Human-labeled with `failure_cluster` and `ideal_intervention` fields |

**Use for:** Comparing analyzer proposals against labeled ideal interventions. Not for driving the improvement loop — the traces are curated from telemetry sources and lack concrete task structure.

**Labels:**
- Failure clusters: HALLUCINATION, SEMANTIC_LOOP, QUALITY_DEGRADATION, CONFUSION, TOOL_FAILURE, SCENARIO_FAIL, SUPPORT_ERROR
- Ideal interventions: PROMPT_GROUNDING, PROMPT_STOP_CONDITION, PROMPT_SELF_CORRECT, PROMPT_CLARIFY, PROMPT_TOOL_USE, PROMPT_STRUCTURE, PROMPT_CONSTRAIN

## Downloading More Traces

To download additional scored traces with concrete expected outputs:

```bash
pip install datasets
python3 field-test/scripts/download_scored_traces.py
```

This downloads from MMLU, GSM8K, TruthfulQA, and HellaSwag — all of which have concrete expected outputs that scorers can match against.