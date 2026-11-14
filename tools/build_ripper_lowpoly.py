"""One supplied-sculpt derivative at roughly one third of a native infantry mesh."""
import bpy,bmesh,math,json,hashlib,os,sys
from pathlib import Path
from mathutils import Vector,Matrix
from mathutils.bvhtree import BVHTree
R=Path(__file__).resolve().parents[1];D=Path(os.environ.get('RIPPER_STAGE_DIR',R/'model-workbench/Ripper/low-poly'));D.mkdir(parents=True,exist_ok=True)
SOURCE=R/'model-workbench/Ripper/supplied-source/One-Ripper-Source.blend'
bpy.ops.wm.open_mainfile(filepath=str(SOURCE),use_scripts=False)
scene=bpy.context.scene
for vl in scene.view_layers:vl.material_override=None
source_meshes=[o for o in scene.objects if o.type=='MESH'];oldrigs=[o for o in scene.objects if o.type=='ARMATURE'];main=bpy.data.objects['Armature.019']
origin=Vector((main.pose.bones['Bone.002'].head.x,main.pose.bones['Bone.002'].head.y,0))
origin=main.matrix_world@main.pose.bones['Bone.002'].head
bpy.context.view_layer.update();dep=bpy.context.evaluated_depsgraph_get()
origin.z=min((o.matrix_world@v.co).z for o in source_meshes for v in o.evaluated_get(dep).data.vertices)
T=Matrix.Scale(8,4)@Matrix.Rotation(math.pi/2,4,'Z')@Matrix.Translation(-origin)
def outward_shells(bm):
 seen=set()
 for first in bm.faces:
  if first in seen:continue
  comp={first};seen.add(first);stack=[first]
  while stack:
   for e in stack.pop().edges:
    for f in e.link_faces:
     if f not in seen:seen.add(f);comp.add(f);stack.append(f)
  volume=0
  for f in comp:
   vs=[v.co for v in f.verts]
   for i in range(1,len(vs)-1):volume+=vs[0].dot(vs[i].cross(vs[i+1]))/6
  if volume<-.000001:bmesh.ops.reverse_faces(bm,faces=list(comp))
 bm.normal_update()

def mat(n,c,rough=.7,pattern='fine'):
 m=bpy.data.materials.new(n);m.use_nodes=True;nt=m.node_tree;bs=nt.nodes['Principled BSDF'];bs.inputs['Roughness'].default_value=rough
 co=nt.nodes.new('ShaderNodeTexCoord');noise=nt.nodes.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=38 if pattern=='fine' else 7;noise.inputs['Detail'].default_value=3
 nt.links.new(co.outputs['Generated'],noise.inputs['Vector']);ramp=nt.nodes.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].color=tuple(v*.65 for v in c)+(1,);ramp.color_ramp.elements[1].color=tuple(min(1,v*1.2) for v in c)+(1,)
 nt.links.new(noise.outputs['Fac'],ramp.inputs[0]);color=ramp.outputs[0]
 if pattern=='chitin':
  stretch=nt.nodes.new('ShaderNodeVectorMath');stretch.operation='MULTIPLY';stretch.inputs[1].default_value=(3,42,16);nt.links.new(co.outputs['Generated'],stretch.inputs[0])
  grain=nt.nodes.new('ShaderNodeTexNoise');grain.inputs['Scale'].default_value=2.3;grain.inputs['Detail'].default_value=2;nt.links.new(stretch.outputs[0],grain.inputs['Vector'])
  lines=nt.nodes.new('ShaderNodeValToRGB');lines.color_ramp.elements[0].position=.28;lines.color_ramp.elements[0].color=(.55,.39,.40,1);lines.color_ramp.elements[1].position=.72;lines.color_ramp.elements[1].color=(1.20,1.04,1.00,1);nt.links.new(grain.outputs['Fac'],lines.inputs[0])
  mix=nt.nodes.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY';mix.inputs[0].default_value=.66;nt.links.new(color,mix.inputs[1]);nt.links.new(lines.outputs[0],mix.inputs[2]);color=mix.outputs[0]
  geo=nt.nodes.new('ShaderNodeNewGeometry');rim=nt.nodes.new('ShaderNodeValToRGB');rim.color_ramp.elements[0].position=.475;rim.color_ramp.elements[0].color=(.46,.35,.37,1);rim.color_ramp.elements[1].position=.54;rim.color_ramp.elements[1].color=(1.8,1.50,1.4,1);nt.links.new(geo.outputs['Pointiness'],rim.inputs[0])
  mix=nt.nodes.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY';mix.inputs[0].default_value=.35;nt.links.new(color,mix.inputs[1]);nt.links.new(rim.outputs[0],mix.inputs[2]);color=mix.outputs[0]
 if n=='Ripper bone cuticle':
  # Restrained transverse throat folds, confined to the living neck under the plates.
  geo=nt.nodes.new('ShaderNodeNewGeometry');xyz=nt.nodes.new('ShaderNodeSeparateXYZ');nt.links.new(geo.outputs['Position'],xyz.inputs[0])
  def mathnode(op,a,b):
   node=nt.nodes.new('ShaderNodeMath');node.operation=op
   if isinstance(a,(int,float)):node.inputs[0].default_value=a
   else:nt.links.new(a,node.inputs[0])
   if isinstance(b,(int,float)):node.inputs[1].default_value=b
   else:nt.links.new(b,node.inputs[1])
   return node.outputs[0]
  mask=mathnode('MULTIPLY',mathnode('GREATER_THAN',xyz.outputs['X'],-8),mathnode('LESS_THAN',xyz.outputs['X'],-.7))
  wave=mathnode('SINE',mathnode('MULTIPLY',xyz.outputs['X'],7.5),0);fold=mathnode('POWER',mathnode('MAXIMUM',wave,0),6)
  amount=mathnode('MULTIPLY',mathnode('MULTIPLY',fold,mask),.21)
  mix=nt.nodes.new('ShaderNodeMixRGB');nt.links.new(amount,mix.inputs[0]);nt.links.new(color,mix.inputs[1]);mix.inputs[2].default_value=(.20,.075,.065,1);color=mix.outputs[0]
 if n not in {'Ripper recessed mouth','Ripper mouth tissue'}:
  ao=nt.nodes.new('ShaderNodeAmbientOcclusion');ao.inputs['Distance'].default_value=.65
  mix=nt.nodes.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY';mix.inputs[0].default_value=.42;nt.links.new(color,mix.inputs[1]);nt.links.new(ao.outputs['Color'],mix.inputs[2]);color=mix.outputs[0]
 nt.links.new(color,bs.inputs['Base Color'])
 return m
