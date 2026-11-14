"""Independent static GLB inspection; not a Gladius runtime export."""
import bpy,json,hashlib,math,tempfile
from pathlib import Path
from mathutils import Vector
R=Path(__file__).resolve().parents[1];D=R/'model-workbench/Squig-Hunter'
(D/'export-temp').mkdir(exist_ok=True);tempfile.tempdir=str(D/'export-temp')
bpy.ops.wm.open_mainfile(filepath=str(D/'Squig-Hunter.blend'));scene=bpy.context.scene
source=[o for o in scene.objects if o.type=='MESH' and not o.hide_render]
source_report={'actions':len(bpy.data.actions),'squig_retained':'WarbossSquig' in bpy.data.objects,'images':[{'name':im.name,'packed':bool(im.packed_file),'readable':bool(len(im.pixels))} for im in bpy.data.images if im.type=='IMAGE' and im.users]}
source_report['mesh_triangles']={o.name:sum(len(p.vertices)-2 for p in o.data.polygons) for o in source}
source_report['source_sha256_before_export']=hashlib.sha256((D/'Squig-Hunter.blend').read_bytes()).hexdigest()
review={}
for original in {m for o in source for m in o.data.materials}:
 if not any(n.type=='GROUP' for n in original.node_tree.nodes):review[original.name]=original;continue
 m=original.copy();bs=m.node_tree.nodes.get('Principled BSDF');color=bs.inputs['Base Color'].links[0].from_socket
 emit=m.node_tree.nodes.new('ShaderNodeEmission');m.node_tree.links.new(color,emit.inputs['Color']);m.node_tree.links.new(emit.outputs[0],m.node_tree.nodes.get('Material Output').inputs['Surface'])
 im=bpy.data.images.new(original.name+' review colour',width=1024,height=1024,alpha=False)
 n=m.node_tree.nodes.new('ShaderNodeTexImage');n.image=im;m.node_tree.nodes.active=n
 bpy.ops.mesh.primitive_plane_add(size=2,location=(0,0,-100));plane=bpy.context.object;plane.data.materials.append(m);plane['gladius_team_color']=(.025,.028,.032)
 bpy.ops.object.select_all(action='DESELECT');plane.select_set(True);bpy.context.view_layer.objects.active=plane
 scene.render.engine='CYCLES';scene.cycles.samples=1;bpy.ops.object.bake(type='EMIT',margin=0)
 im.filepath_raw=str(D/(original.name.replace(' ','-')+'-review.png'));im.file_format='PNG';im.save();bpy.data.objects.remove(plane,do_unlink=True)
 p=bpy.data.materials.new(original.name+' portable');p.use_nodes=True;bs=p.node_tree.nodes.get('Principled BSDF');bs.inputs['Roughness'].default_value=.74
 tex=p.node_tree.nodes.new('ShaderNodeTexImage');tex.image=im;p.node_tree.links.new(tex.outputs['Color'],bs.inputs['Base Color'])
 normal=next((n.image for n in original.node_tree.nodes if n.type=='TEX_IMAGE' and n.image and 'Normal' in n.image.name),None)
 if normal:
  tex=p.node_tree.nodes.new('ShaderNodeTexImage');tex.image=normal;nm=p.node_tree.nodes.new('ShaderNodeNormalMap');p.node_tree.links.new(tex.outputs['Color'],nm.inputs['Color']);p.node_tree.links.new(nm.outputs['Normal'],bs.inputs['Normal'])
 review[original.name]=p
deps=bpy.context.evaluated_depsgraph_get();frozen=[]
for o in source:
 me=bpy.data.meshes.new_from_object(o.evaluated_get(deps));ob=bpy.data.objects.new(o.name+' review',me);scene.collection.objects.link(ob);ob.matrix_world=o.matrix_world.copy()
 for i,m in enumerate(o.data.materials):me.materials[i]=review[m.name]
 frozen.append(ob)
bpy.ops.object.select_all(action='DESELECT')
for o in frozen:o.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(D/'Squig-Hunter-review.glb'),use_selection=True,export_format='GLB',export_animations=False)
for o in list(scene.objects):
 if o.type in {'MESH','ARMATURE','EMPTY'}:bpy.data.objects.remove(o,do_unlink=True)
bpy.ops.import_scene.gltf(filepath=str(D/'Squig-Hunter-review.glb'))
meshes=[o for o in scene.objects if o.type=='MESH'];fail=[]
for o in meshes:
 if 'WarbossSquig' in o.name:o.hide_render=True
for o in meshes:
 if not o.data.uv_layers:fail.append('Missing UV: '+o.name)
 if any(not all(math.isfinite(c) for c in v.co) for v in o.data.vertices):fail.append('Nonfinite vertex: '+o.name)
 if any(p.area<1e-9 for p in o.data.polygons):fail.append('Degenerate face: '+o.name)
 for m in o.data.materials:
  for n in m.node_tree.nodes:
   if n.type=='TEX_IMAGE' and n.image and not len(n.image.pixels):fail.append('Unreadable export image: '+n.image.name)
scene.cycles.samples=24;camera=scene.camera
for o in meshes:
 if 'WarbossSquig' in o.name:o.hide_render=False
focus=Vector((0,30,28));camera.data.ortho_scale=155;camera.location=focus+Vector((190,-150,95));camera.rotation_euler=(focus-camera.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(D/'export-assembly.png');bpy.ops.render.render(write_still=True)
for o in meshes:
 if 'WarbossSquig' in o.name:o.hide_render=True
for name,offset in [('front',(150,-100,60)),('rear',(-150,100,60)),('side',(15,-180,45)),('face',(150,-65,30))]:
 focus=Vector((17,-2,46)) if name=='face' else Vector((3,0,29));camera.data.ortho_scale=42 if name=='face' else 88;camera.location=focus+Vector(offset);camera.rotation_euler=(focus-camera.location).to_track_quat('-Z','Y').to_euler()
 scene.render.filepath=str(D/('export-'+name+'.png'));bpy.ops.render.render(write_still=True)
clay=bpy.data.materials.new('Neutral inspection clay');clay.use_nodes=True;clay.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.45,.45,.45,1)
for o in meshes:
 # Alpha-cut cards retain silhouettes; clay on solid meshes reveals construction.
 if any(m and 'card' in m.name.lower() for m in o.data.materials):continue
 o.data.materials.clear();o.data.materials.append(clay)
focus=Vector((3,0,29));camera.data.ortho_scale=88;camera.location=focus+Vector((150,-100,60));camera.rotation_euler=(focus-camera.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(D/'export-clay.png');bpy.ops.render.render(write_still=True)
pts=[o.matrix_world@v.co for o in meshes for v in o.data.vertices]
report={'failures':fail,'source':source_report,'static_triangles':sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in meshes),'bounds':[[min(p[i] for p in pts) for i in range(3)],[max(p[i] for p in pts) for i in range(3)]],'static_review_only':True,'engine_integration_verified':False,'source_sha256':hashlib.sha256((D/'Squig-Hunter.blend').read_bytes()).hexdigest(),'export_sha256':hashlib.sha256((D/'Squig-Hunter-review.glb').read_bytes()).hexdigest()}
(D/'verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
if fail:raise RuntimeError(fail)
