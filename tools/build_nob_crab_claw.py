"""Local Nob upgrade, derived from the mod Nob, retaining native atlas and rig."""
import bpy, math, json, hashlib
from pathlib import Path
from mathutils import Vector, Matrix
R=Path(__file__).resolve().parents[1];D=R/'model-workbench/Ork-Nob-Crab-Claw';D.mkdir(exist_ok=True)
S=R/'model-workbench/Ork-Nob-current/Ork-Nob-current.blend'
bpy.ops.wm.open_mainfile(filepath=str(S));scene=bpy.context.scene;rig=bpy.data.objects['OrkBoy_rig'];body=bpy.data.objects['OrkBoy']
# Remove the organic left hand. The existing hand joint now drives the claw.
import bmesh
handgroup=body.vertex_groups['LeftHand'].index
weights={v.index:sum(g.weight for g in v.groups if g.group==handgroup) for v in body.data.vertices}
remove=[p.index for p in body.data.polygons if sum(weights[i] for i in p.vertices)/len(p.vertices)>.35]
bm=bmesh.new();bm.from_mesh(body.data);bm.faces.ensure_lookup_table()
bmesh.ops.delete(bm,geom=[bm.faces[i] for i in remove],context='FACES');bm.to_mesh(body.data);bm.free();body.data.update()
# Keep the source donor intact; replace only the melee attachment in this candidate.
for n in ['Choppa','Choppa_rig']:bpy.data.objects.remove(bpy.data.objects[n],do_unlink=True)
mat=body.data.materials[0];added=[]
patch={'steel':(.016,.797,.057,.861),'gold':(.30,.536,.405,.575),'black':(.17,.31,.45,.45),'red':(.025,.565,.15,.64),'edge':(.425,.72,.463,.79)}
def finish(o,region,bone):
 bpy.context.view_layer.update()
 o.data.materials.append(mat)
 # World authored coordinates converted to the original scaled rig frame.
 for v in o.data.vertices:v.co=rig.matrix_world.inverted()@(o.matrix_world@v.co)
 o.matrix_world=Matrix.Identity(4);o.parent=rig;o.matrix_basis=Matrix.Identity(4)
 
 for old_uv in list(o.data.uv_layers):o.data.uv_layers.remove(old_uv)
 uv=o.data.uv_layers.new(name='Native atlas patches');a,b,c,d=patch[region]
 for p in o.data.polygons:
  # Project each polygon into its own tangent frame for stable texel placement.
  pts=[o.data.vertices[i].co for i in p.vertices];normal=p.normal
  axis=max(range(3),key=lambda i:abs(normal[i]));axes=[i for i in range(3) if i!=axis]
  lo=[min(v[i] for v in pts) for i in axes];hi=[max(v[i] for v in pts) for i in axes]
  for li,co in zip(p.loop_indices,pts):
   f=[(co[k]-lo[j])/max(hi[j]-lo[j],.001) for j,k in enumerate(axes)]
   uv.data[li].uv=(a+(c-a)*(.06+.88*f[0]),b+(d-b)*(.06+.88*f[1]))
 g=o.vertex_groups.new(name=bone);g.add(list(range(len(o.data.vertices))),1,'REPLACE');o.modifiers.new('Original Nob skeleton','ARMATURE').object=rig
 added.append(o);return o

def mesh(n,v,f,region='steel',bone='Torso'):
 m=bpy.data.meshes.new(n);m.from_pydata(v,[],f);m.update();o=bpy.data.objects.new(n,m);scene.collection.objects.link(o);return finish(o,region,bone)
def box(n,c,s,region='steel',bone='Torso'):
 bpy.ops.mesh.primitive_cube_add(size=1,location=c);o=bpy.context.object;o.name=n;o.scale=s
 return finish(o,region,bone)
def rod(n,a,b,r,region='steel',bone='Torso',vertices=6):
 a,b=Vector(a),Vector(b);bpy.ops.mesh.primitive_cylinder_add(vertices=vertices,radius=r,depth=(b-a).length,location=(a+b)/2);o=bpy.context.object;o.name=n;o.rotation_euler=(b-a).to_track_quat('Z','Y').to_euler();return finish(o,region,bone)
def plate(n,outline,x,thick,region='steel',bone='Torso'):
 # Outline in yz; proper closed extrusion, deliberately planar and crude.
 k=len(outline);v=[(xx,y,z) for xx in (x-thick/2,x+thick/2) for y,z in outline]
 f=[tuple(reversed(range(k))),tuple(range(k,2*k))]+[(i,(i+1)%k,(i+1)%k+k,i+k) for i in range(k)]
 return mesh(n,v,f,region,bone)
