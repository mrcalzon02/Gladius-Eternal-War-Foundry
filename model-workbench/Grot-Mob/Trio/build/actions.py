"""Gladius Grot one-shot actions, baked for the supplied Blender 4.3 armatures.

make_lifecycle(rig, role) returns unassigned, independent Actions. Frame 1 is the
bind-ready stance. On a 24 fps timeline the engine's 2/3-second release is frame 17.
"""
import math

import bpy
import numpy as np
from mathutils import Euler, Matrix, Vector

LENGTHS = {'Ranged': 49, 'Melee': 41, 'Hit': 25, 'Die': 49, 'Construct': 49, 'Grenade': 41}
MUZZLE_FRAMES = (17, 23, 29)
MELEE_CONTACT = 18
THROW_RELEASE = 17
ZERO = (0., 0., 0.)


def ramp(f, keys):
    """Ease between authored beats without any overshoot at a hold or ground contact."""
    if f <= keys[0][0]:
        return keys[0][1]
    for (a, left), (b, right) in zip(keys, keys[1:]):
        if f <= b:
            t = (f - a) / (b - a)
            return left + (right-left) * t*t*(3-2*t)
    return keys[-1][1]


def add(angles, weight, values):
    for name, xyz in values.items():
        angles[name] = angles.get(name, Vector(ZERO)) + Vector(xyz) * weight


def rot(xyz):
    return Euler(tuple(math.radians(v) for v in xyz),'XYZ').to_matrix().to_4x4()


def at(origin, matrix):
    m=matrix.to_3x3().to_4x4()
    m.translation=origin
    return m


def melee(role, f, angles):
    wind = ramp(f,[(1,0),(10,1),(13,1),(17,0)])
    drive = ramp(f,[(1,0),(13,0),(18,1),(20,.96),(25,.48),(41,0)])
    brace = ramp(f,[(1,0),(11,1),(15,.8),(19,.45),(26,.65),(41,0)])
    wind_arm, wind_fore, wind_wrist, hit_arm, hit_fore, hit_wrist, twist = {
        'mek': ((18,-16,-10),(-54,3,-5),(-22,2,-12),(-44,-7,12),(48,1,-3),(54,-8,6),12),
        'cutter': ((13,-21,-42),(-19,3,-13),(-11,1,-21),(-48,3,35),(9,-5,31),(46,15,23),24),
        'gunner': ((18,-5,-44),(-34,14,-18),(18,-7,-33),(-14,13,27),(21,2,29),(23,12,53),21),
    }[role]
    add(angles,wind,{'spine':(-6,4,-twist),'chest':(-2,0,-7),'head':(5,-2,twist*.45),
         'upper_arm.R':wind_arm,'forearm.R':wind_fore,'hand.R':wind_wrist,
         'upper_arm.L':(-15,14,12),'forearm.L':(-22,-5,0)})
    add(angles,drive,{'spine':(16,-5,twist),'chest':(4,2,5),'head':(-12,3,-twist*.52),
         'upper_arm.R':hit_arm,'forearm.R':hit_fore,'hand.R':hit_wrist,
         'upper_arm.L':(24,11,-18),'forearm.L':(-8,7,-6)})
    return Vector((-.024*brace,-.065*drive,-.06*brace))


def recoil(f):
    return sum(ramp(f,[(n,0),(n+1,1),(n+2,.62),(n+5,0)]) for n in MUZZLE_FRAMES)


def ranged(role, f, angles):
    aim=ramp(f,[(1,0),(12,1),(31,1),(49,0)])
    kick=recoil(f)
    if role=='gunner':
        add(angles,aim,{'spine':(5,-2,10),'chest':(0,0,4),'head':(-4,-2,-11),'upper_arm.R':(-3,1,18),'forearm.R':(0,0,7),
                        'upper_arm.L':(-17,6,5),'forearm.L':(-23,0,-14)})
        add(angles,kick,{'spine':(-5,0,0),'chest':(-2,0,0),'head':(3,1,0),
                        'upper_arm.R':(-6,2,-2),'forearm.R':(-10,1,0),'hand.R':(-6,0,0)})
        return Vector((0,.022*kick,-.041*aim))
    sign=1 if role=='mek' else -1
    add(angles,aim,{'spine':(13,sign*6,sign*15),'head':(-10,-sign*5,-sign*16),
                   'upper_arm.L':(-38,9,10),'forearm.L':(-49,8,-22),
                   'upper_arm.R':(14,-10,-10),'forearm.R':(-17,0,5)})
    add(angles,kick,{'neck':(sign,0,-sign),'upper_arm.L':(-3,0,0)})
    return Vector((sign*.046,0,-.103*aim))*aim


