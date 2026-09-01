"""Download real pi coding agent traces from HuggingFace raw files.

This uses huggingface-hub to download raw session files directly,
bypassing the datasets library which has parsing issues with some files.

pip install huggingface-hub
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))

OUTPUT_DIR = (Path(__file__).resolve().parent.parent
              / "v0.1.0" / "corpus" / "real-life" / "real-traces")
REPO = "MaxDevv/real-pi-coding-agent-traces-sessions"


def _skip_if_exists(path: Path) -> bool:
    if path.exists() and path.stat().st_size > 0:
        print(f"  Skipping {path.name} (already exists, {path.stat().st_size} bytes)")
        return True
    return False


def download_pi_agent_traces(max_sessions: int = 200) -> int:
    output_path = OUTPUT_DIR / "hf-pi-coding-agent-traces.jsonl"
    if _skip_if_exists(output_path):
        return 0

    try:
        from huggingface_hub import hf_hub_download, list_repo_files
    except ImportError:
        print("pip install huggingface-hub first")
        return 0

    print(f"Listing files in {REPO}...")
    files = [f for f in list_repo_files(REPO, repo_type="dataset")
             if f.endswith(".jsonl") and f != "manifest.jsonl"]
    print(f"  Found {len(files)} session files. Processing up to {max_sessions}...")

    count = 0
    with open(output_path, "w") as fout:
        for file_path in sorted(files)[:max_sessions]:
            local_path = hf_hub_download(REPO, file_path, repo_type="dataset")
            try:
                events = [json.loads(line) for line in open(local_path) if line.strip()]
            except (json.JSONDecodeError, OSError) as e:
                print(f"  Skipping malformed file {file_path}: {e}")
                continue

            if not events:
                continue

            session_id = events[0].get("sessionId", events[0].get("id", file_path.split("/")[-1].replace(".jsonl", "")))
            prompt = ""
            success = True
            failure_reason = None
            steps = []
            tool_calls = 0
            user_msgs = 0

            for evt in events:
                evt_type = evt.get("type", "")
                step = {"event_type": evt_type}
                if evt_type == "message":
                    role = evt.get("message", {}).get("role", "")
                    content = evt.get("message", {}).get("content", "")
                    if isinstance(content, list):
                        content = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
                    if role == "user":
                        user_msgs += 1
                        if not prompt:
                            prompt = content[:200]
                    step["role"] = role
                    step["content"] = str(content)[:200]
                    if role == "assistant" and ("error" in content.lower() or "failed" in content.lower()):
                        success = False
                        failure_reason = content[:200]
                elif evt_type == "tool_call":
                    tool_calls += 1
                    step["tool"] = evt.get("name", "")
                    step["arguments"] = str(evt.get("arguments", ""))[:200]
                elif evt_type == "tool_result":
                    step["tool_result"] = str(evt.get("content", ""))[:200]
                elif evt_type == "session":
                    session_id = evt.get("id", session_id)
                steps.append(step)

            trace = {
                "task_id": session_id,
                "task_input": prompt or "Pi coding agent session",
                "final_output": f"Completed {tool_calls} tool calls, {user_msgs} user messages",
                "expected_output": "Successful coding session",
                "success": success,
                "failure_reason": failure_reason,
                "timestamp": events[0].get("timestamp", ""),
                "prompt_version": 1,
                "steps": steps[:50],
                "metadata": {
                    "source": "huggingface",
                    "dataset": REPO,
                    "num_tool_calls": tool_calls,
                    "num_user_messages": user_msgs,
                    "n_events": len(events),
                },
            }
            fout.write(json.dumps(trace) + "\n")
            count += 1
            if count % 50 == 0:
                print(f"  Processed {count}/{min(max_sessions, len(files))}...")

    print(f"  Wrote {count} pi coding agent traces to {output_path}")
    return count


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    total = download_pi_agent_traces()
    print(f"\nTotal: {total} traces")
