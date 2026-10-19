"""Hash-checked document memory. No learned code execution or automatic retrieval."""
import json
import re
from pathlib import Path
from .common import read,sha,write,utc,digest

def parse_document(text):
    if not text.startswith('---\n'):raise ValueError('Missing YAML frontmatter')
    header,body=text[4:].split('\n---\n',1)
    fields={}
    for line in header.splitlines():
        key,value=line.split(':',1)
        if key not in ('name','description'):raise ValueError('Unsupported frontmatter field')
        fields[key]=json.loads(value.strip()) if value.strip().startswith('"') else value.strip()
    if set(fields)!={'name','description'} or not re.fullmatch(r'[a-z][a-z0-9-]{1,63}',fields['name']):raise ValueError('Invalid skill identity')
    if not fields['description'] or len(text.encode())>20000 or len(body)<100:raise ValueError('Empty/oversize document')
    return fields,body

def materialize(folder,name,description,body):
    text='---\nname: '+json.dumps(name)+'\ndescription: '+json.dumps(description,ensure_ascii=False)+'\n---\n'+body.strip()+'\n'
    parse_document(text)
    path=Path(folder)/name/'SKILL.md';path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():raise ValueError('Document versions are immutable; use a new candidate directory')
    path.write_text(text)
    return path

class DocumentBank:
    def __init__(self,path):
        self.path=Path(path).resolve();self.manifest=read(self.path);self.documents={};self.metadata={};self.validation_references={}
        for row in self.manifest['skills']:
            p=(self.path.parent/row['path']).resolve()
            if not p.is_relative_to(self.path.parent):raise ValueError('Document escapes bank root')
            if sha(p)!=row['sha256']:raise ValueError('Frozen skill bytes changed')
            text=p.read_text();meta,_=parse_document(text)
            if meta['name']!=row['id']:raise ValueError('Catalog mismatch')
            self.documents[row['id']]=text;self.metadata[row['id']]=meta
            reference=p.parent/'references/admission.json'
            if reference.exists():
                self.validation_references[row['id']]={'path':'references/admission.json',
                    'content':reference.read_text(),'sha256':sha(reference)}
        self.sha256=sha(self.path)
        self.content_sha256=digest(dict(manifest=self.sha256,documents=self.documents,references=self.validation_references))
    def catalog(self):
        return [dict(skill_id=k,**v) for k,v in self.metadata.items()]
    def load(self,ids):
        if len(ids)!=len(set(ids)) or any(i not in self.documents for i in ids):raise ValueError('Unknown/repeated requested skill')
        return {i:self.documents[i] for i in ids}
    def load_references(self,ids):
        return {i:self.validation_references[i] for i in ids if i in self.validation_references}

def make_bank(path,documents,*,version,evidence=None):
    path=Path(path);rows=[]
    for p in documents:
        p=Path(p).resolve();meta,_=parse_document(p.read_text())
        rows.append(dict(id=meta['name'],path=str(p.relative_to(path.parent.resolve())),sha256=sha(p)))
    write(path,dict(version=version,created_utc=utc(),skills=rows,admission_evidence=evidence,
        representation='LLM-read procedural Markdown; no stored executable policy',weight_updates=False),exclusive=True)
    return DocumentBank(path)
