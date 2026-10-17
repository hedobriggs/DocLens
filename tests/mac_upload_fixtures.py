from pathlib import Path
import fitz,json,time,os,hashlib
root=Path(os.environ.get('DOCLENS_FREEZE_FIXTURES','/tmp/doclens-freeze-fixtures'));root.mkdir(parents=True,exist_ok=True);start=time.perf_counter()
with fitz.open() as d:
 d.new_page().insert_text((30,40),'Synthetic padded 28 MiB upload with one text page.')
 data=d.tobytes();(root/'padded-28mib.pdf').write_bytes(data+b' '*(28*1024*1024-len(data)))
with fitz.open() as d:
 text='\n'.join(('Clause %03d. '%i+'Synthetic property covenant and evidence wording. '*3)[:150] for i in range(150))
 count=0
 while True:
  for _ in range(50):
   page=d.new_page();page.insert_text((20,20),text,fontsize=3)
   for xref in page.get_contents():d.update_stream(xref,d.xref_stream(xref),compress=False)
   count+=1
  data=d.tobytes(deflate=False)
  if len(data)>=28*1024*1024:break
 (root/'text-heavy-28mib.pdf').write_bytes(data)
with fitz.open() as d:
 text='\n'.join(('Clause %02d. '%i+'Synthetic property wording supporting evidence and contractual obligations. '*2)[:120] for i in range(45))
 for i in range(40):d.new_page().insert_text((24,24),text,fontsize=5)
 (root/'text-heavy-40pages.pdf').write_bytes(d.tobytes(deflate=False))
info={}
for p in root.glob('*.pdf'):
 with fitz.open(p) as d:info[p.name]={'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'pages':len(d),'extracted_characters':sum(len(page.get_text()) for page in d)}
(root/'fixtures.json').write_text(json.dumps(info,indent=2)+'\n');print(json.dumps(info));print('generation seconds',time.perf_counter()-start)
