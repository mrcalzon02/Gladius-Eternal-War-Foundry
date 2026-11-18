"""Build the three-member, single-armature Grot team from its approved modelling file."""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion, Vector

here = Path(__file__).resolve().parent
sys.path.insert(0, str(here))
from locomotion import make_walk

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--out', type=Path, required=True, help='Directory for the assembled Blender and GLB files.')
parser.add_argument('--draft', action='store_true', help='Build the shorter locomotion inspection scene.')
options = parser.parse_args(sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else [])
draft = options.draft
out = options.out.expanduser().resolve()
out.mkdir(parents=True, exist_ok=True)
scene = bpy.context.scene
scene.render.fps = 24
scene.render.fps_base = 1
scene.frame_set(1)
bpy.context.preferences.filepaths.save_version = 0
roles = {'Mek': (-16, 7, 8), 'Gunner': (0, -10, 0), 'Cutter': (16, 7, 16)}
sources = {r:bpy.data.objects[r.lower() + ' rig'] for r in roles}
transforms = {}
for role, rig in sources.items():
    x, y, _ = roles[role]
    transforms[role] = rig.matrix_world.copy()
    transforms[role].translation = (x,y,rig.matrix_world.translation.z)
collection = bpy.data.collections.new('Grot Trio')
scene.collection.children.link(collection)
arm = bpy.data.armatures.new('Grot Trio skeleton')
team = bpy.data.objects.new('Grot Trio', arm)
collection.objects.link(team)
team.show_in_front = False
arm.display_type = 'STICK'
bpy.context.view_layer.objects.active = team
team.select_set(True)
bpy.ops.object.mode_set(mode='EDIT')
for role, rig in sources.items():
    trans = transforms[role]
    for source in sorted(rig.data.bones, key=lambda b:len(b.parent_recursive)):
        b = arm.edit_bones.new(role + '_' + source.name)
        b.head = trans @ source.head_local
        b.tail = trans @ source.tail_local
        b.align_roll(trans.to_quaternion() @ source.matrix_local.to_quaternion() @ Vector((0,0,1)))
        if source.parent:
            b.parent = arm.edit_bones[role + '_' + source.parent.name]
            b.use_connect = source.use_connect
bpy.ops.object.mode_set(mode='OBJECT')
for role, rig in sources.items():
    for b in rig.data.bones:
        outbone = team.data.bones[role + '_' + b.name]
        assert abs((transforms[role].to_quaternion() @ b.matrix_local.to_quaternion()).dot(outbone.matrix_local.to_quaternion())) > .999999, (role,b.name)
sources_by_role = {}
for role, rig in sources.items():
    actions = {'Idle':bpy.data.actions[role.lower() + ' | Idle']}
    if not draft:
        from actions import make_lifecycle
        actions.update(make_lifecycle(rig,role))
    actions['Move'] = make_walk(rig,role,11.0,24)
    actions['Run'] = make_walk(rig,role,12.4,18)
    sources_by_role[role] = actions
    for mesh in list(rig.children):
        transform = transforms[role] @ rig.matrix_world.inverted() @ mesh.matrix_world
        for group in mesh.vertex_groups:
            if group.name in rig.data.bones:
                group.name = role + '_' + group.name
        for mod in mesh.modifiers:
            if mod.type == 'ARMATURE':
                mod.object = team
        mesh.parent = team
        mesh.matrix_parent_inverse = Matrix.Identity(4)
        mesh.matrix_world = transform
        mesh['trio_role'] = role
        mesh['native_part'] = 'pistol' if mesh.name.startswith('Slugga |') else 'choppa' if mesh.name.startswith('Choppa |') else 'body'
        for c in list(mesh.users_collection):
            c.objects.unlink(mesh)
        collection.objects.link(mesh)
    c = rig.users_collection[0]
    bpy.data.objects.remove(rig,do_unlink=True)
    if not c.objects and c != collection:
        bpy.data.collections.remove(c)

clips = {'Idle':49,'MoveBegin':9,'Move':25,'MoveEnd':9,'Run':19}
if not draft:
    clips.update({'Melee':41,'Ranged':49,'Hit':25,'Grenade':41,'Construct':49,'Die':49})
parts = {}
for role, acts in sources_by_role.items():
    parts[role] = {name:{(fc.data_path,fc.array_index):fc for fc in action.fcurves} for name,action in acts.items()}

def component_set(table,path,dt,default):
    return [fc.evaluate(dt) if (fc:=table.get((path,component))) else v for component,v in enumerate(default)]

def pose_at(role,name,t,bone):
    offset=roles[role][2]
    if name in ('Move','Run','Idle'):
        period=clips[name]-1
        t=1+(t-1+offset)%period
    tb=parts[role][name]
    prefix='pose.bones["'+bone+'"].'
    q=Quaternion(component_set(tb,prefix+'rotation_quaternion',t,(1,0,0,0))).normalized()
    v=Vector(component_set(tb,prefix+'location',t,(0,0,0)))*transforms[role].to_scale().x
    return q,v

def add_curve(action,bone,prop,axis,values):
    if max(values)-min(values) < .000001:
        keys=[(1,values[0]),(len(values),values[-1])]
    else:
        keys=list(enumerate(values,1))
    fc=action.fcurves.new('pose.bones["'+bone+'"].'+prop,index=axis,action_group=bone)
    fc.keyframe_points.add(len(keys))
    fc.keyframe_points.foreach_set('co',[n for pair in keys for n in pair])
    for k in fc.keyframe_points:
        k.interpolation='LINEAR'
    fc.update()

