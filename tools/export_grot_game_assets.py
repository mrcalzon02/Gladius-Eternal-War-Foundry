"""Native MSH/ANM export of the accepted Grot replacement, in isolated staging."""
from pathlib import Path
import bpy,bmesh,json,struct,math,hashlib,sys
from mathutils import Vector,Matrix
R=Path(__file__).resolve().parents[1];D=R/'model-workbench/Grot-Sneak';OUT=R/'game-ready/Foundry Grot Replacement';DATA=OUT/'Data';GAME=Path(r'C:/Program Files (x86)/Steam/steamapps/common/Warhammer 40000 Gladius - Relics of War/Data')
for sub in ['Video/Meshes/Units/Foundry','Video/Meshes/Weapons/Foundry','Video/Animations/Units/Foundry','Video/Materials/Units/Foundry','Video/Textures/Units/Foundry','World/Units/Orks']:(DATA/sub).mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(R/'tools'));from native_gladius import read_mesh,read_animation
from reference_grot_shape import shape
muzzle_metadata=D/'native-attachments.json';muzzle_ready=None
if muzzle_metadata.is_file():muzzle_ready=Matrix(json.loads(muzzle_metadata.read_text())['muzzle_world_matrix'])
else:
 bpy.ops.wm.open_mainfile(filepath=str(D/'Grot-Sneak-donor.blend'));bpy.context.view_layer.update();mr=bpy.data.objects['Slugga_rig'];mb=mr.data.bones['.Muzzle'];stored=mb['gladius_source_bind'];muzzle_original=mr.matrix_world@Matrix([stored[:4],stored[4:8],stored[8:12],stored[12:]])
SOURCE=D/'Grot-Animation-Work.blend';source_hash=hashlib.sha256(SOURCE.read_bytes()).hexdigest();bpy.ops.wm.open_mainfile(filepath=str(SOURCE));scene=bpy.context.scene;rig=bpy.data.objects['Grot_Animation_rig'];objects=[o for o in scene.objects if o.type=='MESH' and not o.hide_render];body=bpy.data.objects['Grot unified game body'];rig.animation_data.action=None;rig.animation_data.use_nla=False
for t in rig.animation_data.nla_tracks:t.mute=True
for p in rig.pose.bones:p.matrix_basis.identity()
bpy.context.view_layer.update();rig.data.pose_position='REST'
names=[b.name for b in rig.data.bones];rests={b.name:b.matrix_local.copy() for b in rig.data.bones};binds={n:rests[n]@Matrix.Rotation(math.pi/2,4,'Z') for n in names}
weapons={'Grot retained slugga':'GrotPistol','Grot narrow shank blade':'GrotShank','Grot shank bound handle':'GrotShank'}
# Preserve source UVs for sampling while writing a coherent single-material game atlas.
material_cache={};bake=[]
for o in objects:
 o.data.uv_layers.active.name='SourceUV';old=o.data.uv_layers.active;new=o.data.uv_layers.new(name='GameUV');o.data.uv_layers.active=new
 for a,b in zip(new.data,old.data):a.uv=b.uv
 for i,original in enumerate(list(o.data.materials)):
  if original.name not in material_cache:
   m=original.copy();m.name='Grot native bake '+original.name;nodes=m.node_tree.nodes;links=m.node_tree.links;uv=nodes.new('ShaderNodeUVMap');uv.uv_map='SourceUV'
   for node in list(nodes):
    if node.type=='TEX_IMAGE':links.new(uv.outputs['UV'],node.inputs['Vector'])
    if node.type=='NORMAL_MAP':node.uv_map='SourceUV'
   bs=nodes.get('Principled BSDF');em=nodes.new('ShaderNodeEmission');c=bs.inputs['Base Color'];links.new(c.links[0].from_socket,em.inputs['Color']) if c.is_linked else None
   if not c.is_linked:em.inputs['Color'].default_value=c.default_value
   target=nodes.new('ShaderNodeTexImage');nodes.active=target;bake.append((m,bs,em,target));material_cache[original.name]=m
  o.data.materials[i]=material_cache[original.name]
for uv in body.data.uv_layers['GameUV'].data:uv.uv=(uv.uv.x*.75,.25+uv.uv.y*.75)
extras=[o for o in objects if o!=body];bpy.ops.object.select_all(action='DESELECT')
for o in extras:o.select_set(True)
bpy.context.view_layer.objects.active=extras[0];bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(island_margin=.025);bpy.ops.object.mode_set(mode='OBJECT')
for o in extras:
 for uv in o.data.uv_layers['GameUV'].data:uv.uv=(.77+uv.uv.x*.22,.02+uv.uv.y*.96)
