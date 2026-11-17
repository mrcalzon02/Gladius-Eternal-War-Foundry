"""Independently inspect the staged MSH/DDS/XML/ANM officer and its motion."""
from pathlib import Path
from types import SimpleNamespace
import bpy,sys,json,math,hashlib,importlib.util,xml.etree.ElementTree as E,os
from mathutils import Vector
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];A=R/'model-workbench/Imperial-Officer/animation-production';W=A/'accepted-model';O=R/'assets/imperial-officer-animated';D=O/'Data';G=Path(os.environ.get('GLADIUS_DATA',r'C:/Program Files (x86)/Steam/steamapps/common/Warhammer 40000 Gladius - Relics of War/Data'))
sys.path.insert(0,str(R/'tools'));from native_gladius import read_mesh,read_animation
from officer_animation import read_clip
from officer_unit_binding import gameplay_signature
from officer_triangle_intersections import _intersect
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();build=json.loads((A/'animation-build.json').read_text());body_build=json.loads((W/'body-build.json').read_text())
for relative,digest in build['frozen_asset_sha256'].items():assert sha(D/relative)==digest,relative
assert sha(A/'Officer-Animations.blend')==build['animation_source_sha256']
bpy.ops.wm.open_mainfile(filepath=str(A/'Officer-Animations.blend'))
source_actions=[a for a in bpy.data.actions if a.get('officer_native_clip')];assert {a['officer_native_clip'] for a in source_actions}==set(build['clips'])
hand_positions={side:{tuple(round(c,4) for c in p.co) for p in bpy.data.objects['Officer '+side+' closed weapon fist'].data.vertices} for side in ('Left','Right')}
for im in bpy.data.images:
    if im.source=='FILE':
        _=im.pixels[0];assert im.packed_file and im.has_data,im.name
bpy.ops.wm.read_factory_settings(use_empty=True)
spec=importlib.util.spec_from_file_location('officer_production_reimport',R/'references/import_gladius.py');g=importlib.util.module_from_spec(spec);sys.modules[spec.name]=g;spec.loader.exec_module(g);oldroots=g._source_roots_for_xml;g._source_roots_for_xml=lambda p,prefs:list(dict.fromkeys(oldroots(p,prefs)+[str(G)]));messages=[]
saved=g._import_animation_specs;g._import_animation_specs=lambda *a,**k:({},[],0.)
op=SimpleNamespace(filepath=str(D/'World/Units/AstraMilitarum/Officer.xml'),frame_viewport=False,scale_preset='FULL',report=lambda *args:messages.append(str(args)))
assert g.ImportGladiusUnitFromXml.execute(op,bpy.context)=={'FINISHED'},messages;g._import_animation_specs=saved
s=bpy.context.scene;s.render.fps=60;s.render.fps_base=1;rig=bpy.data.objects['ImperialOfficerGuardsman_rig'];body=bpy.data.objects['ImperialOfficerGuardsman'];sword=bpy.data.objects['Chainsword'];pistol=bpy.data.objects['PrimarisPsykerLaspistol'];parts={'sword':sword,'pistol':pistol};rest=[v.co.copy() for v in body.data.vertices]
is_hand=lambda p,side:all(tuple(round(c,4) for c in rest[i]) in hand_positions[side] for i in p.vertices)
hand_faces={side:[tuple(p.vertices) for p in body.data.polygons if is_hand(p,side)] for side in ('Left','Right')};outside_hand={side:[tuple(p.vertices) for p in body.data.polygons if not is_hand(p,side)] for side in ('Left','Right')}
edges=[(e.vertices[0],e.vertices[1],(rest[e.vertices[0]]-rest[e.vertices[1]]).length) for e in body.data.edges if (rest[e.vertices[0]]-rest[e.vertices[1]]).length>.15]
assert len(hand_faces['Left'])==98 and len(hand_faces['Right'])==56
metrics=read_mesh((D/'Video/Meshes/Units/Foundry/ImperialOfficerGuardsman.msh').read_bytes());assert metrics['triangles']==892 and metrics['bones']==body_build['bone_order']
actions={};native_clips={}
for suffix,row in build['clips'].items():
    path=D/('Video/Animations/Units/Foundry/ImperialOfficerGuardsman'+suffix+'.anm');assert sha(path)==row['sha256'];parsed=read_animation(path.read_bytes());assert parsed['bones']==metrics['bones'];native_clips[suffix]=read_clip(path)
    actions[suffix],_=g._load_anm_to_rig(str(path),rig,unit_name='Production Officer',anim_type=suffix)
