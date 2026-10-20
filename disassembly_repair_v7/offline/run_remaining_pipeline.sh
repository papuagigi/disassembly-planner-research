#!/bin/zsh
# Pre-registered continuation (v7.1-P2): no outcome-dependent decision between steps.
cd "${0:A:h}/../.."
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
PY=disassembly_learning_v1/.venv/bin/python
V7=disassembly_repair_v7
stage(){ echo "{\"utc\":\"$(date -u +%FT%TZ)\",\"stage\":\"$1\"}" > $V7/outputs/pipeline_stage.json; echo "STAGE $1 $(date -u +%FT%TZ)"; }
stage waiting_for_pilot_selection
until [ -f $V7/outputs/protocol/pilot_selected_P2.json ]; do
  if ! pgrep -f "disassembly_repair_v7.pilot_inputs select" >/dev/null; then echo "SELECTION_PROCESS_ENDED_WITHOUT_RESULT"; stage selection_failed; exit 1; fi
  sleep 30
done
stage waiting_for_physics_diagnostics
while pgrep -f "disassembly_repair_v7.feasibility" >/dev/null || pgrep -f "run_physics_diagnostics.sh" >/dev/null || pgrep -f "disassembly_repair_v7.pilot_inputs" >/dev/null || pgrep -f "disassembly_repair_v7.offline" >/dev/null; do sleep 30; done
stage protection_check_before
$PY -B -m disassembly_repair_v7.protect || { stage protection_failed; exit 1; }
stage pilot_campaign
$PY -B -m disassembly_repair_v7.campaign || { stage campaign_error; exit 1; }
stage post_run_replay_and_aggregate
$PY -B -m disassembly_repair_v7.post_run || stage post_run_error
stage protection_check_after
$PY -B -m disassembly_repair_v7.protect
stage PIPELINE_DONE