skin=mat('Ripper bone cuticle',(.62,.51,.39),.78)
armor=mat('Ripper burgundy chitin',(.14,.026,.047),.48,'chitin')
claw=mat('Ripper black talon',(.018,.015,.026),.62)
ivory=mat('Ripper ivory teeth',(.77,.66,.43),.55)
gums=mat('Ripper mouth tissue',(.19,.025,.045),.50)
dark=mat('Ripper recessed mouth',(.018,.003,.007),.9)
materials=[skin,armor,claw,ivory,gums,dark]
for o in source_meshes:
 o.data.materials.clear()
 for m in materials:o.data.materials.append(m)
 for p in o.data.polygons:
  c=p.center
  if o.name=='Plane.026':
   # Sculpt-specific atlas regions in the original half-mesh's anatomical frame.
   threshold=-.32-.70*max(0,-c.z-.55)
   p.material_index=1 if c.z> -1.12 and c.y>threshold else 0
   if c.z>-.19 and -.66<c.y<-.30 and c.x<.17:p.material_index=5
   # Ivory is reserved for actual tooth surfaces instead of broad mouth masks.
   if -.05<c.z<.08 and c.y<-.66:p.material_index=4
  elif o.name=='Plane.021':p.material_index=4
  else:p.material_index=2

# Rebuild the many independent posing armatures into one named skeleton in the posed frame.
bone_names={};bone_specs={};legroots=[]
for old in oldrigs:
 if old==main:
  for i,b in enumerate(old.pose.bones):
   name='Head' if b.name=='Bone' else 'Jaw' if b.name=='Bone.001' else 'Body' if b.name=='Bone.002' else 'Tail'+str(int(b.name.split('.')[-1])-2).zfill(2)
   bone_names[old.name,b.name]=name
 elif len(old.pose.bones)==1:
  for b in old.pose.bones:bone_names[old.name,b.name]='Tongue'
 else:legroots.append((old,(T@(old.matrix_world@old.pose.bones[0].head))))
for side in [-1,1]:
 matching=sorted([(old,p) for old,p in legroots if (1 if p.y>0 else -1)==side],key=lambda v:-v[1].x)
 for i,(old,p) in enumerate(matching):
  for j,b in enumerate(old.pose.bones):bone_names[old.name,b.name]=('L' if side>0 else 'R')+f'Leg{i+1}.'+['Upper','Shin','Claw'][j]
for old in oldrigs:
 for pb in old.pose.bones:
  name=bone_names[old.name,pb.name];a=T@(old.matrix_world@pb.head);b=T@(old.matrix_world@pb.tail)
  if name=='Head':a,b=b,a
  parent=bone_names.get((old.name,pb.parent.name)) if pb.parent else None
  if name=='Body':parent='Root'
  elif name=='Head':parent='Body'
  elif name=='Jaw':parent='Head'
  elif name=='Tongue':parent='Jaw'
  elif '.Upper' in name:parent='Body'
  bone_specs[name]=(a,b,parent or 'Root')