bpy.ops.object.select_all(action='DESELECT')
for o in objects:o.select_set(True)
bpy.context.view_layer.objects.active=body;scene.render.engine='CYCLES';scene.cycles.samples=1;scene.render.bake.use_selected_to_active=False;scene.render.bake.use_clear=False;scene.render.bake.margin=4
for role in ([] if '--skip-bake' in sys.argv else ['Diffuse','Normal','SIC']):
 im=bpy.data.images.new('Grot native '+role,width=1024,height=1024,alpha=False)
 if role!='Diffuse':im.colorspace_settings.name='Non-Color'
 for m,bs,em,target in bake:
  target.image=im;m.node_tree.nodes.active=target;links=m.node_tree.links
  if role=='Normal':links.new(bs.outputs[0],m.node_tree.nodes.get('Material Output').inputs['Surface'])
  else:
   if role=='SIC':
    for link in list(em.inputs['Color'].links):links.remove(link)
    em.inputs['Color'].default_value=(.24 if 'steel' in m.name.lower() or 'slugga' in m.name.lower() else .055,0,0,1)
   links.new(em.outputs[0],m.node_tree.nodes.get('Material Output').inputs['Surface'])
 bpy.ops.object.bake(type='NORMAL' if role=='Normal' else 'EMIT');im.filepath_raw=str(OUT/('Grot'+role+'.png'));im.file_format='PNG';im.save()

raw=(GAME/'Video/Meshes/Units/AstraMilitarum/Guardsman.msh').read_bytes();offset=8
for _ in range(raw[7]):offset=raw.index(0,offset)+65
template=raw[offset:offset+111];assert template[37]==1
layout=[('vertexPosition',3),('vertexBoneWeights',4),('vertexBoneIndices',4),('vertexTextureCoordinate',2),('vertexNormal',3),('vertexTangent',4)]
def records(o,bones,transform=None,rigid=False):
 me=o.data
 if any(len(p.vertices)>4 for p in me.polygons):
  bm=bmesh.new();bm.from_mesh(me);bmesh.ops.triangulate(bm,faces=[f for f in bm.faces if len(f.verts)>4]);bm.to_mesh(me);bm.free();me.update()
 me.calc_loop_triangles();me.calc_tangents(uvmap='GameUV');out=[];transform=transform or Matrix.Identity(4);normalmat=transform.to_3x3().inverted().transposed()
 for tri in me.loop_triangles:
  for li in tri.loops:
   loop=me.loops[li];v=me.vertices[loop.vertex_index];influences=[(bones.index(o.vertex_groups[g.group].name),g.weight) for g in v.groups if g.weight>1e-6 and o.vertex_groups[g.group].name in bones] if not rigid else [(0,1)]
   influences.sort(key=lambda v:-v[1]);assert influences and len(influences)<=4;total=sum(w for _,w in influences);weights=[w/total for _,w in influences]+[0]*(4-len(influences));indices=[i for i,w in influences]+[0]*(4-len(influences));uv=me.uv_layers['GameUV'].data[li].uv
   out.append((*(transform@v.co),*weights,*indices,uv.x,1-uv.y,*(normalmat@loop.normal).normalized(),*(transform.to_3x3()@loop.tangent).normalized(),loop.bitangent_sign))
 return out
def write_mesh(path,bones,frames,vertices):
 raw=bytearray(b'MSH1.0\0'+bytes([len(bones)]))
 for name in bones:raw+=name.encode()+b'\0'+struct.pack('<16f',*(frames[name][r][c] for c in range(4) for r in range(4)))
 low=[min(v[k] for v in vertices) for k in range(3)];high=[max(v[k] for v in vertices) for k in range(3)];meta=bytearray(template);struct.pack_into('<3f',meta,5,*low);struct.pack_into('<3f',meta,21,*high);struct.pack_into('<3f',meta,91,*[(a+b)/2 for a,b in zip(low,high)]);struct.pack_into('<f',meta,107,(Vector(high)-Vector(low)).length/2)
 raw+=meta+bytes([len(layout)])
 for name,width in layout:raw+=name.encode()+b'\0'+bytes([width])
 raw+=struct.pack('<I',len(vertices)*20)
 for vertex in vertices:raw+=struct.pack('<20f',*vertex)
 raw+=struct.pack('<I',0);path.write_bytes(raw);return read_mesh(raw)
