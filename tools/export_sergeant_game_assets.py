"""Export the approved Blender sergeant to native MSH1.0/ANM1.0 staging assets.

Preserves native bind frames and excludes preview pivot bones. The source blend
is read only. Texture packing and unit XML are completed by package_sergeant.py.
"""
from pathlib import Path
import bpy,bmesh,struct,json,math,hashlib,sys
from mathutils import Matrix,Vector
R=Path(__file__).resolve().parents[1]
SOURCE=R/'model-workbench/Sergeant-Headset-Variant/Sergeant-Animation-Work.blend'
OUT=R/'game-ready/Foundry Veteran Sergeant';DATA=OUT/'Data'
GAME=Path(r'C:\Program Files (x86)\Steam\steamapps\common\Warhammer 40000 Gladius - Relics of War\Data')
for sub in ('Video/Meshes/Units/Foundry','Video/Meshes/Weapons/Foundry','Video/Animations/Units/Foundry','Video/Textures/Units/Foundry','Video/Materials/Units/Foundry','World/Units/AstraMilitarum'):(DATA/sub).mkdir(parents=True,exist_ok=True)
source_hash=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
sys.path.insert(0,str(R/'tools'))
from native_gladius import read_mesh,read_animation
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
if bpy.context.object and bpy.context.object.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
scene=bpy.context.scene;rig=bpy.data.objects['Guardsman_rig'];body=bpy.data.objects['Guardsman']
bone_names=[b.name for b in sorted((b for b in rig.data.bones if not b.get('gladius_pivot')),key=lambda b:b['gladius_source_index'])]
def bind(b):
    a=b['gladius_source_bind'];return Matrix([a[:4],a[4:8],a[8:12],a[12:16]])
binds={n:bind(rig.data.bones[n]) for n in bone_names}
rig.animation_data.action=bpy.data.actions['Sergeant rework - Idle (draft)'];rig.animation_data.use_nla=False
for t in rig.animation_data.nla_tracks:t.mute=True
scene.frame_set(1);bpy.context.view_layer.update()
weapon_matrices={}
for name,bone in [('Sergeant left hand chainsword','LeftHandBone'),('LordCommissarBoltPistol','RightHandBone')]:
    skin=rig.pose.bones[bone].matrix@rig.data.bones[bone].matrix_local.inverted()
    weapon_matrices[name]=binds[bone].inverted()@skin.inverted()@rig.matrix_world.inverted()@bpy.data.objects[name].matrix_world

def template_header(raw):
    p=8
    for _ in range(raw[7]):p=raw.index(0,p)+65
    assert raw[p+37]==1
    return raw[p:p+111]