arm=bpy.data.armatures.new('Ripper unified deform skeleton');rig=bpy.data.objects.new('Ripper Rig',arm);scene.collection.objects.link(rig)
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.context.view_layer.objects.active=rig;bpy.ops.object.mode_set(mode='EDIT')
root=arm.edit_bones.new('Root');root.head=(0,0,0);root.tail=(0,0,1)
for name,(a,b,parent) in bone_specs.items():eb=arm.edit_bones.new(name);eb.head=a;eb.tail=b
for name,(a,b,parent) in bone_specs.items():arm.edit_bones[name].parent=arm.edit_bones[parent]
blood=arm.edit_bones.new('BloodBone');blood.head=(0,0,3);blood.tail=(0,0,4);blood.parent=arm.edit_bones['Body']
bpy.ops.object.mode_set(mode='OBJECT');rig.show_in_front=True
lowparts=[];pairs=[];partstats={}
highcollection=bpy.data.collections.new('Texture bake source - hidden');scene.collection.children.link(highcollection)
for o in source_meshes:
 targetrig=next(m.object for m in o.modifiers if m.type=='ARMATURE' and m.object)
 names={g.index:bone_names.get((targetrig.name,g.name),'Unused_'+g.name) for g in o.vertex_groups}
 for level in [1,0]:
  for mod in o.modifiers:
   if mod.type=='SUBSURF':mod.levels=level;mod.render_levels=level
  bpy.context.view_layer.update()
  # Applying modifiers to a real object preserves deform groups. Evaluated
  # new_from_object geometry dropped them, leaving the old fallback Body weights.
  ob=o.copy();ob.data=o.data.copy();ob.name=('Bake ' if level else 'Low ')+o.name
  (highcollection if level else scene.collection).objects.link(ob)
  bpy.ops.object.select_all(action='DESELECT');ob.select_set(True);bpy.context.view_layer.objects.active=ob
  for mod in list(ob.modifiers):
   if (mod.type=='ARMATURE' and not mod.object) or (mod.type=='SUBSURF' and level==0):ob.modifiers.remove(mod)
   else:bpy.ops.object.modifier_apply(modifier=mod.name)
  me=ob.data;me.transform(T@o.matrix_world);ob.parent=None;ob.matrix_world=Matrix.Identity(4);me.update()
  for g in ob.vertex_groups:g.name=names[g.index]
  bm=bmesh.new();bm.from_mesh(me);outward_shells(bm);bm.to_mesh(me);bm.free();me.update()
  if level:hi=ob;continue
  if o.name=='Plane.026':
   # Rebuild the whip with deliberate rings. Global collapse flattened the curl.
   bm=bmesh.new();bm.from_mesh(me);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.0001)
   bmesh.ops.bisect_plane(bm,geom=list(bm.verts)+list(bm.edges)+list(bm.faces),plane_co=(-9.2,0,0),plane_no=(1,0,0),clear_inner=True)
   bm.to_mesh(me);bm.free();me.update()
  # Preserve the sculpt's major forms under a strict total triangle budget.
  me.calc_loop_triangles();budget=220 if o.name=='Plane.026' else 8 if o.name=='Plane.021' else 18
  bpy.context.view_layer.objects.active=ob;ob.select_set(True)
  dec=ob.modifiers.new('Infantry third triangle budget','DECIMATE');dec.ratio=budget/len(me.loop_triangles)
  bpy.ops.object.modifier_apply(modifier=dec.name);ob.data.calc_loop_triangles();partstats[o.name]=len(ob.data.loop_triangles)
  if o.name=='Plane.026':
   bm=bmesh.new();bm.from_mesh(ob.data)
   boundary=[e for e in bm.edges if e.is_boundary and all(abs(v.co.x+9.2)<.02 for v in e.verts)]
   ringverts=set(v for e in boundary for v in e.verts)
   if len(ringverts)<3:raise RuntimeError('No usable tail weld boundary')
   center=sum((v.co for v in ringverts),Vector())/len(ringverts)
   ring=sorted(ringverts,key=lambda v:math.atan2(v.co.z-center.z,v.co.y-center.y))
   previous=ring
   # A deliberate cubic sweep distributes the same small cross sections over a curl.
   p0=center;p1=center+Vector((-3.5,0,-1.8));p2=center+Vector((-8,2.5,.25));p3=center+Vector((-5.6,2.1,2.2))
   pts=[];radii=[];root_radius=sum((v.co-center).length for v in ring)/len(ring)
   for j in range(1,8):
    u=j/7;pts.append((1-u)**3*p0+3*(1-u)**2*u*p1+3*(1-u)*u*u*p2+u**3*p3);radii.append(root_radius*(1-u)**1.25+.012)
   deform=bm.verts.layers.deform.verify()
   for j,(point,radius) in enumerate(zip(pts,radii)):
    axis=(pts[min(j+1,len(pts)-1)]-(center if j==0 else pts[j-1])).normalized();a=axis.cross(Vector((0,1,0))).normalized();bb=axis.cross(a).normalized()
    new=[]
    # Five-sided cross sections reserve curvature without spending triangles on tiny detail.
    for k in range(5):
     v=bm.verts.new(point+radius*(a*math.cos(k*math.tau/5)+bb*math.sin(k*math.tau/5)));new.append(v)
     nearest=sorted(( (v.co-(aa+bb)/2).length,n) for n,(aa,bb,parent) in bone_specs.items() if n.startswith('Tail'))[:2]
     total=sum(1/max(.1,d)**3 for d,n in nearest)
     for d,n in nearest:v[deform][ob.vertex_groups[n].index]=(1/max(.1,d)**3)/total
    # Match first ring winding around the X axis, then keep the swept frame consistent.
    new=sorted(new,key=lambda v:math.atan2(v.co.z-point.z,v.co.y-point.y))
    if j>0:
     shift=min(range(5),key=lambda s:sum((previous[k].co-new[(k+s)%5].co).length for k in range(5)))
     new=new[shift:]+new[:shift]
    n=len(previous);m=len(new);i=k=0
    while i<n or k<m:
     if i<n and (k==m or (i+1)/n<=(k+1)/m):face=bm.faces.new((previous[i%n],previous[(i+1)%n],new[k%m]));i+=1
     else:face=bm.faces.new((previous[i%n],new[(k+1)%m],new[k%m]));k+=1
     face.material_index=0;face.smooth=True
    previous=new
   bm.faces.new(tuple(reversed(previous))).material_index=0
   bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(ob.data);bm.free();ob.data.update();ob.data.calc_loop_triangles();partstats[o.name]=len(ob.data.loop_triangles)
  # Normalize and bound all retained donor influences to the engine's four slots.
  for v in ob.data.vertices:
   influences=sorted([(g.group,g.weight) for g in v.groups if g.weight>1e-6],key=lambda x:-x[1])[:4]
   if not influences:influences=[(ob.vertex_groups['Body'].index if 'Body' in ob.vertex_groups else 0,1)]
   for g in ob.vertex_groups:
    try:g.remove([v.index])
    except RuntimeError:pass
   total=sum(w for i,w in influences)
   for i,w in influences:ob.vertex_groups[i].add([v.index],w/total,'REPLACE')
  ob.parent=rig;mod=ob.modifiers.new('Unified ripper deformation','ARMATURE');mod.object=rig
  ob['ripper_lowpoly']=True;lowparts.append(ob);pairs.append((hi,ob))
