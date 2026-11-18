"""Rebuild officer motion around physical wrists and guided two-bone arms."""
from pathlib import Path
import bpy,sys,json,math,hashlib,shutil,importlib.util,os
from mathutils import Vector,Matrix,Quaternion
R=Path(__file__).resolve().parents[1];A=R/'model-workbench/Imperial-Officer/animation-production';B=A/'accepted-model';PILOT='--pilot' in sys.argv;OUT=A/'arm-rebuild' if PILOT else A;D=(OUT/'Data') if PILOT else R/'assets/imperial-officer-animated/Data';G=Path(os.environ.get('GLADIUS_DATA',r'C:/Program Files (x86)/Steam/steamapps/common/Warhammer 40000 Gladius - Relics of War/Data'))
sys.path.insert(0,str(R/'tools'))
from officer_animation import read_clip,sample_clip,clone,curve,smooth,vector_curve,frame,rotate_pose,write_clip,solve_leg
from officer_arm_pose import measure_hands,fit_pistol,ArmController,anatomical_sleeves,export_refitted_mesh
from officer_unit_binding import bind_officer_unit
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    OUT.mkdir(parents=True,exist_ok=True);build=json.loads((B/'body-build.json').read_text());source=B/'Officer-Accepted-Model.blend';bpy.ops.wm.open_mainfile(filepath=str(source));s=bpy.context.scene;s.render.fps=60;rig=bpy.data.objects['Guardsman_rig'];names=build['bone_order'];native=names[:28];rest={n:rig.data.bones[n].head_local.copy() for n in names};binds={n:Matrix([rig.data.bones[n]['gladius_source_bind'][i:i+4] for i in range(0,16,4)]) for n in names};objects=[bpy.data.objects[n] for n in build['body_objects']];regions=json.loads((B/'sleeve-regions.json').read_text());weights={}
    hands,moved=measure_hands({side:bpy.data.objects['Officer '+side+' closed weapon fist'] for side in ('Left','Right')},build['attachments']);attachment=build['attachments']
    pistol=bpy.data.objects['PrimarisPsykerLaspistol'];v=pistol.parent.data.bones['Muzzle0']['gladius_source_bind'];muzzle=Matrix([v[i:i+4] for i in range(0,16,4)]);forward=muzzle.col[0].xyz.normalized();up=muzzle.translation-Vector(attachment['pistol']['local_grip']);up=(up-forward*up.dot(forward)).normalized();fit_pistol(attachment['pistol'],hands['Right'],forward,up)
    spec=importlib.util.spec_from_file_location('officer_anatomical_import',R/'references/import_gladius.py');g=importlib.util.module_from_spec(spec);sys.modules[spec.name]=g;spec.loader.exec_module(g)
    bpy.context.view_layer.objects.active=rig;rig.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
    for a in attachment.values():
        n=a['bone'];matrix=Matrix(a['anchor_bind']);pivot=rig.data.edit_bones[n+'_pivot'];offset=pivot.tail-pivot.head;pivot.head=matrix.translation;pivot.tail=matrix.translation+offset;rig.data.edit_bones[n].matrix=g._rest_matrix_from_bind(matrix)
    bpy.ops.object.mode_set(mode='OBJECT')
    for key,objname in [('pistol','PrimarisPsykerLaspistol'),('sword','Chainsword')]:
        a=attachment[key];n=a['bone'];matrix=Matrix(a['anchor_bind']);bone=rig.data.bones[n];bone['gladius_source_bind']=[c for row in matrix for c in row];rest[n]=bone.head_local.copy();binds[n]=matrix;weapon_rig=bpy.data.objects[objname].parent;g._attach_to_bone_bind(weapon_rig,rig,bone)
    arm_weights,skin_report=anatomical_sleeves(objects,rest,hands,regions);weights.update(arm_weights)
    armhole_changes={}
    for ob in objects:ob.data.update()
    for suffix in ('Idle0','Move'):
        target=B/'reference-motion'/('Guard'+suffix+'.anm')
        if not target.exists():shutil.copy2(G/('Video/Animations/Units/AstraMilitarum/Guardsman'+suffix+'.anm'),target)
    guard={suffix:read_clip(B/'reference-motion'/('Guard'+suffix+'.anm')) for suffix in ('Idle0','Move')};old={suffix:read_clip(B/'reference-motion'/(suffix+'.anm')) for suffix in ('Charge','ChargeDefense','Die')}
    controller=ArmController(rest,hands);upper_names=[n for n in native if n in ('ChestBone','Head') or any(k in n for k in ('Soulder','Shoulder','ArmBone','HandBone','FingerBone','ThumbBone'))]
    def chest_assembly(p):
        cp,cq=p['ChestBone'][0].copy(),p['ChestBone'][1].copy()
        for n in upper_names:p[n]=[cp+cq@(rest[n]-rest['ChestBone']),cq.copy()]
        return p
    ready=chest_assembly(sample_clip(guard['Idle0'],0,rest,native));chest=ready['ChestBone'][0].copy();chest_q=ready['ChestBone'][1].copy();ready_q={}
    sword_frame=attachment['sword']['grip_placement']['grip_frame'];left_q=(frame((1,0,0),(0,0,1))@frame(Vector(sword_frame['shaft_axis_hand_rest']),Vector(sword_frame['thumb_side_hand_rest'])).transposed()).to_quaternion()
    for side in ('Left','Right'):
        sign=1 if side=='Left' else -1;shoulder=ready[side+'UpperArmBone'][0];l1=(rest[side+'LowerArmBone']-rest[side+'UpperArmBone']).length;l2=(hands[side]['cuff']-rest[side+'LowerArmBone']).length
        direction_upper=Vector((1.,-.05,-.45)) if side=='Left' else Vector((.06,-.35,-1.));elbow=shoulder+direction_upper.normalized()*l1
        if side=='Left':q=left_q;direction=q@hands[side]['forward']
        else:direction=Vector((.08,-.25,-1)).normalized();q=(frame(direction,(1,0,0))@frame(hands[side]['forward'],hands[side]['thumb']).transposed()).to_quaternion()
        target=elbow+direction*l2;pole=shoulder+Vector((-5,-3,-15)) if side=='Right' else elbow;controller.solve(ready,side,target,pole,q);ready_q[side]=ready[side+'HandBone'][1].copy()
    def cuff(p,side):return p[side+'HandBone'][0]+p[side+'HandBone'][1]@(hands[side]['cuff']-rest[side+'HandBone'])
    ready_cuffs={side:cuff(ready,side) for side in ('Left','Right')};ready_elbows={side:ready[side+'LowerArmBone'][0].copy() for side in ('Left','Right')}
    ready_left_upper=(ready_elbows['Left']-ready['LeftUpperArmBone'][0]).normalized()
    def follow_ready(p):
        delta=p['ChestBone'][1]@chest_q.inverted();origin=p['ChestBone'][0]
        for side in ('Left','Right'):controller.solve(p,side,origin+delta@(ready_cuffs[side]-chest),origin+delta@(ready_elbows[side]-chest),delta@ready_q[side])
        return p
    def upper_body(p,yaw=0,pitch=0):
        q=Quaternion((0,0,1),math.radians(yaw))@Quaternion((0,1,0),math.radians(pitch));rotate_pose(p,['AbdomenBone']+upper_names,p['AbdomenBone'][0],q);return q
    aim_q=(frame((1,0,0),(0,0,1))@frame(hands['Right']['forward'],hands['Right']['thumb']).transposed()).to_quaternion()
    def idle(t,duration,variant=0):
        p=clone(ready);cycle=2*math.pi*t/duration;upper_body(p,0,.15*math.sin(cycle));p['Head'][1]=Quaternion((0,0,1),math.radians((0 if not variant else 9 if variant==1 else -9)*math.sin(math.pi*t/duration)**2))@p['Head'][1];return p
    def walk(t):
        p=chest_assembly(sample_clip(guard['Move'],t,rest,native));delta=p['ChestBone'][1]@chest_q.inverted();origin=p['ChestBone'][0];phase=t/guard['Move']['duration']*2*math.pi
        for side,sign in [('Left',1),('Right',-1)]:
            offset=Vector(((.25 if side=='Left' else .60)*sign*math.sin(phase),0,.08*(1-math.cos(phase))));controller.solve(p,side,origin+delta@(ready_cuffs[side]-chest+offset),origin+delta@(ready_elbows[side]-chest),delta@ready_q[side])
        return p
    def blend(a,b,u):
        u=smooth(u);p={n:[a[n][0].lerp(b[n][0],u),a[n][1].slerp(b[n][1],u)] for n in native}
        for side in ('Left','Right'):
            target=cuff(a,side).lerp(cuff(b,side),u);pole=a[side+'LowerArmBone'][0].lerp(b[side+'LowerArmBone'][0],u);q=a[side+'HandBone'][1].slerp(b[side+'HandBone'][1],u);controller.solve(p,side,target,pole,q);solve_leg(p,side,p[side+'FootBone'][0].copy(),p[side+'ShinBone'][0].copy(),rest)
        return p
    def fire(t):
        p=clone(ready);u=curve([(0,0),(.36,1),(2.55,1),(3,0)],t);recoil=0.
        for shot in (.4,.75,1.1,1.45,1.8,2.15,2.5):
            d=t-shot
            if 0<=d<.24:recoil+=math.sin(min(1,d/.035)*math.pi/2)*math.exp(-max(0,d-.035)/.065)
        shoulder=p['RightUpperArmBone'][0];length=(rest['RightLowerArmBone']-rest['RightUpperArmBone']).length+(hands['Right']['cuff']-rest['RightLowerArmBone']).length;aim=shoulder+Vector((length-.55,-1.45,-1.0));start=ready_cuffs['Right']-shoulder;end=aim-shoulder;arc=Quaternion().slerp(start.rotation_difference(end),u);target=shoulder+(arc@start.normalized())*(start.length*(1-u)+end.length*u)+Vector((-.34*recoil,-.6*math.sin(math.pi*u),.08*recoil));q=ready_q['Right'].slerp(aim_q,u);q=Quaternion((0,1,0),math.radians(-2.8*recoil))@q;controller.solve(p,'Right',target,shoulder+arc@(ready_elbows['Right']-shoulder),q);return p
    def sword(t,defense=False):
        p=clone(ready);shoulder=ready['LeftUpperArmBone'][0]
        if defense:
            u=curve([(0,0),(.25,1),(.65,1),(1.5,0)],t);angle=-32*u;yaw=3*u;upper_direction=ready_left_upper.lerp(Vector((.85,.05,.38)).normalized(),u).normalized()
        else:
            upper_direction=vector_curve([(0,ready_left_upper),(.24,(.84,.0,.45)),(.31,(.84,.0,.45)),(.58,(.95,-.05,-.28)),(.77,(.72,-.05,-.60)),(.91,(.72,-.05,-.60)),(1.5,ready_left_upper)],t).normalized();angle=curve([(0,0),(.24,-55),(.31,-55),(.58,30),(.77,52),(.91,52),(1.5,0)],t);yaw=curve([(0,0),(.24,8),(.58,-10),(.77,-12),(1.5,0)],t)
            u=curve([(0,0),(.24,1),(.91,1),(1.5,0)],t)
        hand_q=Quaternion((0,1,0),math.radians(angle))@ready_q['Left'];l1=(rest['LeftLowerArmBone']-rest['LeftUpperArmBone']).length;l2=(hands['Left']['cuff']-rest['LeftLowerArmBone']).length;pole=shoulder+upper_direction*l1;target=pole+(hand_q@hands['Left']['forward'])*l2;pivot=p['AbdomenBone'][0].copy();qb=upper_body(p,yaw);controller.solve(p,'Left',pivot+qb@(target-pivot),pivot+qb@(pole-pivot),qb@hand_q);return p
    def charge(t,defense=False):
        p=clone(ready);u=curve([(0,0),(.35,1),(.85,1),(1.5,0)],t);feet={side:ready[side+'FootBone'][0]+Vector(((3 if side=='Left' else -1.5)*u,0,0)) for side in ('Left','Right')}
        for n in native:
            if not n.endswith('FootBone'):p[n][0]+=Vector((2*u,0,-.7*u))
        for side in ('Left','Right'):solve_leg(p,side,feet[side],p[side+'ShinBone'][0]+Vector((4,0,0)),rest)
        upper_body(p,(-2 if defense else -4)*u,(8 if defense else 14)*u);return p
    def command(t):
        p=clone(ready);u=curve([(0,0),(.4,1),(1.3,1),(2,0)],t);controller.solve(p,'Left',ready_cuffs['Left']+Vector((2*u,0,4*u)),ready_elbows['Left']+Vector((u,2*u,0)),Quaternion((0,1,0),math.radians(-18*u))@ready_q['Left']);return p
    def grenade(t):
        p=clone(ready);root=p['RightUpperArmBone'][0];upper0=(ready_elbows['Right']-root).normalized();lower0=(ready_cuffs['Right']-ready_elbows['Right']).normalized();upper1=Vector((.85,-.30,.30)).normalized();lower1=Vector((-.80,-.10,.60)).normalized();upper2=Vector((.90,-.12,-.35)).normalized();lower2=Vector((1.,-.04,.10)).normalized();turn1=lower0.rotation_difference(lower1);turn2=lower1.rotation_difference(lower2);q1=turn1@ready_q['Right'];q2=turn2@q1
        def arc(a,b,u):return Quaternion().slerp(a.rotation_difference(b),u)@a
        if t<.32:u=smooth(t/.32);upper=arc(upper0,upper1,u);lower=arc(lower0,lower1,u);q=ready_q['Right'].slerp(q1,u)
        elif t<.56:upper=upper1;lower=lower1;q=q1
        elif t<.90:u=smooth((t-.56)/.34);upper=arc(upper1,upper2,u);lower=arc(lower1,lower2,u);q=q1.slerp(q2,u)
        else:u=smooth((t-.90)/(7/6-.90));upper=arc(upper2,upper0,u);lower=arc(lower2,lower0,u);q=q2.slerp(ready_q['Right'],u)
        l1=(rest['RightLowerArmBone']-rest['RightUpperArmBone']).length;l2=(hands['Right']['cuff']-rest['RightLowerArmBone']).length;elbow=root+upper*l1;controller.solve(p,'Right',elbow+lower*l2,elbow,q);return p
    def death(t):
        p=sample_clip(old['Die'],t/1.2*old['Die']['duration'],rest,native)
        for parent,child in [('HipBone','AbdomenBone'),('AbdomenBone','ChestBone')]:p[child][0]=p[parent][0]+p[parent][1]@(rest[child]-rest[parent])
        p=follow_ready(chest_assembly(p));u=smooth((t-.58)/.62);axis=p['Head'][0]-p['HipBone'][0];flat=Vector((axis.x,axis.y,0))
        if flat.length>1e-5:rotate_pose(p,native,p['HipBone'][0].copy(),Quaternion().slerp(axis.rotation_difference(flat),u))
        for side,sign in [('Left',1),('Right',-1)]:
            root=p[side+'UpperArmBone'][0];l1=(rest[side+'LowerArmBone']-rest[side+'UpperArmBone']).length;l2=(hands[side]['cuff']-rest[side+'LowerArmBone']).length;end_elbow=root+Vector((.2,sign*.8,-.15)).normalized()*l1;direction=Vector((.93,sign*.25,0)).normalized();end_wrist=end_elbow+direction*l2;qend=(frame(direction,(0,sign,0))@frame(hands[side]['forward'],hands[side]['thumb']).transposed()).to_quaternion();controller.solve(p,side,cuff(p,side).lerp(end_wrist,u),p[side+'LowerArmBone'][0].lerp(end_elbow,u),p[side+'HandBone'][1].slerp(qend,u))
        return p
    durations={'Idle0':2.5,'Idle1':2.5,'Idle2':2.5,'Move':guard['Move']['duration'],'MoveBegin':1/3,'MoveEnd':1/3,'Attack':3.,'Melee':1.5,'MeleeDefense':1.5,'Charge':1.5,'ChargeDefense':1.5,'Grenade':7/6,'Shout':2.,'Die':1.2};descriptions={'Idle0':'Natural ready breathing','Idle1':'Ready scan left','Idle2':'Ready scan right','Move':'Native Guardsman gait with chest-relative guided arms','MoveBegin':'Enter walk','MoveEnd':'Return to ready','Attack':'Straight-wrist pistol aim, recoil and recovery','Melee':'Guided chainsword overhead cut and recovery','MeleeDefense':'Natural chainsword parry','Charge':'Forward chainsword charge','ChargeDefense':'Raised chainsword brace','Grenade':'Guided overhand throw','Shout':'Officer command gesture','Die':'Supported fall with relaxed arms beside body'}
    def evaluate(suffix,t):
        if suffix.startswith('Idle'):return idle(t,durations[suffix],int(suffix[-1]))
        if suffix=='Move':return walk(t)
        if suffix=='MoveBegin':return blend(ready,walk(0),t/durations[suffix])
        if suffix=='MoveEnd':return blend(walk(0),ready,t/durations[suffix])
        if suffix=='Attack':return fire(t)
        if suffix in ('Melee','MeleeDefense'):return sword(t,suffix.endswith('Defense'))
        if suffix in ('Charge','ChargeDefense'):return charge(t,suffix.endswith('Defense'))
        if suffix=='Shout':return command(t)
        if suffix=='Grenade':return grenade(t)
        if suffix=='Die':return death(t)
        raise ValueError(suffix)
    source_vertices=[(v.co.copy(),[(ob.vertex_groups[g.group].name,g.weight) for g in v.groups if g.weight>1e-6]) for ob in objects for v in ob.data.vertices];ground=min(v.z for v,weights_ in source_vertices);foot_offsets={side:[v-rest[side+'FootBone'] for v,ws in source_vertices if sum(w for n,w in ws if n==side+'FootBone')>.98] for side in ('Left','Right')}
    frozen={}
    for category in ('Video/Meshes','Video/Materials','Video/Textures'):
        for src in (B/'Data'/category).rglob('*'):
            if src.is_file():target=D/src.relative_to(B/'Data');target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,target);frozen[target.relative_to(D).as_posix()]=sha(target)
    mesh=D/'Video/Meshes/Units/Foundry/ImperialOfficerGuardsman.msh';mesh.write_bytes(export_refitted_mesh(mesh.read_bytes(),weights,moved,attachment));frozen[mesh.relative_to(D).as_posix()]=sha(mesh)
    an=D/'Video/Animations/Units/Foundry';an.mkdir(parents=True,exist_ok=True);report={};selection=['Idle0','Move','Attack'] if PILOT and '--all-clips' not in sys.argv else list(durations)
    for suffix in selection:
        duration=durations[suffix];fps=240 if suffix in ('Attack','Grenade') else 120;poses=[]
        for i in range(round(duration*fps)+1):
            t=i/fps;p=evaluate(suffix,t)
            if suffix=='Die':
                envelope=curve([(0,0),(.12,1),(duration-.15,1),(duration,0 if suffix!='Die' else 1)],t);p=blend(ready,p,envelope)
            if suffix!='Die':
                for side in ('Left','Right'):
                    n=side+'FootBone';low=p[n][0].z+min((p[n][1]@v).z for v in foot_offsets[side])
                    if low<ground+.002:
                        goal=p[n][0].copy();goal.z+=ground+.002-low;solve_leg(p,side,goal,p[side+'ShinBone'][0],rest)
            else:
                low=min(sum(weight*(p[n][0]+p[n][1]@(v-rest[n])).z for n,weight in ws) for v,ws in source_vertices)
                for key,objname in [('sword','Chainsword'),('pistol','PrimarisPsykerLaspistol')]:
                    hand=attachment[key]['body_hand'];matrix=binds[attachment[key]['bone']];low=min(low,min((p[hand][0]+p[hand][1]@(matrix@v.co-rest[hand])).z for v in bpy.data.objects[objname].data.vertices))
                for n in native:p[n][0].z+=max(0.,ground+.002-low)
            poses.append(p)
        if suffix.startswith('Idle') or suffix=='Move':poses[-1]=clone(poses[0])
        path=an/('ImperialOfficerGuardsman'+suffix+'.anm');row=write_clip(path,poses,rest,binds,attachment,names,fps);row['description']=descriptions[suffix];report[suffix]=row;action,_=g._load_anm_to_rig(str(path),rig,unit_name='Officer',anim_type=suffix);action.name='Officer | '+descriptions[suffix];action['officer_native_clip']=suffix;action.use_fake_user=True;track=rig.animation_data.nla_tracks.new();track.name='Officer library | '+suffix;track.mute=True;track.strips.new(action.name,0,action)
        print('ANATOMICAL_OFFICER_CLIP',suffix,len(poses),flush=True)
    unit=D/'World/Units/AstraMilitarum/Officer.xml';unit.parent.mkdir(parents=True,exist_ok=True);unit.write_bytes(bind_officer_unit((A/'Officer-before-integration.xml').read_bytes()));g._set_direct_animation(rig,next(a for a in bpy.data.actions if a.get('officer_native_clip')=='Idle0'));s.frame_set(0);s.frame_start=0;s.frame_end=150;bpy.ops.file.pack_all();source_out=OUT/('Officer-Arm-Pilot.blend' if PILOT else 'Officer-Animations.blend');bpy.ops.wm.save_as_mainfile(filepath=str(source_out),compress=True)
    anatomy={side:{'cuff_center':list(h['cuff']),'palm_center':list(h['palm_center']),'palm_forward':list(h['forward']),'thumb_direction':list(h['thumb']),'cuff_vertices':h['cuff_ids']} for side,h in hands.items()};pistol_frame={'native_grip':attachment['pistol']['local_grip'],'native_muzzle':list(muzzle.translation),'native_forward':list(forward),'native_barrel_up':list(up),'up_definition':'Measured actual barrel and grip; socket fitted to the anatomical hand frame'}
    result={'status':'pilot; visual/anatomical verification pending' if PILOT else 'rebuilt; independent verification pending','source_file':source_out.name,'source_model_sha256':sha(source),'animation_source_sha256':sha(source_out),'frozen_asset_sha256':frozen,'clips':report,'attachments':attachment,'pistol_frame':pistol_frame,'hand_anatomy':anatomy,'skinning_refinement':skin_report,'original_bones':28,'weapon_sockets':2,'original_bind_frames_preserved':28,'geometry_change':'Accepted Guardsman-derived geometry, topology, shading, UVs and maps retained at 892 triangles','armhole_vertex_changes':armhole_changes,'ground_reference_Z':ground,'unit_xml_sha256':sha(unit),'gameplay_preserved':True,'maximum_authored_wrist_bend_degrees':max(m['wrist_bend_degrees'] for m in controller.metrics),'maximum_physical_arm_length_error':max(m['length_error'] for m in controller.metrics),'minimum_elbow_pole_alignment':min(m['pole_alignment'] for m in controller.metrics),'installed':False,'published':False};(OUT/'animation-build.json').write_text(json.dumps(result,indent=2));(OUT/'hand-anatomy.json').write_text(json.dumps(anatomy,indent=2));(OUT/'pistol-frame.json').write_text(json.dumps(pistol_frame,indent=2))
    if not PILOT:(D.parent/'ANIMATION_BUILD.json').write_text(json.dumps(result,indent=2))
    print('ANATOMICAL_ARMS_STAGED',result['maximum_authored_wrist_bend_degrees'],result['maximum_physical_arm_length_error'],flush=True)

if __name__=='__main__':main()