root=E.parse(D/'World/Units/AstraMilitarum/Officer.xml').getroot();assert gameplay_signature(root)==gameplay_signature(E.parse(A/'Officer-before-integration.xml').getroot())
references=[]
for el in root.iter():
    for key,value in el.attrib.items():
        if key.endswith('Animation') or key=='animation':
            if not value.startswith('Units/Foundry/ImperialOfficerGuardsman'):continue
            resources=[value+str(i) for i in range(3)] if key=='idleAnimation' else [value]
            if key=='animation' and value.endswith('GuardsmanMove'):resources.extend([value+'Begin',value+'End'])
            for resource in resources:assert (D/('Video/Animations/'+resource+'.anm')).is_file(),resource
            references.extend(resources)
entry=build['attachments'];hand_indices=sorted({i for f in hand_faces['Left'] for i in f});max_grip=0;max_hand_affine=0;poses=0;violations=[];rows={};loop_errors={}
segment_pairs=[('LeftUpperArmBone','LeftLowerArmBone'),('LeftLowerArmBone','LeftHandBone'),('RightUpperArmBone','RightLowerArmBone'),('RightLowerArmBone','RightHandBone'),('LeftHipBone','LeftShinBone'),('LeftShinBone','LeftFootBone'),('RightHipBone','RightShinBone'),('RightShinBone','RightFootBone')]
lengths={(a,b):(rig.data.bones[a].head_local-rig.data.bones[b].head_local).length for a,b in segment_pairs}
muzzle=Vector(build['pistol_frame']['native_forward']);barrel_up=Vector(build['pistol_frame']['native_barrel_up']);source_geometry_hash=sha(D/'Video/Meshes/Units/Foundry/ImperialOfficerGuardsman.msh')
body_face_bones={}
for side,faces in outside_hand.items():
    labels=[]
    for face in faces:
        scores={}
        for i in face:
            for w in body.data.vertices[i].groups:
                n=body.vertex_groups[w.group].name;scores[n]=scores.get(n,0)+w.weight
        labels.append(max(scores,key=scores.get))
    body_face_bones[side]=labels

def activate(suffix,time):
    g._set_direct_animation(rig,actions[suffix]);frame=time*60;s.frame_set(math.floor(frame),subframe=frame%1);bpy.context.view_layer.update()

def pose_matrices():return {n:rig.pose.bones[n].matrix.copy() for n in metrics['bones']}

