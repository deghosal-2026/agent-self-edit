# 04 — Users and Customer User Journeys (CUJs)

> Sub-document of the [Design overview](../README.md). Defines target users, their problems, and 12 customer user journeys that drive the product scope.

## 4.1 Target Users

### Primary: Platform Teams Running Production Agents

Teams that maintain fleets of agents (5-50+) and can't afford to hand-tune every prompt. They see recurring failures across agents and want those failures to stop happening without a human editing every system prompt.

**Who they are:** LLMOps engineers, platform engineers, agent-infrastructure teams.
**What they need:** A self-improvement loop that runs unattended, with guardrails, provenance, and rollback.

### Secondary: Solo Builders and Agent Researchers

Individual developers building one or two agents who want them to improve over time without constant manual prompt engineering.

**Who they are:** Indie builders, OSS contributors, AI researchers exploring self-improvement.
**What they need:** A CLI they can point at an agent and walk away. Clear output showing what changed and why.

### Tertiary: Compliance and Audit Teams

Organizations that need to prove their agents' prompts evolved under controlled, auditable conditions.

**Who they are:** Compliance officers, SOC 2 auditors, risk managers.
**What they need:** A versioned, signed lineage of every prompt change with the evidence that justified it.

## 4.2 Domain Use Cases

Self-improving prompts apply anywhere an agent repeats a similar task type and sees execution feedback. The loop is most valuable when the failure rate is high enough to generate signal but varied enough that the agent learns generalizable patterns.

### Domain 1: Customer Support Ticket Classification

An agent classifies incoming support tickets by severity, category, and team. Classification errors cluster around ambiguous edge cases — "billing question that is really a technical issue" or "urgent phrasing that isn't actually urgent."

**Self-edit loop:** After each classification, the agent compares its prediction against the human's actual routing decision. The analyzer identifies which instruction was ambiguous. The A/B test proves the new wording reduces misclassification. The promotion gate prevents a change that works for one category from degrading another.

**Without self-edit:** The same misclassifications repeat daily. A human eventually notices the pattern, manually edits the prompt, and the cycle resets.

### Domain 2: Code Review / PR Analysis

An agent reviews pull requests for common issues — missing tests, error handling gaps, security smells. Review quality degrades when the agent applies the wrong standard (e.g., treating a prototype PR like a production PR).

**Self-edit loop:** The analyzer spots that the agent's "missing test cases" finding is too strict for documentation-only PRs. It proposes a softer instruction for PRs with `docs/` prefix. The A/B test confirms the new instruction reduces false positives without introducing false negatives.

**Without self-edit:** The agent either over-flags (annoying, ignored) or under-flags (missed issues). The team adjusts the prompt manually every few weeks.

### Domain 3: Data Extraction / Entity Parsing

An agent extracts structured data from unstructured documents — invoices, emails, log entries. Extraction quality varies by document format, language, or layout.

**Self-edit loop:** The analyzer identifies that extraction fails consistently on PDFs with embedded tables. It proposes a table-specific extraction instruction. The A/B test validates the new approach. The change is promoted only if it doesn't degrade plain-text extraction.

**Without self-edit:** The team maintains a growing list of format-specific workarounds in the prompt. The prompt becomes bloated. Performance plateaus.

### Domain 4: Content Moderation

An agent flags potentially harmful content. The cost of false positives is wasted reviewer time; the cost of false negatives is policy violations.

**Self-edit loop:** The analyzer detects that the agent over-flags sarcastic content. It proposes a softer rule for "sarcastic but benign" content. The A/B test measures the tradeoff between false positive reduction and false negative risk.

**Without self-edit:** The moderation team manually reviews every flagged item, building mental models of what the agent gets wrong. Turnover means that knowledge is lost.

### Domain 5: Sales Outreach Personalization

An agent drafts personalized sales emails. Response rates vary by industry, persona, and message length.

