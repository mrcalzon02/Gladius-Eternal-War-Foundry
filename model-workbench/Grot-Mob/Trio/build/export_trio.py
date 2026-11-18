"""Blender 4.3 native export for the authored three-character Gladius member."""
import argparse
from collections import defaultdict
from pathlib import Path
import hashlib
import json
import math
import struct
import sys
import xml.etree.ElementTree as ET
import bpy
import numpy as np
from mathutils import Matrix, Vector

NATIVE = Matrix.Rotation(math.pi/2, 4, 'Z')
EVENTS = ('Idle','Move','MoveBegin','MoveEnd','Run','Ranged','Melee','Hit','Die','Construct','Grenade')
HAND = {'pistol':'Gunner_hand.R','choppa':'Cutter_hand.R'}
NAMES = {'body':'GrotTrio', 'pistol':'GrotTrioPistol','choppa':'GrotTrioChoppa'}
TILES = {'mek':(0,0),'gunner':(1,0),'cutter':(0,1)}
LAYOUT = [('vertexPosition',3),('vertexBoneWeights',4),('vertexBoneIndices',4),
          ('vertexTextureCoordinate',2),('vertexNormal',3),('vertexTangent',4)]


def write_mesh(path, binds, records, template):
    raw=bytearray(b'MSH1.0\x00'+bytes([len(binds)]))
    for name,bind in binds.items():
        raw += name.encode()+b'\x00'+np.asarray(bind,dtype='<f4').T.tobytes()
    points=records[:,:3]
    low,high=points.min(0),points.max(0)
    meta=bytearray(template)
    for offset,pos in ((5,low),(21,high),(91,(low+high)/2)):
        struct.pack_into('<3f',meta,offset,*pos)
    struct.pack_into('<f',meta,107,np.linalg.norm(high-low)/2)
    raw+=meta+bytes([len(LAYOUT)])
    for semantic,size in LAYOUT:
        raw+=semantic.encode()+b'\x00'+bytes([size])
    raw+=struct.pack('<I',records.size)+records.astype('<f4').tobytes()+struct.pack('<I',0)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(raw)


def template_from(path):
    raw=path.read_bytes()
    i=8
    for _ in range(raw[7]):
        i=raw.index(0,i)+65
    assert raw[:7]==b'MSH1.0\0' and raw[i+37]==1
    return raw[i:i+111]


def neutral(rig):
    rig.animation_data_create()
    rig.animation_data.action=None
    rig.animation_data.use_nla=False
    for tr in rig.animation_data.nla_tracks: tr.mute=True
    for bone in rig.pose.bones:bone.matrix_basis=Matrix.Identity(4)


def surface_spec(obj):
    name=obj.name.lower()
    if any(word in name for word in ('spanner','slugga','choppa','plate','metal','shell in')):return 65
    if any(word in name for word in ('teeth','tusk','fang','eye')):return 39
    if any(word in name for word in ('boot','binding','strap','belt','leather','goggle')):return 27
    if any(word in name for word in ('trouser','hood','cap','apron','sash','cloth')):return 12
    return 19


def record_mesh(obj, header, role, part, bone_indices):
    mesh=obj.data
    mesh.calc_loop_triangles()
    uv=mesh.uv_layers.active
    assert uv is not None and len(uv.data)==len(mesh.loops)
    normal_mat=header.to_3x3().inverted().transposed()
    corner_normals=mesh.corner_normals
    result=[];faces=[]
    tile=TILES[role]
    for tri in mesh.loop_triangles:
        positions=[header @ mesh.vertices[i].co for i in tri.vertices]
        coords=[uv.data[l].uv.copy() for l in tri.loops]
        e1,e2=positions[1]-positions[0],positions[2]-positions[0]
        u1,u2=coords[1]-coords[0],coords[2]-coords[0]
        det=u1.x*u2.y-u1.y*u2.x
        assert abs(det)>1e-14 and e1.cross(e2).length>1e-12,(obj.name,tri.index)
        tangent=(e1*u2.y-e2*u1.y)/det
        bitangent=(e2*u1.x-e1*u2.x)/det
        faces.append([[u.x,1-u.y] for u in coords])
        for p,coord,li,idx in zip(positions,coords,tri.loops,tri.vertices):
            normal=(normal_mat@corner_normals[li].vector).normalized()
            tan=(tangent-normal*normal.dot(tangent)).normalized()
            hemi=1. if normal.cross(tan).dot(bitangent)>0 else -1.
            groups=[(obj.vertex_groups[g.group].name,g.weight) for g in mesh.vertices[idx].groups if g.weight>1e-7]
            assert 1<=len(groups)<=4,(obj.name,idx,groups)
            if part!='body':
                assert all(name==HAND[part] for name,w in groups),(obj.name,groups)
                weights=[1.,0,0,0];ids=[0]*4
            else:
                groups.sort(key=lambda e:-e[1])
                total=sum(w for n,w in groups)
                assert abs(total-1)<1e-4
                weights=[w/total for n,w in groups]+[0]*(4-len(groups))
                ids=[bone_indices[n] for n,w in groups]+[0]*(4-len(groups))
            result.append([*p,*weights,*ids,(tile[0]+coord.x)*.5,(tile[1]+1-coord.y)*.5,*normal,*tan,hemi])
    return result,faces


