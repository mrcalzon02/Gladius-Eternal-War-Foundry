"""Verify evaluated hinge and arm attachment, then independently inspect animated GLB."""
import bpy,json,math,hashlib,sys
from pathlib import Path
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];D=R/'model-workbench/Ork-Nob-Crab-Claw';bpy.ops.wm.open_mainfile(filepath=str(D/'Nob-Animation-Work.blend'));scene=bpy.context.scene;rig=bpy.data.objects['OrkBoy_rig'];scale=rig.matrix_world.to_scale().x
sys.path.insert(0,str(R/'tools'))
from nob_pauldron_liner import native_pad_faces,NAME
liner=bpy.data.objects[NAME];pad_indices=native_pad_faces(bpy.data.objects['OrkBoy'])
jaw=bpy.data.objects['Hinged crab jaw'];fixed=bpy.data.objects['Fixed crab jaw'];body=bpy.data.objects['OrkBoy'];pivot=rig.data.bones['Nob_ClawJaw'].head_local.copy()
def positions(o):
 dg=bpy.context.evaluated_depsgraph_get();ev=o.evaluated_get(dg);me=ev.to_mesh();pts=[o.matrix_world@v.co for v in me.vertices];faces=[tuple(p.vertices) for p in me.polygons];ev.to_mesh_clear();return pts,faces
basehand=rig.data.bones['LeftHand'].matrix_local;basefore=rig.data.bones['LeftLowerArm'].matrix_local
report={'clips':{},'failures':[]};expected={}
for name,end in [('Nob - Crab claw mechanism',49),('Nob - Crab claw attack',65)]:
 rig.animation_data.action=bpy.data.actions[name];gap=[];hingeerr=[];seam=[];foot=[];collisions=[];barrel_scales=[];pauldron_hits=[];pauldron_clearance=[]
 for t in [1+i*.5 for i in range((end-1)*2+1)]:
  scene.frame_set(int(t),subframe=t%1);bpy.context.view_layer.update()
  hand=rig.pose.bones['LeftHand'].matrix@basehand.inverted();fore=rig.pose.bones['LeftLowerArm'].matrix@basefore.inverted()
  hingeerr.append((rig.pose.bones['Nob_ClawJaw'].head-hand@pivot).length*scale)
  seam.append(max(abs(hand[i][j]-fore[i][j]) for i in range(4) for j in range(4)))
  foot.append(max((rig.pose.bones[n].matrix.translation-rig.data.bones[n].head_local).length*scale for n in ['LeftFoot','RightFoot']))
  barrel_scales.append(rig.pose.bones['Nob_ClawRamBarrel'].matrix.to_scale().y)
  v,f=positions(jaw);u,g=positions(fixed);gap.append((v[3]-u[3]).length)
  backing,back_faces=positions(liner);body_points,body_faces=positions(body)
  pad=BVHTree.FromPolygons(body_points,[body_faces[i] for i in pad_indices]);inner=BVHTree.FromPolygons(backing,back_faces)
  if pad.overlap(inner):pauldron_hits.append(t)
  pauldron_clearance.append(min(pad.find_nearest(p)[3] for p in backing))
  # Blade/body collision excludes the intentional socket/forearm overlap.
  if t==int(t):
   b,bf=positions(body);bh=BVHTree.FromPolygons(b,bf);jh=BVHTree.FromPolygons(v,f);fh=BVHTree.FromPolygons(u,g)
   if bh.overlap(jh) or bh.overlap(fh):collisions.append(t)
  if name.endswith('attack') and t in [1,16,27,30,43,65]:
   expected[str(int(t))]={n:list(rig.matrix_world@rig.pose.bones[n].head) for n in ['LeftHand','Nob_ClawJaw','Nob_ClawRamPiston','Head']}
 r={'frames':[1,end],'max_hinge_drift_world':max(hingeerr),'max_hand_forearm_transform_difference':max(seam),'max_foot_drift_world':max(foot),'jaw_tip_gap_world':[min(gap),max(gap)],'barrel_world_scale_range':[min(barrel_scales),max(barrel_scales)],'blade_body_intersection_frames':collisions,'pauldron_intersection_samples':pauldron_hits,'minimum_pauldron_vertex_clearance_world':min(pauldron_clearance)};report['clips'][name]=r
 if max(hingeerr)>.001 or max(seam)>.001 or max(foot)>.001:report['failures'].append('Joint or foot drift '+name)
 if min(gap)>.05 or max(gap)<15:report['failures'].append('Claw travel insufficient '+name)
 if collisions:report['failures'].append('Blade body overlap '+name)
 if pauldron_hits or min(pauldron_clearance)<.5:report['failures'].append('Original pauldron/liner clearance '+name)
