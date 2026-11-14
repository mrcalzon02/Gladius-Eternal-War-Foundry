"""Reimport the built MSH/ANM/DDS package and compare actual deformations."""
import bpy,bmesh,json,math,sys,hashlib,importlib.util,os
from pathlib import Path
from types import SimpleNamespace
from mathutils import Vector
R=Path(__file__).resolve().parents[1];D=Path(os.environ.get('RIPPER_STAGE_DIR',R/'model-workbench/Ripper/low-poly'));OUT=Path(os.environ.get('RIPPER_NATIVE_DIR',R/'game-ready/Foundry Ripper'));DATA=OUT/'Data'
GAME=Path('C:/Program Files (x86)/Steam/steamapps/common/Warhammer 40000 Gladius - Relics of War/Data')
SOURCE=D/'Ripper-LowPoly.blend';bpy.ops.wm.open_mainfile(filepath=str(SOURCE),use_scripts=False)
scene=bpy.context.scene;rig=bpy.data.objects['Ripper Rig'];body=bpy.data.objects['Ripper'];fail=[]
bm=bmesh.new();bm.from_mesh(body.data);bmesh.ops.triangulate(bm,faces=[f for f in bm.faces if len(f.verts)>4]);bm.to_mesh(body.data);bm.free();body.data.update();body.data.calc_loop_triangles()
indices=[body.data.loops[li].vertex_index for tri in body.data.loop_triangles for li in tri.loops]
source_triangles=len(indices)//3
rest_ground=min(v.co.z for v in body.data.vertices)
if abs(rest_ground)>.001:fail.append('Rest surface is not grounded at Z=0')
if len(indices)//3>450:fail.append('Triangle budget exceeded')
for v in body.data.vertices:
 inf=[g for g in v.groups if g.weight>1e-6]
 if not 1<=len(inf)<=4 or abs(sum(g.weight for g in inf)-1)>1e-4:fail.append('Invalid influence normalization')
 if any(body.vertex_groups[g.group].name not in rig.data.bones for g in inf):fail.append('Unbound deform group')
if any(p.area<1e-9 for p in body.data.polygons):fail.append('Degenerate source face')
if any(not all(math.isfinite(c) for c in v.co) for v in body.data.vertices):fail.append('Nonfinite source coordinate')
if any(not -.001<=c<=1.001 for uv in body.data.uv_layers.active.data for c in uv.uv):fail.append('UV outside atlas')
images=[i for i in bpy.data.images if i.name.startswith('Ripper ') and i.type=='IMAGE']
for im in images:
 _=im.pixels[0]
 if not im.packed_file or not im.has_data:fail.append('Unpacked/unreadable source image '+im.name)
source_image_names=[i.name for i in images]
bm=bmesh.new();bm.from_mesh(body.data);seen=set();components=[]
for v in bm.verts:
 if v in seen:continue
 comp={v};seen.add(v);stack=[v]
 while stack:
  for e in stack.pop().link_edges:
   for other in e.verts:
    if other not in seen:seen.add(other);comp.add(other);stack.append(other)
 edges=set(e for v in comp for e in v.link_edges);faces=set(f for v in comp for f in v.link_faces);volume=0
 for f in faces:
  vs=[v.co for v in f.verts]
  for i in range(1,len(vs)-1):volume+=vs[0].dot(vs[i].cross(vs[i+1]))/6
 closed=all(e.is_manifold for e in edges)
 if closed and volume<-.000001:fail.append('Inward-facing closed shell')
 components.append({'vertices':len(comp),'nonmanifold_edges':sum(not e.is_manifold for e in edges),'signed_volume':volume if closed else None})
bm.free()
core=max(components,key=lambda c:c['vertices'])
if core['nonmanifold_edges']:fail.append('Organic body/tail surface is open')
tooth_root=body.data.attributes.get('Ripper tooth root');tooth_face=body.data.attributes.get('Ripper tooth id');tooth_tip=body.data.attributes.get('Ripper tooth tip')
if not all([tooth_root,tooth_face,tooth_tip]):raise RuntimeError('Missing connected tooth attachment metadata')
root_vertices={}
for v in body.data.vertices:
 n=tooth_root.data[v.index].value
 if n:root_vertices.setdefault(n,[]).append(v.index)
if len(root_vertices)!=6:fail.append('Expected six integrated gum-root teeth')
for n,verts in root_vertices.items():
 if len(verts)!=3:fail.append('Tooth root must have three shared gum vertices')
 for index in verts:
  incident=[p for p in body.data.polygons if index in p.vertices]
  if not any(tooth_face.data[p.index].value==n for p in incident) or not any(tooth_face.data[p.index].value==0 for p in incident):fail.append('Detached tooth root')