for suffix,clip in native_clips.items():
    activate(suffix,0);initial=pose_matrices();activate(suffix,clip['duration']);last=pose_matrices();loop_errors[suffix]=max(abs(initial[n][r][c]-last[n][r][c]) for n in metrics['bones'] for r in range(4) for c in range(4))
    if suffix.startswith('Idle') or suffix=='Move':assert loop_errors[suffix]<.0001,(suffix,loop_errors[suffix])
    # Check every native sample, plus half-sample times through the fastest
    # attack interval. Numerical checks use actual imported native animation.
    times={i/clip['fps'] for i in range(clip['frames'])}
    if suffix in ('Attack','Melee','MeleeDefense'):times.update((i+.5)/clip['fps'] for i in range(clip['frames']-1))
    row={'poses':len(times),'minimum_body_Z':1e9,'minimum_sword_Z':1e9,'maximum_edge_stretch_ratio':0.,'maximum_limb_length_relative_error':0.,'maximum_handle_error':0.,'sword_body_intersections':0,'pistol_body_intersections':0,'firing_muzzle_forward_minimum':1.,'firing_barrel_up_minimum':1.,'firing_muzzle_above_grip_minimum':1e9,'collision_body_bones':{'sword':{},'pistol':{}}}
    for t in sorted(times):
        activate(suffix,t);deps=bpy.context.evaluated_depsgraph_get();ev=body.evaluated_get(deps);wp=[body.matrix_world@v.co for v in ev.data.vertices];row['minimum_body_Z']=min(row['minimum_body_Z'],min(p.z for p in wp));poses+=1
        peak,i,j=max(((wp[i]-wp[j]).length/length,i,j) for i,j,length in edges)
        if peak>row['maximum_edge_stretch_ratio']:
            row['maximum_edge_stretch_ratio']=peak;row['peak_stretch']={'time':t,'rest_points':[list(rest[k]) for k in (i,j)],'weights':[[(body.vertex_groups[w.group].name,w.weight) for w in body.data.vertices[k].groups] for k in (i,j)]}
        for key,side in [('sword','Left'),('pistol','Right')]:
            obj=parts[key];a=entry[key];pb=rig.pose.bones[side+'HandBone'];deform=pb.matrix@rig.data.bones[side+'HandBone'].matrix_local.inverted();want=rig.matrix_world@deform@Vector(a['rest_hand_grip']);actual=obj.matrix_world@Vector(a['local_grip']);err=(want-actual).length;max_grip=max(max_grip,err);row['maximum_handle_error']=max(row['maximum_handle_error'],err)
            if key=='sword':
                affine=max((wp[i]-body.matrix_world@deform@rest[i]).length for i in hand_indices);max_hand_affine=max(max_hand_affine,affine)
            weapon_points=[obj.matrix_world@v.co for v in obj.data.vertices];faces=[tuple(p.vertices) for p in obj.data.polygons]
            if key=='sword':row['minimum_sword_Z']=min(row['minimum_sword_Z'],min(p.z for p in weapon_points))
            if suffix!='Die':
                hit=BVHTree.FromPolygons(weapon_points,faces,all_triangles=True).overlap(BVHTree.FromPolygons(wp,outside_hand[side],all_triangles=True))
                hit=[(a,b) for a,b in hit if _intersect([weapon_points[i] for i in faces[a]],[wp[i] for i in outside_hand[side][b]])]
                if hit:
                    row[key+'_body_intersections']+=len(hit)
                    for _,bi in hit:
                        bone=body_face_bones[side][bi];row['collision_body_bones'][key][bone]=row['collision_body_bones'][key].get(bone,0)+1
                    if len(violations)<160:violations.append({'clip':suffix,'time':round(t,5),'weapon':key,'face_pairs':len(hit)})
        for a,b in segment_pairs:
            length=(rig.pose.bones[a].matrix.translation-rig.pose.bones[b].matrix.translation).length;row['maximum_limb_length_relative_error']=max(row['maximum_limb_length_relative_error'],abs(length/lengths[a,b]-1))
        if suffix=='Attack' and .4<=t<=2.53:
            direction=(pistol.matrix_world.to_3x3()@muzzle).normalized();row['firing_muzzle_forward_minimum']=min(row['firing_muzzle_forward_minimum'],direction.x)
            up=(pistol.matrix_world.to_3x3()@barrel_up).normalized();row['firing_barrel_up_minimum']=min(row['firing_barrel_up_minimum'],up.z)
            height=(pistol.matrix_world@Vector(build['pistol_frame']['native_muzzle'])-pistol.matrix_world@Vector(build['pistol_frame']['native_grip'])).z;row['firing_muzzle_above_grip_minimum']=min(row['firing_muzzle_above_grip_minimum'],height)
    rows[suffix]=row;print('NATIVE_ANIMATION_CHECK',suffix,json.dumps(row),flush=True)
passed=not violations and max_grip<.006 and max_hand_affine<.0001 and rows['Attack']['firing_barrel_up_minimum']>.98 and rows['Attack']['firing_muzzle_above_grip_minimum']>1 and all(row['minimum_body_Z']>build['ground_reference_Z']-.08 and row['maximum_limb_length_relative_error']<.02 and row['maximum_edge_stretch_ratio']<2. for row in rows.values())
report={'status':'passed' if passed else 'needs repair','mesh_sha256':source_geometry_hash,'clips_tested':len(actions),'poses_tested':poses,'samples':rows,'loop_matrix_errors':loop_errors,'maximum_handle_attachment_error':max_grip,'maximum_left_hand_affine_error':max_hand_affine,'weapon_body_intersections':violations,'unit_animation_resource_references':sorted(set(references)),'geometry_materials_and_bind_frames_preserved':True,'source_blend_sha256':build['animation_source_sha256'],'gameplay_preserved':True,'images':{im.name:list(im.size) for im in bpy.data.images if im.source=='FILE'},'messages':messages,'installed':False,'published':False,'live_engine_verified':False}
(O/'ANIMATION_VERIFICATION.json').write_text(json.dumps(report,indent=2));(A/'animation-verification.json').write_text(json.dumps(report,indent=2))
if '--no-render' in sys.argv:
    assert passed,[(n,r['maximum_edge_stretch_ratio'],r['sword_body_intersections'],r['pistol_body_intersections']) for n,r in rows.items()]
    print('OFFICER_NATIVE_ANIMATIONS_VERIFIED_WITHOUT_RENDER',len(actions),poses,flush=True);sys.exit(0)

