"""Fitted Grot rig and authored game-action library; approved appearance stays untouched."""
import bpy,math,json,hashlib,sys
from pathlib import Path
from mathutils import Vector,Matrix,Quaternion
R=Path(__file__).resolve().parents[1];D=R/'model-workbench/Grot-Sneak';P=D/'animation-previews';P.mkdir(exist_ok=True)
sys.path.insert(0,str(R/'tools'));from reference_grot_shape import shape
source=D/'Grot-Sneak.blend';bpy.ops.wm.open_mainfile(filepath=str(source));scene=bpy.context.scene
source_hash=hashlib.sha256(source.read_bytes()).hexdigest();meshes=[o for o in scene.objects if o.type=='MESH' and not o.hide_render]
def q(p):
 p=Vector(p);p.z=p.z if p.z<=13 else 13+(p.z-13)*.82 if p.z<21 else p.z-1.44;return shape(p)
for arm in [o for o in scene.objects if o.type=='ARMATURE']:
 if arm.animation_data:arm.animation_data.action=None;arm.animation_data.use_nla=False
 for pb in arm.pose.bones:pb.matrix_basis.identity()
bpy.context.view_layer.update()
original_geometry={}
for o in meshes:
 points=[o.matrix_world@v.co for v in o.data.vertices];original_geometry[o.name]=[list(v) for v in points]
 for mod in list(o.modifiers):
  if mod.type=='ARMATURE':o.modifiers.remove(mod)
 o.parent=None;o.matrix_world=Matrix.Identity(4)
 for v,p in zip(o.data.vertices,points):v.co=p
 o.vertex_groups.clear()
for o in list(scene.objects):
 if o.type=='ARMATURE':bpy.data.objects.remove(o,do_unlink=True)

pelvis=q((0,0,12.3));chest=q((-.5,0,16.5));neck=q((-1.4,0,22));head=q((3,0,25.5));jaw=q((4.8,0,23.3))
joints={
 'Left':dict(shoulder=q((-1.3,3.6,22.4)),elbow=q((1.8,7.2,17.6)),wrist=q((8.2,7.8,20.1)),palm=q((8.8,7.8,20.7)),hip=q((0,1.8,12.4)),knee=q((6.2,4.4,7.4)),ankle=q((4.4,7.2,1.2))),
 'Right':dict(shoulder=q((-1.3,-3.6,22.5)),elbow=q((-4.3,-7,18.3)),wrist=q((1,-8.5,12.5)),palm=q((1.8,-8.6,11.8)),hip=q((0,-1.8,12.4)),knee=q((2,-5,7.8)),ankle=q((-2.6,-7.4,1.3)))}
armdata=bpy.data.armatures.new('Grot fitted animation skeleton');rig=bpy.data.objects.new('Grot_Animation_rig',armdata);scene.collection.objects.link(rig)
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.context.view_layer.objects.active=rig;bpy.ops.object.mode_set(mode='EDIT')
def bone(name,a,b,parent=None):
 eb=armdata.edit_bones.new(name);eb.head=a;eb.tail=b
 if parent:eb.parent=armdata.edit_bones[parent]
 return eb
bone('Root',(0,0,.2),(0,0,2.2));bone('Hip_Boy',pelvis,chest,'Root');bone('Abdomen',chest,chest.lerp(neck,.5),'Hip_Boy');bone('Torso',chest.lerp(neck,.5),neck,'Abdomen');bone('Neck',neck,head,'Torso');bone('Head',head,q((7.2,0,25.1)),'Neck');bone('Jaw',jaw,q((8.65,0,21.05)),'Head')
for side,j in joints.items():
 bone(side+'UpperArm',j['shoulder'],j['elbow'],'Torso');bone(side+'LowerArm',j['elbow'],j['wrist'],side+'UpperArm');bone(side+'Hand',j['wrist'],j['palm'],side+'LowerArm')
 thigh='LefttLegHip' if side=='Left' else 'RightLegHip';shin='LefttLegShin' if side=='Left' else 'RightLegShin'
 bone(thigh,j['hip'],j['knee'],'Hip_Boy');bone(shin,j['knee'],j['ankle'],thigh);bone(side+'Foot',j['ankle'],j['ankle']+Vector((2.6,.4 if side=='Left' else -.4,-.7)),shin)