# Wraparound lower jaw; the mouth and original tusks stay visible above it.
ys=[-17,-13,-3,8,12];xs=[29,40,44,40,29];zs=[53,50,49,50,53]
v=[]
for x,y,z in zip(xs,ys,zs):v.extend([(x,y,z),(x+1.7,y,z),(x+1.7,y,z+7),(x,y,z+7)])
f=[(0,3,2,1),(16,17,18,19)]
for i in range(4):
 for j in range(4):f.append((i*4+j,i*4+(j+1)%4,(i+1)*4+(j+1)%4,(i+1)*4+j))
mesh('Riveted wraparound iron lower jaw',v,f,'steel','Head')
for y,x,z in zip(ys,xs,zs):
 rod('Jaw stud',(x+1.8,y,z+3.5),(x+2.8,y,z+3.5),1.1,'edge','Head')
for y in [-11,-3,5]:
 plate('Jagged iron jaw tooth',[(y-2,56),(y+2,56),(y+1,63)],43,1.8,'steel','Head')
# Fitted faceted shoulder caps. Each ring is fitted against the actual donor
# surface by raycast; these are wrapped shells, not boxes above the anatomy.
from mathutils.bvhtree import BVHTree
worldverts=[body.matrix_world@v.co for v in body.data.vertices]
bvh=BVHTree.FromPolygons(worldverts,[tuple(p.vertices) for p in body.data.polygons],all_triangles=False)
for side,bone,start,end in [
 (-1,'RightUpperArm',(4.676,-21.673,75.481),(-7.121,-38.647,61.675)),
 (1,'LeftUpperArm',(13.409,18.378,75.779),(-6.04,28.265,63.867))]:
 if side==1:continue # Claw side uses a concealed liner beneath its native pauldron.
 start,end=Vector(start),Vector(end);axis=(end-start).normalized()
 u=Vector((1,0,0));u=(u-axis*u.dot(axis)).normalized();v=axis.cross(u).normalized()
 # Cover the outer and upper arm, leaving the armpit open. A broad middle
 # ridge and tapered lower edge give a hammered dome with eight flat facets.
 angles=[math.radians(-35+i*32) for i in range(9)]
 # Align the radial arc so its middle is the upward-facing shoulder surface.
 up=Vector((0,0,1));up=(up-axis*up.dot(axis)).normalized();u=up;v=axis.cross(u).normalized()
 angles=[math.radians(-120+i*30) for i in range(9)]
 outer=[];inner=[]
 for ring,distance in enumerate([-1,5,12,18]):
  center=start+axis*distance
  for angle in angles:
   direction=u*math.cos(angle)+v*math.sin(angle)
   hit,normal,index,dist=bvh.ray_cast(center,direction,24)
   # Fit to the donor surface; a small clearance prevents cloth clipping.
   radius=dist if hit is not None and 4<dist<22 else [12,13,12,10][ring]
   skin=center+direction*radius
   outer.append(skin+direction*3.0);inner.append(skin+direction*1.7)
 k=len(outer);verts=outer+inner;faces=[]
 for i in range(3):
  for j in range(8):
   q=(i*9+j,i*9+j+1,(i+1)*9+j+1,(i+1)*9+j)
   faces.append(q);faces.append(tuple(x+k for x in reversed(q)))
 for j in range(8):
  for row in [0,3]:
   a=row*9+j;faces.append((a,a+1,a+1+k,a+k))
 for i in range(3):
  for j in [0,8]:
   a=i*9+j;b=(i+1)*9+j;faces.append((a,b,b+k,a+k))
 shell=mesh('Fitted hammered pauldron '+str(side),verts,faces,'gold',bone)
 # Boundary faces are the iron rim itself: no separate rod ornaments.
 steel_slot=1;shell.data.materials.append(mat)
 for face in shell.data.polygons:
  if face.index>=48:face.material_index=steel_slot
 # Two short seated rivets, sunk into the shell and normal to its surface.
 for j in [2,6]:
  a=outer[9+j];direction=(a-(start+axis*5)).normalized()
  rod('Pauldron flush rivet '+str(side),a-direction*.25,a+direction*.65,1,'steel',bone,6)
