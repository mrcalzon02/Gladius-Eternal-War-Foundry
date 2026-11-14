"""Create a static review GLB without losing Gladius player-colour shader output."""
from pathlib import Path
import bpy,json,hashlib
R=Path(__file__).resolve().parents[1];O=R/'model-workbench/Penal-Legion-Standard-Trooper';bpy.ops.wm.open_mainfile(filepath=str(O/'Standard-Trooper.blend'));s=bpy.context.scene;meshes=[o for o in s.objects if o.type=='MESH']
for ob in meshes:
 if not any(mat and mat.use_nodes and any(n.type=='GROUP' for n in mat.node_tree.nodes) for mat in ob.data.materials):continue
 # Bake only the actual game-shader base colour, in the object's existing UVs.
 dims=(512,256) if 'Lasgun' in ob.name else (512,512);im=bpy.data.images.new(ob.name+' preview diffuse',*dims,alpha=False)
 for i,orig in enumerate(ob.data.materials):
  if not orig:continue
  mat=orig.copy();ob.data.materials[i]=mat;mat.use_nodes=True;n=mat.node_tree.nodes;l=mat.node_tree.links;bs=n.get('Principled BSDF');out=n.get('Material Output');em=n.new('ShaderNodeEmission')
  if bs and bs.inputs['Base Color'].is_linked:l.new(bs.inputs['Base Color'].links[0].from_socket,em.inputs['Color'])
  elif bs:em.inputs['Color'].default_value=bs.inputs['Base Color'].default_value
  l.new(em.outputs[0],out.inputs['Surface']);tx=n.new('ShaderNodeTexImage');tx.image=im;n.active=tx
 bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.context.view_layer.objects.active=ob;s.render.engine='CYCLES';s.cycles.samples=4;s.render.bake.margin=2;s.render.bake.use_clear=True;bpy.ops.object.bake(type='EMIT')
 mat=bpy.data.materials.new(ob.name+' faithful preview');mat.use_nodes=True;n=mat.node_tree.nodes;l=mat.node_tree.links;tx=n.new('ShaderNodeTexImage');tx.image=im;bs=n.get('Principled BSDF');l.new(tx.outputs['Color'],bs.inputs['Base Color']);bs.inputs['Roughness'].default_value=.6 if 'Lasgun' in ob.name else .85;ob.data.materials.clear();ob.data.materials.append(mat)
bpy.ops.object.select_all(action='DESELECT')
for ob in meshes:
 ob.select_set(True);bpy.context.view_layer.objects.active=ob;world=ob.matrix_world.copy()
 for mod in list(ob.modifiers):bpy.ops.object.modifier_apply(modifier=mod.name)
 ob.parent=None;ob.matrix_world=world
bpy.ops.export_scene.gltf(filepath=str(O/'Standard-Trooper-review.glb'),export_format='GLB',use_selection=True,export_animations=False)
for ob in list(s.objects):
 if ob.type in {'MESH','ARMATURE'}:bpy.data.objects.remove(ob,do_unlink=True)
bpy.ops.import_scene.gltf(filepath=str(O/'Standard-Trooper-review.glb'))
for name in ['front','rear','head-closeup']:
 s.camera=bpy.data.objects[name];s.cycles.samples=24;s.render.filepath=str(O/('export-'+name+'.png'));bpy.ops.render.render(write_still=True)
p=O/'verification.json';r=json.loads(p.read_text());r['review_export_reimported']=True;r['hashes']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in O.iterdir() if p.suffix in {'.blend','.glb','.png'}};p.write_text(json.dumps(r,indent=2))