sys.path.insert(0,str(R/'tools'));from ripper_mouth import build_gum_fangs,boost_mouth_uv,clear_tooth_normal
tooth_records=build_gum_fangs(lowparts[0],outward_shells);partstats['Integrated gum-root fangs']=48
for m in [skin,dark,gums]:
 nt=m.node_tree;bs=nt.nodes['Principled BSDF'];source=bs.inputs['Base Color'].links[0].from_socket
 attr=nt.nodes.new('ShaderNodeAttribute');attr.attribute_name='Ripper gum socket';power=nt.nodes.new('ShaderNodeMath');power.operation='POWER';power.inputs[1].default_value=2;nt.links.new(attr.outputs['Fac'],power.inputs[0])
 mix=nt.nodes.new('ShaderNodeMixRGB');nt.links.new(power.outputs[0],mix.inputs[0]);nt.links.new(source,mix.inputs[1]);mix.inputs[2].default_value=(.24,.036,.052,1);nt.links.new(mix.outputs[0],bs.inputs['Base Color'])
for o in source_meshes+oldrigs:bpy.data.objects.remove(o,do_unlink=True)
bpy.ops.object.select_all(action='DESELECT')
for o in lowparts:o.select_set(True)
bpy.context.view_layer.objects.active=lowparts[0];bpy.ops.object.join()
joined=lowparts[0];joined.name='Ripper';lowparts=[joined];pairs=[(None,joined)]
bm=bmesh.new();bm.from_mesh(joined.data)
bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.003)
bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=.003)
wire=[e for e in bm.edges if not e.link_faces]
if wire:bmesh.ops.delete(bm,geom=wire,context='EDGES')
loose=[v for v in bm.verts if not v.link_faces]
if loose:bmesh.ops.delete(bm,geom=loose,context='VERTS')
holes=[e for e in bm.edges if e.is_boundary]
if holes:bmesh.ops.holes_fill(bm,edges=holes,sides=12)
# The supplied mirrored sculpt contains narrow internal center caps and a pinched
# snout edge. Remove those interior membranes, then close the exterior surface.
interior=[f for f in bm.faces if any(e.is_boundary for e in f.edges) and any(len(e.link_faces)>2 for e in f.edges)]
if interior:bmesh.ops.delete(bm,geom=interior,context='FACES_ONLY')
for e in list(bm.edges):
 if e.is_valid and len(e.link_faces)>2:
  verts=list(e.verts);bmesh.ops.pointmerge(bm,verts=verts,merge_co=(verts[0].co+verts[1].co)/2)
