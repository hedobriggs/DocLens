"""Create a fresh, credential-free frontend build context from tracked files only."""
from pathlib import Path
import shutil,subprocess,sys,tempfile
ROOT=Path(__file__).resolve().parents[2]
DEST=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(tempfile.mkdtemp(prefix='doclens-candidate-context-'))
if len(sys.argv)>1:DEST.mkdir(mode=0o700) # Refuse overwriting any existing directory.
for name in subprocess.check_output(['git','ls-files','frontend'],cwd=ROOT,text=True).splitlines():
 relative=Path(name).relative_to('frontend');source=ROOT/name
 if relative.name.startswith('.env') or relative.name=='Dockerfile':continue
 if source.is_symlink():raise RuntimeError('Refuse symlink in build input')
 target=DEST/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
shutil.copyfile(Path(__file__).parent/'Dockerfile.frontend',DEST/'Dockerfile')
print(DEST)