**Self-edit loop:** The analyzer correlates response rate with draft structure. It proposes a shorter opening for C-suite recipients. The A/B test validates the change against the existing template on a held-out segment.

**Without self-edit:** The sales team A/B tests manually using spreadsheets. Winning variants are copy-pasted into the prompt. The prompt grows organically without structure.

### Domain 6: Documentation Generation

An agent generates documentation from code changes. Output quality varies by codebase structure, comment quality, and change type.

**Self-edit loop:** The analyzer identifies that the agent generates overly verbose documentation for small bug fixes. It proposes a change-length-based instruction. The A/B test confirms the shorter output is preferred.

**Without self-edit:** Documentation is regenerated from scratch each time. The agent never learns from past feedback.

## 4.3 Customer User Journeys

### CUJ-01: Deploy, Observe, Improve (Platform Engineer)

**Persona:** Maya, platform engineer at a company with 15 agents.

Maya deploys AgentSelfEdit alongside a customer support classification agent. She configures the guardrails (frozen core sections, edit-distance limits) and sets a minimum sample floor of 50 tasks before any promotion. She walks away.

Three days later, she checks the dashboard. The agent has proposed 12 edits, A/B tested 8 of them, and promoted 2. The promoted edits reduced misclassification by 18%. The 6 rejected edits are logged with their reasoning. Maya can see exactly what changed, why, and the confidence interval that justified the promotion.

**Success criteria:** Deploy once, observe improvement, audit the lineage. No manual prompt edits needed.

### CUJ-02: Catch a Bad Edit Before It Ships (Platform Engineer)

**Scenario:** The analyzer proposes an edit that looks good on paper but degrades performance on a rare but important task type.

Maya's agent proposes an edit that improves classification on 90% of tickets but degrades it on the 10% that are security-related. The guardrails don't catch it, but the A/B test reveals the degradation on the security segment. The promotion gate rejects the edit. Maya sees a near-miss report: "Edit rejected — security segment accuracy dropped 12%."

**Success criteria:** The guardrails or statistical gate catch the bad edit before it ships. The near-miss is logged for human review.

### CUJ-03: Trace a Prompt's Lineage (Compliance Officer)

**Scenario:** An auditor asks why a moderation agent changed its behavior over the last quarter.

The compliance officer opens the prompt registry. They see a timeline of every promoted edit, the analyzer's hypothesis, the A/B test results, and the promotion gate decision. Each edit is linked to the execution traces that triggered it. The officer can see that every change was justified by statistically significant improvement on a held-out test set.

**Success criteria:** Full lineage available, each edit linked to evidence, one-click rollback to any previous version.

### CUJ-04: Roll Back a Promoted Edit (Operator)

**Scenario:** A promoted edit that passed all tests turns out to degrade behavior on a new task type that wasn't in the held-out set.

The operator sees a regression alert. They open the prompt registry, identify the problematic edit, and run one command to roll back to the last known-good version. The failed edit is flagged so the analyzer learns not to propose similar changes.

**Success criteria:** One-command rollback, failed edit flagged, lineage preserved.

### CUJ-05: First-Time Setup (Solo Builder)

**Scenario:** An indie developer builds a code review agent and wants it to improve over time.

The developer runs `agent-self-edit init` on their agent. The CLI scaffolds the config, runs a baseline evaluation on the held-out task set, and starts the loop. The developer sees the first edit proposal within hours. They can approve or reject it, or let the promotion gate decide automatically.

**Success criteria:** Setup in under 5 minutes, first edit proposed within hours, automatic or manual promotion.

### CUJ-06: Multi-Agent Fleet Optimization (Platform Engineer)

**Scenario:** A platform team has 12 agents performing similar tasks across different domains.

The team configures AgentSelfEdit for each agent independently. The dashboard shows per-agent improvement rates, edit velocity, and near-miss patterns. The team notices that all 12 agents independently proposed similar edits for one recurring failure pattern — suggesting a shared prompt template improvement.