body_records=[]
for o in objects:
 if o.name not in weapons:body_records.extend(records(o,names))
exports={'body':write_mesh(DATA/'Video/Meshes/Units/Foundry/GrotReplacement.msh',names,binds,body_records)}
if muzzle_ready is not None:muzzleworld=muzzle_ready;muzzle=muzzleworld.translation.copy()
else:
 muzzle=shape((muzzle_original.translation-Vector((4.4,-11.4,12)))*.76+Vector((2,-8.6,11.9)));pivot=Vector((1.8,-8.6,11.8));rot=Matrix.Rotation(math.radians(31),4,'Y');muzzle=pivot+rot@((muzzle-pivot)*.9);muzzleworld=rot@muzzle_original.to_3x3().to_4x4();muzzleworld.translation=muzzle
for file,bone in [('GrotPistol','RightHand'),('GrotShank','LeftHand')]:
 transform=binds[bone].inverted();vertices=[]
 for o in objects:
  if weapons.get(o.name)==file:vertices.extend(records(o,['Root'],transform,True))
 wb={'Root':Matrix.Identity(4)}
 if file=='GrotPistol':wb['.Muzzle']=transform@muzzleworld
 exports[file]=write_mesh(DATA/('Video/Meshes/Weapons/Foundry/'+file+'.msh'),list(wb),wb,vertices)
rig.data.pose_position='POSE';clips={};specs=json.loads((D/'animation-build.json').read_text())['clips']
for label,suffix in [('Idle','Idle'),('Snarl','Snarl'),('Sneak','Move'),('Run','Run'),('Pistol fire','Ranged'),('Shank stab','Melee'),('Hit reaction','Hit'),('Death','Die')]:
 rig.animation_data.action=bpy.data.actions['Grot - '+label];frames=[]
 for f in range(1,specs[label]['frames'][1]+1):scene.frame_set(f);bpy.context.view_layer.update();frames.append({name:rig.pose.bones[name].matrix.copy() for name in names})
 clips[suffix]=frames
def mix(a,b,t):
 al,ar,asc=a.decompose();bl,br,bsc=b.decompose();return Matrix.LocRotScale(al.lerp(bl,t),ar.slerp(br,t),asc.lerp(bsc,t))
for suffix,start,end in [('MoveBegin',clips['Idle'][0],clips['Move'][0]),('MoveEnd',clips['Move'][0],clips['Idle'][0])]:clips[suffix]=[{n:mix(start[n],end[n],i/8) for n in names} for i in range(9)]
clips['Grenade']=clips['Ranged'];clips['Construct']=clips['Idle'];maxerr=0
for suffix,frames in clips.items():
 raw=bytearray(b'ANM1.0\0'+struct.pack('<BII',len(names),len(frames),24))
 for name in names:
  raw+=name.encode()+b'\0';last=None
  for frame in frames:
   pose=frame[name];linear=pose.to_3x3()@rests[name].to_3x3().inverted();scale=Vector([linear.row[i].length for i in range(3)]);rotation=Matrix([[linear[i][j]/scale[i] for j in range(3)] for i in range(3)]).to_quaternion().normalized()
   if last and rotation.dot(last)<0:rotation.negate()
   last=rotation.copy();position=pose.translation-rests[name].translation;rebuild=Matrix.Diagonal(scale)@rotation.to_matrix();maxerr=max(maxerr,max(abs(linear[r][c]-rebuild[r][c]) for r in range(3) for c in range(3)));raw+=struct.pack('<10f',*position,rotation.x,rotation.y,rotation.z,rotation.w,*scale)
 (DATA/('Video/Animations/Units/Foundry/GrotReplacement'+suffix+'.anm')).write_bytes(raw);assert read_animation(raw)['frames']==len(frames)
assert maxerr<.0001,maxerr
report={'source_sha256':source_hash,'exports':exports,'frames':{s:len(f) for s,f in clips.items()},'max_animation_matrix_error':maxerr,'muzzle_world':list(muzzle),'weapon_bind_frames':{n:[list(row) for row in binds[n]] for n in ['LeftHand','RightHand']},'total_triangles':sum(e['triangles'] for e in exports.values()),'native_bones':names,'grenade_note':'Fitted raise-and-release fallback uses the ranged pose library; original grenade gameplay is retained.'}
(OUT/'EXPORT.json').write_text(json.dumps(report,indent=2));assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==source_hash;print('NATIVE_GROT_EXPORTED',report['total_triangles'],maxerr)
