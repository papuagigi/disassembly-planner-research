#!/bin/zsh
# Start the frozen v7.4 evaluation (bank S5, user decision 2026-10-21) as soon as the model-free selection ends.
# Launched as `zsh <this file>` so that procs.project_processes() does not count this waiting shell as project work.
set -u
cd "${0:A:h}/../.."
PY=disassembly_learning_v1/.venv/bin/python
while pgrep -f "selection74 select" >/dev/null; do sleep 60; done
SEL=disassembly_repair_v7_4/outputs/protocol/selection_selected.json
[ -f $SEL ] || { echo "selection did not finish (no selection_selected.json)"; exit 3; }
export PYTHONDONTWRITEBYTECODE=1
echo "$(date -u +%FT%TZ) selection finished; freezing"
$PY -B -m disassembly_repair_v7_4.campaign74 freeze --bank S5 || { echo "freeze refused (see message above)"; exit 4; }
echo "$(date -u +%FT%TZ) evaluation starting"
$PY -B -m disassembly_repair_v7_4.campaign74 evaluation --bank S5
echo "$(date -u +%FT%TZ) evaluation exit=$?"
