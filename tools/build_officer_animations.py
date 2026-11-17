"""Author and stage the accepted officer's complete native animation set."""
from pathlib import Path
import bpy,sys,json,math,hashlib,shutil,importlib.util,xml.etree.ElementTree as E
from mathutils import Vector,Quaternion,Matrix
R=Path(__file__).resolve().parents[1];A=R/'model-workbench/Imperial-Officer/animation-production';B=A/'accepted-model';O=R/'assets/imperial-officer-animated';D=O/'Data';OLD=B/'Data'
A.mkdir(parents=True,exist_ok=True);sys.path.insert(0,str(R/'tools'));from officer_animation import *
from native_gladius import read_animation
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();source=B/'Officer-Accepted-Model.blend';source_hash=sha(source);build=json.loads((B/'body-build.json').read_text())
spec=importlib.util.spec_from_file_location('officer_animation_import',R/'references/import_gladius.py');g=importlib.util.module_from_spec(spec);sys.modules[spec.name]=g;spec.loader.exec_module(g)
bpy.ops.wm.open_mainfile(filepath=str(source));s=bpy.context.scene;rig=bpy.data.objects['Guardsman_rig'];s.render.fps=60;s.render.fps_base=1
names=build['bone_order'];native=names[:28];rest={n:rig.data.bones[n].head_local.copy() for n in names};binds={}
for n in names:
    v=rig.data.bones[n]['gladius_source_bind'];binds[n]=Matrix([v[:4],v[4:8],v[8:12],v[12:16]])
from officer_skinning import sleeve_weights,refine_native_weights
weight_changes,skinning=sleeve_weights([bpy.data.objects[n] for n in build['body_objects']],rest,json.loads((B/'sleeve-regions.json').read_text()))
attachment=build['attachments'];clips={p.stem:read_clip(p) for p in (B/'reference-motion').glob('*.anm')}
# A small, constant held-weapon fitting shift clears the loose cuff while the
# original pistol handle remains seated between thumb and fingers.
attachment['pistol']['grip_adjustment']=[0.,.60,0.]
attachment['pistol']['rest_hand_grip']=list(Vector(attachment['pistol']['rest_hand_grip'])+Vector(attachment['pistol']['grip_adjustment']))
reference=sample_clip(clips['Idle0'],0,rest,native);ready=clone(reference);arm_errors=[]
for side,target,hint in [('Left',(4,16,37),(-7,11,44)),('Right',(1,-15,36),(-7,-10,44))]:
    error,_=solve_arm(ready,side,Vector(target),Vector(hint),ready[side+'HandBone'][1],.10);arm_errors.append(error)
arm_reference=clone(ready)
upper_names=[n for n in native if n in ('ChestBone','Head') or any(k in n for k in ('Soulder','Shoulder','ArmBone','HandBone','FingerBone','ThumbBone'))]
all_upper=['AbdomenBone']+upper_names;waist=ready['AbdomenBone'][0].copy();qleft=ready['LeftHandBone'][1].copy();qright=ready['RightHandBone'][1].copy()
pistol_object=bpy.data.objects['PrimarisPsykerLaspistol'];v=pistol_object.parent.data.bones['Muzzle0']['gladius_source_bind'];muzzle_bind=Matrix([v[:4],v[4:8],v[8:12],v[12:16]])
pistol_muzzle=muzzle_bind.col[0].xyz.normalized();grip_to_muzzle=muzzle_bind.translation-Vector(attachment['pistol']['local_grip']);pistol_up=(grip_to_muzzle-pistol_muzzle*grip_to_muzzle.dot(pistol_muzzle)).normalized();pistol_rest=binds[attachment['pistol']['bone']].to_3x3();aim_q=(frame((1,0,0),(0,0,1))@frame(pistol_rest@pistol_muzzle,pistol_rest@pistol_up).transposed()).to_quaternion()
pistol_frame={'native_grip':attachment['pistol']['local_grip'],'native_muzzle':list(muzzle_bind.translation),'native_forward':list(pistol_muzzle),'native_barrel_up':list(pistol_up),'up_definition':'Actual handle grip toward actual muzzle, perpendicular to barrel; not the mesh +Z axis'};(A/'pistol-frame.json').write_text(json.dumps(pistol_frame,indent=2))
source_vertices=[];foot_offsets={side:[] for side in ('Left','Right')}
for name in build['body_objects']:
    ob=bpy.data.objects[name]
    for vertex in ob.data.vertices:
        weights=[(ob.vertex_groups[w.group].name,w.weight) for w in vertex.groups if w.weight>1e-6];source_vertices.append((vertex.co.copy(),weights))
        for side in ('Left','Right'):
            if sum(w for n,w in weights if n==side+'FootBone')>.98:foot_offsets[side].append(vertex.co-rest[side+'FootBone'])