def hit(role, f, angles):
    sign={'mek':1,'cutter':-1,'gunner':.58}[role]
    snap=ramp(f,[(1,0),(4,1),(7,.78),(15,-.19),(25,0)])
    fold=ramp(f,[(1,0),(7,1),(12,.76),(25,0)])
    add(angles,snap,{'spine':(-18,sign*14,sign*17),'chest':(-7,-sign*3,5*sign),
        'neck':(-7,7*sign,-10*sign),'head':(-10,9*sign,-6*sign),'upper_arm.L':(14,26,9),
        'forearm.L':(-35,-4,12),'upper_arm.R':(-13,-18,-13),'forearm.R':(-17,5,-4)})
    return Vector((-.043*sign*snap,.046*snap,-.085*fold))


def grenade(role, f, angles):
    if role!='gunner':
        watch=ramp(f,[(1,0),(11,.3),(17,1),(23,.85),(41,0)])
        side=1 if role=='mek' else -1
        add(angles,watch,{'spine':(12,side*7,0),'head':(-15,side*4,side*12),'upper_arm.L':(-48,18,0),'forearm.L':(-27,5,-9),'upper_arm.R':(7,-8,side*6)})
        return Vector((side*.034,-.013,-.08))*watch
    # The left hand is free on all three roles; the tool stays in the right fist.
    carry=ramp(f,[(1,0),(10,1),(13,1),(17,0)])
    throw=ramp(f,[(1,0),(13,0),(17,1),(21,.87),(41,0)])
    prep=ramp(f,[(1,0),(11,1),(23,.35),(41,0)])
    add(angles,carry,{'spine':(-6,-5,15),'upper_arm.L':(-77,27,33),
        'forearm.L':(-50,-15,-18),'hand.L':(-35,0,-18),'head':(3,2,-14)})
    add(angles,throw,{'spine':(15,4,-21),'chest':(4,3,-5),'head':(-14,0,16),
        'upper_arm.L':(-88,3,-20),'forearm.L':(-3,1,-12),'hand.L':(28,0,-8),
        'upper_arm.R':(16,-10,8)})
    return Vector((.04*prep,-.053*throw,-.045*prep))


def construct(role, f, angles):
    down=ramp(f,[(1,0),(8,1),(40,1),(49,0)])
    if role=='mek':
        wind=sum(ramp(f,[(n-8,0),(n-4,1),(n-2,1),(n,0)]) for n in (17,33))
        strike=sum(ramp(f,[(n-3,0),(n,1),(n+2,.93),(n+7,0)]) for n in (17,33))
        add(angles,down,{'spine':(20,5,-5),'head':(6,-4,-6),'upper_arm.L':(-28,5,10),
            'forearm.L':(-12,0,5),'upper_arm.R':(-25,-4,8),'hand.R':(35,0,0)})
        add(angles,wind,{'upper_arm.R':(13,-4,-7),'forearm.R':(-37,0,0),'hand.R':(-23,0,0)})
        add(angles,strike,{'spine':(5,0,3),'upper_arm.R':(-20,0,8),'forearm.R':(39,0,0),'hand.R':(36,0,4)})
    elif role=='cutter':
        reach=ramp(f,[(1,0),(12,1),(19,1),(26,.2),(36,1),(43,.35),(49,0)])
        add(angles,down,{'spine':(21,-7,-9),'head':(9,4,7),'upper_arm.R':(7,-14,-9),
            'forearm.R':(-21,-4,0)})
        add(angles,reach,{'chest':(7,0,-4),'upper_arm.L':(-53,3,-8),'forearm.L':(12,-6,0),'hand.L':(18,3,18)})
    else:
        scan=ramp(f,[(1,0),(13,-1),(31,1),(49,0)])
        add(angles,down,{'spine':(3,-3,0),'upper_arm.L':(-29,14,9),'forearm.L':(-27,-4,-9)})
        add(angles,scan,{'spine':(0,0,11),'head':(2,0,17),'upper_arm.R':(1,0,-4)})
    return Vector((0,-.038*down,-(.09 if role!='gunner' else .025)*down))


