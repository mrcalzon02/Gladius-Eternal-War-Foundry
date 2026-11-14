"""Short native bite preview from the real MSH/ANM/DDS build."""
import bpy,sys,importlib.util,os
from pathlib import Path
from types import SimpleNamespace
from mathutils import Vector
R=Path(__file__).resolve().parents[1];D=Path(os.environ.get('RIPPER_STAGE_DIR',R/'model-workbench/Ripper/low-poly'));OUT=Path(os.environ.get('RIPPER_NATIVE_DIR',R/'game-ready/Foundry Ripper'));DATA=OUT/'Data'
spec=importlib.util.spec_from_file_location('ripper_motion_import',R/'references/import_gladius.py');g=importlib.util.module_from_spec(spec);sys.modules[spec.name]=g;spec.loader.exec_module(g)
GAME=Path('C:/Program Files (x86)/Steam/steamapps/common/Warhammer 40000 Gladius - Relics of War/Data');roots=g._source_roots_for_xml;g._source_roots_for_xml=lambda path,prefs:list(dict.fromkeys(roots(path,prefs)+[str(GAME)]))
bpy.ops.wm.read_factory_settings(use_empty=True);op=SimpleNamespace(filepath=str(DATA/'World/Units/Tyranids/Ripperswarm.xml'),frame_viewport=False,scale_preset='FULL',report=lambda *args:None)
assert g.ImportGladiusUnitFromXml.execute(op,bpy.context)=={'FINISHED'}
rig=bpy.data.objects['Ripper_rig'];action,_=g._load_anm_to_rig(str(DATA/'Video/Animations/Units/Foundry/RipperMelee.anm'),rig,unit_name='Ripper motion',anim_type='Melee');rig.animation_data.action=action;rig.animation_data.use_nla=False
for track in rig.animation_data.nla_tracks:track.mute=True
scene=bpy.context.scene;scene.world=bpy.data.worlds.new('Motion studio');scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.12,.14,.18,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.4
focus=Vector((2,0,4.5))
for name,loc,power,size in [('Key',(25,-30,45),15000,25),('Fill',(15,35,30),9000,25),('Rim',(-20,15,35),12000,20)]:
 data=bpy.data.lights.new(name,'AREA');data.energy=power;data.size=size;ob=bpy.data.objects.new(name,data);scene.collection.objects.link(ob);ob.location=loc;ob.rotation_euler=(focus-ob.location).to_track_quat('-Z','Y').to_euler()
data=bpy.data.cameras.new('Bite preview');camera=bpy.data.objects.new('Bite preview',data);scene.collection.objects.link(camera);scene.camera=camera;camera.location=focus+Vector((9,-7,3));camera.rotation_euler=(focus-camera.location).to_track_quat('-Z','Y').to_euler();data.type='ORTHO';data.ortho_scale=9
scene.render.engine='CYCLES';scene.cycles.samples=16;scene.cycles.use_denoising=True;scene.render.resolution_x=500;scene.render.resolution_y=420;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='AgX'
frames=D/'motion-frames';frames.mkdir(exist_ok=True)
for f in range(0,24,3):scene.frame_set(f);scene.render.filepath=str(frames/f'bite-{f:02d}.png');bpy.ops.render.render(write_still=True)
print('Native bite preview frames rendered')