bpy.ops.object.mode_set(mode='OBJECT');rig.show_in_front=True
base={b.name:b.matrix_local.copy() for b in rig.data.bones};order=sorted(rig.pose.bones,key=lambda b:len(b.parent_recursive))
for pb in rig.pose.bones:pb.rotation_mode='QUATERNION'
segments={b.name:(b.head_local.copy(),b.tail_local.copy()) for b in rig.data.bones}
def distance(p,a,b):
 d=b-a;t=max(0,min(1,(p-a).dot(d)/max(1e-9,d.length_squared)));return (p-a-d*t).length
def blended(p,names):
 choices=sorted((distance(p,*segments[n]),n) for n in names)[:3];minimum=choices[0][0];weights={n:math.exp(-((d-minimum)/1.20)**2)*math.exp(-(d/3.0)**2) for d,n in choices};total=sum(weights.values());return {n:w/total for n,w in weights.items() if w/total>.015}
def weights(p):
 x,y,z=p;side='Left' if y>=0 else 'Right';j=joints[side]
 for handside,hj in joints.items():
  if (p-hj['palm']).length<1.85:return {handside+'Hand':1}
 if z>23.2 or (z>22 and x>0) or (x>3.5 and z>17.8 and abs(y)<4.2):
  jawweight=max(0,min(1,(20.9-z)/.85))*max(0,min(1,(x-4.4)/1.7))
  return {'Head':1-jawweight,'Jaw':jawweight}
 armnames=[side+'UpperArm',side+'LowerArm',side+'Hand'];armdist=min(distance(p,*segments[n]) for n in armnames)
 if abs(y)>5.5 and z>9.7 and armdist<2.8:return blended(p,['Torso']+armnames)
 if z<12.5:
  if z<2.2:return {side+'Foot':1}
  thigh='LefttLegHip' if side=='Left' else 'RightLegHip';shin='LefttLegShin' if side=='Left' else 'RightLegShin'
  if abs(y)<2.6 and z>10.4:return {'Hip_Boy':1}
  return blended(p,['Hip_Boy',thigh,shin,side+'Foot'])
 if abs(y)>3.0 and armdist<2.8:
  if (p-j['palm']).length<1.85:return {side+'Hand':1}
  return blended(p,['Torso',side+'UpperArm',side+'LowerArm',side+'Hand'])
 if z>20:return blended(p,['Torso','Neck','Head'])
 return blended(p,['Hip_Boy','Abdomen','Torso'])
for o in meshes:
 o.parent=rig;o.matrix_parent_inverse=Matrix.Identity(4);o.matrix_basis=Matrix.Identity(4)
 for name in base:o.vertex_groups.new(name=name)
 if o.name=='Grot unified game body':
  weightmap={v.index:weights(v.co) for v in o.data.vertices};neighbours={v.index:set() for v in o.data.vertices}
  for edge in o.data.edges:
   a,b=edge.vertices;neighbours[a].add(b);neighbours[b].add(a)
  for iteration in range(2):
   updated={}
   for v in o.data.vertices:
    p=v.co;w=weightmap[v.index]
    if abs(p.y)>2.5 and 13.8<p.z<22.6 and min((p-j['palm']).length for j in joints.values())>2.0:
     combined={name:value*.65 for name,value in w.items()};adj=neighbours[v.index]
     for index in adj:
      for name,value in weightmap[index].items():combined[name]=combined.get(name,0)+value*.35/max(1,len(adj))
     combined=dict(sorted(combined.items(),key=lambda item:item[1],reverse=True)[:4]);total=sum(combined.values());w={name:value/total for name,value in combined.items()}
    updated[v.index]=w
   weightmap=updated
  for v in o.data.vertices:
   w=weightmap[v.index];total=sum(w.values())
   for name,value in w.items():
    if value>0:o.vertex_groups[name].add([v.index],value/total,'REPLACE')
 else:
  name='Head'
  if 'lower snag' in o.name:name='Jaw'
  elif 'LeftFoot' in o.name:name='LeftFoot'
  elif 'RightFoot' in o.name:name='RightFoot'
  elif 'shank' in o.name:name='LeftHand'
  elif 'slugga' in o.name:name='RightHand'
  elif 'belt' in o.name or 'loincloth' in o.name:name='Hip_Boy'
  elif 'binding' in o.name:
   name=o.name.split('binding ')[1]
   if 'LegShin' in name:name='LeftFoot' if name.startswith('Left') else 'RightFoot'
  o.vertex_groups[name].add(list(range(len(o.data.vertices))),1,'REPLACE')
 mod=o.modifiers.new('Fitted Grot deformation','ARMATURE');mod.object=rig;mod.use_deform_preserve_volume=False

