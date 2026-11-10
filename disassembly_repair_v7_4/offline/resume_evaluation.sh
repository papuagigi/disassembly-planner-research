#!/bin/zsh
# Resume the frozen v7.4 evaluation after amendment 1 (finished episodes are skipped, never rerun).
set -u
cd "${0:A:h}/../.."
PY=disassembly_learning_v1/.venv/bin/python
export PYTHONDONTWRITEBYTECODE=1
echo "$(date -u +%FT%TZ) evaluation resuming after amendment 1"
$PY -B -m disassembly_repair_v7_4.campaign74 evaluation --bank S5
code=$?
echo "$(date -u +%FT%TZ) evaluation exit=$code"
