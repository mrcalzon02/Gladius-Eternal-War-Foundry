from pathlib import Path
import bpy
from mathutils import Vector
R=Path(__file__).resolve().parents[1];D=R/'model-workbench/Ork-Nob-Crab-Claw';P=D/'animation-previews'
bpy.ops.wm.open_mainfile(filepath=str(D/'Nob-Animation-Work.blend'));scene=bpy.context.scene;rig=bpy.data.objects['OrkBoy_rig'];cam=scene.camera
for i,t in enumerate(range(1,66,2)):
 scene.frame_set(t);scene.render.filepath=str(P/f'attack-{i:03d}.png');bpy.ops.render.render(write_still=True)
rig.animation_data.action=bpy.data.actions['Nob - Crab claw mechanism'];focus=Vector((6,47,32));cam.location=focus+Vector((105,155,65));cam.rotation_euler=(focus-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=72
for i,t in enumerate(range(1,50,2)):
 scene.frame_set(t);scene.render.filepath=str(P/f'claw-{i:03d}.png');bpy.ops.render.render(write_still=True)
