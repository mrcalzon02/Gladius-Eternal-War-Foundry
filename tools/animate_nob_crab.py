"""Add crab hinge, telescoping ram and authored heavy claw attack to approved Nob."""
from pathlib import Path
import bpy,math,json,hashlib
from mathutils import Vector,Matrix,Quaternion
R=Path(__file__).resolve().parents[1];D=R/'model-workbench/Ork-Nob-Crab-Claw';P=D/'animation-previews';P.mkdir(exist_ok=True)
source=D/'Ork-Nob-Crab-Claw.blend';source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(source));scene=bpy.context.scene;rig=bpy.data.objects['OrkBoy_rig']
def signature(a):
 return hashlib.sha256(repr([(c.data_path,c.array_index,[tuple(k.co) for k in c.keyframe_points]) for l in a.layers for s in l.strips for b in s.channelbags for c in b.fcurves]).encode()).hexdigest()
old_actions={a.name:signature(a) for a in bpy.data.actions}
geometry={o.name:[tuple(v.co) for v in o.data.vertices] for o in scene.objects if o.type=='MESH'}
for o in scene.objects:
 if o.type=='ARMATURE':
  o.animation_data_create();o.animation_data.action=None;o.animation_data.use_nla=False
  for t in o.animation_data.nla_tracks:t.mute=True
  for pb in o.pose.bones:pb.matrix_basis.identity();pb.rotation_mode='QUATERNION'
bpy.context.view_layer.update()
base={b.name:b.matrix_local.copy() for b in rig.data.bones if not b.get('gladius_pivot')}
w=rig.data.bones['LeftHand'].head_local.copy();e=rig.data.bones['LeftLowerArm'].head_local.copy();shoulder=rig.data.bones['LeftUpperArm'].head_local.copy()
axis=(w-e).normalized();op=Vector((1,0,0));op=(op-axis*op.dot(axis)).normalized();hinge=axis.cross(op).normalized();scale=rig.matrix_world.to_scale().x
cp=lambda s,t=0,h=0:w+(axis*s+op*t+hinge*h)/scale
pivot=cp(8);anchor=cp(-1,-6,-7);lug=cp(14,-8,-7)
# One real hinge bone; rigid jaw weight moves about the physical transverse axle.
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.context.view_layer.objects.active=rig;bpy.ops.object.mode_set(mode='EDIT')
b=rig.data.edit_bones.new('Nob_ClawWrist');b.head=w;b.tail=w+base['LeftHand'].col[1].xyz*10;b.align_roll(base['LeftHand'].col[2].xyz);b.parent=rig.data.edit_bones['LeftLowerArm']
b=rig.data.edit_bones.new('Nob_ClawJaw');b.head=pivot;b.tail=pivot+hinge*5;b.parent=rig.data.edit_bones['Nob_ClawWrist']
for name,a,z in [('Nob_ClawRamBarrel',anchor,anchor.lerp(lug,.6)),('Nob_ClawRamPiston',anchor.lerp(lug,.45),lug)]:
 b=rig.data.edit_bones.new(name);b.head=a;b.tail=z;b.parent=rig.data.edit_bones['Nob_ClawWrist']
bpy.ops.object.mode_set(mode='OBJECT')
for pb in rig.pose.bones:pb.rotation_mode='QUATERNION'
constraint=rig.pose.bones['LeftHand'].constraints.new('COPY_TRANSFORMS');constraint.name='Rigid claw wrist continuity';constraint.target=rig;constraint.subtarget='Nob_ClawWrist';constraint.target_space='POSE';constraint.owner_space='POSE'
assert max(abs(rig.data.bones['Nob_ClawWrist'].matrix_local[i][j]-base['LeftHand'][i][j]) for i in range(4) for j in range(4))<1e-4
# Rebuild just the existing ram meshes as a coherent coaxial actuator.
def reweight(o,bone):
 o.vertex_groups.clear();o.vertex_groups.new(name=bone).add(list(range(len(o.data.vertices))),1,'REPLACE')
reweight(bpy.data.objects['Hinged crab jaw'],'Nob_ClawJaw')
for o in scene.objects:
 if o.type=='MESH' and o.name!='OrkBoy' and o.vertex_groups.get('LeftHand'):o.vertex_groups['LeftHand'].name='Nob_ClawWrist'