bmesh.ops.dissolve_degenerate(bm,edges=list(bm.edges),dist=.003)
wire=[e for e in bm.edges if not e.link_faces]
if wire:bmesh.ops.delete(bm,geom=wire,context='EDGES')
holes=[e for e in bm.edges if e.is_boundary]
if holes:bmesh.ops.holes_fill(bm,edges=holes,sides=12)
bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));outward_shells(bm);bm.to_mesh(joined.data);bm.free();joined.data.update()
actual_triangles=sum(len(p.vertices)-2 for p in joined.data.polygons)
partstats['Seam repair delta']=actual_triangles-sum(partstats.values())
# Small conforming surface inlays keep the eye outline crisp at gameplay scale.
eye_frames=[]
head_index=joined.vertex_groups['Head'].index
for side in [-1,1]:
 polys=[list(p.vertices) for p in joined.data.polygons if p.center.x>0 and p.center.z>6 and p.center.y*side>.3 and p.normal.y*side>.1 and joined.data.materials[p.material_index]==armor]
 tree=BVHTree.FromPolygons([v.co for v in joined.data.vertices],polys)
 hit=tree.ray_cast(Vector((2.15,side*10,8.15)),Vector((0,-side,0)))
 if not hit or hit[0] is None:hit=tree.find_nearest(Vector((2.15,side*3,8.15)))
 if hit and hit[0] is not None:
  center,normal=hit[:2];long=(Vector((1,0,0))-normal*normal.x).normalized();up=normal.cross(long).normalized()
  if up.z<0:up=-up
  eye_frames.append((center,long,up,normal,tree))
eye_mats=[]
for name,tint,rough in [('Ripper eye recess',(.005,.003,.006),.7),('Ripper amber iris',(.65,.20,.018),.28)]:
 m=bpy.data.materials.new(name);m.use_nodes=True;m.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value=(*tint,1);m.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=rough;eye_mats.append(m);materials.append(m);joined.data.materials.append(m)
bm=bmesh.new();bm.from_mesh(joined.data);deform=bm.verts.layers.deform.verify()
for center,long,up,normal,support in eye_frames:
 socket_support=None;iris_lift=.1
 for j,(w,h) in enumerate([(.49,.155),(.25,.073)]):
  verts=[]
  for offset in [long*w,up*h,-long*w,-up*h]:
   # Project each corner onto the actual low-poly head rather than floating a card.
   hit=support.find_nearest(center+offset)
   co=center+offset+normal*iris_lift if j else hit[0]+hit[1]*.06
   v=bm.verts.new(co);v[deform][head_index]=1;verts.append(v)
  index=list(joined.data.materials).index(eye_mats[j])
  for corners in [(0,1,2),(0,2,3)]:
   face=bm.faces.new(tuple(verts[k] for k in corners));face.material_index=index
   face.normal_update()
   if face.normal.dot(normal)<0:face.normal_flip()
  if j==0:
   iris_lift=max((v.co-center).dot(normal) for v in verts)+.045
   polys=[(0,1,2),(0,2,3)]
   if (verts[1].co-verts[0].co).cross(verts[2].co-verts[0].co).dot(normal)<0:polys=[tuple(reversed(p)) for p in polys]
   socket_support=BVHTree.FromPolygons([v.co for v in verts],polys)
bm.to_mesh(joined.data);bm.free();joined.data.update()
partstats['Eye surface inlays']=4*len(eye_frames)
for v in joined.data.vertices:
 inf=sorted([(g.group,g.weight) for g in v.groups if joined.vertex_groups[g.group].name in rig.data.bones and g.weight>1e-6],key=lambda g:-g[1])[:4]
 if not inf:inf=[(joined.vertex_groups['Body'].index,1)]
 for group in joined.vertex_groups:
  try:group.remove([v.index])
  except RuntimeError:pass
 total=sum(w for i,w in inf)
 for i,w in inf:joined.vertex_groups[i].add([v.index],w/total,'REPLACE')