def around(p,angle,axis='Y'):return Matrix.Translation(p)@Matrix.Rotation(math.radians(angle),4,axis)@Matrix.Translation(-p)
def segment(a,b,c,d):return Matrix.Translation(c)@(b-a).rotation_difference(d-c).to_matrix().to_4x4()@Matrix.Translation(-a)
def ik(h,k,w,target,hint,rest_h):
 l1=(k-rest_h).length;l2=(w-k).length;d=target-h;length=max(.01,min(d.length,l1+l2-.001));axis=d.normalized();along=(l1*l1-l2*l2+length*length)/(2*length);pole=hint-h-axis*(hint-h).dot(axis)
 if pole.length<.001:pole=axis.cross(Vector((0,1,0)))
 return h+axis*along+pole.normalized()*math.sqrt(max(0,l1*l1-along*along)),h+axis*length
def smooth(t):t=max(0,min(1,t));return t*t*(3-2*t)
def keys(t,entries):
 for a,b in zip(entries,entries[1:]):
  if a[0]<=t<=b[0]:return a[1]+(b[1]-a[1])*smooth((t-a[0])/(b[0]-a[0]))
 return entries[-1][1]
def step(phase,stride,lift,duty):
 phase%=1
 if phase<duty:return stride*(1-2*phase/duty),0,True
 s=(phase-duty)/(1-duty);return -stride+2*stride*s,lift*math.sin(math.pi*s),False
def apply_deltas(deltas):
 target={name:delta@base[name] for name,delta in deltas.items()}
 for pb in order:
  if pb.parent:pb.matrix_basis=base[pb.name].inverted()@base[pb.parent.name]@target[pb.parent.name].inverted()@target[pb.name]
  else:pb.matrix_basis=base[pb.name].inverted()@target[pb.name]
 bpy.context.view_layer.update()

