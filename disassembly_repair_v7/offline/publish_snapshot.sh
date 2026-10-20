#!/bin/zsh
# Usage: publish_snapshot.sh "<commit subject>" [commit|push] [groups...]
# Copies allowlisted v7 files (disassembly_repair_v7/publish.py) into the public clone and
# commits on branch claude/repair-v7. "push" (core update, user rule 2026-10-20) also pushes
# the branch, merges it into main (after syncing origin/main) and pushes main.
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
  export GIT_TERMINAL_PROMPT=0
  git -C $REPO push -q origin claude/repair-v7
  git -C $REPO fetch -q origin
  git -C $REPO checkout -q main
  git -C $REPO merge -q --ff-only origin/main
  if ! git -C $REPO merge -q --no-edit claude/repair-v7; then
    git -C $REPO merge --abort; git -C $REPO checkout -q claude/repair-v7; echo "MAIN MERGE CONFLICT; branch pushed, main unchanged"; exit 1
  fi
  git -C $REPO push -q origin main
  MAIN=$(git -C $REPO rev-parse HEAD)
  git -C $REPO checkout -q claude/repair-v7
  [ "$(git -C $REPO rev-parse HEAD)" = "$(git -C $REPO ls-remote origin refs/heads/claude/repair-v7 | cut -f1)" ] || { echo "branch remote mismatch"; exit 1; }
  [ "$MAIN" = "$(git -C $REPO ls-remote origin refs/heads/main | cut -f1)" ] || { echo "main remote mismatch"; exit 1; }
  echo "PUSHED branch $(git -C $REPO rev-parse --short HEAD); main $(git -C $REPO rev-parse --short $MAIN)"
else
  echo "COMMITTED $(git -C $REPO rev-parse --short HEAD)"
fi