# Keep the tongue as supported soft tissue rather than a long triangular blade.
tongue_group=joined.vertex_groups['Tongue'].index
tongue_vertices=sorted([v for v in joined.data.vertices if any(g.group==tongue_group and g.weight>.9 for g in v.groups)],key=lambda v:v.co.x)
assert len(tongue_vertices)==6,'Unexpected tongue topology'
floor_z=min(v.co.z for v in joined.data.vertices)
targets=[None,(.95,.05,3.82),(1.70,.46,3.92),(1.60,-.46,3.92),(1.95,0,3.72),(2.65,.03,4.05)]
for v,p in zip(tongue_vertices,targets):
 if p:v.co=Vector(p)+Vector((0,0,floor_z))
tongue_ids={v.index for v in tongue_vertices}
for p in joined.data.polygons:
 if all(i in tongue_ids for i in p.vertices):p.use_smooth=True
bm=bmesh.new();bm.from_mesh(joined.data);outward_shells(bm);bm.to_mesh(joined.data);bm.free();joined.data.update()
# Set the rest surface on Z=0 while keeping Root as the ground-level motion control.
ground_offset=min(v.co.z for v in joined.data.vertices)
for v in joined.data.vertices:v.co.z-=ground_offset
for high in highcollection.objects:
 for v in high.data.vertices:v.co.z-=ground_offset
bpy.ops.object.select_all(action='DESELECT');rig.select_set(True);bpy.context.view_layer.objects.active=rig;bpy.ops.object.mode_set(mode='EDIT')
for b in arm.edit_bones:
 if b.name!='Root':b.head.z-=ground_offset;b.tail.z-=ground_offset
bpy.ops.object.mode_set(mode='OBJECT');bpy.context.view_layer.update()
bpy.ops.object.select_all(action='DESELECT')
for o in lowparts:o.select_set(True)
bpy.context.view_layer.objects.active=lowparts[0]
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(angle_limit=.95,island_margin=.02);bpy.ops.uv.select_all(action='SELECT');bpy.ops.uv.average_islands_scale();bpy.ops.object.mode_set(mode='OBJECT')
boost_mouth_uv(joined)
# Keep the enlarged islands in tile 1001 before packing, and explicitly select
# UVs: mesh selection alone left newly authored gum islands unpacked.
uv=joined.data.uv_layers.active.data;low=Vector([min(v.uv[i] for v in uv) for i in range(2)]);high=Vector([max(v.uv[i] for v in uv) for i in range(2)]);span=max(high-low)
for loop in uv:loop.uv=Vector((.04,.04))+(loop.uv-low)*(.92/span)
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.select_all(action='SELECT');bpy.ops.uv.pack_islands(margin=.018,udim_source='CLOSEST_UDIM');bpy.ops.object.mode_set(mode='OBJECT')
assert all(0<=c<=1 for loop in joined.data.uv_layers.active.data for c in loop.uv),'Atlas packing escaped tile 1001'

# Bake high-detail sculpt coloring and tangent normals into the low-poly UV atlas.
scene.render.engine='CYCLES';scene.cycles.samples=16;scene.render.bake.use_selected_to_active=True;scene.render.bake.cage_extrusion=.30;scene.render.bake.max_ray_distance=1.2;scene.render.bake.margin=5
color=bpy.data.images.new('Ripper Diffuse 512',512,512,alpha=False);normal=bpy.data.images.new('Ripper Normal 512',512,512,alpha=False);normal.colorspace_settings.name='Non-Color'
color.generated_color=(.08,.04,.045,1);normal.generated_color=(.5,.5,1,1)
lowmat=bpy.data.materials.new('Ripper portable PBR');lowmat.use_nodes=True
targets=[]
for m in materials+[lowmat]:targets.append((m,m.node_tree.nodes.new('ShaderNodeTexImage')))
for role,img,kind in [('Diffuse',color,'DIFFUSE'),('Normal',normal,'NORMAL')]:
 highcollection.hide_render=kind!='NORMAL'
 for m,target in targets:target.image=img;m.node_tree.nodes.active=target
 scene.render.bake.use_pass_direct=False;scene.render.bake.use_pass_indirect=False;scene.render.bake.use_pass_color=True
 for i,(hi,lo) in enumerate(pairs):
  bpy.ops.object.select_all(action='DESELECT');lo.select_set(True);bpy.context.view_layer.objects.active=lo;scene.render.bake.use_clear=False
  # Color comes from clean low-poly anatomical regions, avoiding projection holes.
  # Normals transfer sculpt relief using an actual high-to-low tangent bake.
  scene.render.bake.use_selected_to_active=kind=='NORMAL'
  if kind=='NORMAL':
   for high in highcollection.objects:high.select_set(True)
  bpy.ops.object.bake(type=kind)
 if role=='Normal':
  pixels=list(img.pixels)
  for k in range(0,len(pixels),4):
   n=Vector([pixels[k+j]*2-1 for j in range(3)])
   # Reject back-facing/missed projections; retain a restrained sculpt relief.
   if n.z<.15:n=Vector((0,0,1))
   n=Vector((n.x*.35,n.y*.35,.65+n.z*.35)).normalized()
   pixels[k:k+3]=[(c+1)*.5 for c in n]
  clear_tooth_normal(joined,pixels,512);img.pixels[:]=pixels
 img.filepath_raw=str(D/('Ripper'+role+'.png'));img.file_format='PNG';img.save();img.pack()
