#!/bin/zsh
# Usage: publish_snapshot.sh "<commit subject>" [push] [groups...]
# Copies allowlisted v7 files (disassembly_repair_v7/publish.py) into the public clone,
# commits on branch claude/repair-v7, and pushes only when the 2nd argument is "push".
set -e
cd "${0:A:h}/../.."
MSG="$1"; MODE="$2"; shift 2 || true
GROUPS=(${@:-code docs evidence pilot})
REPO=disassembly-planner-research
git -C $REPO checkout -q claude/repair-v7
PYTHONDONTWRITEBYTECODE=1 disassembly_learning_v1/.venv/bin/python -B -m disassembly_repair_v7.publish $GROUPS >/dev/null
if grep -rlqE "/Use[r]s/[A-Za-z]" $REPO/disassembly_repair_v7 $REPO/results/repair_v7; then echo "local path leak; abort"; exit 1; fi
git -C $REPO add disassembly_repair_v7 results/repair_v7
if ! git -C $REPO diff --cached --quiet; then
  git -C $REPO commit -q -m "$MSG" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
fi
if [ "$MODE" = "push" ]; then
  GIT_TERMINAL_PROMPT=0 git -C $REPO push -q origin claude/repair-v7
  [ "$(git -C $REPO rev-parse HEAD)" = "$(git -C $REPO ls-remote origin refs/heads/claude/repair-v7 | cut -f1)" ] && echo "PUSHED $(git -C $REPO rev-parse --short HEAD)"
else
  echo "COMMITTED $(git -C $REPO rev-parse --short HEAD)"
fi
