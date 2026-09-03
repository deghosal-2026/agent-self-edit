"""Run the Docker pytest suite with OMLX real LLM.

Usage:
    python field-test/scripts/run_docker_tests.py

Runs: pytest tests/test_docker.py -m docker
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def main():
    cmd = [
        sys.executable, "-m", "pytest", "tests/test_docker.py",
        "-v", "-m", "docker", "--no-header",
        "-p", "no:cacheprovider", "--no-cov", "-n", "4",
    ]
    result = subprocess.run(cmd, cwd=REPO_ROOT)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
