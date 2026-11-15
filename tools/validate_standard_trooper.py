"""Check the approved trooper's actual runtime wiring inside Penal Legion."""
from pathlib import Path
import argparse,hashlib,json,struct,xml.etree.ElementTree as E
from native_gladius import read_mesh

def digest(path):
 raw=path.read_bytes()
 if path.suffix=='.xml':raw=raw.replace(b'\r\n',b'\n')
 return hashlib.sha256(raw).hexdigest()

def gameplay(root):
 return [root.tag,sorted(root.attrib.items()),(root.text or '').strip(),[gameplay(c) for c in root if c.tag!='model']]

def validate(repo):
 manifest=json.loads((repo/'docs/standard-trooper/runtime-manifest.json').read_text(encoding='utf-8'))
 for rel,expected in manifest['files'].items():assert digest(repo/rel)==expected,rel
 data=repo/'2525618649/Data'
 unit=E.parse(data/'World/Units/AstraMilitarum/Guardsman.xml').getroot();model=unit.find('model/unit')
 assert model.get('mesh')==model.get('material')=='Units/Foundry/PenalStandardTrooper'
 assert model.get('idleAnimation')=='Units/AstraMilitarum/GuardsmanIdle' and model.get('idleAnimationCount')=='3'
 assert model.get('scale')=='0.8 0.8 0.8'
 assert hashlib.sha256(json.dumps(gameplay(unit),separators=(',',':')).encode()).hexdigest()==manifest['gameplay_signature']
 mesh=read_mesh((data/'Video/Meshes/Units/Foundry/PenalStandardTrooper.msh').read_bytes())
 assert mesh['triangles']==1090 and len(mesh['bones'])==28
 for role in ('Diffuse','Normal','SIC'):
  raw=(data/('Video/Textures/Units/Foundry/PenalStandardTrooper'+role+'.dds')).read_bytes()
  assert raw[:4]==b'DDS ' and raw[84:88]==b'DXT5' and struct.unpack_from('<II',raw,12)==(1024,1024)
 source=repo/'model-workbench/Penal-Legion-Standard-Trooper/Standard-Trooper.blend'
 assert digest(source)==manifest['source_sha256']
 verification=json.loads((repo/'docs/standard-trooper/native-verification.json').read_text(encoding='utf-8'))
 assert not verification['failures'] and verification['sampled_poses']==33
 assert verification['maximum_world_vertex_error']<.002
 print('Standard trooper passed: existing Guardsman wired to approved model; 1090 body triangles; 28 bones; 33 native poses; gameplay unchanged.')

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--repository',type=Path,default=Path(__file__).resolve().parents[1]);validate(parser.parse_args().repository)