template=template_header((GAME/'Video/Meshes/Units/AstraMilitarum/Guardsman.msh').read_bytes())
layout=[('vertexPosition',3),('vertexBoneWeights',4),('vertexBoneIndices',4),('vertexTextureCoordinate',2),('vertexNormal',3),('vertexTangent',4)]
def write_mesh(path,names,matrices,records):
    raw=bytearray(b'MSH1.0\0'+bytes([len(names)]))
    for name in names:
        raw+=name.encode()+b'\0'+struct.pack('<16f',*(matrices[name][r][c] for c in range(4) for r in range(4)))
    metadata=bytearray(template)
    low=[min(v[k] for v in records) for k in range(3)];high=[max(v[k] for v in records) for k in range(3)]
    center=[(a+b)/2 for a,b in zip(low,high)];radius=math.sqrt(sum((b-a)**2 for a,b in zip(low,high)))/2
    struct.pack_into('<3f',metadata,5,*low);struct.pack_into('<3f',metadata,21,*high)
    struct.pack_into('<3f',metadata,91,*center);struct.pack_into('<f',metadata,107,radius)
    raw+=metadata+bytes([len(layout)])
    for name,width in layout:raw+=name.encode()+b'\0'+bytes([width])
    raw+=struct.pack('<I',len(records)*20)
    for record in records:
        assert len(record)==20 and all(math.isfinite(v) for v in record)
        raw+=struct.pack('<20f',*record)
    raw+=struct.pack('<I',0);path.write_bytes(raw)
    parsed=read_mesh(bytes(raw));assert parsed['triangles']==len(records)//3
    return dict(triangles=len(records)//3,bones=names,bounds=[low,high],sha256=hashlib.sha256(raw).hexdigest())

# Bake only the additional kit. The original diffuse/normal/team masks occupy an
# unchanged atlas tile, avoiding a baked-in player colour on the body.
extras=[o for o in scene.objects if o.type=='MESH' and o!=body and any(m.type=='ARMATURE' and m.object==rig for m in o.modifiers)]
assert len(extras)==3,[o.name for o in extras]
rig.data.pose_position='REST'
bpy.ops.object.select_all(action='DESELECT')
for obj in extras:obj.select_set(True)
bpy.context.view_layer.objects.active=extras[0]
bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(island_margin=.025);bpy.ops.object.mode_set(mode='OBJECT')
for obj in extras:
    for uv in obj.data.uv_layers.active.data:uv.uv=(.52+uv.uv.x*.46,.02+uv.uv.y*.96)
for uv in body.data.uv_layers.active.data:uv.uv=(uv.uv.x*.5,.5+uv.uv.y*.5)
bake_materials=[]
for obj in extras:
    for index,original in enumerate(list(obj.data.materials)):
        mat=original.copy();obj.data.materials[index]=mat
        nodes=mat.node_tree.nodes;links=mat.node_tree.links;bs=nodes.get('Principled BSDF')
        color=bs.inputs['Base Color'];source=color.links[0].from_socket if color.is_linked else None
        emission=nodes.new('ShaderNodeEmission')
        if source:links.new(source,emission.inputs['Color'])
        else:emission.inputs['Color'].default_value=color.default_value
        links.new(emission.outputs[0],nodes.get('Material Output').inputs['Surface'])
        target=nodes.new('ShaderNodeTexImage');bake_materials.append((mat,emission,target,'ember' in original.name.lower()))
scene.render.engine='CYCLES';scene.cycles.samples=1;scene.render.bake.use_clear=False;scene.render.bake.margin=6
for channel in ('Diffuse','SIC'):
    im=bpy.data.images.new('Sergeant kit '+channel,1024,1024,alpha=False)
    if channel=='SIC':im.colorspace_settings.name='Non-Color'
    for mat,emission,target,ember in bake_materials:
        target.image=im;mat.node_tree.nodes.active=target
        if channel=='SIC':
            for link in list(emission.inputs['Color'].links):mat.node_tree.links.remove(link)
            emission.inputs['Color'].default_value=(.08,1 if ember else 0,0,1)
    bpy.ops.object.bake(type='EMIT');im.filepath_raw=str(OUT/('kit-'+channel+'.png'));im.file_format='PNG';im.save()

def mesh_records(obj,names,transform=None):
    mesh=obj.data
    if any(len(p.vertices)>4 for p in mesh.polygons):
        bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.triangulate(bm,faces=[f for f in bm.faces if len(f.verts)>4]);bm.to_mesh(mesh);bm.free();mesh.update()
    mesh.calc_loop_triangles();mesh.calc_tangents(uvmap=mesh.uv_layers.active.name)
    records=[];normal_matrix=transform.to_3x3().inverted().transposed() if transform else None
    for tri in mesh.loop_triangles:
        for li in tri.loops:
            loop=mesh.loops[li];vertex=mesh.vertices[loop.vertex_index]
            position=transform@vertex.co if transform else vertex.co
            normal=(normal_matrix@loop.normal).normalized() if transform else loop.normal
            tangent=(transform.to_3x3()@loop.tangent).normalized() if transform else loop.tangent
            influences=[(names.index(obj.vertex_groups[w.group].name),w.weight) for w in vertex.groups if w.weight>.00001 and obj.vertex_groups[w.group].name in names]
            influences.sort(key=lambda p:-p[1]);assert influences and len(influences)<=4
            total=sum(w for _,w in influences);indices=[i for i,w in influences]+[0]*(4-len(influences));weights=[w/total for i,w in influences]+[0]*(4-len(influences))
            uv=mesh.uv_layers.active.data[li].uv
            records.append((*position,*weights,*indices,uv.x,1-uv.y,*normal,*tangent,loop.bitangent_sign))
    return records
records=[]
for obj in [body]+extras:records.extend(mesh_records(obj,bone_names))
exports={}
exports['body']=write_mesh(DATA/'Video/Meshes/Units/Foundry/VeteranSergeant.msh',bone_names,binds,records)
for obj_name,file,bone in [('Sergeant left hand chainsword','VeteranChainsword','LeftHandBone'),('LordCommissarBoltPistol','VeteranBoltPistol','RightHandBone')]:
    obj=bpy.data.objects[obj_name];weapon_rig=obj.parent
    names=[b.name for b in sorted((b for b in weapon_rig.data.bones if not b.get('gladius_pivot')),key=lambda b:b['gladius_source_index'])]
    transform=weapon_matrices[obj_name]
    weapon_binds={n:transform@bind(weapon_rig.data.bones[n]) for n in names}
    exports[file]=write_mesh(DATA/('Video/Meshes/Weapons/Foundry/'+file+'.msh'),names,weapon_binds,mesh_records(obj,names,transform))

rig.data.pose_position='POSE'
def activate(action):
    rig.animation_data.action=None
    for pb in rig.pose.bones:pb.matrix_basis.identity()
    rig.animation_data.action=action;rig.animation_data.use_nla=False
def sample(action,frames):
    activate(action);result=[]
    for frame in frames:
        scene.frame_set(math.floor(frame),subframe=frame-math.floor(frame));bpy.context.view_layer.update()
        result.append({n:rig.pose.bones[n].matrix.copy() for n in bone_names})
    return result
clips={}
for suffix,action_name in [('Idle','Sergeant rework - Idle (draft)'),('Move','Sergeant rework - Walk (draft)'),('Ranged','Sergeant rework - Pistol fire (draft)'),('Melee','Sergeant rework - Chainsword lunge (draft)')]:
    action=bpy.data.actions[action_name];start,end=map(int,action.frame_range);clips[suffix]=sample(action,range(start,end+1))
def blend(a,b,t):
    al,ar,asc=a.decompose();bl,br,bsc=b.decompose();return Matrix.LocRotScale(al.lerp(bl,t),ar.slerp(br,t),asc.lerp(bsc,t))
clips['MoveBegin']=[{n:blend(clips['Idle'][0][n],clips['Move'][0][n],i/8) for n in bone_names} for i in range(9)]
clips['MoveEnd']=[{n:blend(clips['Move'][0][n],clips['Idle'][0][n],i/8) for n in bone_names} for i in range(9)]
max_error=0
for suffix,frames in clips.items():
    raw=bytearray(b'ANM1.0\0'+struct.pack('<BII',len(bone_names),len(frames),24))
    for n in bone_names:
        raw+=n.encode()+b'\0';rest=rig.data.bones[n].matrix_local
        last=None
        for matrices in frames:
            pose=matrices[n];linear=pose.to_3x3()@rest.to_3x3().inverted()
            scale=Vector(tuple(linear.row[i].length for i in range(3)))
            rotation=Matrix(tuple(tuple(linear[i][j]/scale[i] for j in range(3)) for i in range(3))).to_quaternion().normalized()
            if last and rotation.dot(last)<0:rotation.negate()
            last=rotation.copy();position=pose.translation-rest.translation
            reconstructed=Matrix.Diagonal(scale)@rotation.to_matrix()
            max_error=max(max_error,max(abs(linear[r][c]-reconstructed[r][c]) for r in range(3) for c in range(3)))
            raw+=struct.pack('<10f',*position,rotation.x,rotation.y,rotation.z,rotation.w,*scale)
    assert read_animation(bytes(raw))['frames']==len(frames)
    (DATA/('Video/Animations/Units/Foundry/VeteranSergeant'+suffix+'.anm')).write_bytes(raw)
assert max_error<.0001,max_error
report=dict(source_blend=str(SOURCE),source_sha256=source_hash,exports=exports,
            animation_frames={k:len(v) for k,v in clips.items()},animation_linear_matrix_error=max_error,
            body_preview_uses_dual_quaternion=body.modifiers[0].use_deform_preserve_volume,
            weapon_attachment_transforms={k:[list(r) for r in v] for k,v in weapon_matrices.items()})
(OUT/'EXPORT.json').write_text(json.dumps(report,indent=2))
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==source_hash
print('NATIVE_SERGEANT_EXPORTED',json.dumps({k:v['triangles'] for k,v in exports.items()}),flush=True)