ground=min(p.z for p,weights in source_vertices);leg_errors=[]

def torso(pose,yaw=0,pitch=0,lift=0):
    q=Quaternion((0,0,1),math.radians(yaw))@Quaternion((0,1,0),math.radians(pitch));rotate_pose(pose,all_upper,pose['AbdomenBone'][0],q,Vector((0,0,lift)));return q

def arm(pose,side,target,hint,q,follow=.22):
    error,_=solve_armed_pose(pose,side,target,q,rest,arm_reference);arm_errors.append(error)

def idle(t,duration,variant):
    p=clone(ready);cycle=2*math.pi*t/duration;breath=.10*(1-math.cos(cycle));torso(p,0,.30*math.sin(cycle),breath)
    gaze=(0 if variant==0 else (11 if variant==1 else -10))*math.sin(math.pi*t/duration)**2
    p['Head'][1]=Quaternion((0,0,1),math.radians(gaze))@p['Head'][1]
    return p

def walk(t):
    p=sample_clip(clips['Move'],t,rest,native);phase=2*math.pi*t/clips['Move']['duration']
    # Native legs retain the established gait; the fitted weapon arms have a
    # controlled opposite-phase swing and keep the saw forward, edge below.
    for side,sign in [('Left',1),('Right',-1)]:
        target=ready[side+'HandBone'][0]+Vector((sign*.55*math.sin(phase),0,.13*(1-math.cos(phase))))
        hint=p[side+'LowerArmBone'][0]+Vector((-2,2*sign,1));q=Quaternion((0,1,0),math.radians(sign*1.1*math.sin(phase)))@ready[side+'HandBone'][1]
        arm(p,side,target,hint,q)
    return p

def blend_pose(a,b,u):
    u=smooth(u);p={n:[a[n][0].lerp(b[n][0],u),a[n][1].slerp(b[n][1],u)] for n in native}
    for side in ('Left','Right'):
        upper=side+'UpperArmBone';lower=side+'LowerArmBone';hand=side+'HandBone';target=p[hand][0].copy();hint=p[lower][0].copy();hand_q=p[hand][1].copy()
        arm(p,side,target,hint,hand_q,0)
        target=p[side+'FootBone'][0].copy();hint=p[side+'ShinBone'][0].copy();leg_errors.append(solve_leg(p,side,target,hint,rest))
    return p

def fire(t):
    p=clone(ready);mix=curve([(0,0),(.30,1),(2.55,1),(3.,0)],t);recoil=0
    for shot in (.4,.75,1.1,1.45,1.8,2.15,2.5):
        d=t-shot
        if 0<=d<.24:recoil+=math.sin(min(1,d/.035)*math.pi/2)*math.exp(-max(0,d-.035)/.065)
    shoulder=p['RightUpperArmBone'][0];length=sum((p[b][0]-p[a][0]).length for a,b in [('RightUpperArmBone','RightLowerArmBone'),('RightLowerArmBone','RightHandBone')]);aim=shoulder+Vector((length-1.7,-6.,-1.2))
    target=p['RightHandBone'][0].lerp(aim,mix)+Vector((-.65*recoil,-2*math.sin(math.pi*mix),.18*recoil));q=qright.slerp(aim_q,smooth((mix-.18)/.82));q=Quaternion((0,1,0),math.radians(-6.5*recoil))@q
    arm(p,'Right',target,shoulder+Vector((8,0,-6)),q);return p

