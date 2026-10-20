#!/bin/zsh
# Diagnostic-only physics controls (no LLM). Evaluated physics unchanged unless --variant is given.
cd "${0:A:h}/../.."
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
PY=disassembly_learning_v1/.venv/bin/python
OUT=disassembly_repair_v7/analysis/physics/reference_search
W=${WORKERS:-6}
# 1. 06444: evaluated physics seeded with the v6 A accepted 11-removal prefix (re-verified first).
$PY -B -m disassembly_repair_v7.feasibility disassembly_final_v6/cases/evaluation/asap_06444.json --wall 7200 --workers $W --max-checks 2500 --prefix-json "$(cat $OUT/06444_v6A_prefix.json)" --out $OUT/dev_asap_06444_from_v6A_prefix.json
# 2. 05954: evaluated physics, no remaining-set pruning.
$PY -B -m disassembly_repair_v7.feasibility disassembly_final_v6/cases/evaluation/asap_05954.json --wall 7200 --workers $W --no-prune --max-checks 2500 --out $OUT/dev_asap_05954_noprune.json
# 3. P1 diagnostic rule (pre-existing interference may persist, not grow).
for c in asap_05954 asap_03114 asap_06444; do
  $PY -B -m disassembly_repair_v7.feasibility disassembly_final_v6/cases/evaluation/$c.json --wall 7200 --workers $W --max-checks 2500 --variant P1_persisting_interference --out $OUT/diag_P1_$c.json
done
