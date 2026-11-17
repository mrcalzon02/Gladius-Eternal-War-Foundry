"""Independently decode native mesh, animation and image bytes; measure actual deformation.

Run in Blender with the authored rig open. Source evaluated polygons are compared with
native decoded triangle-corners, including the game-style attached weapon transforms.
"""
import argparse
from pathlib import Path
import hashlib
import sys
import json
import math
import struct
import bpy
import numpy as np
from itertools import combinations
from mathutils import Matrix
from mathutils.bvhtree import BVHTree

PARTS={'body':('Units','GrotTrio'),'pistol':('Weapons','GrotTrioPistol'),'choppa':('Weapons','GrotTrioChoppa')}
HANDS={'pistol':'Gunner_hand.R','choppa':'Cutter_hand.R'}
EVENTS=('Idle','Move','MoveBegin','MoveEnd','Run','Ranged','Melee','Hit','Die','Construct','Grenade')
# Map a Blender point (x, y, z) to native coordinates (-y, x, z).
NATIVE=np.array([[0,-1,0],[1,0,0],[0,0,1]],dtype=float)


def unpack_mesh(path):
    raw=path.read_bytes();assert raw[:7]==b'MSH1.0\x00'
    pos=8;bind={}
    for _ in range(raw[7]):
        z=raw.index(0,pos);key=raw[pos:z].decode()
        bind[key]=np.frombuffer(raw,dtype='<f4',count=16,offset=z+1).reshape(4,4).T.copy();pos=z+65
    bounds=np.array([struct.unpack_from('<3f',raw,pos+5),struct.unpack_from('<3f',raw,pos+21)])
    assert raw[pos+37]==1;pos+=111
    count=raw[pos];pos+=1;fields={}
    basis=0
    for _ in range(count):
        z=raw.index(0,pos);key=raw[pos:z].decode();n=raw[z+1];pos=z+2
        fields[key]=slice(basis,basis+n);basis+=n
    total,=struct.unpack_from('<I',raw,pos);pos+=4
    verts=np.frombuffer(raw,dtype='<f4',count=total,offset=pos).reshape(-1,basis);pos+=4*total
    indices,=struct.unpack_from('<I',raw,pos);pos+=4
    if indices:verts=verts[np.frombuffer(raw,dtype='<u4',count=indices,offset=pos)]
    assert pos+indices*4==len(raw)
    xyz=verts[:,fields['vertexPosition']].astype(float)
    assert np.allclose(bounds,np.array([xyz.min(0),xyz.max(0)]),atol=2e-5)
    normal=verts[:,fields['vertexNormal']];tangent=verts[:,fields['vertexTangent']]
    assert float(np.min(np.linalg.norm(normal,axis=1)))>.999
    assert np.max(np.abs((normal*tangent[:,:3]).sum(axis=1)))<.0004
    assert np.all(np.abs(tangent[:,3])==1)
    weights=verts[:,fields['vertexBoneWeights']]
    joints=verts[:,fields['vertexBoneIndices']]
    assert not np.any(np.abs(weights.sum(1)-1)>.0001) and np.all(joints.astype(int)==joints)
    assert np.max(joints[weights>0])<len(bind)
    return dict(bind=bind,xyz=xyz,joints=joints.astype(int),weights=weights,uv=verts[:,fields['vertexTextureCoordinate']],bounds=bounds)


def unpack_animation(path, expected):
    b=path.read_bytes();assert b[:7]==b'ANM1.0\x00'
    n,frames,fps=struct.unpack_from('<BII',b,7)
    assert n==len(expected) and fps==24
    pos=16;clips={}
    for _ in range(n):
        z=b.index(0,pos);name=b[pos:z].decode()
        clips[name]=np.frombuffer(b,dtype='<f4',count=frames*10,offset=z+1).astype(float).reshape(frames,10)
        pos=z+1+frames*40
    assert pos==len(b) and set(clips)==set(expected)
    raw=np.stack([clips[n] for n in expected],axis=1)
    q=raw[:,:,3:7];assert np.max(abs(np.linalg.norm(q,axis=2)-1))<.0001
    x,y,z,w=q.transpose(2,0,1);m=np.empty((*x.shape,3,3))
    m[:,:,0,0]=1-2*(y*y+z*z);m[:,:,0,1]=2*(x*y-z*w);m[:,:,0,2]=2*(x*z+y*w)
    m[:,:,1,0]=2*(x*y+z*w);m[:,:,1,1]=1-2*(x*x+z*z);m[:,:,1,2]=2*(y*z-x*w)
    m[:,:,2,0]=2*(x*z-y*w);m[:,:,2,1]=2*(y*z+x*w);m[:,:,2,2]=1-2*(x*x+y*y)
    assert np.min(raw[:,:,7:])>0 and np.isfinite(raw).all()
    return raw[:,:,:3],m*raw[:,:,7:,None]


