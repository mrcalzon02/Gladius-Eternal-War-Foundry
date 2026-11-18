"""Bake a 24 fps Grot march, with no constraints or external dependencies after export.

Character forward is armature -Y. 'stride' is world displacement per full two-step
cycle. Frame 1 is the left foot strike. Frames 1 and 1+period are identical.
The caller moves its formation or actor origin steadily forward (stride / period
per frame) and applies arbitrary phase offsets by sampling modulo period.
"""

import math
import bpy
from mathutils import Matrix, Vector


_STYLE = {
    # L/R stance fraction, sole rise, outward step, free arm swing, weapon-arm swing.
    'mek':    (.605, .570, 2.00, .22, 17.0, 7.2),
    'gunner': (.585, .575, 1.73, .15, 14.0, 2.8),
    'cutter': (.580, .560, 2.19, .25, 21.0, 11.0),
}
_SIDES = ('L', 'R')
_TAU = math.tau


def _rotation(axis, degrees):
    return Matrix.Rotation(math.radians(degrees), 4, axis)


def _at(origin, orientation):
    matrix = orientation.to_4x4()
    matrix.translation = origin
    return matrix


def _around_parent(rest, parent_pose, name, rotation):
    bone = rest[name]
    inherited = parent_pose @ bone.parent.matrix_local.inverted() @ bone.matrix_local
    return _at(inherited.translation, rotation @ inherited.to_3x3().to_4x4())


def _aim_bone(bone, origin, tip):
    rest_axis = bone.tail_local - bone.head_local
    turn = rest_axis.rotation_difference(tip - origin)
    return _at(origin, turn.to_matrix() @ bone.matrix_local.to_3x3())


def _boot_shape(rig, side):
    name = 'foot.' + side
    boot = next(obj for obj in rig.children if obj.type == 'MESH'
                and 'fitted ork boot' in obj.name.lower() and name in obj.vertex_groups)
    to_armature = rig.matrix_world.inverted() @ boot.matrix_world
    return [to_armature @ vertex.co for vertex in boot.data.vertices]


def _stance(role, side):
    return _STYLE[role][0 if side == 'L' else 1]


def _foot(phase, role, side, scale, stride, ankle, boots, line_y):
    duty = _stance(role, side)
    swing = max(0.0, (phase - duty) / (1.0 - duty))
    blend = swing ** 3 * (10 + swing * (-15 + 6 * swing))
    clearance = 16 * swing ** 2 * (1 - swing) ** 2
    sign = 1 if side == 'L' else -1
    rise = _STYLE[role][2] * (1.04 if side == 'L' else .96) / scale
    pitch = 7.0 * math.sin(_TAU * swing) * clearance
    rotation = _rotation('X', pitch)
    sole = min(p.z for p in boots)
    rotated_sole = min((rotation @ (p - ankle)).z for p in boots)
    target = Vector((ankle.x * .87 + sign * _STYLE[role][3] * clearance / scale,
                     line_y + stride * (phase - duty / 2 - blend),
                     sole - rotated_sole + rise * clearance))
    return target, rotation


def _knee(hip, goal, thigh, shin):
    a = thigh.length
    b = shin.length
    axis = goal - hip
    reach = axis.length
    axis.normalize()
    along = (a * a - b * b + reach * reach) / (2 * reach)
    flex = math.sqrt(max(0, a * a - along * along))
    # Use the donor's sagittal knee plane; keep a small amount of characteristic splay.
    rest_axis = (shin.tail_local - thigh.head_local).normalized()
    rest_knee = thigh.tail_local - thigh.head_local
    rest_knee -= rest_axis * rest_knee.dot(rest_axis)
    pole = rest_knee - axis * rest_knee.dot(axis)
    return hip + axis * along + pole.normalized() * flex