def sword_attack(t,defense=False):
    p=clone(ready);length=1.5
    if defense:
        mix=curve([(0,0),(.20,1),(.54,1),(1.25,0),(length,0)],t);target=ready['LeftHandBone'][0].lerp(Vector((7,18,51)),mix);angle=-48*mix;yaw=4*mix;lean=-1.5*mix
    else:
        target=vector_curve([(0,ready['LeftHandBone'][0]),(.20,(6,18,54)),(.26,(6,18,54)),(.52,(13,15,44)),(.68,(14,14,38)),(.82,(14,14,38)),(1.42,ready['LeftHandBone'][0]),(length,ready['LeftHandBone'][0])],t)
        angle=curve([(0,0),(.20,-70),(.26,-70),(.52,30),(.68,52),(.82,52),(1.42,0),(length,0)],t);yaw=curve([(0,0),(.20,10),(.26,10),(.52,-10),(.68,-16),(.82,-16),(1.42,0),(length,0)],t);lean=curve([(0,0),(.20,-2),(.52,3),(.68,4),(1.42,0),(length,0)],t)
    pivot=p['AbdomenBone'][0].copy();qbody=torso(p,yaw,lean);goal=pivot+qbody@(target-pivot);q=qbody@Quaternion((0,1,0),math.radians(angle))@qleft
    arm(p,'Left',goal,pivot+qbody@(Vector((-7,10,43))-pivot),q);return p

def charge(t,defense=False):
    suffix='ChargeDefense' if defense else 'Charge';p=sample_clip(clips[suffix],t,rest,native);mix=curve([(0,0),(.24,1),(.88,1),(1.5,0)],t)
    delta=p['ChestBone'][1]@ready['ChestBone'][1].inverted();origin=p['ChestBone'][0];target=origin+delta@(ready['LeftHandBone'][0]-ready['ChestBone'][0]+Vector((6*mix,(2 if defense else -1)*mix,(9 if defense else 3)*mix)));angle=(-34 if defense else -10)*mix
    for n in upper_names:p[n]=[origin+delta@(ready[n][0]-ready['ChestBone'][0]),delta@ready[n][1]]
    arm(p,'Left',target,origin+delta@(Vector((-7,10,43))-ready['ChestBone'][0]),delta@Quaternion((0,1,0),math.radians(angle))@qleft)
    arm(p,'Right',origin+delta@(ready['RightHandBone'][0]-ready['ChestBone'][0]),origin+delta@(Vector((-7,-10,43))-ready['ChestBone'][0]),delta@qright);return p

def command(t):
    p=clone(ready);mix=curve([(0,0),(.35,1),(1.35,1),(2.,0)],t);torso(p,-3*mix,-1*mix)
    arm(p,'Left',ready['LeftHandBone'][0]+Vector((3*mix,0,7*mix)),Vector((-5,23,46)),Quaternion((0,1,0),math.radians(-23*mix))@qleft)
    p['Head'][1]=Quaternion((0,1,0),math.radians(-3*mix))@p['Head'][1];return p

def grenade(t):
    p=clone(ready);target=vector_curve([(0,ready['RightHandBone'][0]),(.28,(0,-18,58)),(.62,(0,-18,58)),(.9,(19,-16,51)),(.97,(19,-16,51)),(durations['Grenade'],ready['RightHandBone'][0])],t)
    q=qright.slerp(aim_q,curve([(0,0),(.23,1),(.98,1),(durations['Grenade'],0)],t));q=Quaternion((0,1,0),math.radians(curve([(0,0),(.28,-45),(.62,-45),(.9,0),(durations['Grenade'],0)],t)))@q
    arm(p,'Right',target,Vector((-7,-9,45)),q)
    return p

def die(t):
    # Preserve the game's weight and ground contact rather than invent a fall.
    p=sample_clip(clips['Die'],t/1.2*clips['Die']['duration'],rest,native)
    chest_delta=p['ChestBone'][1]@ready['ChestBone'][1].inverted();p['Head']=[p['ChestBone'][0]+chest_delta@(ready['Head'][0]-ready['ChestBone'][0]),chest_delta@ready['Head'][1]]
    u=smooth((t-.58)/.62)
    # Complete the retargeted fall: the original final tilt left the back
    # unsupported even though a boot reached the floor. Settle the spine onto
    # the horizontal plane before laying the hands and weapons beside him.
    axis=p['Head'][0]-p['HipBone'][0];flat=Vector((axis.x,axis.y,0))
    if flat.length>1e-5:rotate_pose(p,native,p['HipBone'][0].copy(),Quaternion().slerp(axis.rotation_difference(flat),u))
    for side,goal in [('Left',Quaternion((1,0,0),math.pi/2)@qleft),('Right',Quaternion((1,0,0),math.pi/2)@aim_q)]:
        hand=side+'HandBone';origin=p[hand][0].copy();q=p[hand][1].slerp(goal,u);delta=q@p[hand][1].inverted();rotate_pose(p,[n for n in native if n.startswith(side) and any(k in n for k in ('HandBone','FingerBone','ThumbBone'))],origin,delta)
    return p

