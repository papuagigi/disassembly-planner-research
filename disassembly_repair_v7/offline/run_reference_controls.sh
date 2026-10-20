#!/bin/zsh
# Physical feasibility control (no LLM). One CAD at a time; 10 worker processes.
cd "${0:A:h}/../.."
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
PY=disassembly_learning_v1/.venv/bin/python
OUT=disassembly_repair_v7/analysis/physics/reference_search
$PY -B -m disassembly_repair_v7.feasibility disassembly_final_v5/cases/development/asap_01613.json --wall 1200 --workers 10 --out $OUT/positive_control_asap_01613.json
for c in asap_05954 asap_06444 asap_03114; do
  $PY -B -m disassembly_repair_v7.feasibility disassembly_final_v6/cases/evaluation/$c.json --wall 1800 --workers 10 --out $OUT/dev_$c.json
done