# Review the actual native export before promoting it into the mod checkout.
s.world=bpy.data.worlds.new('Officer motion studio');s.world.use_nodes=True;s.world.node_tree.nodes['Background'].inputs[0].default_value=(.09,.105,.125,1);s.world.node_tree.nodes['Background'].inputs[1].default_value=.55
for loc,power in [((90,-85,130),180000),((30,110,95),110000),((-80,0,120),150000)]:
    light=bpy.data.lights.new('Motion softbox','AREA');light.energy=power;light.size=85;o=bpy.data.objects.new(light.name,light);s.collection.objects.link(o);o.location=loc;o.rotation_euler=(Vector((0,0,34))-o.location).to_track_quat('-Z','Y').to_euler()
cam=bpy.data.objects.new('Native animation review',bpy.data.cameras.new('Native animation review'));s.collection.objects.link(cam);s.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=96;s.render.engine='CYCLES';s.cycles.samples=8;s.cycles.use_denoising=True;s.render.resolution_x=800;s.render.resolution_y=900;s.render.resolution_percentage=100;s.view_settings.view_transform='Standard'
for o in bpy.data.objects:
    if 'Bounding' in o.name:o.hide_render=True
preview=A/'native-previews';preview.mkdir(exist_ok=True)
for name,suffix,t,loc in [('ready','Idle0',0,(150,-110,88)),('walk','Move',.27,(150,-110,88)),('pistol','Attack',.45,(150,-110,88)),('wind-up','Melee',.22,(100,160,85)),('sword-strike','Melee',.52,(100,160,85)),('follow-through','Melee',.70,(100,160,85)),('parry','MeleeDefense',.4,(100,160,85)),('command','Shout',1.,(150,-110,88)),('grenade','Grenade',.90,(150,-110,88)),('death','Die',1.2,(100,140,90))]:
    activate(suffix,t);target=Vector((4,0,34));cam.data.ortho_scale=96
    if suffix=='Die':
        ev=body.evaluated_get(bpy.context.evaluated_depsgraph_get());points=[body.matrix_world@p.co for p in ev.data.vertices];target=Vector([(min(p[k] for p in points)+max(p[k] for p in points))/2 for k in range(3)]);loc=target+Vector((100,140,90));cam.data.ortho_scale=110
    cam.location=loc;cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();s.render.filepath=str(preview/(name+'.png'));bpy.ops.render.render(write_still=True)
activate('Idle0',0);s.frame_start=0;s.frame_end=150;bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(A/'Officer-Native-Animation-Review.blend'),compress=True)
report['native_review_blend_sha256']=sha(A/'Officer-Native-Animation-Review.blend');report['render_sha256']={name+'.png':sha(preview/(name+'.png')) for name in ('ready','walk','pistol','wind-up','sword-strike','follow-through','parry','command','grenade','death')};(O/'ANIMATION_VERIFICATION.json').write_text(json.dumps(report,indent=2));(A/'animation-verification.json').write_text(json.dumps(report,indent=2))
assert report['status']=='passed',(max_grip,max_hand_affine,violations[:12]);assert rows['Attack']['firing_muzzle_forward_minimum']>.98 and rows['Attack']['firing_barrel_up_minimum']>.98,rows['Attack']
print('OFFICER_NATIVE_ANIMATIONS_VERIFIED',len(actions),'clips',poses,'poses;',max_grip,'max grip error',flush=True)