def _pose(rig, role, stride_world, t, boots, scale):
    rest = rig.data.bones
    stride = stride_world / scale
    angle = _TAU * t
    ankles = {side:rest['foot.' + side].head_local for side in _SIDES}
    # The static display poses have deliberately staggered boots; for walking they
    # exchange leading and trailing positions around one common centre of travel.
    line_y = (ankles['L'].y + ankles['R'].y) * .5
    foot = {side:_foot((t + (.5 if side == 'R' else 0)) % 1, role, side, scale,
                       stride, ankles[side], boots[side], line_y) for side in _SIDES}
    support = math.sin(angle - .18)
    contact = math.cos(2 * angle - .46)
    shift = Vector((.57 * support, .17 * math.sin(2 * angle), -.40 - .34 * contact)) / scale
    pelvis = rest['pelvis']
    pelvis_turn = _rotation('Z', -4.2 * math.cos(angle)) @ _rotation('Y', -2.6 * support)
    poses = {'pelvis':_at(pelvis.head_local + shift, pelvis_turn @ pelvis.matrix_local)}
    # If a longer stride approaches full extension, lower the pelvis; the sole
    # targets stay exact even for the short right leg of the Mek.
    hip_limit = 0.0
    for side in _SIDES:
        thigh, shin = rest['thigh.' + side], rest['shin.' + side]
        hip = poses['pelvis'] @ pelvis.matrix_local.inverted() @ thigh.head_local
        goal = foot[side][0]
        horizontal_sq = (goal.x-hip.x)**2 + (goal.y-hip.y)**2
        limit = ((thigh.length + shin.length) * .991)**2 - horizontal_sq
        if limit <= 0:
            raise ValueError('Stride is too long for the Grot to reach its planted foot.')
        hip_limit = min(hip_limit, goal.z + math.sqrt(limit) - hip.z)
    origin = poses['pelvis'].translation.copy()
    origin.z = pelvis.head_local.z + shift.z + hip_limit
    poses['pelvis'].translation = origin
    counter_turn = math.cos(angle)
    spine_turn = (_rotation('Z', 7.0*counter_turn) @ _rotation('X', .9*contact)
                  @ _rotation('Y', 3.3*support))
    poses['spine'] = _around_parent(rest, poses['pelvis'], 'spine', spine_turn)
    poses['chest'] = _around_parent(rest, poses['spine'], 'chest', _rotation('Y', -1.3*support))
    poses['neck'] = _around_parent(rest, poses['chest'], 'neck', _rotation('Z', -2.3*counter_turn))
    poses['head'] = _around_parent(rest, poses['neck'], 'head',
        _rotation('X', -1.5*contact) @ _rotation('Y', 1.3*support))
    for side in _SIDES:
        suffix = '.' + side
        thigh, shin, ankle = (rest[p + suffix] for p in ('thigh', 'shin', 'foot'))
        hip = poses['pelvis'] @ pelvis.matrix_local.inverted() @ thigh.head_local
        planted, foot_turn = foot[side]
        knee = _knee(hip, planted, thigh, shin)
        poses[thigh.name] = _aim_bone(thigh, hip, knee)
        poses[shin.name] = _aim_bone(shin, knee, planted)
        poses[ankle.name] = _at(planted, foot_turn @ ankle.matrix_local)
        arm, fore, hand = ('upper_arm' + suffix, 'forearm' + suffix, 'hand' + suffix)
        reach = math.cos(angle - .13) * (1 if side == 'L' else -1)
        arm_amp = _STYLE[role][4 if side == 'L' else 5]
        stabilise = .68 if (role == 'gunner' and side == 'R') else .27
        poses[arm] = _around_parent(rest, poses['chest'], arm, _rotation('X', reach * arm_amp))
        poses[fore] = _around_parent(rest, poses[arm], fore,
            _rotation('X', -reach * arm_amp * stabilise - (1.3 if side == 'L' else .5)*contact))
        poses[hand] = _around_parent(rest, poses[fore], hand, _rotation('Y', .8*support))
    return poses


def make_walk(rig, role, stride, period):
    """Create an in-place walking action without assigning it or changing the input rig."""
    role = role.lower()
    if role not in _STYLE or period < 4 or int(period) != period or stride <= 0:
        raise ValueError('Expected a Mek, Gunner or Cutter, positive stride and integral cycle period.')
    period = int(period)
    scale = rig.matrix_world.to_scale().y
    boots = {side:_boot_shape(rig, side) for side in _SIDES}
    channels = {}
    previous_quat = {}
    for frame in range(period + 1):
        pose = _pose(rig, role, stride, (frame % period) / period, boots, scale)
        for bone in rig.data.bones:
            parent = bone.parent
            relative = bone.matrix_local
            if parent:
                relative = pose[parent.name] @ parent.matrix_local.inverted() @ relative
            basis = relative.inverted() @ pose[bone.name]
            position, quat, _ = basis.decompose()
            if bone.name in previous_quat and quat.dot(previous_quat[bone.name]) < 0:
                quat.negate()
            previous_quat[bone.name] = quat.copy()
            for property_name, components in [('rotation_quaternion', quat), ('location', position)]:
                if property_name == 'location' and bone.name != 'pelvis':
                    continue
                for axis, value in enumerate(components):
                    channels.setdefault((bone.name, property_name, axis), []).append(value)
    action = bpy.data.actions.new(f'{role} | March {period}f')
    action.use_fake_user = True
    action.use_cyclic = True
    action['stride_world'] = float(stride)
    action['left_stance_fraction'] = _stance(role, 'L')
    action['right_stance_fraction'] = _stance(role, 'R')
    action['forward_axis'] = '-Y'
    for (bone, prop, axis), values in channels.items():
        path = rig.pose.bones[bone].path_from_id(prop)
        curve = action.fcurves.new(path, index=axis, action_group=bone)
        points = curve.keyframe_points
        points.add(len(values))
        points.foreach_set('co',[v for f, value in enumerate(values, 1) for v in (f,value)])
        for point in points:
            point.interpolation = 'LINEAR'
        curve.update()
    return action
