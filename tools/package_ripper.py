from pathlib import Path
import sys,json,hashlib,os
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'tools/_resource_deps'))
from PIL import Image
D=Path(os.environ.get('RIPPER_STAGE_DIR',R/'model-workbench/Ripper/low-poly'));OUT=Path(os.environ.get('RIPPER_NATIVE_DIR',R/'game-ready/Foundry Ripper'));DATA=OUT/'Data';textures=DATA/'Video/Textures/Units/Foundry'
for role in ['Diffuse','Normal','SIC']:
 im=Image.open(D/('Ripper'+role+'.png')).convert('RGBA')
 im.save(textures/('Ripper'+role+'.dds'))
 with Image.open(textures/('Ripper'+role+'.dds')) as check:assert check.size==(512,512)
manifest={'asset':'Foundry Ripper','source_author':'minipainting40k','source_url':'https://cults3d.com/en/3d-model/game/chompy-xeno-bugs','source_file':'User supplied One_Monchy_boi_for_posing.blend','source_license_as_displayed':'CULTS PU; source listing also displays No AI','derivative_work':'Low triangle retopology, new tail geometry/teeth, new texture atlas, unified rig and new animation clips','distribution_status':'Local private build; no publication or license clearance claimed','triangles':json.loads((OUT/'EXPORT.json').read_text())['mesh']['triangles'],'workshop_dependency':'2525618729','files':{p.relative_to(OUT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in DATA.rglob('*') if p.is_file()}}
(OUT/'MANIFEST.json').write_text(json.dumps(manifest,indent=2));print('RIPPER_PACKAGED',len(manifest['files']))