def place_feet(pose):
    for side in ('Left','Right'):
        n=side+'FootBone';low=pose[n][0].z+min((pose[n][1]@v).z for v in foot_offsets[side])
        if low<ground+.002:
            target=pose[n][0].copy();target.z+=ground+.002-low;leg_errors.append(solve_leg(pose,side,target,pose[side+'ShinBone'][0],rest))
    return pose

def body_floor(pose):
    return min(sum(weight*(pose[n][0]+pose[n][1]@(v-rest[n])).z for n,weight in weights) for v,weights in source_vertices)

FPS=120;durations={'Idle0':2.5,'Idle1':2.5,'Idle2':2.5,'Move':clips['Move']['duration'],'MoveBegin':1/3,'MoveEnd':1/3,'Attack':3.,'Melee':1.5,'MeleeDefense':1.5,'Charge':1.5,'ChargeDefense':1.5,'Grenade':clips['Grenade']['duration'],'Shout':2.,'Die':1.2}
descriptions={'Idle0':'Forward-ready breathing loop','Idle1':'Ready stance, scan left and return','Idle2':'Ready stance, scan right and return','Move':'Native officer gait with fitted forward-ready arms','MoveBegin':'Ready-to-walk transition','MoveEnd':'Walk-to-ready transition','Attack':'One-handed laspistol aim, seven timed recoil pulses, recovery','Melee':'Chainsword anticipation, overhead cut, follow-through, recovery','MeleeDefense':'Raised chainsword parry and return','Charge':'Native charge stance with forward chainsword threat','ChargeDefense':'Native brace with raised chainsword guard','Grenade':'Overhand grenade throw with timed forward release and recovery','Shout':'Officer command gesture and recovery','Die':'Native officer fall retimed to 1.2 seconds'}
def evaluate(suffix,t):
    if suffix.startswith('Idle'):return idle(t,durations[suffix],int(suffix[-1]))
    if suffix=='Move':return walk(t)
    if suffix=='MoveBegin':return blend_pose(ready,walk(0),t/durations[suffix])
    if suffix=='MoveEnd':return blend_pose(walk(0),ready,t/durations[suffix])
    if suffix=='Attack':return fire(t)
    if suffix in ('Melee','MeleeDefense'):return sword_attack(t,suffix.endswith('Defense'))
    if suffix in ('Charge','ChargeDefense'):return charge(t,suffix.endswith('Defense'))
    if suffix=='Shout':return command(t)
    if suffix=='Grenade':return grenade(t)
    if suffix=='Die':return die(t)
    raise ValueError(suffix)

# Maps and materials stay verbatim. The mesh changes only sleeve skin weights.
frozen={}
for category in ('Video/Meshes','Video/Textures','Video/Materials'):
    for source_file in (OLD/category).rglob('*'):
        if source_file.is_file():
            relative=source_file.relative_to(OLD);target=D/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source_file,target);frozen[relative.as_posix()]=sha(target)