clips=[('Idle',49,True),('Snarl',33,False),('Sneak',49,True),('Run',25,True),('Pistol fire',49,False),('Shank stab',41,False),('Hit reaction',25,False),('Death',49,False)]
rig.animation_data_create();rest_floor=min(v.co.z for o in meshes for v in o.data.vertices);stats={};samples={}
def pose(kind,frame,end):
 phase=(frame-1)/(end-1);theta=phase*math.tau;bob=0;lean=0;twist=0;root=Vector();jawangle=0;look=0
 if kind=='Idle':bob=.09*math.sin(theta);lean=.75*math.sin(theta);look=2.5*math.sin(theta)
 if kind=='Snarl':jawangle=keys(frame,[(1,0),(9,7),(17,-8),(24,5),(33,0)]);lean=keys(frame,[(1,0),(13,3),(23,-1),(33,0)]);look=3*math.sin(theta)
 if kind in ['Sneak','Run']:bob=(.12 if kind=='Sneak' else .35)*(math.cos(theta*2)-1);lean=5 if kind=='Sneak' else 9;twist=(2.0 if kind=='Sneak' else 3.5)*math.sin(theta);jawangle=1.5*math.sin(theta*2)
 if kind=='Shank stab':lean=keys(frame,[(1,0),(10,-4),(17,9),(21,8),(41,0)]);root.x=keys(frame,[(1,0),(10,-.15),(18,.65),(24,.35),(41,0)]);twist=keys(frame,[(1,0),(10,-8),(18,10),(25,3),(41,0)]);jawangle=4*math.sin(math.pi*phase)**2
 if kind=='Hit reaction':lean=keys(frame,[(1,0),(5,-11),(10,-7),(25,0)]);twist=keys(frame,[(1,0),(5,8),(13,-3),(25,0)]);bob=keys(frame,[(1,0),(6,-.7),(25,0)])
 death=smooth((frame-4)/31) if kind=='Death' else 0
 if kind=='Death':lean=0;jawangle=-6*death
 hipdelta=Matrix.Translation(root+Vector((0,0,bob)));abd=hipdelta@around(pelvis,lean*.40)@around(pelvis,twist*.30,'Z');upper=abd@around(chest,lean*.60)@around(chest,twist*.70,'Z');hd=upper@around(head,look,'Z')@around(head,-.8*jawangle)
 desired={'Root':Matrix.Translation(root),'Hip_Boy':hipdelta,'Abdomen':abd,'Torso':upper,'Neck':upper,'Head':hd,'Jaw':hd@around(jaw,jawangle)}
 planted={};grips={}
 for side,j in joints.items():
  phaseleg=phase+(0 if side=='Left' else .5);footdx=footlift=0;stance=True
  if kind in ['Sneak','Run']:footdx,footlift,stance=step(phaseleg,2.6 if kind=='Sneak' else 4.1,.75 if kind=='Sneak' else 1.65,.66 if kind=='Sneak' else .50)
  H=hipdelta@j['hip'];target=j['ankle']+Vector((footdx,0,footlift))
  if kind in ['Sneak','Run']:target.x=.9+footdx;target.y=5.8 if side=='Left' else -5.8
  if kind=='Death':target.y=j['ankle'].y*(1-death)+(2.2 if side=='Left' else -2.2)*death
  K,A=ik(H,j['knee'],j['ankle'],target,hipdelta@j['knee'],j['hip'])
  thigh='LefttLegHip' if side=='Left' else 'RightLegHip';shin='LefttLegShin' if side=='Left' else 'RightLegShin'
  desired[thigh]=segment(j['hip'],j['knee'],H,K);desired[shin]=segment(j['knee'],j['ankle'],K,A);desired[side+'Foot']=Matrix.Translation(A-j['ankle']);planted[side]=(stance,A.copy(),target.copy())
  S=upper@j['shoulder'];target=upper@j['wrist'];hint=upper@j['elbow'];handrot=upper.to_quaternion()
  if kind in ['Sneak','Run']:
   swing=(.50 if kind=='Sneak' else 1.1)*math.sin(theta+(0 if side=='Left' else math.pi));target+=Vector((swing,.30 if side=='Left' else -.20,.10*math.sin(theta*2)))
  if kind=='Pistol fire' and side=='Right':
   aim=keys(frame,[(1,0),(4,0),(13,1),(35,1),(49,0)]);recoil=sum(math.exp(-(frame-f)/1.1) if 0<=frame-f<4 else 0 for f in [17,23,29]);target+=Vector((5*aim-.4*recoil,.8*aim,4.5*aim+.25*recoil));handrot=Quaternion((0,1,0),math.radians(-80*aim-9*recoil))@handrot;hint+=Vector((0,-1.4,1.0*aim))
  if kind=='Shank stab' and side=='Left':
   wind=keys(frame,[(1,0),(10,1),(13,1),(17,0),(41,0)]);strike=keys(frame,[(1,0),(13,0),(17,1),(20,1),(28,0),(41,0)]);target+=Vector((-2*wind+3.0*strike,1.4*wind+.7*strike,1.5*wind-.85*strike));hint+=Vector((-.7,2.5,.4));handrot=Quaternion((0,1,0),math.radians(-12*wind+8*strike))@handrot
  if kind=='Death':
   target.y=target.y*(1-death)+(2.3 if side=='Left' else -2.3)*death;hint.y=hint.y*(1-death)+(3.4 if side=='Left' else -3.4)*death
   target.x+=.5*death;target.z+=.7*death
  E,W=ik(S,j['elbow'],j['wrist'],target,hint,j['shoulder']);desired[side+'UpperArm']=segment(j['shoulder'],j['elbow'],S,E);desired[side+'LowerArm']=segment(j['elbow'],j['wrist'],E,W);desired[side+'Hand']=Matrix.Translation(W)@handrot.to_matrix().to_4x4()@Matrix.Translation(-j['wrist']);grips[side]=W.copy()
 if death:
  collapse=Matrix.Translation((0,0,-9*death))@around(pelvis,92*death,'X')@around(pelvis,-12*death,'Z')
  desired={name:collapse@delta for name,delta in desired.items()}
 apply_deltas(desired)
 if death:
  deps=bpy.context.evaluated_depsgraph_get();minimum=min((o.matrix_world@v.co).z for o in meshes for v in o.evaluated_get(deps).data.vertices);shift=max(0,rest_floor-minimum)
  if shift:
   adjust=Matrix.Translation((0,0,shift))
   apply_deltas({name:adjust@delta for name,delta in desired.items()})
 return planted,grips

