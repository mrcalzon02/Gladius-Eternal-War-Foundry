import bpy
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];D=R/'model-workbench/Ork-Nob-Crab-Claw'
bpy.ops.wm.open_mainfile(filepath=str(D/'Ork-Nob-Crab-Claw.blend'));scene=bpy.context.scene;cam=scene.camera;center=Vector((0,3,61));scene.cycles.samples=24
for name,offset in [('front',(210,-260,150)),('rear',(-210,240,130))]:
 cam.location=center+Vector(offset);cam.rotation_euler=(center-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=163;scene.render.filepath=str(D/(name+'.png'));bpy.ops.render.render(write_still=True)
bpy.ops.wm.open_mainfile(filepath=str(D/'Nob-Animation-Work.blend'));scene=bpy.context.scene;cam=scene.camera;scene.render.resolution_x=800;scene.render.resolution_y=800;scene.cycles.samples=16
for frame,name in [(1,'rest'),(16,'raised'),(30,'strike')]:
 scene.frame_set(frame);focus=Vector((10,23,74));cam.location=focus+Vector((110,180,70));cam.rotation_euler=(focus-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=83
 scene.render.filepath=str(D/('pauldron-fit-'+name+'.png'));bpy.ops.render.render(write_still=True)
