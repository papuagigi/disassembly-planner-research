"""Final local source/data/evidence distribution, after scored runs and replay."""
import argparse
import importlib.metadata
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
from .common import ROOT,WORKSPACE,read,write,sha,utc

EXCLUDE={'.git','__pycache__','.venv','node_modules','.deps','.collision_deps','.conversion_deps',
         'deliverables','.codex-finalizer','.build'}

def copy_tree(source,target):
    for parent,dirs,names in os.walk(source,followlinks=False):
        dirs[:]=[d for d in dirs if d not in EXCLUDE and not (Path(parent)/d).is_symlink()]
        for name in names:
            p=Path(parent)/name
            if p.is_symlink() or p.suffix=='.pyc':continue
            dest=target/p.relative_to(source);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dest)

def main():
    assert (ROOT/'outputs/evaluation/complete.json').exists()
    assert read(ROOT/'replay/audit.json')['status']=='PASS'
    frozen=read(ROOT/'outputs/protocol/freeze.json')
    dist=ROOT/'deliverables';build=dist/'project_build';assert not build.exists(),'Use a new release directory; do not replace a reviewed bundle'
    build.mkdir(parents=True);copy_tree(ROOT,build/ROOT.name)
    # Excluding deliverables prevents recursive archives; the three final
    # human-facing outputs are copied explicitly for a complete handoff.
    for name in ['Disassembly_DocumentSkill_Presentation.pptx','Disassembly_DocumentSkill_Submission.pdf','speaker_notes_ko.md']:
        source=ROOT/'deliverables'/name
        if source.exists():
            target=build/ROOT.name/'deliverables'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    # Exact read-only compatibility sources from the freeze, preserving package
    # layout. Their old datasets/results are not required for the new replays.
    for name,expected in frozen['code_sha256'].items():
        p=Path(name);assert sha(p)==expected
        relative=p.relative_to(WORKSPACE);target=build/relative;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(p,target)
    for package in ['disassembly_planner_2d','disassembly_mujoco','disassembly_recovery','disassembly_learning_v1',
                    'disassembly_learning_v2','disassembly_learning_v3','disassembly_abc_v1','disassembly_abc_v2',
                    'disassembly_abc_v3','disassembly_abc_v4','disassembly_abc_v5','disassembly_hybrid','disassembly_real_v1',
                    'disassembly_real_v2','disassembly_real_v3']:
        source=WORKSPACE/package
        if not source.exists():continue
        for p in source.glob('*.py'):
            target=build/package/p.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
        for sub in ['planner2d']:
            for p in (source/sub).glob('*.py'):
                target=build/package/sub/p.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
    fixture=WORKSPACE/'disassembly_real_v3/tests/test_task_adapter.py'
    target=build/'disassembly_real_v3/tests/test_task_adapter.py';target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(fixture,target)
    for source in [WORKSPACE/'disassembly_real_v3/vendor/ASAP/LICENSE',ROOT/'references/upstream/aspire_LICENSE']:
        if source.exists():
            target=build/'THIRD_PARTY_NOTICES'/('ASAP_LICENSE' if source.name=='LICENSE' else source.name)
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    pins=[]
    for name in ['mujoco','numpy','scipy','trimesh','rtree','python-fcl']:
        try:pins.append(name+'=='+importlib.metadata.version(name))
        except importlib.metadata.PackageNotFoundError:pass
    (build/'requirements-replay.txt').write_text('\n'.join(pins)+'\n')
    readme='''# Disassembly document-skill final project

This bundle preserves the new study source, original/converted CAD, frozen S0/S1, raw trials, qualification/admission evidence, tables and exact offline replays. Old experiments are preserved in the original workspace; only read-only compatibility sources are copied here.

Start with disassembly_docskills_v1/STATUS.md, analysis/RESULTS.md, outputs/protocol/freeze.json and the signed metadata_parser_erratum.json. The admitted skill is a narrow API-schema repair, not a validated whole-search or nearest-ancestor strategy. Earlier rejected documents remain rejected.

Verified runtime: Python3.12 on the original macOS host. Frozen MuJoCo/geometry/native dependencies and source hashes are in protocol and conversion receipts. Native copied libraries can be platform-specific; a clean different-OS installation is not claimed verified. Install replay requirements in an isolated environment; use matching python-fcl/rtree native libraries as needed. Original mesh conversion additionally needs the exact CoACD settings/dependencies in the receipts. Official ASAP diagnostics require the pinned RedMax/ASAP build documented in references.

From this directory:

    python -B -m disassembly_docskills_v1.reproduce verify
    python -B -m disassembly_docskills_v1.reproduce unit
    python -B -m disassembly_docskills_v1.reproduce replay --arm A
    python -m http.server 8780 --bind 127.0.0.1 --directory disassembly_docskills_v1

Then open http://127.0.0.1:8780/viewer/index.html. Mesh paths and replay links are relative; the raw evidence's original absolute paths remain unchanged. Portable replay remaps only a working descriptor's case_path.

An optional NEW model episode requires the logged-in Codex CLI and consumes inference resources:

    python -B -m disassembly_docskills_v1.reproduce new-model-episode --arm B

It writes a separate reproduction directory and is never substituted for the recorded first episode. LLM samples may differ; seeds are not controlled. No robot control is included.

The original full phase drivers intentionally protect immutable results instead of silently rerunning/overwriting them. Refer to their source and phase receipts for clean regeneration in a separate study copy.
'''
    (build/'README.md').write_text(readme)
    files={str(p.relative_to(build)):sha(p) for p in build.rglob('*') if p.is_file()}
    write(build/'SOURCE_BUNDLE_MANIFEST.json',dict(created_utc=utc(),files=files,source_study=ROOT.name,
        model_seed_control=False,source_paths_preserved_in_raw_evidence=True))
    env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','PYTHONPATH':str(build)}
    for command in ['verify','unit','replay']:
        with (dist/('bundle_'+command+'.log')).open('x') as log:
            process=subprocess.run([sys.executable,'-B','-m','disassembly_docskills_v1.reproduce',command],
                cwd=build,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=600)
        assert process.returncode==0,('Standalone bundle verification failed',command)
    # This note is written only after the copied, isolated bundle passed all
    # three actual checks. It does not infer a clean different-OS installation.
    status_path=build/ROOT.name/'FINAL_STATUS.md'
    status_path.write_text(status_path.read_text()+'\n\n## Distribution verification completed\n\nThe copied standalone bundle passed relative source checksums,9 document/controller unit regressions and one exact offline scored replay on the original macOS host. No model was called. SOURCE_BUNDLE_MANIFEST.json binds the released bytes. A clean different-OS installation is not claimed. The local study has completed its fixed campaign, evidence replay and15-slide presentation/PDF QA; no new model experiment is pending.\n')
    # Include independently produced reproduction receipts in the released hash set.
    files={str(p.relative_to(build)):sha(p) for p in build.rglob('*') if p.is_file() and p.name!='SOURCE_BUNDLE_MANIFEST.json'}
    write(build/'SOURCE_BUNDLE_MANIFEST.json',dict(created_utc=utc(),files=files,source_study=ROOT.name,
        standalone_same_host_verify_unit_and_offline_replay='PASS',different_OS_clean_install_verified=False))
    archive=dist/'disassembly_document_skills_final_project.zip';assert not archive.exists()
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(build.rglob('*')):
            if p.is_file():z.write(p,str(Path('disassembly_final_project')/p.relative_to(build)))
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    write(dist/'project_release.json',dict(status='PASS',created_utc=utc(),archive=str(archive),archive_sha256=sha(archive),
        bytes=archive.stat().st_size,files=len(files),standalone_same_host=['source checksum','unit tests','one exact offline scored replay'],
        different_os_verified=False,raw_primary_results_unchanged=True))
    print('FINAL_PROJECT_RELEASE',archive,flush=True)

if __name__=='__main__':main()
