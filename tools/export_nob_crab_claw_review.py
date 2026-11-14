"""Bake native color logic for a static review GLB; reopen and audit actual export."""
import bpy,json,hashlib,math,bmesh
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];D=R/'model-workbench/Ork-Nob-Crab-Claw';bpy.ops.wm.open_mainfile(filepath=str(D/'Ork-Nob-Crab-Claw.blend'));scene=bpy.context.scene
source_meshes=[o for o in scene.objects if o.type=='MESH'];reviews={}
for original in {o.data.materials[0] for o in source_meshes}:
 m=original.copy();bs=m.node_tree.nodes.get('Principled BSDF');color=bs.inputs['Base Color'].links[0].from_socket
 emit=m.node_tree.nodes.new('ShaderNodeEmission');m.node_tree.links.new(color,emit.inputs['Color']);m.node_tree.links.new(emit.outputs[0],m.node_tree.nodes.get('Material Output').inputs['Surface'])
 image=bpy.data.images.new(original.name+' review color',width=1024,height=1024,alpha=False)
 target=m.node_tree.nodes.new('ShaderNodeTexImage');target.image=image;m.node_tree.nodes.active=target
 bpy.ops.mesh.primitive_plane_add(size=2,location=(0,0,-100));plane=bpy.context.object;plane.data.materials.append(m);plane['gladius_team_color']=bpy.data.objects['OrkBoy'].get('gladius_team_color',(.1,.5,.9))
 bpy.ops.object.select_all(action='DESELECT');plane.select_set(True);bpy.context.view_layer.objects.active=plane
 scene.render.engine='CYCLES';scene.cycles.samples=1;bpy.ops.object.bake(type='EMIT',margin=0)
 image.filepath_raw=str(D/(original.name+'-review-color.png'));image.file_format='PNG';image.save();bpy.data.objects.remove(plane,do_unlink=True)
 p=bpy.data.materials.new(original.name+' review PBR');p.use_nodes=True;n=p.node_tree.nodes.new('ShaderNodeTexImage');n.image=image;pb=p.node_tree.nodes.get('Principled BSDF');p.node_tree.links.new(n.outputs['Color'],pb.inputs['Base Color']);pb.inputs['Roughness'].default_value=.72
 # Normal data remains the original native image, rather than procedural source only.
 normal=next((n.image for n in original.node_tree.nodes if n.type=='TEX_IMAGE' and n.image and 'Normal' in n.image.name),None)
 if normal:
  n=p.node_tree.nodes.new('ShaderNodeTexImage');n.image=normal;n.image.colorspace_settings.name='Non-Color';nm=p.node_tree.nodes.new('ShaderNodeNormalMap');p.node_tree.links.new(n.outputs['Color'],nm.inputs['Color']);p.node_tree.links.new(nm.outputs['Normal'],pb.inputs['Normal'])
 reviews[original.name]=p
# Freeze a separate review copy; editable source retains original skeleton and animation library.
deps=bpy.context.evaluated_depsgraph_get();frozen=[]
for o in source_meshes:
 me=bpy.data.meshes.new_from_object(o.evaluated_get(deps));ob=bpy.data.objects.new(o.name+' review',me);scene.collection.objects.link(ob);ob.matrix_world=o.matrix_world.copy();me.materials.clear();me.materials.append(reviews[o.data.materials[0].name])
 frozen.append(ob)
bpy.ops.object.select_all(action='DESELECT')
for o in frozen:o.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(D/'Ork-Nob-Crab-Claw-review.glb'),use_selection=True,export_format='GLB',export_animations=False)
# Delete all geometry, import independently and inspect actual GLB.
for o in list(scene.objects):
 if o.type in {'MESH','ARMATURE','EMPTY'}:bpy.data.objects.remove(o,do_unlink=True)
bpy.ops.import_scene.gltf(filepath=str(D/'Ork-Nob-Crab-Claw-review.glb'))
meshes=[o for o in scene.objects if o.type=='MESH'];points=[o.matrix_world@v.co for o in meshes for v in o.data.vertices]
fail=[];tri=sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in meshes)
for o in meshes:
 if not o.data.uv_layers:fail.append('Missing UV '+o.name)
 if any(not all(math.isfinite(c) for c in v.co) for v in o.data.vertices):fail.append('Nonfinite '+o.name)
 if any(p.area<1e-9 for p in o.data.polygons):fail.append('Degenerate '+o.name)
 for m in o.data.materials:
  for n in m.node_tree.nodes:
   if n.type=='TEX_IMAGE' and n.image:
    try: _=n.image.pixels[0]
    except Exception: fail.append('Unreadable image '+o.name)
report={'triangles':tri,'bounds':[[min(p[i] for p in points) for i in range(3)],[max(p[i] for p in points) for i in range(3)]],'failures':fail,'static_review_only':True,'source_sha256':hashlib.sha256((D/'Ork-Nob-Crab-Claw.blend').read_bytes()).hexdigest(),'export_sha256':hashlib.sha256((D/'Ork-Nob-Crab-Claw-review.glb').read_bytes()).hexdigest()}
scene.cycles.samples=24;scene.render.resolution_x=900;scene.render.resolution_y=900
center=Vector((0,3,61));camera=scene.camera
for name,offset in [('export-front',(230,-260,120)),('export-rear',(-230,260,120)),('export-side',(30,300,50))]:
 camera.location=center+Vector(offset);camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(D/(name+'.png'));bpy.ops.render.render(write_still=True)
# Tight views verify the forearm termination and fitted shoulder interfaces.
for name,focus,offset,scale in [('claw-closeup',(5,47,32),(100,145,55),68),('shoulder-closeup',(10,23,74),(110,180,70),83)]:
 focus=Vector(focus);camera.location=focus+Vector(offset);camera.rotation_euler=(focus-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=scale
 scene.render.filepath=str(D/(name+'.png'));bpy.ops.render.render(write_still=True)
camera.data.ortho_scale=163
# Clay read of actual artifact.
clay=bpy.data.materials.new('Neutral inspection clay');clay.diffuse_color=(.42,.42,.42,1);clay.use_nodes=True;clay.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.42,.42,.42,1)
for o in meshes:o.data.materials.clear();o.data.materials.append(clay)
camera.location=center+Vector((230,-260,120));camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(D/'export-clay.png');bpy.ops.render.render(write_still=True)
(D/'verification.json').write_text(json.dumps(report,indent=2));print(report)