def deformed(mesh,linear,offset):
    xyz=mesh['xyz'];joints=mesh['joints'];weights=mesh['weights']
    out=np.zeros_like(xyz)
    for k in range(4):
        active=weights[:,k]>0
        if not np.any(active):continue
        j=joints[active,k]
        sk=np.einsum('nij,nj->ni',linear[j],xyz[active])+offset[j]
        out[active]+=sk*weights[active,k,None]
    return out


def world_points(o,dep,indices=None):
    e=o.evaluated_get(dep);points=np.empty((len(e.data.vertices),3),dtype='f4')
    e.data.vertices.foreach_get('co',points.ravel())
    m=np.asarray(e.matrix_world);native=(points@m[:3,:3].T+m[:3,3])@NATIVE.T
    return native if indices is None else native[indices]


def barrel(verts):
    p=np.unique(verts.round(5),axis=0)
    _,axes=np.linalg.eigh(np.cov(p.T));sense=axes[:,-1]
    d=p@sense;lo=p[d<d.min()+.015];hi=p[d>d.max()-.015]
    # The lip has a wider ring and a concentric recess. The rear socket is a single ring.
    if len(lo)>len(hi):hi,lo=lo,hi
    assert len(hi)>len(lo)>=6,(len(hi),len(lo))
    direction=hi.mean(0)-lo.mean(0)
    return hi.mean(0),direction/np.linalg.norm(direction)


