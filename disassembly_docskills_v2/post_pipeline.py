"""Finite continuation of this already authorized study, not an automation.

The current qualification process remains the sole source selector. After its
final receipt exists, run the frozen first-episode campaign exactly once, then
offline analysis/replay/integrity checks. Errors stop the pipeline; no scored
episode is retried and no document or actor is changed.
"""
from __future__ import annotations
import functools
import http.server
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback
from .common import ROOT, WORKSPACE, read, write, sha, utc
from .protocol import verify

STATE = ROOT/'outputs/pipeline_state.json'


def status(phase, **kwargs):
    value = dict(phase=phase, utc=utc(), pid=os.getpid(),
                 protocol_sha256=sha(ROOT/'outputs/protocol/freeze.json'), **kwargs)
    write(STATE, value)
    print(json.dumps(value, ensure_ascii=False), flush=True)


def module(name, log):
    verify()
    status(name)
    with (ROOT/'outputs'/log).open('x') as handle:
        result = subprocess.run([sys.executable, '-B', '-m',
                                 'disassembly_docskills_v2.'+name],
                                cwd=WORKSPACE, stdout=handle,
                                stderr=subprocess.STDOUT,
                                env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    if result.returncode:
        raise RuntimeError(name+' stopped; see '+log)
    verify()


def main():
    if STATE.exists():
        prior = read(STATE)
        try:
            os.kill(prior['pid'], 0)
        except ProcessLookupError:
            pass
        else:
            raise RuntimeError('Existing pipeline process; duplicate refused')
        raise RuntimeError('Existing pipeline receipt; inspect it before any explicit continuation')
    status('waiting_for_original_frozen_qualification')
    selected_path = ROOT/'outputs/input_audit/selected_cases.json'
    end = time.monotonic()+6*3600
    while not selected_path.exists():
        if time.monotonic() > end:
            raise RuntimeError('Qualification did not complete within the finite wait')
        time.sleep(3)
    selected = read(selected_path)
    assert selected['status'] == 'FINITE_COHORT_COMPLETE'
    verify()
    # Read-only authentication confirmation; no login/credential/billing changes.
    auth = subprocess.run([shutil.which('codex') or 'codex', 'login', 'status'],
                          capture_output=True, text=True, timeout=15)
    assert auth.returncode == 0 and 'Logged in using ChatGPT' in auth.stdout+auth.stderr, \
        'Expected existing ChatGPT subscription authentication; no API-key fallback permitted'
    assert not os.environ.get('OPENAI_API_KEY') and not os.environ.get('CODEX_API_KEY')
    write(ROOT/'outputs/infrastructure/pre_evaluation_access.json',
          dict(utc=utc(), chatgpt_login_confirmed=True, api_key_fallback=False,
               scope='Authentication route only; not a billing invoice'), exclusive=True)
    module('campaign', 'evaluation_campaign.log')
    module('post_analysis', 'final_analysis.log')
    module('post_replay', 'replay.log')
    verify()
    status('preservation_audit')
    from .preservation import audit
    audit()
    replay = read(ROOT/'replay/audit.json')
    complete = read(ROOT/'outputs/evaluation/complete.json')
    assert complete['status'] == 'COMPLETE'
    if not selected['cases']:
        status('finite_cohort_finished_without_eligible_CAD',
               attempted=selected['attempted'], evaluated_episodes=0,
               study_question_answered=False, no_planner_success_rate_claim=True)
        return
    if replay['status'] != 'PASS':
        status('episodes_finished_replay_incomplete',
               cases=len(selected['cases']), episodes=len(complete['episodes']),
               replay_error_count=len(replay['errors']),
               raw_results_preserved=True)
        return
    handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                directory=str(ROOT))
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 8781), handler)
    status('finite_campaign_and_replay_verified_serving',
           cases=len(selected['cases']), episodes=len(complete['episodes']),
           url='http://127.0.0.1:8781/viewer/index.html',
           results='analysis/RESULTS.md', no_ppt_changes=True)
    server.serve_forever()


if __name__ == '__main__':
    try:
        main()
    except BaseException as exc:
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        status('pipeline_stopped_requires_inspection', error=repr(exc),
               traceback=traceback.format_exc(), no_automatic_episode_retry=True)
        raise
