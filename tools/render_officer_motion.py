"""Render complete performances from the independently imported native assets."""
from pathlib import Path
import bpy,sys,json,math,hashlib,importlib.util
from mathutils import Vector
R=Path(__file__).resolve().parents[1];A=R/'model-workbench/Imperial-Officer/animation-production';D=R/'assets/imperial-officer-animated/Data'
report=json.loads((A/'animation-verification.json').read_text());assert report['status']=='passed'
review=A/'Officer-Native-Animation-Review.blend';assert hashlib.sha256(review.read_bytes()).hexdigest()==report['native_review_blend_sha256']
spec=importlib.util.spec_from_file_location('officer_motion_preview',R/'references/import_gladius.py');g=importlib.util.module_from_spec(spec);sys.modules[spec.name]=g;spec.loader.exec_module(g)
bpy.ops.wm.open_mainfile(filepath=str(review));s=bpy.context.scene;rig=bpy.data.objects['ImperialOfficerGuardsman_rig'];cam=s.camera
s.render.resolution_x=480;s.render.resolution_y=600;s.cycles.samples=4;s.render.image_settings.file_format='PNG'
cam.location=(85,-180,90);cam.rotation_euler=(Vector((7,0,34))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=96
# The floor makes foot planting visible without changing any asset geometry.
bpy.ops.mesh.primitive_plane_add(size=1000,location=(0,0,json.loads((A/'animation-build.json').read_text())['ground_reference_Z']-.03));floor=bpy.context.object;floor.name='Preview ground only';mat=bpy.data.materials.new('Preview ground');mat.diffuse_color=(.10,.12,.14,1);floor.data.materials.append(mat)
out=A/'motion-frames';out.mkdir(exist_ok=True);manifest=json.loads((A/'motion-frames.json').read_text()) if (A/'motion-frames.json').exists() else {}
suffixes=['Idle0','Move','Attack','Melee','MeleeDefense','Charge','ChargeDefense','Grenade','Shout','Die']
if '--clip' in sys.argv:suffixes=[sys.argv[sys.argv.index('--clip')+1]]
for suffix in suffixes:
    target=Vector((-16,0,22)) if suffix=='Die' else Vector((7,0,34));cam.location=target+Vector((78,-180,56));cam.rotation_euler=(target-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=165 if suffix=='Die' else 96
    clip=json.loads((A/'animation-build.json').read_text())['clips'][suffix];action,_=g._load_anm_to_rig(str(D/('Video/Animations/Units/Foundry/ImperialOfficerGuardsman'+suffix+'.anm')),rig,unit_name='Officer motion',anim_type=suffix);g._set_direct_animation(rig,action)
    count=max(2,round(clip['duration']*20));folder=out/suffix;folder.mkdir(exist_ok=True)
    for i in range(count):
        t=min(clip['duration'],i/20);frame=t*60;s.frame_set(math.floor(frame),subframe=frame%1);bpy.context.view_layer.update();s.render.filepath=str(folder/(f'{i:03}.png'));bpy.ops.render.render(write_still=True)
    manifest[suffix]={'frames':count,'frame_duration_ms':50,'folder':folder.relative_to(A).as_posix(),'native_clip_sha256':hashlib.sha256((D/('Video/Animations/Units/Foundry/ImperialOfficerGuardsman'+suffix+'.anm')).read_bytes()).hexdigest()};print('OFFICER_MOTION_RENDERED',suffix,count,flush=True)
(A/'motion-frames.json').write_text(json.dumps(manifest,indent=2))