def measure_textures(path,stage):
    result={}
    for layer,codec in [('Diffuse','DXT5'),('Normal','DXT1'),('SIC','DXT1')]:
        f=path/('GrotTrio'+layer+'.dds');raw=f.read_bytes()
        assert raw[:4]==b'DDS '
        height,width=struct.unpack_from('<II',raw,12);levels=struct.unpack_from('<I',raw,28)[0]
        assert height==width==2048 and levels==12 and raw[84:88].decode()==codec
        block=16 if codec=='DXT5' else 8
        size=128+sum(max(1,((width>>l)+3)//4)*max(1,((height>>l)+3)//4)*block for l in range(levels))
        assert size==len(raw)
        image=bpy.data.images.load(str(f),check_existing=False)
        assert image.size[:]==(width,height) and len(image.pixels)>0 and math.isfinite(image.pixels[0])
        result[layer]={'size':[width,height],'codec':codec,'mip_levels':levels,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
    result['source_colour_tile_comparison']=json.loads((stage/'texture-check.json').read_text())
    assert max(t['mean_error_8bit_rgb'] for t in result['source_colour_tile_comparison'].values())<4
    return result


def main():
    cli=argparse.ArgumentParser()
    for n in ('data','stage'):cli.add_argument('--'+n,type=Path,required=True)
    cli.add_argument('--draft',action='store_true')
    opt=cli.parse_args(sys.argv[sys.argv.index('--')+1:])
    stage=opt.stage;data=opt.data
    scene=bpy.context.scene;dep=bpy.context.evaluated_depsgraph_get()
    rig=next(o for o in scene.objects if o.type=='ARMATURE')
    objects=sorted([o for o in scene.objects if 'native_part' in o and o.type=='MESH'],key=lambda o:o.name)
    meshes={k:unpack_mesh(data/f'Video/Meshes/{typ}/Foundry/{name}.msh') for k,(typ,name) in PARTS.items()}
    names=list(meshes['body']['bind']);bonebind=np.array([meshes['body']['bind'][n] for n in names])
    assert len(names)==51 and set(names)==set(rig.data.bones.keys())
    assert set(meshes['pistol']['bind'])=={'Root','.Muzzle'} and set(meshes['choppa']['bind'])=={'Root'}
    assert sum(len(m['xyz'])//3 for m in meshes.values())==4486
    setup={p:[] for p in PARTS};offsets={p:0 for p in PARTS};indices={};uv_error=0
    for o in objects:
        m=o.data;m.calc_loop_triangles()
        part=o['native_part'];role=o['trio_role'].lower()
        ids=np.array([t.vertices[:] for t in m.loop_triangles],dtype=int).ravel();indices[o.name]=ids
        start=offsets[part];end=start+len(ids);offsets[part]=end
        setup[part].append((o,slice(start,end)))
        uv=m.uv_layers.active.data
        check=np.asarray([uv[li].uv[:] for tri in m.loop_triangles for li in tri.loops])
        check[:,1]=1-check[:,1]
        tile={'mek':(0,0),'gunner':(1,0),'cutter':(0,1)}[role]
        check=(check+np.array(tile))*.5
        uv_error=max(uv_error,float(np.max(abs(check-meshes[part]['uv'][start:end]))))
    assert uv_error<1e-6 and all(len(m['xyz'])==offsets[k] for k,m in meshes.items())
    rig.animation_data_create();rig.animation_data.use_nla=False
    for tr in rig.animation_data.nla_tracks:tr.mute=True
    rig.data.pose_position='POSE'
    report={'status':'PASS','source_sha256':hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest(),'format':'MSH1.0 / ANM1.0 / legacy DDS with full mip chains','frames_checked':0,'events':{},'max_world_vertex_error':0.,'max_socket_position_error':0.,'max_socket_axis_error_degrees':0.,'max_source_uv_error':uv_error,'failures':[],'engine_in_game_verified':False}
    report['materials']=measure_textures(data/'Video/Textures/Units/Foundry',stage)
    report['mesh_triangles']={p:len(m['xyz'])//3 for p,m in meshes.items()}
    report['native_bones']={p:len(m['bind']) for p,m in meshes.items()}
    muzzle_obj=next(o for o in objects if 'dark inset muzzle' in o.name.lower())
    origin=bonebind[:,:3,3]
    role_owners = {r:[(part,sl) for part in PARTS for ob,sl in setup[part] if ob['trio_role'].lower()==r] for r in ('mek','gunner','cutter')}
    role_faces={r:np.arange(sum(sl.stop-sl.start for part,sl in ranges)).reshape(-1,3).tolist() for r,ranges in role_owners.items()}
    for suffix in EVENTS:
        if opt.draft and bpy.data.actions.get(suffix) is None:continue
        action=bpy.data.actions[suffix]
        rig.animation_data.action=None
        for bone in rig.pose.bones:bone.matrix_basis=Matrix.Identity(4)
        rig.animation_data.action=action
        delta,linear=unpack_animation(data/f'Video/Animations/Units/Foundry/GrotTrio{suffix}.anm',names)
        f0,f1=map(round,action.frame_range)
        assert len(delta)==f1-f0+1 and f0==1
        errors={p:0. for p in PARTS};max_socket,max_angle=0.,0.
        lo=math.inf;hi=-math.inf;fire={};intersections={};friendly_hits=[]
        role_ground={role:[] for role in ('mek','gunner','cutter')}
        for i in range(len(delta)):
            scene.frame_set(f0+i)
            affine=linear[i]
            offs=origin+delta[i]-np.einsum('nij,nj->ni',affine,origin)
            pnt={}
            pnt['body']=deformed(meshes['body'],affine,offs)
            for part,handbone in HANDS.items():
                j=names.index(handbone);hand=np.eye(4)
                hand[:3,:3]=affine[j]@bonebind[j,:3,:3]
                hand[:3,3]=origin[j]+delta[i,j]
                pnt[part]=meshes[part]['xyz']@hand[:3,:3].T+hand[:3,3]
                if part=='pistol':socket=hand@meshes[part]['bind']['.Muzzle']
            role_min={role:math.inf for role in role_ground}
            for part in PARTS:
                for o,ran in setup[part]:
                    expected=world_points(o,dep,indices[o.name])
                    err=np.linalg.norm(pnt[part][ran]-expected,axis=1)
                    errors[part]=max(errors[part],float(err.max()))
                    role=o['trio_role'].lower()
                    role_min[role]=min(role_min[role],float(pnt[part][ran,2].min()))
            for role in role_min:role_ground[role].append(role_min[role])
            lo=min(lo,min(role_min.values()));hi=max(hi,max(role_min.values()))
            tip,direction=barrel(world_points(muzzle_obj,dep))
            poserr=float(np.linalg.norm(socket[:3,3]-tip))
            axis=socket[:3,0]/np.linalg.norm(socket[:3,0])
            angle=math.degrees(math.atan2(np.linalg.norm(np.cross(axis,direction)),axis.dot(direction)))
            max_socket=max(max_socket,poserr);max_angle=max(max_angle,angle)
            f=f0+i
            # Check the native assembled silhouettes, including both attached meshes.
            members={r:np.concatenate([pnt[part][sl] for part,sl in ranges]) for r,ranges in role_owners.items()}
            lohi={r:(v.min(0),v.max(0)) for r,v in members.items()}
            trees={}
            def surface(r):
                if r not in trees:trees[r]=BVHTree.FromPolygons(members[r].tolist(),role_faces[r],all_triangles=True)
                return trees[r]
            for a,b in combinations(members,2):
                if np.any(lohi[a][1]<lohi[b][0]) or np.any(lohi[b][1]<lohi[a][0]):continue
                if surface(a).overlap(surface(b)):intersections.setdefault(a+'/'+b,[]).append(f)
            if suffix=='Ranged' and f in (17,23,29):
                for r in ('mek','cutter'):
                    if surface(r).ray_cast(socket[:3,3],axis,160)[0] is not None:friendly_hits.append([r,f])
            if suffix=='Ranged' and f in (17,18,23,24,29,30):
                fire[str(f)]={'native_origin':socket[:3,3].tolist(),'direction':axis.tolist(),'pitch_degrees':math.degrees(math.asin(axis[2])),'yaw_degrees':math.degrees(math.atan2(axis[1],axis[0]))}
        report['frames_checked']+=len(delta)
        report['max_world_vertex_error']=max(report['max_world_vertex_error'],max(errors.values()))
        report['max_socket_position_error']=max(report['max_socket_position_error'],max_socket)
        report['max_socket_axis_error_degrees']=max(report['max_socket_axis_error_degrees'],max_angle)
        event={'frames':len(delta),'per_part_peak_native_vertex_error':errors,'max_socket_position_error':max_socket,'max_socket_axis_error_degrees':max_angle,'ground_min_per_member':{r:[min(vals),max(vals)] for r,vals in role_ground.items()}}
        event['cross_member_surface_intersections']=intersections
        if fire:
            event['firing_and_recoil_frames']=fire
            event['shot_marker_intersections_with_teammates']=friendly_hits
        if friendly_hits:report['failures'].append(suffix+' friendly muzzle occlusion')
        if lo<-.001 or hi>.001:report['failures'].append(suffix+' ground contact exceeds .001')
        if intersections:report['failures'].append(suffix+' cross-member mesh intersection')

        report['events'][suffix]=event
        print('VERIFY',suffix,len(delta),errors,'ground',lo,hi,flush=True)
        if max(errors.values())>.001 or max_angle>.003 or max_socket>.001:report['failures'].append(suffix+' source/native deformation or socket error')
    if 'Ranged' in report['events']:
        shots=report['events']['Ranged']['firing_and_recoil_frames']
        for event in (17,23,29):
            s=shots[str(event)]
            if abs(s['pitch_degrees'])>.05 or abs(s['yaw_degrees'])>.05:report['failures'].append('Muzzle misses forward axis on frame '+str(event))
            if not (6<shots[str(event+1)]['pitch_degrees']<9):report['failures'].append('Muzzle recoil excursion '+str(event+1))
    if report['failures']:report['status']='FAIL'
    (stage/'verify.json').write_text(json.dumps(report,indent=2)+'\n')
    print('NATIVE_VERIFY',report['status'],report['frames_checked'],report['max_world_vertex_error'],report['failures'],flush=True)
    if report['failures']:raise ValueError(report['failures'])

if __name__=='__main__':main()
