"""AgentSelfEdit — An agent that rewrites its own system prompt from execution feedback."""

from importlib.metadata import version as _version

try:
    __version__ = _version("agent-self-edit")
except Exception:
    __version__ = "0.0.0"