results={}
for name,length in clips.items():
    action=bpy.data.actions.new(name)
    action.use_fake_user=True
    action.use_cyclic=name in ('Idle','Move','Run','Construct')
    for role in roles:
        for bone in team.data.bones:
            if not bone.name.startswith(role+'_'):continue
            short=bone.name.split('_',1)[1]
            samples=[]
            for f in range(1,length+1):
                if name in ('MoveBegin','MoveEnd'):
                    t=(f-1)/(length-1)
                    if name=='MoveEnd':t=1-t
                    t=t*t*(3-2*t)
                    q1,v1=pose_at(role,'Idle',1,short)
                    q2,v2=pose_at(role,'Move',1,short)
                    q,v=q1.slerp(q2,t),v1.lerp(v2,t)
                else:
                    q,v=pose_at(role,name,f,short)
                if samples:q.make_compatible(samples[-1][0])
                samples.append((q,v))
            for axis in range(4):
                add_curve(action,bone.name,'rotation_quaternion',axis,[s[0][axis] for s in samples])
            if short=='pelvis':
                for axis in range(3):
                    add_curve(action,bone.name,'location',axis,[s[1][axis] for s in samples])
    results[name]=action
# Blending two foot rotations bends the sole path between its grounded endpoints.
# Bake the measured per-actor ground correction in each start/stop transition.
team.animation_data_create()
for name in ('MoveBegin','MoveEnd'):
    ac=results[name]
    team.animation_data.action=ac
    boots={role:[o for o in team.children if o.get('trio_role')==role and 'fitted ork boot' in o.name.lower()] for role in roles}
    corrected={role:[] for role in roles}
    for f in range(1,clips[name]+1):
        scene.frame_set(f)
        dep=bpy.context.evaluated_depsgraph_get()
        for role,feet in boots.items():
            height=min((o.matrix_world @ v.co).z for o in feet for v in o.evaluated_get(dep).data.vertices)
            pelvis=team.pose.bones[role+'_pelvis']
            offset=pelvis.bone.matrix_local.to_quaternion().inverted() @ Vector((0,0,-height))
            corrected[role].append(pelvis.location.copy()+offset)
    for role,poses in corrected.items():
        bone=role+'_pelvis'
        path='pose.bones["'+bone+'"].location'
        for index in range(3):
            ac.fcurves.remove(ac.fcurves.find(path,index=index))
            add_curve(ac,bone,'location',index,[p[index] for p in poses])
team.animation_data.action=None
for b in team.pose.bones:
    b.matrix_basis=Matrix.Identity(4)
for ac in list(bpy.data.actions):
    if ac not in results.values():
        bpy.data.actions.remove(ac)
team['forward'] = 'Blender -Y / Gladius +X'
team['formation'] = 'Gunner at point; Mek left and Cutter right in Blender front review.'
team['timing'] = '24 fps; shot frames 17, 23, 29; melee contact 18; grenade release 17.'
team.animation_data_create()
cursor = 1
ranges = {}
for name, action in results.items():
    track = team.animation_data.nla_tracks.new()
    track.name = name
    clip = track.strips.new(name,cursor,action)
    clip.extrapolation='NOTHING'
    clip.blend_type='REPLACE'
    last=cursor+clips[name]-1
    ranges[name]=(cursor,last)
    scene.timeline_markers.new(name,frame=cursor)
    cursor=last+1
scene['clip_ranges_json']=json.dumps(ranges)
scene.frame_start=1
scene.frame_end=cursor-1
scene.frame_set(1)
camera=scene.camera
focus=Vector((0,0,11.8))
camera.location=focus+Vector((.11,-1,.63)).normalized()*150
camera.rotation_euler=(focus-camera.location).to_track_quat('-Z','Y').to_euler()
camera.data.type='ORTHO'
camera.data.ortho_scale=64
camera.data.clip_end=500
scene.render.resolution_x=1000
scene.render.resolution_y=760
scene.render.resolution_percentage=100
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            view=area.spaces.active
            view.region_3d.view_perspective='CAMERA'
            view.region_3d.view_camera_zoom=0
            view.overlay.show_overlays=False
            view.shading.color_type='TEXTURE'
bpy.ops.object.select_all(action='DESELECT')
team.select_set(True)
bpy.context.view_layer.objects.active=team
blend=out/('Grot-Trio-Draft.blend' if draft else 'Grot-Trio.blend')
bpy.ops.wm.save_as_mainfile(filepath=str(blend),compress=True)
print('READY',blend,ranges,flush=True)
if not draft:
    for t in team.animation_data.nla_tracks:
        original=t.strips[0]
        action=original.action
        t.strips.remove(original)
        replacement=t.strips.new(t.name,1,action)
        replacement.extrapolation='NOTHING'
        assert abs(replacement.frame_end-clips[t.name])<.00001 and replacement.scale==1 and replacement.repeat==1
    for o in collection.all_objects:o.select_set(True)
    bpy.ops.export_scene.gltf(filepath=str(out/'Grot-Trio.glb'),use_selection=True,
        export_animations=True,export_animation_mode='NLA_TRACKS',export_anim_slide_to_zero=True,
        export_frame_range=False,export_force_sampling=True,export_optimize_animation_size=True,
        export_yup=True,export_skins=True,export_cameras=False,export_lights=False,export_extras=False)
