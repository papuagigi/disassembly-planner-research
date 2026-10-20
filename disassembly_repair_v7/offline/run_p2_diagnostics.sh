#!/bin/zsh
# P2 candidate physics: reference search on development CADs only (no LLM).
cd "${0:A:h}/../.."
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
PY=disassembly_learning_v1/.venv/bin/python
OUT=disassembly_repair_v7/analysis/physics/reference_search
for c in asap_05954 asap_03114 asap_06444; do
  $PY -B -m disassembly_repair_v7.feasibility disassembly_final_v6/cases/evaluation/$c.json --wall 7200 --workers 8 --max-checks 2500 --variant P2_persist_up_to_stable_penetration --out $OUT/diag_P2_$c.json
done
