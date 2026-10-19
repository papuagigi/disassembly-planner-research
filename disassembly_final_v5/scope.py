"""Prospective cohort sizes;episode budgets and policy behavior stay unchanged."""
from .common import ROOT,read

DEFAULT_SCOPE=dict(full_discovery_CADs=10,reused_discovery_CADs=4,new_discovery_CADs=6,
                   validation_CADs=10,evaluation_CADs=10,prior_local_probe_discovery_CADs=90)

def study_scope():
    path=ROOT/'config/study_scope.json'
    value=read(path) if path.exists() else dict(DEFAULT_SCOPE)
    assert value['full_discovery_CADs']==value['reused_discovery_CADs']+value['new_discovery_CADs']
    assert value['reused_discovery_CADs']>=4 and value['validation_CADs']>=3 and value['evaluation_CADs']>=4
    return value
