import importlib.util
from pathlib import Path
import struct
import unittest

SPEC = importlib.util.spec_from_file_location(
    'hip_sword', Path(__file__).resolve().parents[1] / 'build_sergeant_hip_sword.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def fixture():
    identity = struct.pack('<16f', 1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1)
    fields = [('vertexPosition',3),('vertexBoneWeights',4),('vertexBoneIndices',4),
              ('vertexTextureCoordinate',2),('vertexNormal',3),('vertexTangent',4)]
    data = b'MSH1.0\0\x01Hilt\0' + identity
    data += b'\x01\0\0\0\0' + struct.pack('<8f', 0,0,0,1,1,0,2,1)
    data += b'\x01' + bytes(48+25) + bytes([len(fields)])
    data += b''.join(n.encode()+b'\0'+bytes([w]) for n,w in fields)
    data += struct.pack('<I', 60)
    for position in [(0,0,0),(1,0,0),(0,0,2)]:
        data += struct.pack('<20f', *position,1,0,0,0,0,0,0,0,0.2,0.3,0,0,1,1,0,0,1)
    return data + bytes(4)


class HipSwordTests(unittest.TestCase):
    def test_blade_runs_downward_in_verified_hip_frame(self):
        base = MODULE.place((0,0,0))
        tip = MODULE.place((0,0,10))
        # Guardsman's hip-local +X is model-space -Z.
        model_vertical_change = -(tip[0]-base[0])
        self.assertLess(model_vertical_change, 0)
        self.assertEqual(base[2], tip[2])

    def test_uv_weights_indices_and_tangent_handedness_are_preserved(self):
        source = fixture()
        output, _ = MODULE.transform(source)
        _, start, stride, count, fields = MODULE.layout(source)
        for i in range(count):
            for name in ['vertexTextureCoordinate','vertexBoneWeights','vertexBoneIndices']:
                offset,width = fields[name];a=start+(i*stride+offset)*4
                self.assertEqual(source[a:a+width*4], output[a:a+width*4])
            tangent = start+(i*stride+fields['vertexTangent'][0]+3)*4
            self.assertEqual(source[tangent:tangent+4], output[tangent:tangent+4])

    def test_bounds_follow_the_transformed_geometry(self):
        output, metadata = MODULE.transform(fixture())
        bounds, _, _, _, _ = MODULE.layout(output)
        self.assertEqual(3, metadata['vertices'])
        for a,b in zip(struct.unpack_from('<3f',output,bounds+5), metadata['bounds_min']):
            self.assertAlmostEqual(a,b,places=5)

    def test_non_rigid_input_is_rejected(self):
        source = bytearray(fixture())
        _,start,_,_,fields = MODULE.layout(source)
        struct.pack_into('<f',source,start+fields['vertexBoneWeights'][0]*4,0.5)
        with self.assertRaises(ValueError):
            MODULE.transform(source)


if __name__ == '__main__':
    unittest.main()
