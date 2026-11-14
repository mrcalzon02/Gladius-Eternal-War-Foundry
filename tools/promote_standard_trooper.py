"""Promote the user-approved trooper with bounded UV-only cleanup."""
from pathlib import Path
import bpy,bmesh,math,json,hashlib,struct,shutil
from mathutils import Vector
R=Path(__file__).resolve().parents[1];SRC=R/'model-workbench/Penal-Legion-Trooper';OUT=R/'model-workbench/Penal-Legion-Standard-Trooper';OUT.mkdir(exist_ok=True);source=SRC/'Penal-Legion-Trooper.blend';source_hash=hashlib.sha256(source.read_bytes()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(source))
if bpy.context.object and bpy.context.object.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
s=bpy.context.scene;head=bpy.data.objects['Penal Legion bald Guardsman head'];me=head.data;uv=me.uv_layers.active
meshes=[o for o in s.objects if o.type=='MESH']
def gh(obj):return hashlib.sha256(b''.join(struct.pack('<fff',*v.co) for v in obj.data.vertices)).hexdigest()
def uh(obj):return hashlib.sha256(b''.join(struct.pack('<ff',*p.uv) for p in obj.data.uv_layers.active.data)).hexdigest()
geometry={o.name:gh(o) for o in meshes};body_uv={o.name:uh(o) for o in meshes if o!=head};before_uv={i:tuple(p.uv) for i,p in enumerate(uv.data)}
# Ears are separate 12-vertex components inside the same mesh. Reproject only those
# islands after the user's small ear movements using their existing scalp mapping.
adj={v.index:set() for v in me.vertices}
for e in me.edges:a,b=e.vertices;adj[a].add(b);adj[b].add(a)
todo=set(adj);ears=set()
while todo:
 first=todo.pop();found={first};stack=[first]
 while stack:
  for v in adj[stack.pop()]:
   if v in todo:todo.remove(v);found.add(v);stack.append(v)
 center=sum((me.vertices[i].co for i in found),Vector())/len(found)
 if len(found)==12 and abs(center.y)>2.5 and 58<center.z<62:ears|=found
changes={'ear_loops':0,'temple_loops':0}
for p in me.polygons:
 for li in p.loop_indices:
  v=me.vertices[me.loops[li].vertex_index];x,y,z=v.co
  if v.index in ears:
   uv.data[li].uv=(.425+.065*(.5+math.atan2(y+.25,x-.5)/(2*math.pi)),.61+.09*((z-54)/12));changes['ear_loops']+=1
  elif uv.data[li].uv.x>.70 and 2.5<abs(y)<3.5 and 2.6<x<4.0 and 57.5<z<61.7:
   desired=.779+(y+.30)*.024;delta=max(-.0015,min(.0015,desired-uv.data[li].uv.x));uv.data[li].uv.x+=delta;changes['temple_loops']+=1
assert all(gh(o)==geometry[o.name] for o in meshes),'Geometry changed'
assert all(uh(o)==body_uv[o.name] for o in meshes if o!=head),'Body UV changed'
# Place the consumed atlas alongside the source and pack all references.
head_image=next(n.image for n in me.materials[0].node_tree.nodes if n.type=='TEX_IMAGE' and n.image)
assert tuple(head_image.size)==(512,512)
atlas=OUT/'Standard-Trooper-Diffuse512.png';shutil.copy2(SRC/'PenalLegionGuardsmanDiffuse512.png',atlas);head_image.filepath=str(atlas)
for im in bpy.data.images:
 if im.packed_file and im.name!='Render Result':pass
s.camera=bpy.data.objects['front'];s.render.engine='CYCLES';s.cycles.samples=24
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'Standard-Trooper.blend'))
report={'asset':'Penal Legion standard trooper','stage':'approved modeling baseline; Gladius runtime export/in-game animation unvalidated','source_user_edit_sha256':source_hash,'geometry_unchanged':all(gh(o)==geometry[o.name] for o in meshes),'body_uv_unchanged':all(uh(o)==body_uv[o.name] for o in meshes if o!=head),'triangles':sum(len(p.vertices)-2 for o in meshes for p in o.data.polygons),'atlas_size':list(head_image.size),'cleanup':changes,'max_uv_change_pixels':max((Vector(uv.data[i].uv)-Vector(co)).length*512 for i,co in before_uv.items()),'animation_actions':len(bpy.data.actions),'rig':'Guardsman_rig','meshes':[]}
for obj in meshes:
 bm=bmesh.new();bm.from_mesh(obj.data);report['meshes'].append({'name':obj.name,'vertices':len(obj.data.vertices),'triangles':sum(len(p.vertices)-2 for p in obj.data.polygons),'degenerate_faces':sum(f.calc_area()<1e-7 for f in bm.faces)});bm.free()
for name in ['head-closeup','front','rear']:
 s.camera=bpy.data.objects[name];s.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
# Final source remains rigged; GLB is a static review artifact with native UVs/images.
for obj in meshes:
 bpy.context.view_layer.objects.active=obj;world=obj.matrix_world.copy()
 for mod in list(obj.modifiers):bpy.ops.object.modifier_apply(modifier=mod.name)
 obj.parent=None;obj.matrix_world=world
for m in list(bpy.data.materials):
 if not m.use_nodes:continue
 nt=m.node_tree;n=nt.nodes;bs=n.get('Principled BSDF');out=n.get('Material Output')
 if not bs or not out:continue
 images=[nd.image for nd in n if nd.type=='TEX_IMAGE' and nd.image]
 diffuse=next((im for im in images if 'skin and body 512' in im.name or 'Diffuse' in im.name),None)
 if diffuse:
  tex=n.new('ShaderNodeTexImage');tex.image=diffuse;nt.links.new(tex.outputs['Color'],bs.inputs['Base Color'])
 nt.links.new(bs.outputs['BSDF'],out.inputs['Surface'])
bpy.ops.object.select_all(action='DESELECT')
for obj in meshes:obj.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(OUT/'Standard-Trooper-review.glb'),export_format='GLB',use_selection=True,export_animations=False)
for obj in list(s.objects):
 if obj.type in {'MESH','ARMATURE'}:bpy.data.objects.remove(obj,do_unlink=True)
bpy.ops.import_scene.gltf(filepath=str(OUT/'Standard-Trooper-review.glb'))
for name in ['head-closeup','front','rear']:
 s.camera=bpy.data.objects[name];s.render.filepath=str(OUT/('export-'+name+'.png'));bpy.ops.render.render(write_still=True)
report['review_export_reimported']=True;report['hashes']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir() if p.suffix in {'.blend','.glb','.png'}}
assert hashlib.sha256(source.read_bytes()).hexdigest()==source_hash,'Original user source changed'
(OUT/'verification.json').write_text(json.dumps(report,indent=2));print('STANDARD_READY',json.dumps({k:v for k,v in report.items() if k not in ['meshes','hashes']}),flush=True)
