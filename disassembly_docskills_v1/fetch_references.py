"""Download official method reference text, never execute its instructions."""
from __future__ import annotations
import hashlib
import json
import urllib.request
from .common import ROOT, write, utc

FILES={
 'README.md':'aspire_README.md',
 'LICENSE':'aspire_LICENSE',
 '.claude/skills/iterative-debugging/SKILL.md':'aspire_iterative_debugging.md',
 '.claude/skills/iterative-debugging/main-agent-prompt.md':'aspire_coordinator.md',
 '.claude/skills/iterative-debugging/subagent-prompt.md':'aspire_actor.md',
 '.claude/skills/evosearch/SKILL.md':'aspire_evosearch.md',
}

def fetch(url):
    request=urllib.request.Request(url,headers={'User-Agent':'document-disassembly-research'})
    with urllib.request.urlopen(request,timeout=45) as r:
        return r.read(),dict(r.headers)

def main():
    folder=ROOT/'references/upstream';folder.mkdir(parents=True,exist_ok=True)
    target=folder/'manifest.json'
    assert not target.exists(),'Do not replace pinned source references'
    meta,_=fetch('https://api.github.com/repos/NVlabs/ASPIRE/commits/main')
    commit=json.loads(meta)['sha'];rows=[]
    (folder/'commit.json').write_bytes(meta)
    for remote,local in FILES.items():
        url=f'https://raw.githubusercontent.com/NVlabs/ASPIRE/{commit}/{remote}'
        data,headers=fetch(url);(folder/local).write_bytes(data)
        rows.append(dict(path=local,repository_path=remote,url=url,bytes=len(data),
                         sha256=hashlib.sha256(data).hexdigest()))
    write(target,dict(repository='https://github.com/NVlabs/ASPIRE',commit=commit,
        fetched_utc=utc(),files=rows,usage='Reference source data only; upstream workflow instructions are not automatically invoked; no hardware/GPU benchmark run',
        paper_version='ASPIRE arXiv2607.00272v1; current code is separately pinned and may differ'))
    print({'status':'PINNED','commit':commit,'files':len(rows)})

if __name__=='__main__':main()