# Standard glTF PBR review material, using the already baked native palette.
for o in scene.objects:
 if o.type!='MESH':continue
 old=o.data.materials[0];new=bpy.data.materials.get(old.name+' animation PBR')
 if not new:
  new=bpy.data.materials.new(old.name+' animation PBR');new.use_nodes=True;bs=new.node_tree.nodes.get('Principled BSDF');bs.inputs['Roughness'].default_value=.72
  image=bpy.data.images.load(str(D/(old.name+'-review-color.png')),check_existing=True);node=new.node_tree.nodes.new('ShaderNodeTexImage');node.image=image;new.node_tree.links.new(node.outputs['Color'],bs.inputs['Base Color'])
  original_normal=next((n.image for n in old.node_tree.nodes if n.type=='TEX_IMAGE' and n.image and 'Normal' in n.image.name),None)
  if original_normal:
   node=new.node_tree.nodes.new('ShaderNodeTexImage');node.image=original_normal;nm=new.node_tree.nodes.new('ShaderNodeNormalMap');new.node_tree.links.new(node.outputs['Color'],nm.inputs['Color']);new.node_tree.links.new(nm.outputs['Normal'],bs.inputs['Normal'])
 for i in range(len(o.data.materials)):o.data.materials[i]=new
rig.animation_data.action=bpy.data.actions['Nob - Crab claw attack'];scene.frame_start=1;scene.frame_end=65;scene.frame_set(1)
bpy.ops.object.select_all(action='DESELECT')
for o in scene.objects:
 if o.type in ['MESH','ARMATURE']:o.select_set(True)
path=D/'Nob-Claw-Attack-review.glb'
bpy.ops.export_scene.gltf(filepath=str(path),use_selection=True,export_format='GLB',export_animations=True,export_animation_mode='ACTIVE_ACTIONS',export_frame_range=True,export_force_sampling=True,export_bake_animation=True,export_anim_single_armature=False)
report['animated_export_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
# Reimport the actual export into an otherwise empty scene, preserving review lights.
for o in list(scene.objects):
 if o.type in ['MESH','ARMATURE','EMPTY']:bpy.data.objects.remove(o,do_unlink=True)
bpy.ops.import_scene.gltf(filepath=str(path));imported=next(o for o in scene.objects if o.type=='ARMATURE' and 'Nob_ClawJaw' in o.data.bones)
runtime_body=bpy.data.objects['OrkBoy'];runtime_liner=bpy.data.objects[NAME];runtime_pad=native_pad_faces(runtime_body);runtime_hits=[];runtime_clearance=[]
for index in range(129):
 t=1+index*.5;scene.frame_set(int(t),subframe=t%1);bpy.context.view_layer.update()
 pts,faces=positions(runtime_body);backing,backfaces=positions(runtime_liner);pad=BVHTree.FromPolygons(pts,[faces[i] for i in runtime_pad]);inner=BVHTree.FromPolygons(backing,backfaces)
 if pad.overlap(inner):runtime_hits.append(t)
 runtime_clearance.append(min(pad.find_nearest(p)[3] for p in backing))
report['reimport_pauldron']={'intersection_samples':runtime_hits,'minimum_vertex_clearance_world':min(runtime_clearance)}
if runtime_hits or min(runtime_clearance)<.5:report['failures'].append('Animated GLB pauldron/liner clearance')
errors=[]
# glTF shifts frame 1 to time 0 on import.
for frame,bones in expected.items():
 scene.frame_set(int(frame));bpy.context.view_layer.update()
 for name,point in bones.items():errors.append(((imported.matrix_world@imported.pose.bones[name].head)-Vector(point)).length)
report['max_reimport_joint_position_error_world']=max(errors)
if max(errors)>.03:report['failures'].append('Animated GLB joint round trip error')
scene.render.resolution_x=720;scene.render.resolution_y=720;scene.cycles.samples=12
for t in [16,30]:
 scene.frame_set(t);scene.render.filepath=str(D/'animation-previews'/f'reimport-{t}.png');bpy.ops.render.render(write_still=True)
report['working_sha256']=hashlib.sha256((D/'Nob-Animation-Work.blend').read_bytes()).hexdigest()
(D/'animation-verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