# Three different resting orientations, with independent leg, head and arm timing.
_FALL = {
    'mek': {
        'pelvis': (-102.4, 22.6, 12.0),
        'spine': (3.0, 3.0, -9.0),
        'head': (16.6, 7.4, 23.0),
        'thigh.L': (-5.0, -12.0, -6.0),
        'shin.L': (46.1, 0.0, 0.0),
        'foot.L': (-10.0, 0.0, 0.0),
        'thigh.R': (-20.6, 16.0, 10.0),
        'shin.R': (94.7, -5.0, 0.0),
        'foot.R': (-19.0, 0.0, 2.0),
        'upper_arm.L': (-4.4, 18.6, 6.0),
        'forearm.L': (-51.6, 2.0, -8.0),
        'upper_arm.R': (-37.0, -35.8, -12.0),
        'forearm.R': (11.5, 7.0, -33.0),
        'hand.R': (14.3, 5.0, -18.0),
    },
    'gunner': {
        'pelvis': (15.8, 87.6, -67.0),
        'spine': (8.6, -8.8, 3.0),
        'head': (-3.7, -11.5, -24.0),
        'thigh.L': (-30.7, -0.2, 4.0),
        'shin.L': (53.4, 4.0, 3.0),
        'foot.L': (-25.0, 0.0, 3.0),
        'thigh.R': (-58.1, -35.7, 17.0),
        'shin.R': (74.0, 3.0, 0.0),
        'foot.R': (-20.0, 0.0, 0.0),
        'upper_arm.L': (-71.8, 15.8, -30.0),
        'forearm.L': (-30.6, 0.0, -6.0),
        'hand.L': (12.0, 3.0, 2.0),
        'upper_arm.R': (7.1, -9.9, 36.4),
        'forearm.R': (-22.3, 2.0, 43.2),
        'hand.R': (17.0, 10.0, -18.0),
    },
    'cutter': {
        'pelvis': (64.8, -8.3, 59.0),
        'spine': (-1.5, -6.8, 10.0),
        'head': (-20.5, 11.6, -44.0),
        'thigh.L': (-27.5, -6.3, 7.0),
        'shin.L': (33.8, -4.0, 4.0),
        'foot.L': (-6.0, 0.0, 2.0),
        'thigh.R': (-24.3, 14.8, -8.0),
        'shin.R': (67.0, 0.0, -2.0),
        'foot.R': (-18.0, 0.0, 0.0),
        'upper_arm.L': (-22.3, 45.7, 17.1),
        'forearm.L': (9.4, 12.0, 13.0),
        'upper_arm.R': (14.2, -41.0, -25.3),
        'forearm.R': (36.9, 0.0, -27.2),
        'hand.R': (-28.2, 0.0, -5.0),
    },
}


def dying(role,f,angles):
    flinch=ramp(f,[(1,0),(5,1),(11,.82),(19,0)])
    fall=ramp(f,[(1,0),(7,0),(12,.09),(17,.31),(23,.79),(26,1.035),(30,.98),(36,1)])
    fold=ramp(f,[(1,0),(6,.15),(13,1),(19,.67),(29,0)])
    settle=ramp(f,[(1,0),(11,0),(19,.21),(25,.74),(30,1.06),(38,1)])
    sign= -1 if role=='cutter' else 1
    add(angles,flinch,{'spine':(-14,sign*11,13*sign),'head':(-13,-8*sign,17*sign),
        'upper_arm.L':(-30,30,5),'forearm.L':(-29,1,0),'upper_arm.R':(-23,-17,-9)})
    add(angles,fold,{'thigh.L':(-29,2,3),'shin.L':(49,0,3),'thigh.R':(-44,1,-5),
        'shin.R':(72,-4,-2),'spine':(18,2,0)})
    for bone,xyz in _FALL[role].items():
        add(angles,fall if bone in ('pelvis','spine') or bone.startswith('thigh') else settle,{bone:xyz})
    delta={'mek':(.13,.29,0),'gunner':(.08,-.34,0),'cutter':(.23,-.25,0)}[role]
    return Vector(delta)*fall


def bmat(bone, pose, angles, shift):
    base=bone.matrix_local
    if bone.parent:
        base=pose[bone.parent.name] @ bone.parent.matrix_local.inverted() @ base
    r=bone.matrix_local.to_3x3().to_4x4()
    return base @ Matrix.Translation(r.inverted().to_3x3() @ shift) @ r.inverted() @ rot(angles) @ r


def pin_legs(rest,pose):
    # Solve the two reaches against the unshifted ankles; the heel never slides
    # in standing attacks, even during the forward drive and the crouch.
    for side in ('L','R'):
        t,s,b=(rest[key+'.'+side] for key in ('thigh','shin','foot'))
        h=pose['pelvis'] @ rest['pelvis'].matrix_local.inverted() @ t.head_local
        axis=b.head_local-h;reach=axis.length;axis.normalize()
        tangent=s.head_local-t.head_local
        default=b.head_local-t.head_local;default.normalize()
        tangent-=default*tangent.dot(default)
        tangent-=axis*tangent.dot(axis);tangent.normalize()
        a=(t.length*t.length-s.length*s.length+reach*reach)/(2*reach)
        knee=h+axis*a+tangent*math.sqrt(max(0,t.length*t.length-a*a))
        for bone,p,q in [(t,h,knee),(s,knee,b.head_local)]:
            rotation=(bone.tail_local-bone.head_local).rotation_difference(q-p)
            pose[bone.name]=at(p,rotation.to_matrix() @ bone.matrix_local.to_3x3())
        pose[b.name]=b.matrix_local.copy()


