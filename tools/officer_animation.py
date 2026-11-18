"""Native officer animation math; no geometry or bind-frame changes."""
from pathlib import Path
import math,struct,hashlib
from mathutils import Vector,Quaternion,Matrix

def read_clip(path):
    raw=Path(path).read_bytes();assert raw[:7]==b'ANM1.0\0';count,frames,fps=struct.unpack_from('<BII',raw,7);at=16;tracks={}
    for _ in range(count):
        end=raw.index(0,at);name=raw[at:end].decode();at=end+1;tracks[name]=[struct.unpack_from('<10f',raw,at+i*40) for i in range(frames)];at+=frames*40
    assert at==len(raw)
    return {'tracks':tracks,'frames':frames,'fps':fps,'duration':(frames-1)/fps,'sha256':hashlib.sha256(raw).hexdigest()}

def smooth(t):
    t=max(0.,min(1.,t));return t*t*(3-2*t)

def curve(keys,t):
    if t<=keys[0][0]:return keys[0][1]
    for a,b in zip(keys,keys[1:]):
        if t<=b[0]:
            u=smooth((t-a[0])/(b[0]-a[0]));return a[1]+(b[1]-a[1])*u
    return keys[-1][1]

def vector_curve(keys,t):
    return Vector([curve([(time,v[k]) for time,v in keys],t) for k in range(3)])

def sample_clip(clip,t,rest,names):
    f=max(0.,min(clip['frames']-1,t*clip['fps']));a=int(f);b=min(clip['frames']-1,a+1);u=f-a;out={}
    for n in names:
        x=clip['tracks'][n][a];y=clip['tracks'][n][b];qa=Quaternion((x[6],*x[3:6])).normalized();qb=Quaternion((y[6],*y[3:6])).normalized()
        out[n]=[rest[n]+Vector(x[:3]).lerp(Vector(y[:3]),u),qa.slerp(qb,u)]
    return out

def clone(pose):return {n:[p.copy(),q.copy()] for n,(p,q) in pose.items()}

def rotate_pose(pose,names,pivot,rotation,translation=Vector((0,0,0))):
    for n in names:
        p,q=pose[n];pose[n]=[pivot+rotation@(p-pivot)+translation,rotation@q]

def frame(forward,up):
    f=Vector(forward).normalized();z=Vector(up);z=(z-f*f.dot(z)).normalized();y=z.cross(f).normalized();return Matrix((f,y,z)).transposed()

def solve_leg(pose,side,target,hint,rest):
    hip=side+'HipBone';shin=side+'ShinBone';foot=side+'FootBone';s=pose[hip][0].copy()
    l1=(rest[shin]-rest[hip]).length;l2=(rest[foot]-rest[shin]).length
    # Restore the exact segment lengths before IK, including during blends.
    e=s+pose[hip][1]@(rest[shin]-rest[hip]);w=e+pose[shin][1]@(rest[foot]-rest[shin])
    v=Vector(target)-s;distance=min(max(v.length,abs(l1-l2)+1e-5),l1+l2-1e-5);axis=v.normalized();target=s+axis*distance
    pole=Vector(hint)-s;pole-=axis*pole.dot(axis)
    if pole.length<1e-5:pole=Vector((1,0,0))-axis*axis.x
    along=(l1*l1-l2*l2+distance*distance)/(2*distance);height=math.sqrt(max(0,l1*l1-along*along));knee=s+axis*along+pole.normalized()*height
    pose[hip]=[s,(e-s).rotation_difference(knee-s)@pose[hip][1]];pose[shin]=[knee,(w-e).rotation_difference(target-knee)@pose[shin][1]];pose[foot][0]=target
    return max(abs((knee-s).length-l1),abs((target-knee).length-l2))

def write_clip(path,poses,rest,binds,attachments,names,fps):
    tracks={n:[] for n in names};previous={}
    for pose in poses:
        for n in names[:28]:
            p,q=pose[n];q=q.normalized()
            if n in previous and q.dot(previous[n])<0:q.negate()
            previous[n]=q.copy();tracks[n].append((* (p-rest[n]),q.x,q.y,q.z,q.w,1.,1.,1.))
        for key in ('pistol','sword'):
            a=attachments[key];hand=a['body_hand'];anchor=a['bone'];position,q=pose[hand];origin=binds[anchor].translation
            p=position+q@(origin-rest[hand]+Vector(a.get('grip_adjustment',(0,0,0))));tracks[anchor].append((*(p-origin),q.x,q.y,q.z,q.w,1.,1.,1.))
    raw=bytearray(b'ANM1.0\0'+struct.pack('<BII',len(names),len(poses),fps))
    for n in names:
        raw+=n.encode()+b'\0'
        for row in tracks[n]:raw+=struct.pack('<10f',*row)
    target=Path(path)
    if not target.is_file() or target.read_bytes()!=raw:
        temporary=target.with_suffix('.anm.tmp');temporary.write_bytes(raw);temporary.replace(target)
    return {'frames':len(poses),'fps':fps,'duration':(len(poses)-1)/fps,'sha256':hashlib.sha256(raw).hexdigest()}
