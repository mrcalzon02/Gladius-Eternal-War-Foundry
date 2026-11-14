"""Create a rigid hip-carried chainsword variant from the locally installed mesh.

The new geometry attaches to Guardsman's HipBone. Its long +Z blade axis maps
to hip-local +X (down in model space), with a left-belt offset. Only this rigid
one-bone MSH1.0 asset is supported; no shared game mesh is overwritten.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct


def layout(data):
    if data[:8] != b'MSH1.0\0\x01':
        raise ValueError('Expected the rigid one-bone MSH1.0 chainsword')
    end = data.index(0, 8)
    if data[8:end] != b'Hilt':
        raise ValueError('Expected the chainsword Hilt bone')
    bone = struct.unpack_from('<16f', data, end + 1)
    identity = (1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1)
    if any(abs(a-b) > 0.00001 for a, b in zip(bone, identity)):
        raise ValueError('Weapon bind matrix is not identity')
    bounds = end + 65
    if data[bounds:bounds+5] != b'\x01\0\0\0\0' or data[bounds+37] != 1:
        raise ValueError('Unsupported bounding geometry layout')
    cursor = bounds + 37 + 1 + 48 + 25
    count = data[cursor]
    cursor += 1
    fields = {}
    stride = 0
    for _ in range(count):
        end = data.index(0, cursor)
        name = data[cursor:end].decode('ascii')
        width = data[end+1]
        if name in fields or not 1 <= width <= 16:
            raise ValueError('Invalid vertex layout')
        fields[name] = (stride, width)
        stride += width
        cursor = end + 2
    expected = {'vertexPosition':3, 'vertexBoneWeights':4, 'vertexBoneIndices':4,
                'vertexTextureCoordinate':2, 'vertexNormal':3, 'vertexTangent':4}
    if {key:value[1] for key,value in fields.items()} != expected:
        raise ValueError('Unexpected chainsword vertex attributes')
    size = struct.unpack_from('<I', data, cursor)[0]
    start = cursor + 4
    if size % stride or start + size*4 + 4 != len(data) or data[-4:] != b'\0\0\0\0':
        raise ValueError('Expected an unindexed triangle-list mesh')
    vertices = size // stride
    if vertices == 0 or vertices % 3:
        raise ValueError('Invalid triangle count')
    return bounds, start, stride, vertices, fields


def rotate(vector):
    x, y, z = vector
    return z, x, y


def place(vector, scale=0.6):
    x, y, z = rotate(vector)
    return x*scale, y*scale-6, z*scale+12


def transform(source):
    bounds, start, stride, count, fields = layout(source)
    result = bytearray(source)
    before_positions, after_positions = [], []
    for i in range(count):
        vertex_start = start + i*stride*4
        weights = struct.unpack_from('<4f', source, vertex_start+fields['vertexBoneWeights'][0]*4)
        indices = struct.unpack_from('<4f', source, vertex_start+fields['vertexBoneIndices'][0]*4)
        if weights != (1, 0, 0, 0) or indices[0] != 0:
            raise ValueError('Expected fully rigid Hilt weights')
        for name in ('vertexPosition', 'vertexNormal', 'vertexTangent'):
            offset = vertex_start+fields[name][0]*4
            vector = struct.unpack_from('<3f', source, offset)
            if not all(math.isfinite(value) for value in vector):
                raise ValueError('Non-finite geometry')
            transformed = place(vector) if name == 'vertexPosition' else rotate(vector)
            struct.pack_into('<3f', result, offset, *transformed)
            if name == 'vertexPosition':
                before_positions.append(vector)
                after_positions.append(transformed)
    before_bounds = [min(v[k] for v in before_positions) for k in range(3)] + [max(v[k] for v in before_positions) for k in range(3)]
    stored_bounds = list(struct.unpack_from('<3f', source, bounds+5)) + list(struct.unpack_from('<3f', source, bounds+21))
    if any(abs(a-b) > 0.001 for a,b in zip(before_bounds,stored_bounds)):
        raise ValueError('Bounding layout did not match original geometry')
    low = [min(v[k] for v in after_positions) for k in range(3)]
    high = [max(v[k] for v in after_positions) for k in range(3)]
    struct.pack_into('<3f', result, bounds+5, *low)
    struct.pack_into('<3f', result, bounds+21, *high)
    return bytes(result), dict(vertices=count, triangles=count//3, scale=0.6,
                               rotation='(x,y,z) -> (z,x,y)', hip_local_offset=[0,-6,12],
                               attachment='HipBone', bounds_min=low, bounds_max=high)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-data', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Refusing to overwrite an existing asset')
    source = args.game_data/'Video/Meshes/Weapons/SpaceMarines/Chainsword.msh'
    try:
        raw = source.read_bytes()
        converted, metadata = transform(raw)
    except (OSError, ValueError, struct.error) as error:
        parser.error(str(error))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(converted)
    print(json.dumps(dict(metadata, source_sha256=hashlib.sha256(raw).hexdigest(),
                          output_sha256=hashlib.sha256(converted).hexdigest())))


if __name__ == '__main__':
    main()