mesh=D/'Video/Meshes/Units/Foundry/ImperialOfficerGuardsman.msh';refined,records=refine_native_weights(mesh.read_bytes(),weight_changes);mesh.write_bytes(refined);skinning['native_records_refined']=records;frozen[mesh.relative_to(D).as_posix()]=sha(mesh)
an=D/'Video/Animations/Units/Foundry';an.mkdir(parents=True,exist_ok=True);report={}
for suffix,duration in durations.items():
    fps=240 if suffix=='Attack' else FPS;frames=round(duration*fps)+1;poses=[]
    for i in range(frames):
        t=i/fps;p=evaluate(suffix,t)
        if suffix not in ('Move','MoveBegin','MoveEnd') and not suffix.startswith('Idle'):
            envelope=curve([(0,0),(.13,1),(duration-.17,1),(duration,0 if suffix!='Die' else 1)],t)
            p=blend_pose(ready,p,envelope)
        if suffix!='Die':p=place_feet(p)
        else:
            low=body_floor(p)
            for key,objname in [('sword','Chainsword'),('pistol','PrimarisPsykerLaspistol')]:
                hand=attachment[key]['body_hand'];matrix=binds[attachment[key]['bone']];low=min(low,min((p[hand][0]+p[hand][1]@(matrix@v.co-rest[hand])).z for v in bpy.data.objects[objname].data.vertices))
            lift=max(0.,ground+.002-low)
            for n in native:p[n][0].z+=lift
        poses.append(p)
    if suffix.startswith('Idle') or suffix=='Move':poses[-1]=clone(poses[0])
    path=an/('ImperialOfficerGuardsman'+suffix+'.anm');row=write_clip(path,poses,rest,binds,attachment,names,fps);assert read_animation(path.read_bytes())['frames']==frames
    row['description']=descriptions[suffix];row['source_motion']='Ready and arm performance authored for this officer' if suffix not in ('Move','Charge','ChargeDefense','Die') else 'Existing game motion fitted to the accepted officer; original source provenance retained';report[suffix]=row
    action,_=g._load_anm_to_rig(str(path),rig,unit_name='Officer',anim_type=suffix);action.name='Officer | '+descriptions[suffix];action.use_fake_user=True;action['officer_native_clip']=suffix
    track=rig.animation_data.nla_tracks.new();track.name='Officer animation | '+suffix;track.mute=True;track.strips.new(action.name,0,action)
    print('OFFICER_CLIP_AUTHORED',suffix,frames,'frames',flush=True)
assert max(arm_errors)<.0001,max(arm_errors)
from officer_unit_binding import bind_officer_unit,gameplay_signature
snapshot=A/'Officer-before-integration.xml'
if not snapshot.exists():snapshot.write_bytes(Path(r'C:/GITS/Gladius-Eternal-War-Foundry/2525618649/Data/World/Units/AstraMilitarum/Officer.xml').read_bytes())
prior=snapshot.read_bytes();unit=bind_officer_unit(prior);target=D/'World/Units/AstraMilitarum/Officer.xml';target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(unit);assert gameplay_signature(E.fromstring(prior))==gameplay_signature(E.fromstring(unit))
s.frame_start=0;s.frame_end=150;idle_action=next(a for a in bpy.data.actions if a.get('officer_native_clip')=='Idle0');g._set_direct_animation(rig,idle_action);s.frame_set(0);s.timeline_markers.clear()
for name,time in [('Ready loop',0),('Pistol first shot',.4),('Chainsword impact',.52)]:s.timeline_markers.new(name,frame=round(time*60))
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(A/'Officer-Animations.blend'),compress=True)
result={'status':'authored; independent native verification pending','model_appearance_user_accepted':True,'source_model_sha256':source_hash,'animation_source_sha256':sha(A/'Officer-Animations.blend'),'approved_geometry_materials_bind_frames_unchanged':True,'skinning_refinement':skinning,'attachments':attachment,'frozen_asset_sha256':frozen,'original_bones':28,'weapon_sockets':2,'clips':report,'pistol_frame':pistol_frame,'ground_reference_Z':ground,'source_motion_sha256':{n:c['sha256'] for n,c in clips.items()},'maximum_arm_length_error':max(arm_errors),'maximum_leg_length_error':max(leg_errors,default=0),'integration_baseline_xml_sha256':hashlib.sha256(prior).hexdigest(),'unit_xml_sha256':sha(target),'gameplay_preserved':True,'events':{'Attack':{'shots':[.4,.75,1.1,1.45,1.8,2.15,2.5],'beginFire':.4,'endFire':2.53},'Melee':{'beginSwing':.30,'impact':.52,'endSwing':.70},'MeleeDefense':{'beginSwing':.20,'endSwing':.55},'Grenade':{'release':.9}},'installed':False,'published':False}
(A/'animation-build.json').write_text(json.dumps(result,indent=2));(O/'ANIMATION_BUILD.json').write_text(json.dumps(result,indent=2));assert sha(source)==source_hash;print('OFFICER_ANIMATION_SET_STAGED',len(report),'clips;',max(arm_errors),'arm length error',flush=True)
