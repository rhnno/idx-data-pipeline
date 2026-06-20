#!/usr/bin/env bash
# Tests for the Dockerfile, runnable two ways:
#
#   1. WITHOUT Docker (this script): simulates the builder stage's exact
#      `pip install -r requirements.txt` inside a clean, isolated venv,
#      then runs the same commands the image's ENTRYPOINT would run. This
#      catches dependency/environment bugs (e.g. a package only present by
#      accident in the dev machine, not actually declared) without needing
#      a Docker daemon available.
#
#   2. WITH Docker (if you have it): run the commands in
#      docker_build_test.txt below, which exercise the real, built image -
#      this additionally validates the Dockerfile syntax itself, the
#      multi-stage COPY, non-root user permissions, and ENTRYPOINT/CMD
#      behavior, none of which step 1 can verify on its own.
#
# Disclosure: this repo's dev/test environment does not have a Docker
# daemon available, so step 2 has NOT been run against this Dockerfile.
# Step 1 has been run and is what this script automates. Before treating
# the Docker image itself as verified, run step 2 somewhere Docker is
# available.

set -euo pipefail
cd "$(dirname "$0")/.."

VENV_DIR="$(mktemp -d)/docker_sim_venv"
echo "== Simulating builder stage: clean venv install =="
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --no-cache-dir -q -r requirements.txt
echo "OK: requirements.txt installs cleanly with no transitive-dependency assumptions."

echo
echo "== Simulating ENTRYPOINT default CMD: python main.py validate =="
"$VENV_DIR/bin/python" main.py validate
echo "OK: validate command runs end-to-end in the isolated environment."

echo
echo "== Simulating test suite in the same isolated environment =="
"$VENV_DIR/bin/pip" install -q pytest
"$VENV_DIR/bin/python" -m pytest tests/ -q
echo "OK: test suite passes using only what's declared in requirements.txt."

echo
echo "== Dockerfile static checks (no daemon needed) =="
python3 - <<'PYEOF'
content = open("Dockerfile").read()
checks = {
    "uses a pinned slim base image": "python:3.12-slim" in content,
    "multi-stage build present": content.count("FROM") >= 2,
    "creates a non-root user": "useradd" in content,
    "switches to non-root user before running": "USER pipeline" in content,
    "does not COPY a venv/cache dir into the final image": ".venv" not in content,
    "has an ENTRYPOINT": "ENTRYPOINT" in content,
}
failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(f"{'OK' if ok else 'FAIL'}: {name}")
if failed:
    raise SystemExit(f"Dockerfile static checks failed: {failed}")
PYEOF

rm -rf "$VENV_DIR"
echo
echo "All simulated checks passed. This does NOT confirm 'docker build' itself"
echo "succeeds - see docker_build_test.txt for the real-Docker test commands."