def physics_samples(rig):
    """Skinning weights for ground support checks, in armature coordinates."""
    inverse=rig.matrix_world.inverted()
    groups={}
    points=[]
    for obj in rig.children:
        if obj.type!='MESH':continue
        to_rig=inverse@obj.matrix_world
        for v in obj.data.vertices:
            p=to_rig@v.co
            index=len(points);points.append(tuple(p))
            weights=[(obj.vertex_groups[g.group].name,g.weight) for g in v.groups if g.weight>0 and obj.vertex_groups[g.group].name in rig.data.bones]
            assert weights, obj.name
            wsum=sum(w for name,w in weights)
            for name,w in weights:
                groups.setdefault(name,[]).append((index,[*p,1],w/wsum))
    cloud={}
    for name,raw in groups.items():
        indices,xyz,weights=zip(*raw)
        cloud[name]=(np.array(indices),np.asarray(xyz)*np.asarray(weights)[:,None])
    return cloud, len(points), min(p[2] for p in points)


def support_shift(geometry,pose,rest):
    cloud,count,base=geometry
    heights=np.zeros(count)
    for name,(indices,raw) in cloud.items():
        transform=pose[name] @ rest[name].matrix_local.inverted()
        heights[indices]+=raw @ np.array(transform[2])
    return float(base-heights.min())


def make_lifecycle(rig,role):
    """Build and return unassigned Actions for a Mek, Gunner or Cutter."""
    role=role.lower()
    if role not in _FALL:raise ValueError('Unknown Grot role '+role)
    rig.data.update_tag()
    bpy.context.view_layer.update()
    rest=rig.data.bones
    physics=physics_samples(rig)
    bore=None
    if role=='gunner':
        muzzle=next(o for o in rig.children if 'dark inset muzzle' in o.name.lower())
        transform=rig.matrix_world.inverted()@muzzle.matrix_world
        rear=sum((transform@v.co for v in list(muzzle.data.vertices)[:6]),Vector(ZERO))/6
        lip=sum((transform@v.co for v in list(muzzle.data.vertices)[6:12]),Vector(ZERO))/6
        bore=(lip-rear).normalized()
    out={}
    moves={'Melee':melee,'Ranged':ranged,'Hit':hit,'Die':dying,
           'Grenade':grenade,'Construct':construct}
    # Parent-first iteration is explicit so this works on cloned rigs as well.
    ordered=sorted(rest,key=lambda b:len(b.parent_recursive))
    for clip,length in LENGTHS.items():
        action=bpy.data.actions.new(f'{role} | {clip}')
        action.use_fake_user=True;action.use_cyclic=clip=='Construct'
        action['fps']=24
        channels={};previous={}
        for frame in range(1,length+1):
            angles={}
            shift=moves[clip](role,frame,angles)
            pose={}
            for b in ordered:
                pose[b.name]=bmat(b,pose,angles.get(b.name,ZERO),shift if b.name=='pelvis' else Vector(ZERO))
            if clip=='Die':
                dz=support_shift(physics,pose,rest)
                for m in pose.values():m.translation.z+=dz
            else:
                pin_legs(rest,pose)
            if clip=='Ranged' and bore is not None:
                aim=ramp(frame,[(1,0),(12,1),(33,1),(49,0)])
                hand=pose['hand.R']
                current=(hand@rest['hand.R'].matrix_local.inverted()).to_3x3()@bore
                target=Vector((0,-1,math.tan(math.radians(7.5*recoil(frame))))).normalized()
                desired=current.normalized().lerp(target,aim).normalized()
                fix=current.rotation_difference(desired).to_matrix()
                pose['hand.R']=at(hand.translation,fix@hand.to_3x3())
            for b in ordered:
                base=b.matrix_local
                if b.parent:base=pose[b.parent.name]@b.parent.matrix_local.inverted()@base
                loc,q,_=(base.inverted()@pose[b.name]).decompose()
                if b.name in previous and previous[b.name].dot(q)<0:q.negate()
                previous[b.name]=q.copy()
                for prop,values in [('rotation_quaternion',q),('location',loc)]:
                    if prop=='location' and b.name!='pelvis':continue
                    for i,val in enumerate(values):
                        channels.setdefault((b.name,prop,i),[]).append(val)
        for (bone,prop,index),vals in channels.items():
            fc=action.fcurves.new(f'pose.bones["{bone}"].{prop}',index=index,action_group=bone)
            ks=fc.keyframe_points;ks.add(length)
            ks.foreach_set('co',[component for f,val in enumerate(vals,1) for component in (f,val)])
            for k in ks:k.interpolation='LINEAR'
            fc.update()
        out[clip]=action
    return out