def muzzle(objs, hand_frame, reference):
    def points(fragment):
        obj=next(o for o in objs if fragment in o.name.lower())
        return np.array([NATIVE @ obj.matrix_world @ v.co for v in obj.data.vertices])
    rings=np.unique(points('dark inset muzzle'),axis=0)
    approximate=rings.mean(0)-points('armoured receiver').mean(0)
    _,axes=np.linalg.eigh(np.cov(rings.T));v=axes[:,-1]
    if v.dot(approximate)<0:v=-v
    depth=rings@v
    front=rings[depth>depth.max()-.015];back=rings[depth<depth.min()+.015]
    assert len(front)>=6 and len(back)>=6
    lip=front.mean(0);axis=lip-back.mean(0);axis/=np.linalg.norm(axis)
    down=points('battered stock').mean(0)-lip
    down-=down.dot(axis)*axis;down/=np.linalg.norm(down)
    mat=Matrix.Identity(4)
    # Match the shipped effect-frame scale and its outward +X / grip-side +Y axes.
    scale=reference.get('.Muzzle').to_scale().x
    for i,vec in enumerate((axis,down,np.cross(axis,down))):
        for j in range(3):mat[j][i]=float(vec[j])*scale
    mat.translation=Vector(lip)
    return hand_frame.inverted() @ mat


def sample_action(rig,action,rest):
    neutral(rig);rig.animation_data.action=action
    first,last=map(round,action.frame_range)
    assert first==1 and last>1
    names=list(rest);poses=[]
    for f in range(first,last+1):
        bpy.context.scene.frame_set(f)
        to_native=NATIVE@rig.matrix_world
        poses.append([to_native@rig.pose.bones[n].matrix for n in names])
    raw=bytearray(b'ANM1.0\x00'+struct.pack('<BII',len(names),len(poses),24))
    for i,n in enumerate(names):
        raw+=n.encode()+b'\x00';prev=None
        for frame in poses:
            rot=frame[i].to_3x3()@rest[n].to_3x3().inverted()
            scale=Vector([row.length for row in rot.row])
            r=Matrix([[rot[a][b]/scale[a] for b in range(3)] for a in range(3)]).to_quaternion().normalized()
            if prev is not None and r.dot(prev)<0:r.negate()
            prev=r
            assert np.max(np.abs(np.array(rot)-np.array(Matrix.Diagonal(scale)@r.to_matrix())))<.001
            raw+=struct.pack('<10f',*(frame[i].translation-rest[n].translation),r.x,r.y,r.z,r.w,*scale)
    return raw, len(poses)


