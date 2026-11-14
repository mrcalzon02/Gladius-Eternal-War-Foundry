"""Author Yarrick's red power claw and emissive eye; export native skinned kit."""
from pathlib import Path
import bpy,bmesh,struct,math,json,sys
from mathutils import Vector,Matrix
R=Path(__file__).resolve().parents[1];W=R/'model-workbench/Yarrick';O=R/'assets/yarrick-build';D=O/'Data'
G=Path(r'C:\Program Files (x86)\Steam\steamapps\common\Warhammer 40000 Gladius - Relics of War\Data')
sys.path.insert(0,str(R/'tools'));from native_gladius import read_mesh
bpy.ops.wm.open_mainfile(filepath=str(W/'Yarrick-donor.blend'))
rig=bpy.data.objects['LordCommissar_rig'];body=bpy.data.objects['LordCommissar']
rig.data.pose_position='REST';bpy.context.view_layer.update()
sword=bpy.data.objects['LordCommissarSword'];sword.hide_render=True;sword.hide_set(True)
names=[b.name for b in sorted((b for b in rig.data.bones if not b.get('gladius_pivot')),key=lambda b:b['gladius_source_index'])]
def bind(b):
 a=b['gladius_source_bind'];return Matrix([a[:4],a[4:8],a[8:12],a[12:16]])
binds={n:bind(rig.data.bones[n]) for n in names}
palette=[('Crimson armour',(.42,.008,.012,1)),('Red edge',(.7,.022,.025,1)),('Oiled steel',(.045,.055,.065,1)),('Blade steel',(.38,.43,.48,1)),('Brass',(.48,.27,.065,1)),('Laser lens',(1,.005,.002,1))]
materials=[]
for i,(name,color) in enumerate(palette):
 m=bpy.data.materials.new(name);m.diffuse_color=color;m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Base Color'].default_value=color;p.inputs['Roughness'].default_value=.34;p.inputs['Metallic'].default_value=.65
 if i==5:p.inputs['Emission Color'].default_value=color;p.inputs['Emission Strength'].default_value=5
 materials.append(m)
kit=[];eye=[]
def finish(o,name,mat,bone,collection):
 o.name=name;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 o.data.materials.clear();o.data.materials.append(materials[mat]);o['palette']=mat;o['bone']=bone
 # Store authored coordinates directly in the donor's body space.
 o.data.transform(o.matrix_world);o.matrix_world=Matrix.Identity(4)
 group=o.vertex_groups.new(name=bone);group.add(list(range(len(o.data.vertices))),1,'REPLACE')
 mod=o.modifiers.new('Native commissar animation','ARMATURE');mod.object=rig
 collection.append(o);return o
def box(name,loc,size,mat=0,bone='LeftHandBone',collection=kit,bevel=.28):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.dimensions=size;bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 if bevel:
  b=o.modifiers.new('Machined edge','BEVEL');b.width=bevel;b.segments=1;bpy.context.view_layer.objects.active=o;bpy.ops.object.modifier_apply(modifier=b.name)
 return finish(o,name,mat,bone,collection)
def rod(name,a,b,r,mat=3,bone='LeftHandBone',collection=kit):
 a,b=Vector(a),Vector(b);delta=b-a;bpy.ops.mesh.primitive_cylinder_add(vertices=8,radius=r,depth=delta.length,location=(a+b)/2)
 o=bpy.context.object;o.rotation_euler=delta.to_track_quat('Z','Y').to_euler();return finish(o,name,mat,bone,collection)