import sys
sys.path.insert(0,str(R/'tools'))
from nob_pauldron_liner import fit_inner_liner
added.append(fit_inner_liner(scene,rig,mat))
# Crab claw is authored in the forearm frame: the wrist enters the BACK
# of the socket and the pincer tips continue down the elbow-to-wrist axis.
wrist=rig.matrix_world@rig.data.bones['LeftHand'].head_local
elbow=rig.matrix_world@rig.data.bones['LeftLowerArm'].head_local
claw_axis=(wrist-elbow).normalized()
claw_open=Vector((1,0,0));claw_open=(claw_open-claw_axis*claw_open.dot(claw_axis)).normalized()
claw_hinge=claw_axis.cross(claw_open).normalized()
def clawpoint(s,t=0,h=0):return wrist+claw_axis*s+claw_open*t+claw_hinge*h
def socket(name,stations,region,bone):
 # Eight-sided hollow, tapering sleeve with physical wall thickness.
 verts=[];count=len(stations);N=8
 for inside in [False,True]:
  for distance,radius,inner_radius in stations:
   r=inner_radius if inside else radius
   for j in range(N):
    angle=2*math.pi*(j+.5)/N
    verts.append(clawpoint(distance,r*math.cos(angle),r*math.sin(angle)))
 k=count*N;faces=[]
 for layer in [0,k]:
  for i in range(count-1):
   for j in range(N):
    q=(layer+i*N+j,layer+i*N+(j+1)%N,layer+(i+1)*N+(j+1)%N,layer+(i+1)*N+j)
    faces.append(tuple(reversed(q)) if layer else q)
 for ring in [0,count-1]:
  for j in range(N):
   a=ring*N+j;b=ring*N+(j+1)%N;faces.append((a,b,b+k,a+k))
 return mesh(name,verts,faces,region,bone)
socket('Tapered octagonal claw socket',[(-7,7.7,6.2),(-2,8.5,6.4),(3,9.6,6.4),(9,6.8,4.8)],'gold','LeftHand')
socket('Claw rear steel ferrule',[(-15,9.3,6.0),(-10,8.7,6.0),(-6,8.0,6.2)],'steel','LeftLowerArm')
# Two broad hooked jaws open across the forearm rather than pointing sideways.
for label,sign in [('Fixed crab jaw',1),('Hinged crab jaw',-1)]:
 outline=[(7,3),(13,10),(21,12),(31,2),(23,5),(18,6),(13,4),(9,0)]
 k=len(outline)
 verts=[clawpoint(distance,sign*spread,h) for h in [-3.7,3.7] for distance,spread in outline]
 mesh(label,verts,[tuple(reversed(range(k))),tuple(range(k,2*k))]+[(i,(i+1)%k,(i+1)%k+k,i+k) for i in range(k)],'steel','LeftHand')
rod('Crab claw transverse hinge',clawpoint(8,0,-9),clawpoint(8,0,9),2.8,'black','LeftHand',8)
for side in [-1,1]:
 rod('Seated crab hinge cap',clawpoint(8,0,side*8.5),clawpoint(8,0,side*9.5),3.2,'gold','LeftHand',8)
# A short actuator is pinned to the socket flank and the moving jaw root.
rod('Crab actuator barrel',clawpoint(-1,-5,-6),clawpoint(8,-6,-6),1.6,'black','LeftHand',6)
rod('Crab actuator piston',clawpoint(6,-6,-6),clawpoint(14,-8,-4),.9,'steel','LeftHand',6)
# Back mounting saddle and two visible clamps anchor the standard to the torso.
box('Standard back mounting block',(-17,3,71),(8,14,18),'black')
rod('Bent standard pole',(-19,3,65),(-23,3,116),2,'steel')
for z in [69,79]:box('Standard mounting clamp',(-20,3,z),(7,18,3),'gold')
plate('Jagged metal boss standard',[(-13,102),(-13,122),(-8,117),(-5,124),(0,117),(5,125),(8,117),(14,122),(14,102),(8,106),(3,101),(-3,106),(-8,101)],-23,2.8,'gold')
# Iron glyph on the forward face: angular brow, eyes and jaw silhouette.
plate('Standard black iron glyph',[(-9,115),(-6,118),(0,115),(6,118),(10,114),(7,109),(7,105),(-6,105),(-6,109)],-20.7,1,'black')
for y in [-4,4]:box('Standard glyph iron eye',(-19.8,y,113),(1,3,2),'steel')
for y in [-4,0,4]:box('Standard glyph tooth',(-19.8,y,106),(1,2,3),'steel')
# Explicit load-bearing attachments; no speculative floating shin panels.
# Jaw side arms run back to the skull; hinge pins pass through both supports.
for y in [-16,11]:
 box('Jaw cheek mounting arm '+str(y),(26,y,57),(14,3,8),'steel','Head')
 rod('Jaw cheek hinge '+str(y),(21,y-2,59),(21,y+2,59),2.4,'black','Head',8)
# Saddle straps continue from the pole block into the torso on both sides.
for y in [-5,11]:
 rod('Standard saddle torso brace '+str(y),(-20,y,73),(-10,y,75),1.8,'steel','Torso')
