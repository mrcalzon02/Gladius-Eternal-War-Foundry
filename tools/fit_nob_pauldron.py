from pathlib import Path
from datetime import datetime
import bpy,hashlib,json,shutil,sys
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'tools'));from nob_pauldron_liner import fit_inner_liner
D=R/'model-workbench/Ork-Nob-Crab-Claw';stamp=datetime.now().strftime('%Y%m%d-%H%M%S');report={}
def actions():
 return {a.name:hashlib.sha256(repr([(c.data_path,c.array_index,[tuple(k.co) for k in c.keyframe_points]) for l in a.layers for s in l.strips for b in s.channelbags for c in b.fcurves]).encode()).hexdigest() for a in bpy.data.actions}
def geo(o):return hashlib.sha256(repr(([tuple(v.co) for v in o.data.vertices],[tuple(p.vertices) for p in o.data.polygons],[(g.name) for g in o.vertex_groups],[tuple(x.uv) for uv in o.data.uv_layers for x in uv.data])).encode()).hexdigest()
for filename in ['Ork-Nob-Crab-Claw.blend','Nob-Animation-Work.blend']:
 path=D/filename;cp=D/'checkpoints'/('before-inner-liner-'+stamp+'-'+filename);shutil.copy2(path,cp);oldhash=hashlib.sha256(path.read_bytes()).hexdigest();bpy.ops.wm.open_mainfile(filepath=str(path));before=actions();unchanged={o.name:geo(o) for o in bpy.context.scene.objects if o.type=='MESH' and o.name!='Fitted hammered pauldron 1' and not o.name.startswith('Pauldron flush rivet 1')}
 fit_inner_liner(bpy.context.scene,bpy.data.objects['OrkBoy_rig'],bpy.data.objects['OrkBoy'].data.materials[0]);assert before==actions()
 assert all(geo(bpy.data.objects[n])==h for n,h in unchanged.items())
 bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(path));report[filename]={'before':oldhash,'after':hashlib.sha256(path.read_bytes()).hexdigest(),'all_actions_preserved':True,'all_other_meshes_uvs_and_groups_preserved':True,'checkpoint':str(cp)}
(D/'pauldron-fit-source.json').write_text(json.dumps(report,indent=2));print(report)
