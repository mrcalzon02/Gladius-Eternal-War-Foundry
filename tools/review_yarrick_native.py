"""Independently reload the delivered unit, render it and check moving sockets."""
from pathlib import Path
from types import SimpleNamespace
import bpy,sys,json,importlib.util
from mathutils import Vector
R=Path(__file__).resolve().parents[1];W=R/'model-workbench/Yarrick';D=R/'assets/yarrick-build/Data'
G=Path(r'C:\Program Files (x86)\Steam\steamapps\common\Warhammer 40000 Gladius - Relics of War\Data')
spec=importlib.util.spec_from_file_location('yarrick_import',R/'references/import_gladius.py');g=importlib.util.module_from_spec(spec);sys.modules[spec.name]=g;spec.loader.exec_module(g)
bpy.ops.wm.read_factory_settings(use_empty=True);roots=g._source_roots_for_xml;g._source_roots_for_xml=lambda path,prefs:list(dict.fromkeys(roots(path,prefs)+[str(G)]))
messages=[];op=SimpleNamespace(filepath=str(D/'World/Units/AstraMilitarum/CommissarYarrick.xml'),frame_viewport=False,scale_preset='FULL',report=lambda *x:messages.append(str(x)))
assert g.ImportGladiusUnitFromXml.execute(op,bpy.context)=={'FINISHED'},messages
scene=bpy.context.scene;rig=bpy.data.objects['Yarrick_rig'];body=bpy.data.objects['Yarrick'];claw=bpy.data.objects['YarrickClaw']
original_bounds=json.loads((W/'donor.json').read_text())['objects']['LordCommissar']['bounds']
rig.data.pose_position='REST';bpy.context.view_layer.update()
claw_points=[claw.matrix_world@v.co for v in claw.data.vertices]
bounds=[[min(p[i] for p in claw_points) for i in range(3)],[max(p[i] for p in claw_points) for i in range(3)]]
assert all(abs(bounds[0][i]-(-4.5,13.5,18)[i])<3 for i in range(3)),bounds
rig.data.pose_position='POSE';errors={}
for suffix in ('Idle0','Move','Attack','Melee','Shout','Die'):
 path=D/f'Video/Animations/Units/Foundry/Yarrick{suffix}.anm'
 if not path.exists():continue
 action,_=g._load_anm_to_rig(str(path),rig,unit_name='Yarrick',anim_type=suffix)
 rig.animation_data.action=action;rig.animation_data.use_nla=False
 for track in rig.animation_data.nla_tracks:track.mute=True
 maximum=0
 for frame in (0,int(action.frame_range[1]/2),int(action.frame_range[1])):
  scene.frame_set(frame);bpy.context.view_layer.update()
  h=rig.pose.bones['Head'];m=rig.pose.bones['YarrickEyeMuzzle'];expected=h.matrix@h.bone.matrix_local.inverted()@Vector((12.1,-2.3,63))
  maximum=max(maximum,(m.matrix.translation-expected).length)
 errors[suffix]=maximum
 assert maximum<.01,(suffix,maximum)
 if suffix=='Idle0':idle=action
rig.animation_data.action=idle;scene.frame_set(0)
scope={'__file__':str(R/'tools/prepare_model_starters.py')};exec((R/'tools/prepare_model_starters.py').read_text().split('OUT.mkdir(exist_ok=True)')[0],scope)
scene.world=bpy.data.worlds.new('Native Yarrick studio');scope['setup_view']()
center=Vector((2,2,35));camera=scene.camera;camera.location=center+Vector((100,-125,65));camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.type='ORTHO';camera.data.ortho_scale=95
scene.render.resolution_x=1000;scene.render.resolution_y=1000;scene.render.filepath=str(W/'Yarrick-native-preview.png');bpy.ops.render.render(write_still=True)
result={'native_import':'passed','eye_socket_max_error':errors,'claw_rest_bounds':bounds,'messages':messages,'live_game_verified':False}
(W/'native-review.json').write_text(json.dumps(result,indent=2));print('NATIVE REVIEW',json.dumps(result))