for name,end,loop in clips:
 action=bpy.data.actions.new('Grot - '+name);action.use_fake_user=True;action['fps']=24;action['loop']=loop;action['stage']='authored fitted Grot animation';rig.animation_data.action=action;rig.animation_data.use_nla=False
 for f in range(1,end+1):
  scene.frame_set(f)
  for pb in rig.pose.bones:pb.matrix_basis.identity()
  bpy.context.view_layer.update();planted,grips=pose(name,f,end)
  for pb in rig.pose.bones:
   for prop in ['location','rotation_quaternion','scale']:pb.keyframe_insert(data_path=prop,frame=f,group=pb.name)
  if f in [1,end//3,end*2//3,end]:samples[name+' '+str(f)]={b:list(rig.pose.bones[b].head) for b in ['Head','LeftHand','RightHand','LeftFoot','RightFoot']}
 for layer in action.layers:
  for strip in layer.strips:
   for bag in strip.channelbags:
    for curve in bag.fcurves:
     for key in curve.keyframe_points:key.interpolation='LINEAR'
 track=rig.animation_data.nla_tracks.new();track.name=action.name;track.mute=True;track.strips.new(action.name,1,action)
 stats[name]={'frames':[1,end],'fps':24,'loop':loop}
rig.animation_data.action=None
for pb in rig.pose.bones:pb.matrix_basis.identity()
bpy.context.view_layer.update()
max_bind_error=max((o.matrix_world@v.co-Vector(original_geometry[o.name][v.index])).length for o in meshes for v in o.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.vertices)
if max_bind_error>1e-4:raise RuntimeError('Bind geometry changed '+str(max_bind_error))
rig.animation_data.action=bpy.data.actions['Grot - Idle'];scene.frame_start=1;scene.frame_end=49;scene.render.fps=24;scene.frame_set(1)
scene['animation_library']='Select a Grot action on Grot_Animation_rig; muted NLA tracks retain all eight clips.';scene['stage']='Local authored Grot animation; native engine export unverified'
camera=scene.camera;focus=Vector((3,0,13));camera.data.ortho_scale=39;camera.location=focus+Vector((70,-110,30));camera.rotation_euler=(focus-camera.location).to_track_quat('-Z','Y').to_euler();scene.render.resolution_x=640;scene.render.resolution_y=640;scene.cycles.samples=12
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.context.view_layer.objects.active=rig
bpy.ops.file.pack_all();out=D/'Grot-Animation-Work.blend';bpy.ops.wm.save_as_mainfile(filepath=str(out))
report={'appearance_source_sha256':source_hash,'working_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'clips':stats,'bones':len(base),'visible_triangles':sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in meshes),'max_bind_error':max_bind_error,'reference_joint_samples':samples,'native_engine_export_verified':False,'rig':'Grot_Animation_rig','notes':'Fitted skeleton and smooth joint weights replace the incompatible imported rig in this animation working copy. Original 15 actions retained as reference only.'}
(D/'animation-build.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='reference_joint_samples'},indent=2))
