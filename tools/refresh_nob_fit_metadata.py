import bpy,json,hashlib
from pathlib import Path
D=Path(__file__).resolve().parents[1]/'model-workbench/Ork-Nob-Crab-Claw';bpy.ops.wm.open_mainfile(filepath=str(D/'Ork-Nob-Crab-Claw.blend'))
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH'];count=lambda o:sum(len(p.vertices)-2 for p in o.data.polygons)
p=D/'build.json';d=json.loads(p.read_text());d['body_triangles']=count(bpy.data.objects['OrkBoy']);d['added_triangles']=sum(count(o) for o in meshes if o.name not in ['OrkBoy','Slugga']);d['added_objects']=len([o for o in meshes if o.name not in ['OrkBoy','Slugga']]);d['claw_shoulder_fit']='Native pauldron preserved; extra projecting shell replaced by concealed Torso-weighted inner liner';p.write_text(json.dumps(d,indent=2))
p=D/'animation-build.json';d=json.loads(p.read_text());d['source_sha256']=hashlib.sha256((D/'Ork-Nob-Crab-Claw.blend').read_bytes()).hexdigest();d['working_sha256']=hashlib.sha256((D/'Nob-Animation-Work.blend').read_bytes()).hexdigest();d['pauldron_refinement']='Claw-side inner liner fitted without changing any action data';p.write_text(json.dumps(d,indent=2))