box('Red armoured wrist',(2,21,33),(9,10,8),0)
box('Power claw palm',(8,23,28),(11,13,8),0)
box('Raised red knuckle plate',(11,23,31.8),(7,12,1.7),1)
box('Black wrist coupling',(-.5,21,36),(7,8,2),2)
box('Brass armour badge',(8,23,32.9),(3,4,.5),4,bevel=.15)
for y in (18,23,28):
 rod('Hydraulic piston',(0,y,34),(11,y,30),.52,3)
 rod('Piston sleeve',(-1,y,35),(4,y,33),.9,2)
 rod('Knuckle hinge',(12,y-1.7,27),(12,y+1.7,27),1.35,4)
 # Swept, tapered scything talons. Six points on each side keep a sharp edge.
 profile=[(11,29),(17,29),(24,24),(25,18),(22,21),(17,24),(11,25)]
 verts=[(x,y+s,z) for s in (-1,1) for x,z in profile];n=len(profile)
 faces=[tuple(range(n-1,-1,-1)),tuple(range(n,n*2))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
 me=bpy.data.meshes.new('Talons');me.from_pydata(verts,[],faces);me.update();ob=bpy.data.objects.new('Steel power talon',me);bpy.context.collection.objects.link(ob);finish(ob,'Steel power talon',3,'LeftHandBone',kit)
rod('Opposing thumb hinge',(6,15,27),(6,18,27),1.5,4)
rod('Opposing thumb',(6,15,27),(15,14,24),1.3,0)
rod('Opposing thumb tip',(15,14,24),(19,18,22),.9,3)
for x in (4,12):
 for y in (18,28):rod('Armour rivet',(x,y,31.8),(x,y,33),.42,4)
# The commissar faces +X. Keep the eye below the cap brim, on his right side.
box('Bionic eye mounting plate',(10.0,-2.25,63.0),(1.5,3.7,3.1),2,'Head',eye,.18)
rod('Bionic eye brass housing',(10,-2.3,63),(11.8,-2.3,63),1.1,4,'Head',eye)
rod('Bale Eye emissive lens',(11.7,-2.3,63),(12,-2.3,63),.74,5,'Head',eye)
rod('Temple conduit',(9.5,-3.6,63),(6.5,-5,61.5),.3,2,'Head',eye)
# Native export uses the original bone names and bind frames. Add a true muzzle
# anchor to the body so the Lasgun beam originates at the new lens.
names.append('YarrickEyeMuzzle');binds['YarrickEyeMuzzle']=Matrix.Translation((12.1,-2.3,63))
raw=(G/'Video/Meshes/Units/AstraMilitarum/LordCommissar.msh').read_bytes();at=8
for _ in range(raw[7]):at=raw.index(0,at)+65
metadata=raw[at:at+111];assert metadata[37]==1
layout=[('vertexPosition',3),('vertexBoneWeights',4),('vertexBoneIndices',4),('vertexTextureCoordinate',2),('vertexNormal',3),('vertexTangent',4)]
def records(obj,bone_names,transform=Matrix.Identity(4),native=False):
 me=obj.data;bm=bmesh.new();bm.from_mesh(me);bmesh.ops.triangulate(bm,faces=list(bm.faces));bm.to_mesh(me);bm.free();me.update()
 if not me.uv_layers:me.uv_layers.new(name='UVMap')
 if not native:
  # Six swatches occupy the right half of the atlas.
  for uv in me.uv_layers.active.data:uv.uv=(.75,(obj['palette']+.5)/6)
 me.calc_loop_triangles();me.calc_tangents(uvmap=me.uv_layers.active.name)
 result=[]
 for tri in me.loop_triangles:
  for li in tri.loops:
   loop=me.loops[li];v=me.vertices[loop.vertex_index];pos=transform@v.co;normal=(transform.to_3x3()@loop.normal).normalized();tangent=(transform.to_3x3()@loop.tangent).normalized()
   if native:
    inf=[(bone_names.index(obj.vertex_groups[w.group].name),w.weight) for w in v.groups if w.weight>1e-5 and obj.vertex_groups[w.group].name in bone_names];inf.sort(key=lambda x:-x[1]);inf=inf[:4]
   else:inf=[(bone_names.index(obj['bone']) if obj['bone'] in bone_names else 0,1)]
   total=sum(w for _,w in inf);weights=[w/total for _,w in inf]+[0]*(4-len(inf));indices=[i for i,_ in inf]+[0]*(4-len(inf))
   uv=me.uv_layers.active.data[li].uv
   result.append((*pos,*weights,*indices,uv.x*.5 if native else uv.x,1-(.5+uv.y*.5) if native else 1-uv.y,*normal,*tangent,loop.bitangent_sign))
 return result
def export(path,bone_names,matrices,recs):
 p=D/path;p.parent.mkdir(parents=True,exist_ok=True);out=bytearray(b'MSH1.0\0'+bytes([len(bone_names)]))
 for name in bone_names:out+=name.encode()+b'\0'+struct.pack('<16f',*(matrices[name][r][c] for c in range(4) for r in range(4)))
 meta=bytearray(metadata);lo=[min(v[i] for v in recs) for i in range(3)];hi=[max(v[i] for v in recs) for i in range(3)]
 struct.pack_into('<3f',meta,5,*lo);struct.pack_into('<3f',meta,21,*hi);struct.pack_into('<3f',meta,91,*[(a+b)/2 for a,b in zip(lo,hi)]);struct.pack_into('<f',meta,107,math.sqrt(sum((a-b)**2 for a,b in zip(lo,hi)))/2)
 out+=meta+bytes([len(layout)])
 for name,width in layout:out+=name.encode()+b'\0'+bytes([width])
 out+=struct.pack('<I',len(recs)*20)
 for rec in recs:out+=struct.pack('<20f',*rec)
 out+=struct.pack('<I',0);p.write_bytes(out);return read_mesh(out)
recs=records(body,names,native=True)
for ob in eye:recs+=records(ob,names)
report={'body':export(Path('Video/Meshes/Units/Foundry/Yarrick.msh'),names,binds,recs)}
recs=[]
for ob in kit:recs+=records(ob,['LeftHandBone'],binds['LeftHandBone'].inverted())
report['claw']=export(Path('Video/Meshes/Weapons/Foundry/YarrickClaw.msh'),['LeftHandBone'],{'LeftHandBone':Matrix.Identity(4)},recs)
# Extend every native animation with the eye anchor following the Head transform.
# No other native channels are resampled or modified.
head_rest=binds['Head'].translation;eye_rest=binds['YarrickEyeMuzzle'].translation
from mathutils import Quaternion
animation_dir=D/'Video/Animations/Units/Foundry';animation_dir.mkdir(parents=True,exist_ok=True)
for source in (G/'Video/Animations/Units/AstraMilitarum').glob('LordCommissar*.anm'):
 data=source.read_bytes();count,frames,fps=struct.unpack_from('<BII',data,7);cur=16;head=None
 for _ in range(count):
  end=data.index(0,cur);name=data[cur:end].decode();cur=end+1
  if name=='Head':head=[struct.unpack_from('<10f',data,cur+f*40) for f in range(frames)]
  cur+=frames*40
 if head is None:continue
 out=bytearray(data);out[7]=count+1;out+=b'YarrickEyeMuzzle\0'
 for sample in head:
  loc=Vector(sample[:3]);rot=Quaternion((sample[6],*sample[3:6]));scale=Vector(sample[7:]);delta=rot@(eye_rest-head_rest)
  p=head_rest+loc+Vector(tuple(delta[i]*scale[i] for i in range(3)))-eye_rest
  out+=struct.pack('<10f',*p,rot.x,rot.y,rot.z,rot.w,*scale)
 (animation_dir/(source.stem.replace('LordCommissar','Yarrick')+'.anm')).write_bytes(out)
# Preview uses native team-colour material for the body and authored materials
# for the kit. Keep its source UVs intact; the export alone remaps the body UVs.
rig.data.pose_position='POSE';bpy.context.view_layer.update()
bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(W/'Yarrick.blend'))
scene=bpy.context.scene
visible=[o for o in scene.objects if o.type=='MESH' and not o.hide_render]
pts=[o.matrix_world@Vector(v) for o in visible for v in o.bound_box];lo=Vector(tuple(min(p[i] for p in pts) for i in range(3)));hi=Vector(tuple(max(p[i] for p in pts) for i in range(3)));center=(lo+hi)/2
camera=scene.camera;camera.location=center+Vector((100,-125,65));camera.rotation_euler=(center-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.type='ORTHO';camera.data.ortho_scale=95
scene.render.resolution_x=1000;scene.render.resolution_y=1000;scene.render.filepath=str(W/'Yarrick-preview.png');bpy.ops.render.render(write_still=True)
(W/'model-validation.json').write_text(json.dumps(report,indent=2));print('EXPORTED YARRICK',report)