group_totals={g.name:sum(w.weight for v in body.data.vertices for w in v.groups if w.group==g.index) for g in body.vertex_groups}
for name in ['Head','Jaw']+[side+f'Leg{i}.Upper' for side in ['L','R'] for i in [1,2,3]]:
 if group_totals.get(name,0)<.1:fail.append('Missing surface deformation weights '+name)
native_root_copies={index:[i for i,v in enumerate(indices) if v==index] for roots in root_vertices.values() for index in roots}
def activate(rig,action):
 rig.animation_data_create();rig.animation_data.action=None
 for p in rig.pose.bones:p.matrix_basis.identity()
 rig.animation_data.action=action;rig.animation_data.use_nla=False
 for t in rig.animation_data.nla_tracks:t.mute=True
expected={}
for suffix,frames in [('Idle',[1,17,33,49]),('Move',[1,9,17,25]),('Melee',[1,9,13,21]),('Die',[1,13,25,37])]:
 activate(rig,bpy.data.actions['Ripper '+suffix])
 for frame in frames:
  scene.frame_set(frame);bpy.context.view_layer.update();ev=body.evaluated_get(bpy.context.evaluated_depsgraph_get())
  expected[suffix,frame]={'positions':[body.matrix_world@ev.data.vertices[i].co for i in indices],'bones':{b.name:b.matrix.copy() for b in rig.pose.bones}}
spec=importlib.util.spec_from_file_location('ripper_native_reimport',R/'references/import_gladius.py');g=importlib.util.module_from_spec(spec);sys.modules[spec.name]=g;spec.loader.exec_module(g)
bpy.ops.wm.read_factory_settings(use_empty=True)
original_roots=g._source_roots_for_xml;g._source_roots_for_xml=lambda path,prefs:list(dict.fromkeys(original_roots(path,prefs)+[str(GAME)]))
messages=[];op=SimpleNamespace(filepath=str(DATA/'World/Units/Tyranids/Ripperswarm.xml'),frame_viewport=False,scale_preset='FULL',report=lambda level,msg:messages.append([sorted(level),msg]))
assert g.ImportGladiusUnitFromXml.execute(op,bpy.context)=={'FINISHED'},messages
scene=bpy.context.scene;body=bpy.data.objects['Ripper'];rig=bpy.data.objects['Ripper_rig'];actions={}
for suffix in ['Idle','Move','Melee','Die']:
 action,_=g._load_anm_to_rig(str(DATA/f'Video/Animations/Units/Foundry/Ripper{suffix}.anm'),rig,unit_name='Ripper export',anim_type=suffix);actions[suffix]=action
errors={};maxvertex=maxbone=max_tooth_seam=0
for (suffix,frame),wanted in expected.items():
 activate(rig,actions[suffix]);scene.frame_set(frame-1);bpy.context.view_layer.update();ev=body.evaluated_get(bpy.context.evaluated_depsgraph_get())
 if len(ev.data.vertices)!=len(wanted['positions']):raise RuntimeError('Native vertex table does not match source triangle stream')
 vertex=max((body.matrix_world@v.co-p).length for v,p in zip(ev.data.vertices,wanted['positions']))
 for copies in native_root_copies.values():
  p=ev.data.vertices[copies[0]].co
  max_tooth_seam=max(max_tooth_seam,max((ev.data.vertices[i].co-p).length for i in copies))
 bone=max(abs(rig.pose.bones[n].matrix[r][c]-m[r][c]) for n,m in wanted['bones'].items() for r in range(4) for c in range(4))
 maxvertex=max(maxvertex,vertex);maxbone=max(maxbone,bone);errors[suffix+' '+str(frame)]={'vertex_error':vertex,'bone_matrix_error':bone}
if maxvertex>.002:fail.append('Native deformation mismatch')
if maxbone>.0002:fail.append('Native bone matrix mismatch')
if max_tooth_seam>.00001:fail.append('Tooth/gum seam opens in native animation')
runtimeimages=[i for i in bpy.data.images if i.source=='FILE' and i.filepath]
for im in runtimeimages:
 if not len(im.pixels):fail.append('Unreadable native DDS '+im.name)
runtime_image_names=[i.name for i in runtimeimages]
points=[body.matrix_world@v.co for v in body.data.vertices];focus=Vector([(min(p[i] for p in points)+max(p[i] for p in points))/2 for i in range(3)]);size=max(max(p[i] for p in points)-min(p[i] for p in points) for i in range(3))
scene.world=bpy.data.worlds.new('Native review world');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.12,.14,.18,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.4
for name,offset,power in [('Key',(1,-1,2),35),('Fill',(-1,-.3,1),20),('Rim',(.4,1,1.3),30)]:
 data=bpy.data.lights.new(name,'AREA');data.energy=power*size*size;data.size=size*1.3;o=bpy.data.objects.new(name,data);scene.collection.objects.link(o);o.location=focus+Vector(offset)*size;o.rotation_euler=(focus-o.location).to_track_quat('-Z','Y').to_euler()