**Success criteria:** Per-agent dashboards, cross-agent pattern detection, fleet-wide improvement visibility.

### CUJ-07: Shadow Mode Before Production (Platform Engineer)

**Scenario:** A team wants to test AgentSelfEdit without risking their production agent.

They run AgentSelfEdit in shadow mode: the analyzer proposes edits, the A/B test runs, and the promotion gate makes a decision — but the prompt is never actually changed. The operator reviews the proposed edits and their evidence, then manually approves the first promotion.

**Success criteria:** Shadow mode produces all the same output as live mode without modifying the prompt. Manual approval gate for the first promotion.

### CUJ-08: Drift Detection Alerts (Platform Engineer)

**Scenario:** An agent's prompt has been self-improving for months. The operator wants to know if it has drifted too far from the original intent.

The drift detector compares the current prompt against the original. It reports a divergence score and highlights the sections that have changed most. If the drift exceeds the configured threshold, it alerts the operator and suggests a review.

**Success criteria:** Drift score visible on dashboard, alerts at configurable threshold, ability to diff against any historical version.

### CUJ-09: Custom Guardrails (Platform Engineer)

**Scenario:** A team has specific requirements about what the agent can and cannot change in its own prompt.

The team configures frozen core sections — paragraphs of the prompt that the agent cannot modify. They also set edit-distance limits, drift thresholds, and a minimum sample floor. The analyzer respects all of these constraints when proposing edits.

**Success criteria:** Frozen sections never modified, edit-distance limits enforced, sample floor checked before promotion.

### CUJ-10: Held-Out Task Set Management (Platform Engineer)

**Scenario:** A team needs to update the held-out task set that the A/B test engine uses.

The team adds new tasks to the held-out set. The next A/B test cycle uses the updated set. The operator can see per-task performance changes across prompt versions.

**Success criteria:** Held-out set can be updated without restarting the loop, per-task performance tracked, regression detection on new tasks.

### CUJ-11: Audit Trail for Compliance (Compliance Officer)

**Scenario:** A SOC 2 auditor requests evidence that the agent's prompt changes were reviewed and justified.

The compliance officer exports the full audit trail: every promoted edit, every rejected edit, every near-miss, with timestamps, hypotheses, and evidence. The export is a structured document that maps directly to SOC 2 control requirements.

**Success criteria:** One-click export, SOC 2 control mapping, tamper-evident audit trail.

### CUJ-12: Learning from Rejected Edits (Platform Engineer)

**Scenario:** The analyzer keeps proposing the same type of edit that keeps getting rejected by the guardrails.

The near-miss logger captures the rejected edit, the guardrail that blocked it, and the reasoning. The analyzer incorporates this into its proposal generation, reducing the frequency of similar proposals over time.

**Success criteria:** Near-miss logging, analyzer adapts to avoid re-proposing rejected edits, measurable reduction in rejection rate over time.

## 4.4 User Types vs. CUJ Matrix

| User Type | Primary CUJs |
|---|---|
| Platform Engineer | CUJ-01, CUJ-02, CUJ-06, CUJ-07, CUJ-08, CUJ-09, CUJ-10, CUJ-12 |
| Solo Builder | CUJ-05 |
| Operator | CUJ-04, CUJ-08 |
| Compliance Officer | CUJ-03, CUJ-11 |

## 4.5 Grounded in (sources)

- Industry pattern: production agents are prompt-tuned once by hand, then never revisited
- Voyager (arXiv 2305.16291) — self-verification accumulates correct skills, 3.3x more items
- Self-correction blind spot (arXiv 2507.02778) — 64.5% same-model review failure rate
- OWASP Agentic Top 10 2026 — ASI08 (Cascading Failures), ASI09 (Misaligned Behavior)
- Common pattern across 6 domains: recurring failure → manual prompt edit → recurrence → repeat