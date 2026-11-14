"""Independently reimport actual MSH/ANM/DDS unit assets and compare deformation."""
from pathlib import Path
from types import SimpleNamespace
import bpy,json,sys,math,hashlib,importlib.util
from mathutils import Vector
from mathutils.kdtree import KDTree
R=Path(__file__).resolve().parents[1];D=R/'model-workbench/Grot-Sneak';OUT=R/'game-ready/Foundry Grot Replacement';DATA=OUT/'Data';GAME=Path(r'C:/Program Files (x86)/Steam/steamapps/common/Warhammer 40000 Gladius - Relics of War/Data')
spec=importlib.util.spec_from_file_location('grot_native_import',R/'references/import_gladius.py');g=importlib.util.module_from_spec(spec);sys.modules[spec.name]=g;spec.loader.exec_module(g)
bpy.ops.wm.open_mainfile(filepath=str(D/'Grot-Animation-Work.blend'));scene=bpy.context.scene;rig=bpy.data.objects['Grot_Animation_rig'];objs=[o for o in scene.objects if o.type=='MESH' and not o.hide_render];weapons={'Grot retained slugga':'GrotPistol','Grot narrow shank blade':'GrotShank','Grot shank bound handle':'GrotShank'};expected={}
def activate(rig,action):
 rig.animation_data.action=None;rig.animation_data.use_nla=False
 for t in rig.animation_data.nla_tracks:t.mute=True
 for p in rig.pose.bones:p.matrix_basis.identity()
 rig.animation_data.action=action
def positions(o):
 ev=o.evaluated_get(bpy.context.evaluated_depsgraph_get());return [o.matrix_world@v.co for v in ev.data.vertices]
for suffix,label,frames in [('Idle','Idle',[1,13,49]),('Move','Sneak',[1,13,25,37,49]),('Run','Run',[1,7,13,19,25]),('Ranged','Pistol fire',[1,13,17,23,29,49]),('Melee','Shank stab',[1,10,17,28,41]),('Snarl','Snarl',[1,9,17,33]),('Hit','Hit reaction',[1,6,25]),('Die','Death',[1,17,33,49])]:
 activate(rig,bpy.data.actions['Grot - '+label])
 for frame in frames:
  scene.frame_set(frame);bpy.context.view_layer.update();pts={'body':[],'GrotPistol':[],'GrotShank':[]}
  for o in objs:pts[weapons.get(o.name,'body')].extend(positions(o))
  expected[suffix,frame]=pts
bpy.ops.wm.read_factory_settings(use_empty=True);original=g._source_roots_for_xml;g._source_roots_for_xml=lambda path,prefs:list(dict.fromkeys(original(path,prefs)+[str(GAME)]));messages=[]
op=SimpleNamespace(filepath=str(DATA/'World/Units/Orks/Grotz.xml'),frame_viewport=False,scale_preset='FULL',report=lambda level,msg:messages.append([sorted(level),msg]))
assert g.ImportGladiusUnitFromXml.execute(op,bpy.context)=={'FINISHED'},messages
scene=bpy.context.scene;scene.render.fps=24;rig=bpy.data.objects['GrotReplacement_rig'];runtime={'body':bpy.data.objects['GrotReplacement'],'GrotPistol':bpy.data.objects['GrotPistol'],'GrotShank':bpy.data.objects['GrotShank']};actions={}
for suffix in set(s for s,f in expected):actions[suffix]=g._load_anm_to_rig(str(DATA/('Video/Animations/Units/Foundry/GrotReplacement'+suffix+'.anm')),rig,unit_name='Native Grot',anim_type=suffix)[0]
errors={};fail=[]
for (suffix,frame),reference in expected.items():
 activate(rig,actions[suffix]);scene.frame_set(frame-1);bpy.context.view_layer.update();sample={}
 for name,o in runtime.items():
  tree=KDTree(len(reference[name]))
  for i,p in enumerate(reference[name]):tree.insert(p,i)
  tree.balance();sample[name]=max(tree.find(p)[2] for p in positions(o))
 if max(sample.values())>.002:fail.append('Native deformation mismatch '+suffix+' '+str(frame))
 errors[suffix+' '+str(frame)]=sample
triangles=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in runtime.values())
if triangles!=1540:fail.append('Native triangle count')
images=[]
for im in bpy.data.images:
 if im.source=='FILE' and im.users:
  _=im.pixels[0];images.append({'name':im.name,'readable':im.has_data,'size':list(im.size)})
  if not im.has_data:fail.append('Missing native texture '+im.name)
# Render actual native assets, including an attack pose and the regular Grot bind appearance.
scene.world=bpy.data.worlds.new('Native Grot studio');scene.world.color=(.18,.18,.18);scene.render.engine='CYCLES';scene.cycles.samples=12;scene.render.resolution_x=800;scene.render.resolution_y=800
focus=Vector((4,0,12));camdata=bpy.data.cameras.new('Native Grot camera');cam=bpy.data.objects.new(camdata.name,camdata);scene.collection.objects.link(cam);camdata.type='ORTHO';camdata.ortho_scale=40;cam.location=focus+Vector((70,-110,35));cam.rotation_euler=(focus-cam.location).to_track_quat('-Z','Y').to_euler();scene.camera=cam
for point,energy in [((30,-45,65),70000),((-30,-10,35),35000),((10,35,45),45000)]:
 data=bpy.data.lights.new('Native Grot softbox','AREA');data.energy=energy;data.size=40;o=bpy.data.objects.new(data.name,data);scene.collection.objects.link(o);o.location=point;o.rotation_euler=(focus-o.location).to_track_quat('-Z','Y').to_euler()
for suffix,frame in [('Idle',1),('Ranged',17),('Melee',17)]:
 activate(rig,actions[suffix]);scene.frame_set(frame-1);scene.render.filepath=str(OUT/('native-'+suffix+'.png'));bpy.ops.render.render(write_still=True)
report={'status':'Native assets independently reimported','failures':fail,'sampled_poses':len(expected),'total_triangles':triangles,'maximum_world_vertex_error':max(max(v.values()) for v in errors.values()),'samples':errors,'textures':images,'messages':messages,'source_sha256':hashlib.sha256((D/'Grot-Animation-Work.blend').read_bytes()).hexdigest(),'actual_game_combat_tested':False}
(OUT/'NATIVE_VERIFICATION.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k not in ['samples','messages']},indent=2))
if fail:raise RuntimeError(fail)
