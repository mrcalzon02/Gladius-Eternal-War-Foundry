"""Dependency-free validation of the Grot integrated into the numeric mod tree."""
from pathlib import Path
import argparse,copy,hashlib,json,struct,xml.etree.ElementTree as ET
from native_gladius import read_mesh,read_animation

def file_hash(path):
 raw=path.read_bytes()
 if path.suffix.lower()=='.xml':raw=raw.replace(b'\r\n',b'\n').replace(b'\r',b'\n')
 return hashlib.sha256(raw).hexdigest()

def gameplay_signature(unit):
 unit=copy.deepcopy(unit)
 def node(n):return [n.tag,sorted(n.attrib.items()),(n.text or '').strip(),[node(c) for c in n if c.tag!='model']]
 return hashlib.sha256(json.dumps(node(unit),separators=(',',':')).encode()).hexdigest()

def validate(root):
 manifest=json.loads((root/'docs/grot/manifest.json').read_text());data=root/'3038342810/Data'
 for name,sha in manifest['runtime_files'].items():assert file_hash(root/name)==sha,name
 for name,sha in manifest['editable_sources'].items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==sha,name
 body=read_mesh((data/'Video/Meshes/Units/Foundry/GrotReplacement.msh').read_bytes());assert len(body['bones'])==19;weapons={}
 for name,baseline in manifest['units'].items():
  unit=ET.parse(root/name).getroot();assert gameplay_signature(unit)==baseline['gameplay_signature'],name
  model=unit.find('model/unit');assert model.get('mesh')=='Units/Foundry/GrotReplacement';assert model.get('scale')=='1 1 1'
  for w in unit.findall('weapons/weapon/model/*'):
   if w.get('mesh'):
    mesh=read_mesh((data/('Video/Meshes/'+w.get('mesh')+'.msh')).read_bytes());assert w.get('bone') in body['bones'];weapons[w.get('mesh')]=mesh['triangles']
    if w.get('muzzleBone'):assert w.get('muzzleBone') in mesh['bones']
  for n in unit.iter():
   for key,value in n.attrib.items():
    if 'animation' in key.lower() and value.startswith('Units/'):
     a=read_animation((data/('Video/Animations/'+value+'.anm')).read_bytes());assert a['bones']==body['bones'] and a['fps']==24
 for f in (data/'Video/Animations/Units/Foundry').glob('GrotReplacement*.anm'):assert read_animation(f.read_bytes())['bones']==body['bones']
 for role in ['Diffuse','Normal','SIC']:
  raw=(data/f'Video/Textures/Units/Foundry/GrotReplacement{role}.dds').read_bytes();assert raw[:4]==b'DDS ' and struct.unpack_from('<II',raw,12)==(1024,1024)
 assert body['triangles']+sum(weapons.values())==1540
 verification=json.loads((root/'docs/grot/native-verification.json').read_text());assert not verification['failures'] and verification['maximum_world_vertex_error']<.002
 return {'status':'passed','units':len(manifest['units']),'triangles':1540,'bones':19,'native_roundtrip_poses':verification['sampled_poses'],'gameplay_preserved':True}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--repository',type=Path,default=Path(__file__).resolve().parents[1]);args=p.parse_args();print(json.dumps(validate(args.repository),indent=2))