# Authored material response: moist mouth/iris, satin chitin, dry cuticle and talons.
highcollection.hide_render=True;scene.render.bake.use_selected_to_active=False
bpy.ops.object.select_all(action='DESELECT');joined.select_set(True);bpy.context.view_layer.objects.active=joined
roughmap=bpy.data.images.new('Ripper Roughness 512',512,512,alpha=False);roughmap.colorspace_settings.name='Non-Color'
sic=bpy.data.images.new('Ripper SIC 512',512,512,alpha=False);sic.colorspace_settings.name='Non-Color'
emits=[]
for m,target in targets:
 nt=m.node_tree;em=nt.nodes.new('ShaderNodeEmission');nt.links.new(em.outputs[0],nt.nodes['Material Output'].inputs['Surface']);emits.append((m,target,em))
for role,img in [('Roughness',roughmap),('SIC',sic)]:
 for m,target,em in emits:
  target.image=img;m.node_tree.nodes.active=target
  rough=m.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value
  spec=.24 if m==armor else .14 if m==claw else .22 if m==gums else .32 if m==eye_mats[1] else .14 if m==ivory else .065
  em.inputs['Color'].default_value=(rough,rough,rough,1) if role=='Roughness' else (spec,0,0,1)
 bpy.ops.object.bake(type='EMIT');img.filepath_raw=str(D/('Ripper'+role+'.png'));img.file_format='PNG';img.save();img.pack()
for m,target,em in emits:m.node_tree.links.new(m.node_tree.nodes['Principled BSDF'].outputs[0],m.node_tree.nodes['Material Output'].inputs['Surface'])
for hi in highcollection.objects:hi.hide_render=True;hi.hide_set(True)
highcollection.hide_render=True
for o in lowparts:
 for p in o.data.polygons:p.material_index=0
 o.data.materials.clear();o.data.materials.append(lowmat)
nt=lowmat.node_tree;bs=nt.nodes['Principled BSDF'];bs.inputs['Roughness'].default_value=.68
tex=nt.nodes.new('ShaderNodeTexImage');tex.image=color;nt.links.new(tex.outputs['Color'],bs.inputs['Base Color'])
tex=nt.nodes.new('ShaderNodeTexImage');tex.image=normal;nm=nt.nodes.new('ShaderNodeNormalMap');nt.links.new(tex.outputs['Color'],nm.inputs['Color']);nt.links.new(nm.outputs['Normal'],bs.inputs['Normal'])
tex=nt.nodes.new('ShaderNodeTexImage');tex.image=roughmap;nt.links.new(tex.outputs['Color'],bs.inputs['Roughness'])

# Four editable first-pass animation clips. Translation stays on Root.
scene.render.fps=24;rig.animation_data_create();clips={}
for clip,end in [('Idle',49),('Move',25),('Melee',25),('Die',37)]:
 action=bpy.data.actions.new('Ripper '+clip);rig.animation_data.action=action
 for f in range(1,end+1,2):
  u=(f-1)/(end-1);t=u*math.tau
  for pb in rig.pose.bones:pb.rotation_mode='XYZ';pb.rotation_euler=(0,0,0);pb.location=(0,0,0)
  rig.pose.bones['Head'].rotation_euler.x=.025*math.sin(t)
  rig.pose.bones['Jaw'].rotation_euler.x=.18+.04*math.sin(t)
  rig.pose.bones['Tongue'].rotation_euler.x=.025*math.sin(t+.7)
  for name in bone_specs:
   if name.startswith('Tail'):rig.pose.bones[name].rotation_euler.z=.04*math.sin(t-int(name[-2:])*.45)
  if clip=='Move':
   rig.pose.bones['Root'].location=arm.bones['Root'].matrix_local.to_3x3().inverted()@Vector((0,0,.08*math.sin(t*2)))
   for name in bone_specs:
    if 'Leg' in name:
     phase=t+int(name[4])*math.pi+(math.pi if name[0]=='L' else 0)
     if name.endswith('Upper'):rig.pose.bones[name].rotation_euler.z=.20*math.sin(phase)
     if name.endswith('Shin'):rig.pose.bones[name].rotation_euler.x=.20*math.cos(phase)
  if clip=='Melee':
   attack=math.sin(math.pi*u)**3;rig.pose.bones['Root'].location=arm.bones['Root'].matrix_local.to_3x3().inverted()@Vector((.9*attack,0,0));rig.pose.bones['Head'].rotation_euler.x=-.12*attack;rig.pose.bones['Jaw'].rotation_euler.x=.18+.30*attack
   for name in bone_specs:
    if 'Leg1.' in name:rig.pose.bones[name].rotation_euler.x=-.30*attack
  if clip=='Die':
   fall=min(1,u*1.6);rig.pose.bones['Root'].rotation_euler.x=.9*fall;rig.pose.bones['Root'].location=arm.bones['Root'].matrix_local.to_3x3().inverted()@Vector((0,0,-1.1*fall));rig.pose.bones['Jaw'].rotation_euler.x=.18+.22*fall
  for pb in rig.pose.bones:
   pb.keyframe_insert(data_path='rotation_euler',frame=f,group=pb.name)
   if pb.name=='Root':pb.keyframe_insert(data_path='location',frame=f,group=pb.name)
 action.use_fake_user=True;clips[clip]=[1,end];rig.animation_data.action=None