for objname,bone,a,z,radius in [('Crab actuator barrel','Nob_ClawRamBarrel',anchor,anchor.lerp(lug,.6),1.6/scale),('Crab actuator piston','Nob_ClawRamPiston',anchor.lerp(lug,.45),lug,.9/scale)]:
 o=bpy.data.objects[objname];bpy.ops.mesh.primitive_cylinder_add(vertices=6,radius=radius,depth=(z-a).length,location=(a+z)/2);tmp=bpy.context.object;tmp.rotation_euler=(z-a).to_track_quat('Z','Y').to_euler();bpy.context.view_layer.update()
 me=tmp.data.copy()
 for v in me.vertices:v.co=tmp.matrix_world@v.co
 # Assign native patch coordinates explicitly for the new actuator geometry.
 
 for olduv in list(me.uv_layers):me.uv_layers.remove(olduv)
 uv=me.uv_layers.new(name='Native atlas patches')
 for p in me.polygons:
  for j,li in enumerate(p.loop_indices):uv.data[li].uv=(.02+.03*(j%2),.805+.045*((j//2)%2))
 old=o.data;me.materials.clear()
 for m in old.materials:me.materials.append(m)
 o.data=me;bpy.data.objects.remove(tmp,do_unlink=True);reweight(o,bone)
# Clevis pin bridges the actuator end to the actual moving jaw side plate.
a=cp(14,-8,-3.2);z=cp(14,-8,-7.8)
bpy.ops.mesh.primitive_cylinder_add(vertices=6,radius=1.15/scale,depth=(z-a).length,location=(a+z)/2)
pin=bpy.context.object;pin.name='Crab actuator jaw clevis pin';pin.rotation_euler=(z-a).to_track_quat('Z','Y').to_euler();bpy.context.view_layer.update()
for v in pin.data.vertices:v.co=pin.matrix_world@v.co
pin.matrix_world=Matrix.Identity(4);pin.parent=rig;pin.matrix_basis=Matrix.Identity(4)
pin.data.materials.append(bpy.data.objects['Hinged crab jaw'].data.materials[0])
for olduv in list(pin.data.uv_layers):pin.data.uv_layers.remove(olduv)
uv=pin.data.uv_layers.new(name='Native atlas patches')
for face in pin.data.polygons:
 for j,li in enumerate(face.loop_indices):uv.data[li].uv=(.02+.03*(j%2),.805+.045*((j//2)%2))
reweight(pin,'Nob_ClawJaw');pin.modifiers.new('Claw hinge deformation','ARMATURE').object=rig
restjaw=rig.data.bones['Nob_ClawJaw'].matrix_local.copy();ramrest={n:rig.data.bones[n].matrix_local.copy() for n in ['Nob_ClawRamBarrel','Nob_ClawRamPiston']}
rig['claw_control']='Nob_ClawJaw local Y: +9.94 degrees closed; -42 degrees fully open';rig['claw_hinge_axis_local']=list(hinge)
close=math.degrees(2*math.atan2(2,23))
def segment(a,b,c,d):return Matrix.Translation(c)@(b-a).rotation_difference(d-c).to_matrix().to_4x4()@Matrix.Translation(-a)
def solve(target,hint):
 l1=(e-shoulder).length;l2=(w-e).length;v=target-shoulder;dist=min(v.length,l1+l2-.005);d=v.normalized();along=(l1*l1-l2*l2+dist*dist)/(2*dist);h=hint-shoulder-d*(hint-shoulder).dot(d)
 return shoulder+d*along+h.normalized()*math.sqrt(max(0,l1*l1-along*along)),shoulder+d*dist
# frame, wrist world target, elbow world hint, torso twist, lean, jaw angle
keys=[(1,None,None,0,0,0),(16,(3,39,95),(-11,43,79),-10,-4,-42),(20,(3,39,95),(-11,43,79),-10,-4,-42),(27,(44,29,55),(19,42,73),8,7,-36),(30,(46,27,49),(23,39,66),12,9,close),(36,(46,27,49),(23,39,66),12,9,close),(43,(34,40,45),(12,45,62),-2,5,close),(52,(17,43,44),(0,37,64),-3,2,-22),(65,None,None,0,0,0)]
def values(time):
 for a,b in zip(keys,keys[1:]):
  if a[0]<=time<=b[0]:
   f=(time-a[0])/(b[0]-a[0]);f=f*f*(3-2*f)
   A=w if a[1] is None else Vector(a[1])/scale;B=w if b[1] is None else Vector(b[1])/scale
   H=e if a[2] is None else Vector(a[2])/scale;J=e if b[2] is None else Vector(b[2])/scale
   return A.lerp(B,f),H.lerp(J,f),*[a[i]+(b[i]-a[i])*f for i in [3,4,5]]
def key(pb,t):
 for prop in ['location','rotation_quaternion','scale']:pb.keyframe_insert(data_path=prop,frame=t,group=pb.name)
def pose(t,target,hint,twist,lean,angle):
 scene.frame_set(t)
 for pb in rig.pose.bones:pb.matrix_basis.identity()
 bpy.context.view_layer.update()
 ne,nw=solve(target,hint);upper=segment(shoulder,e,shoulder,ne);lower=segment(e,w,ne,nw)
 pelvis=base['Hip_Boy'].translation;torso=Matrix.Translation(pelvis)@Matrix.Rotation(math.radians(twist),4,'Z')@Matrix.Rotation(math.radians(lean),4,'Y')@Matrix.Translation(-pelvis)
 uppernames=['Torso','Abdomen','Head','LeftUpperArm','LeftLowerArm','LeftHand','RightUpperArm','RightLowerArm','RightHand']
 for name,m in base.items():
  delta=upper if name=='LeftUpperArm' else lower if name in ['LeftLowerArm','LeftHand'] else Matrix.Identity(4)
  rig.pose.bones[name].matrix=(torso if name in uppernames else Matrix.Identity(4))@delta@m
 bpy.context.view_layer.update()
 hand_delta=rig.pose.bones['Nob_ClawWrist'].matrix@base['LeftHand'].inverted()
 jaw=rig.pose.bones['Nob_ClawJaw'];jaw.rotation_quaternion=Quaternion((0,1,0),math.radians(angle))
 bpy.context.view_layer.update()
 jawdelta=Matrix.Translation(pivot)@Quaternion(hinge,math.radians(angle)).to_matrix().to_4x4()@Matrix.Translation(-pivot)
 A=hand_delta@anchor;B=hand_delta@jawdelta@lug
 direction=(B-A).normalized();barrel_length=(lug-anchor).length*.6
 for name,start,end in [('Nob_ClawRamBarrel',A,A+direction*barrel_length),('Nob_ClawRamPiston',A+direction*barrel_length*.75,B)]:
  old=rig.data.bones[name];q=(old.tail_local-old.head_local).rotation_difference(end-start)
  m=Matrix.Translation(start)@q.to_matrix().to_4x4()@ramrest[name].to_quaternion().to_matrix().to_4x4()@Matrix.Diagonal((1,(end-start).length/old.length,1,1))
  rig.pose.bones[name].matrix=m
 for pb in rig.pose.bones:key(pb,t)
 bpy.context.view_layer.update()
 return nw,ne
clips=[]
for name,end in [('Nob - Crab claw mechanism',49),('Nob - Crab claw attack',65)]:
 action=bpy.data.actions.new(name);action.use_fake_user=True;rig.animation_data.action=action;action['fps']=24
 for t in range(1,end+1):
  if end==65:pose(t,*values(t))
  else:
   # Hold open, snap shut and release, twice, without moving the arm.
   cycles=[(1,0),(9,-42),(15,-42),(18,close),(24,close),(33,-42),(39,-42),(42,close),(46,close),(49,0)]
   for a,b in zip(cycles,cycles[1:]):
    if a[0]<=t<=b[0]:
     f=(t-a[0])/(b[0]-a[0]);f=f*f*(3-2*f);angle=a[1]+(b[1]-a[1])*f;break
   pose(t,w,e,0,0,angle)
 for l in action.layers:
  for st in l.strips:
   for bag in st.channelbags:
    for c in bag.fcurves:
     for k in c.keyframe_points:k.interpolation='LINEAR'
 track=rig.animation_data.nla_tracks.new();track.name=name;track.mute=True;track.strips.new(name,1,action)
 clips.append(action)
rig.animation_data.action=clips[1]
scene.render.fps=24;scene.frame_start=1;scene.frame_end=65
for title,t in [('Ready',1),('Claw wide - windup',16),('Strike',27),('Snap impact',30),('Grip hold',36),('Wrench',43),('Recover',52)]:scene.timeline_markers.new(title,frame=t)
# Geometry checks: only the two short actuator cylinders were rebuilt.
changed=[o.name for o in scene.objects if o.type=='MESH' and geometry.get(o.name)!=[tuple(v.co) for v in o.data.vertices]]
assert set(changed)=={'Crab actuator barrel','Crab actuator piston','Crab actuator jaw clevis pin'},changed
assert all(signature(bpy.data.actions[n])==h for n,h in old_actions.items())
scene.frame_set(1);bpy.context.view_layer.update()
# Front-side view keeps the claw action out from behind the face.
cam=scene.camera;focus=Vector((10,8,60));cam.location=focus+Vector((210,280,135));cam.rotation_euler=(focus-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=172
scene.render.resolution_x=720;scene.render.resolution_y=720;scene.render.resolution_percentage=100;scene.cycles.samples=12
path=D/'Nob-Animation-Work.blend';bpy.ops.wm.save_as_mainfile(filepath=str(path))
report={'source_sha256':source_hash,'working_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'clips':[{'name':a.name,'frames':list(a.frame_range)} for a in clips],'original_15_actions_unchanged':True,'geometry_changes':changed,'hinge_bone':'Nob_ClawJaw','closed_degrees':close,'open_degrees':-42,'impact_frame':30,'fps':24,'limitations':['Local Blender animation; native Gladius exporter and in-game timing unverified.']}
(D/'animation-build.json').write_text(json.dumps(report,indent=2))
import sys
if '--skip-previews' in sys.argv:raise SystemExit(0)
for i,t in enumerate(range(1,66,2)):
 scene.frame_set(t);scene.render.filepath=str(P/f'attack-{i:03d}.png');bpy.ops.render.render(write_still=True)
rig.animation_data.action=clips[0];focus=rig.matrix_world@cp(13);cam.location=focus+Vector((105,155,65));cam.rotation_euler=(focus-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=72
for i,t in enumerate(range(1,50,2)):
 scene.frame_set(t);scene.render.filepath=str(P/f'claw-{i:03d}.png');bpy.ops.render.render(write_still=True)
print(json.dumps(report,indent=2))

