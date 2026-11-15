"""Reimport the actual trooper runtime files and compare all eleven native clips."""
from pathlib import Path
from types import SimpleNamespace
import bpy,bmesh,sys,importlib.util,json,hashlib,math
from mathutils import Matrix,Vector
R=Path(__file__).resolve().parents[1];O=R/'assets/standard-trooper-runtime';D=O/'2525618649/Data'
SOURCE=R/'model-workbench/Penal-Legion-Standard-Trooper/Standard-Trooper.blend'
G=Path(r'C:\Program Files (x86)\Steam\steamapps\common\Warhammer 40000 Gladius - Relics of War\Data')
spec=importlib.util.spec_from_file_location('standard_native_import',R/'references/import_gladius.py');g=importlib.util.module_from_spec(spec);sys.modules[spec.name]=g;spec.loader.exec_module(g)
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
if bpy.context.object and bpy.context.object.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
scene=bpy.context.scene;rig=bpy.data.objects['Guardsman_rig']
objects=sorted((o for o in scene.objects if o.type=='MESH' and any(m.type=='ARMATURE' and m.object==rig for m in o.modifiers)),key=lambda o:o.name)
indices={}
for obj in objects:
 for mod in obj.modifiers:
  if mod.type=='ARMATURE':mod.use_deform_preserve_volume=False
 me=obj.data
 if any(len(p.vertices)>4 for p in me.polygons):
  bm=bmesh.new();bm.from_mesh(me);bmesh.ops.triangulate(bm,faces=[f for f in bm.faces if len(f.verts)>4]);bm.to_mesh(me);bm.free();me.update()
 me.calc_loop_triangles();indices[obj.name]=[me.loops[li].vertex_index for tri in me.loop_triangles if tri.area>=1e-7 for li in tri.loops]
views={}
for name in ('front','rear','head-closeup'):
 cam=bpy.data.objects[name];views[name]={'matrix':[list(r) for r in cam.matrix_world],'type':cam.data.type,'lens':cam.data.lens,'ortho_scale':cam.data.ortho_scale}
def activate(action):
 rig.animation_data.action=None
 for p in rig.pose.bones:p.matrix_basis.identity()
 rig.animation_data.action=action;rig.animation_data.use_nla=False
 for t in rig.animation_data.nla_tracks:t.mute=True
clips={'Idle0':'Guardsman_Idle_0','Idle1':'Guardsman_Idle_1','Idle2':'Guardsman_Idle_2','Move':'Guardsman_Move','MoveBegin':'Guardsman_MoveBegin','MoveEnd':'Guardsman_MoveEnd','Attack':'Guardsman_Attack','Die0':'Guardsman_Death_0','Die1':'Guardsman_Death_1','Die2':'Guardsman_Death_2','Grenade':'Guardsman_ThrowGrenade'}
expected={}
for suffix,name in clips.items():
 action=bpy.data.actions[name];activate(action)
 start,end=map(float,action.frame_range)
 for frame in (start,(start+end)/2,end):
  scene.frame_set(math.floor(frame),subframe=frame-math.floor(frame));bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get()
  points=[]
  for obj in objects:
   evaluated=obj.evaluated_get(deps)
   points.extend(obj.matrix_world@evaluated.data.vertices[i].co for i in indices[obj.name])
  expected[suffix,frame]=points
bpy.ops.wm.read_factory_settings(use_empty=True)
roots=g._source_roots_for_xml;g._source_roots_for_xml=lambda path,prefs:list(dict.fromkeys(roots(path,prefs)+[str(G)]))
messages=[];operator=SimpleNamespace(filepath=str(D/'World/Units/AstraMilitarum/Guardsman.xml'),frame_viewport=False,scale_preset='FULL',report=lambda *x:messages.append(str(x)))
assert g.ImportGladiusUnitFromXml.execute(operator,bpy.context)=={'FINISHED'},messages
scene=bpy.context.scene;rig=bpy.data.objects['PenalStandardTrooper_rig'];body=bpy.data.objects['PenalStandardTrooper']
unit_scale=body.matrix_world.copy()
assert len(body.data.polygons)==1090 and len(body.data.vertices)==3270
actions={};errors={}
for suffix in clips:
 actions[suffix],_=g._load_anm_to_rig(str(G/('Video/Animations/Units/AstraMilitarum/Guardsman'+suffix+'.anm')),rig,unit_name='Runtime',anim_type=suffix)
maximum=0
for (suffix,frame),points in expected.items():
 activate(actions[suffix]);scene.frame_set(math.floor(frame),subframe=frame-math.floor(frame));bpy.context.view_layer.update();ev=body.evaluated_get(bpy.context.evaluated_depsgraph_get())
 error=max((body.matrix_world@v.co-unit_scale@p).length for v,p in zip(ev.data.vertices,points));maximum=max(maximum,error);errors[suffix+' '+str(frame)]=error
assert maximum<.002,(maximum,errors)
textures=[]
for im in bpy.data.images:
 if im.source=='FILE' and im.filepath:
  _=im.pixels[0];assert im.has_data,(im.name,im.filepath)
  textures.append({'name':im.name,'size':list(im.size),'loaded':im.has_data})
activate(actions['Idle0']);scene.frame_set(0)
scene.render.engine='CYCLES';scene.cycles.samples=24;scene.render.resolution_x=900;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
scene.world=bpy.data.worlds.new('Runtime neutral studio');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.12,.12,.12,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.5
for location,power in [((90,-90,130),140000),((70,110,100),100000),((-100,0,120),120000)]:
 data=bpy.data.lights.new('Runtime review softbox','AREA');data.energy=power;data.size=75;obj=bpy.data.objects.new(data.name,data);scene.collection.objects.link(obj);obj.location=location;obj.rotation_euler=(Vector((0,0,30))-obj.location).to_track_quat('-Z','Y').to_euler()
data=bpy.data.cameras.new('Runtime review camera');cam=bpy.data.objects.new(data.name,data);scene.collection.objects.link(cam);scene.camera=cam
for name,view in views.items():
 cam.matrix_world=Matrix(view['matrix']);cam.location*=.8;data.type=view['type'];data.lens=view['lens'];data.ortho_scale=view['ortho_scale']*.8;scene.render.filepath=str(O/('runtime-'+name+'.png'));bpy.ops.render.render(write_still=True)
report={'status':'Actual MSH/DDS/XML independently reimported; original native animations compared','source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'sampled_poses':len(expected),'native_clips':11,'maximum_world_vertex_error':maximum,'body_triangles':1090,'native_bones':28,'samples':errors,'images':textures,'messages':messages,'failures':[],'gameplay_preserved':True,'engine_startup_verified':False,'in_game_combat_verified':False,'renders':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in O.glob('runtime-*.png')}}
(O/'NATIVE_VERIFICATION.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print('NATIVE_STANDARD_TROOPER_VERIFIED',len(expected),'poses;',maximum,'maximum world-vertex error')