def main():
    cli=argparse.ArgumentParser()
    for n in ('repo','data','stage'):cli.add_argument('--'+n,type=Path,required=True)
    opts=cli.parse_args(sys.argv[sys.argv.index('--')+1:])
    ref=opts.repo/'3038342810/Data/Video/Meshes'
    sys.path.insert(0,str(opts.repo/'tools'))
    from native_gladius import read_mesh,read_animation
    stage=opts.stage;stage.mkdir(parents=True,exist_ok=True)
    data=opts.data
    rigs=[o for o in bpy.context.scene.objects if o.type=='ARMATURE']
    assert len(rigs)==1
    rig=rigs[0];neutral(rig);rig.data.pose_position='REST'
    bpy.context.scene.frame_set(1)
    objs=sorted([o for o in bpy.context.scene.objects if o.type=='MESH' and 'native_part' in o],key=lambda o:o.name)
    assert objs and len(rig.data.bones)==51
    native_rig=NATIVE@rig.matrix_world
    rests={b.name:native_rig@b.matrix_local for b in rig.data.bones}
    binds={}
    for n,m in rests.items():
        trans,q,_=m.decompose();binds[n]=Matrix.LocRotScale(trans,q,None)@Matrix.Rotation(math.pi/2,4,'Z')
    idx={n:i for i,n in enumerate(binds)}
    template=template_from(ref/'Units/Foundry/GrotReplacement.msh')
    refdata=(ref/'Weapons/Foundry/GrotPistol.msh').read_bytes();refbind={};at=8
    for _ in range(refdata[7]):
        end=refdata.index(0,at);n=refdata[at:end].decode()
        refbind[n]=Matrix(np.frombuffer(refdata,dtype='<f4',count=16,offset=end+1).reshape(4,4).T.tolist());at=end+65
    allrecords=defaultdict(list)
    meta=[];tex={}
    for obj in objs:
        role=obj['trio_role'].lower();part=obj['native_part'].lower()
        header=NATIVE@obj.matrix_world
        if part!='body':header=binds[HAND[part]].inverted()@header
        records,faces=record_mesh(obj,header,role,part,idx)
        im=next(n.image for n in obj.data.materials[0].node_tree.nodes if n.type=='TEX_IMAGE' and n.image)
        assert im.packed_file
        if role not in tex:
            (stage/(role+'.png')).write_bytes(im.packed_file.data);tex[role]=im.name
        else:assert tex[role]==im.name
        meta.append(dict(name=obj.name,role=role,part=part,specular=surface_spec(obj),uv_triangles=faces,start=len(allrecords[part]),count=len(records)))
        allrecords[part].extend(records)
    (stage/'objects.json').write_text(json.dumps(meta,separators=(',',':')))
    assert set(allrecords)==set(NAMES)
    gun_bones={'Root':Matrix.Identity(4),'.Muzzle':muzzle(objs,binds[HAND['pistol']],refbind)}
    plans={'body':binds,'pistol':gun_bones,'choppa':{'Root':Matrix.Identity(4)}}
    report={'source_sha256':hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest(),'meshes':{},'animations':{}}
    for k,r in allrecords.items():
        folder='Units' if k=='body' else 'Weapons'
        p=data/f'Video/Meshes/{folder}/Foundry/{NAMES[k]}.msh'
        write_mesh(p,plans[k],np.asarray(r,dtype='<f4'),template)
        info=read_mesh(p.read_bytes());report['meshes'][k]={'triangles':info['triangles'],'bones':len(info['bones']),'bounds':info['bounds']}
    total=sum(tr['triangles'] for tr in report['meshes'].values())
    assert total==4486,(total,report['meshes'])
    rig.data.pose_position='POSE';bpy.context.view_layer.update()
    target=data/'Video/Animations/Units/Foundry';target.mkdir(parents=True,exist_ok=True)
    for suffix in EVENTS:
        raw,count=sample_action(rig,bpy.data.actions[suffix],rests)
        path=target/f'GrotTrio{suffix}.anm';path.write_bytes(raw)
        parsed=read_animation(raw);assert parsed['frames']==count and parsed['fps']==24
        report['animations'][suffix]=count
    mat=ET.Element('material');t=ET.SubElement(mat,'textures')
    for name in ('GrotTrioDiffuse','GrotTrioNormal','GrotTrioSIC'):ET.SubElement(t,'texture',name='Units/Foundry/'+name)
    ET.SubElement(t,'texture',name='ShadowMapColor');ET.indent(mat)
    m=data/'Video/Materials/Units/Foundry/GrotTrio.xml';m.parent.mkdir(parents=True,exist_ok=True)
    ET.ElementTree(mat).write(m,encoding='utf-8',xml_declaration=True)
    (stage/'export.json').write_text(json.dumps(report,indent=2))
    print('NATIVE_EXPORTED',json.dumps(report),flush=True)


if __name__=='__main__':main()