# Crooked scrap top hat: broad bent octagonal brim, flared patchwork crown,
# metal hatband and a mounted scrap feather. All components follow Head.
hat_center=Vector((26,-3,79.5));N=8
def hat_ring(z,rx,ry,shift=0):
 return [hat_center+Vector((shift+rx*math.cos(2*math.pi*(j+.5)/N),ry*math.sin(2*math.pi*(j+.5)/N),z)) for j in range(N)]
# Bent brim has actual thickness and a visibly uneven outline.
low=hat_ring(-.6,12.4,15.0);high=hat_ring(.8,12.4,15.0)
for j in [1,2,5]:low[j].z+=.9;high[j].z+=.9
mesh('Bent eight-sided scrap hat brim',low+high,[tuple(reversed(range(N))),tuple(range(N,2*N))]+[(j,(j+1)%N,(j+1)%N+N,j+N) for j in range(N)],'steel','Head')
bottom=hat_ring(.9,7.6,9.8);middle=hat_ring(8.5,8.5,10.4,-1.0);top=hat_ring(16,9.3,11.0,-2.3)
faces=[]
for row in range(2):
 for j in range(N):faces.append((row*N+j,row*N+(j+1)%N,(row+1)*N+(j+1)%N,(row+1)*N+j))
faces.extend([tuple(reversed(range(N))),tuple(range(2*N,3*N))])
crown=mesh('Crooked faceted top hat crown',bottom+middle+top,faces,'black','Head')
# Individual ochre repair panels overlap the black iron crown and are seated
# on its actual facets rather than floating decorations.
for j,row in [(0,0),(4,1)]:
 a=bottom if row==0 else middle;b=middle if row==0 else top
 normal=((a[j]+a[(j+1)%N]+b[j]+b[(j+1)%N])/4-hat_center);normal.z=0;normal.normalize()
 v=[a[j]+normal*.15,a[(j+1)%N]+normal*.15,b[(j+1)%N]+normal*.15,b[j]+normal*.15]
 mesh('Ochre scrap crown repair '+str(j),v,[(0,1,2,3)],'gold','Head')
# An octagonal band follows the taper of the crown.
bandlow=hat_ring(1.3,7.9,10.1,-.05);bandhigh=hat_ring(4.3,8.25,10.4,-.45)
mesh('Riveted ochre metal hatband',bandlow+bandhigh,[(j,(j+1)%N,(j+1)%N+N,j+N) for j in range(N)],'gold','Head')
for j in [0,2,4,6]:
 a=(bandlow[j]+bandlow[(j+1)%N]+bandhigh[j]+bandhigh[(j+1)%N])/4
 direction=a-hat_center;direction.z=0;direction.normalize()
 rod('Seated top hat band rivet',a-direction*.1,a+direction*.65,.8,'steel','Head',6)
# Crooked scrap feather fixed beneath the hatband on the far side.
plate('Jagged scrap hat feather',[(6,83),(8,84),(12,98),(10,95),(11,102),(8,97),(7,91)],23,1.1,'steel','Head')
scene.render.engine='CYCLES';scene.cycles.samples=32;scene.render.resolution_x=1000;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
camera=scene.camera;center=Vector((0,3,61));camera.location=center+Vector((210,-260,150));camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=163
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':
   area.spaces.active.region_3d.view_location=center;area.spaces.active.region_3d.view_distance=200
bpy.ops.object.select_all(action='DESELECT');body.select_set(True);bpy.context.view_layer.objects.active=body
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(D/'Ork-Nob-Crab-Claw.blend'))
scene.render.filepath=str(D/'front.png');bpy.ops.render.render(write_still=True)
camera.location=center+Vector((-210,240,130));camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(D/'rear.png');bpy.ops.render.render(write_still=True)
stats={'source':str(S),'source_sha256':hashlib.sha256(S.read_bytes()).hexdigest(),'added_triangles':sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in added),'body_triangles':sum(len(p.vertices)-2 for p in body.data.polygons),'added_objects':len(added),'role':'Regular Nob; two-jaw crab claw replaces organic left hand; original LeftHand joint drives claw','removed_organic_hand_faces':len(remove),'claw_axis_world':list(claw_axis),'claw_attachment':'Rear-entry tapered octagonal socket, aligned elbow to wrist','palette':'Unmodified OrkBoy3 native diffuse / normal / SIC; authored UV patches','hat':'Faceted scrap top hat attached to Head joint','integration':'Editable local candidate; not deployed to game'}
(D/'build.json').write_text(json.dumps(stats,indent=2));print(stats)