data=bpy.data.cameras.new('Actual native export review');cam=bpy.data.objects.new('Actual native export review',data);scene.collection.objects.link(cam);scene.camera=cam;data.type='ORTHO';data.ortho_scale=size*1.25
scene.render.engine='CYCLES';scene.cycles.samples=48;scene.cycles.use_denoising=True;scene.render.resolution_x=1100;scene.render.resolution_y=850;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='AgX'
for name,suffix,frame,offset in [('native-front','Idle',0,(1,-1,.7)),('native-rear','Idle',0,(-1,1,.6)),('native-side','Idle',0,(.1,-1,.2)),('native-crawl','Move',8,(1,-1,.7)),('native-bite','Melee',12,(1,-1,.7)),('native-death','Die',24,(1,-1,.7))]:
 activate(rig,actions[suffix]);scene.frame_set(frame);cam.location=focus+Vector(offset)*size*2;cam.rotation_euler=(focus-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(D/(name+'.png'));bpy.ops.render.render(write_still=True)
for name,suffix,frame,offset in [('native-mouth-rest','Idle',0,(9,-7,3)),('native-mouth-bite','Melee',12,(9,-7,3)),('native-mouth-side','Idle',0,(0,-10,1))]:
 activate(rig,actions[suffix]);scene.frame_set(frame);close=Vector((2,0,4.5));cam.data.ortho_scale=8.5;cam.location=close+Vector(offset);cam.rotation_euler=(close-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(D/(name+'.png'));bpy.ops.render.render(write_still=True)
cam.data.ortho_scale=size*1.25;cam.location=focus+Vector((1,-1,.7))*size*2;cam.rotation_euler=(focus-cam.location).to_track_quat('-Z','Y').to_euler()
clay=bpy.data.materials.new('Actual mesh clay');clay.use_nodes=True;clay.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(.4,.4,.4,1);scene.view_layers[0].material_override=clay
activate(rig,actions['Idle']);scene.frame_set(0);scene.render.filepath=str(D/'native-clay.png');bpy.ops.render.render(write_still=True);scene.view_layers[0].material_override=None
scene.render.resolution_x=160;scene.render.resolution_y=124;scene.render.filepath=str(D/'gameplay-scale.png');bpy.ops.render.render(write_still=True)
source_check={'packed_images':source_image_names,'rest_ground_z':rest_ground,'components':components,'core':core,'intentional_eye_surface_inlays':4,'connected_teeth':len(root_vertices),'shared_gum_root_vertices':18,'native_tooth_gum_seam_gap':max_tooth_seam,'deform_group_totals':group_totals}
# Independently inspect the GLB, including embedded normal/color maps and animation library.
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=str(D/'Ripper-LowPoly.glb'));bpy.context.view_layer.update()
glbmeshes=[o for o in bpy.context.scene.objects if o.type=='MESH' and any(m.type=='ARMATURE' for m in o.modifiers)]
glbtris=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in glbmeshes);glbactions=[a.name for a in bpy.data.actions]
glbchannels=[]
if len(glbmeshes)!=1 or glbtris!=source_triangles:fail.append('GLB topology mismatch')
if len(glbactions)<4:fail.append('GLB animation clips missing')
for o in glbmeshes:
 for mat in o.data.materials:
  bs=next(n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED')
  channels={channel:bs.inputs[channel].is_linked for channel in ['Base Color','Normal','Roughness']};glbchannels.append(channels)
  if not all(channels.values()):fail.append('GLB baked material channel missing')
  for node in mat.node_tree.nodes:
   if node.type=='TEX_IMAGE' and node.image and not len(node.image.pixels):fail.append('GLB image unreadable')
result={'status':'Native MSH/ANM/DDS round trip checked','triangles':glbtris,'source_checks':source_check,'sampled_native_poses':len(expected),'max_vertex_error':maxvertex,'max_bone_error':maxbone,'samples':errors,'glb_meshes':len(glbmeshes),'glb_actions':glbactions,'glb_baked_material_channels':glbchannels,'native_images':runtime_image_names,'failures':sorted(set(fail)),'source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'engine_in_game_verified':False}
(OUT/'NATIVE_VERIFICATION.json').write_text(json.dumps(result,indent=2));print('RIPPER_VERIFICATION',json.dumps(result))
if fail:raise RuntimeError(fail)