for pb in rig.pose.bones:pb.matrix_basis.identity()
scene.frame_set(1);bpy.context.view_layer.update()
points=[o.matrix_world@v.co for o in lowparts for v in o.data.vertices];focus=Vector([(min(p[i] for p in points)+max(p[i] for p in points))/2 for i in range(3)]);size=max(max(p[i] for p in points)-min(p[i] for p in points) for i in range(3))
for o in list(scene.objects):
 if o.type in {'LIGHT','CAMERA'}:bpy.data.objects.remove(o,do_unlink=True)
for name,offset,power in [('Key',(1,-1,2),35),('Fill',(-1,-.3,1),20),('Rim',(.4,1,1.3),30)]:
 data=bpy.data.lights.new(name,'AREA');data.energy=power*size*size;data.size=size*1.3;o=bpy.data.objects.new(name,data);scene.collection.objects.link(o);o.location=focus+Vector(offset)*size;o.rotation_euler=(focus-o.location).to_track_quat('-Z','Y').to_euler()
data=bpy.data.cameras.new('Ripper review');cam=bpy.data.objects.new('Ripper review',data);scene.collection.objects.link(cam);scene.camera=cam;data.type='ORTHO';data.ortho_scale=size*1.25
cam.location=focus+Vector((1,-1,.7))*size*2;cam.rotation_euler=(focus-cam.location).to_track_quat('-Z','Y').to_euler()
scene.cycles.samples=48;scene.cycles.use_denoising=True;scene.render.resolution_x=1100;scene.render.resolution_y=850;scene.render.resolution_percentage=100;scene.render.image_settings.file_format='PNG'
scene['asset_stage']='Single low-poly supplied-sculpt derivative; native export pending'
scene['source_url']='https://cults3d.com/en/3d-model/game/chompy-xeno-bugs';scene['source_author']='minipainting40k';scene['source_file']='User supplied One_Monchy_boi_for_posing.blend'
for screen in bpy.data.screens:
 for area in screen.areas:
  if area.type=='VIEW_3D':area.spaces.active.region_3d.view_location=focus;area.spaces.active.region_3d.view_distance=size*1.7
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(D/'Ripper-LowPoly.blend'))
for name,offset in [('front',(1,-1,.7)),('side',(.1,-1,.20)),('rear',(-1,1,.6))]:
 cam.location=focus+Vector(offset)*size*2;cam.rotation_euler=(focus-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(D/(name+'.png'));bpy.ops.render.render(write_still=True)
measured_triangles=sum(len(p.vertices)-2 for p in joined.data.polygons)
assert measured_triangles==sum(partstats.values()),(measured_triangles,partstats)
report={'revision':4,'triangles':measured_triangles,'parts':partstats,'bones':len(arm.bones),'clips':clips,'color_atlas':[512,512],'eye_count':len(eye_frames),'ground_offset':ground_offset,'surface_revision':'v4: compact rounded tongue, dry keratin talons, moist mouth, consistent idle/bite jaw baseline; connected tooth roots retained','tooth_count':len(tooth_records),'teeth':tooth_records,'source_reference_url':scene['source_url'],'source_sha256':hashlib.sha256(Path('C:/Users/Admin/Downloads/One_Monchy_boi_for_posing.blend').read_bytes()).hexdigest(),'engine_integration_verified':False}
(D/'build.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
if report['triangles']>450:raise RuntimeError('Infantry third triangle budget exceeded')
