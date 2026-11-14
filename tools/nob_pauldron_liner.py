"""Fit a concealed liner beneath the native Nob claw-side pauldron.

World coordinates are the native 1.5x Nob assembly. The original pauldron and
liner share Torso, preserving the inset clearance throughout arm animation.
"""
from mathutils import Vector,Matrix
import bpy,bmesh
NAME='Claw-arm pauldron inner liner'
EDGE=[(22.5369,24.3072,57.5704),(26.4953,24.6318,65.6902),(25.2624,24.8344,74.5592),(19.4985,26.041,81.3075),(11.0742,27.8598,83.745),(2.4639,28.5090,81.0717)]
def native_pad_faces(body):
 uv=body.data.uv_layers.active.data
 seed=[p.index for p in body.data.polygons if all(.235<uv[i].uv.x<.61 and .465<uv[i].uv.y<.63 for i in p.loop_indices)]
 lookup={};keys={}
 for p in body.data.polygons:
  keys[p.index]=[tuple(round(c,3) for c in body.matrix_world@body.data.vertices[i].co) for i in p.vertices]
  for k in keys[p.index]:lookup.setdefault(k,set()).add(p.index)
 seen=set(seed);todo=list(seed)
 while todo:
  i=todo.pop()
  for k in keys[i]:
   for j in lookup[k]-seen:seen.add(j);todo.append(j)
 return sorted(seen)
def geometry():
 verts=[]
 for thickness in [0,.7]:
  for point in EDGE:
   p=Vector(point);normal=Vector((p.x-10,0,p.z-68)).normalized()
   for depth in [-4.5,-1.0]:verts.append(p+Vector((0,depth,0))-normal*(6.0+thickness))
 faces=[]
 for i in range(5):
  a=2*i;faces.extend([(a,a+2,a+3,a+1),(a+12,a+13,a+15,a+14),(a,a+12,a+14,a+2),(a+1,a+3,a+15,a+13)])
 faces.extend([(0,1,13,12),(10,22,23,11)])
 return verts,faces
def fit_inner_liner(scene,rig,material):
 obj=bpy.data.objects.get('Fitted hammered pauldron 1') or bpy.data.objects.get(NAME)
 if obj is None:
  obj=bpy.data.objects.new(NAME,bpy.data.meshes.new(NAME));scene.collection.objects.link(obj)
 for rivet in list(scene.objects):
  if rivet.name.startswith('Pauldron flush rivet 1'):bpy.data.objects.remove(rivet,do_unlink=True)
 verts,faces=geometry();mesh=bpy.data.meshes.new(NAME+' geometry');mesh.from_pydata([rig.matrix_world.inverted()@v for v in verts],[],faces);mesh.update()
 bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh);bm.free()
 mesh.materials.append(material);uv=mesh.uv_layers.new(name='Native atlas patches')
 # Native dark region reads as an internal iron backing, tucked under the rim.
 for face in mesh.polygons:
  for j,li in enumerate(face.loop_indices):uv.data[li].uv=(.20+.06*(j%2),.35+.05*(j//2))
 obj.name=NAME;obj.data=mesh;obj.parent=rig;obj.matrix_basis=Matrix.Identity(4);obj.vertex_groups.clear();obj.vertex_groups.new(name='Torso').add(list(range(len(mesh.vertices))),1,'REPLACE')
 for mod in list(obj.modifiers):obj.modifiers.remove(mod)
 obj.modifiers.new('Follow original shoulder armour','ARMATURE').object=rig
 obj['fit']='Original pauldron inner curve; 0.7-unit liner; fully inset beneath existing rim'
 return obj
