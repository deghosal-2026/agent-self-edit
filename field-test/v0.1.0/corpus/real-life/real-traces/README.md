# Real Traces — AgentSelfEdit v0.1.0 Field Test
#
# These traces are sourced from real agent executions across the portfolio:
# - agent-exec-trace (AgentObservatory): real LLM telemetry traces
# - agent-eval-forge (EvalForge): real agent scenario failures
#
# Format: JSON-lines, one Trace object per line.
# Schema: field-test/v0.1.0/corpus/real-traces/
# Source attribution: agent-exec-trace m13-results, agent-eval-forge field/results
#
# Conversion notes:
# - Telemetry trace_id -> task_id
# - Detector name -> failure_reason
# - Latency/tokens -> included in steps metadata
# - EvalForge failed scenarios: scenario_id -> task_id, scenario goal -> task_input,
#   agent output -> final_output, expected -> expected_output, pass/fail -> success