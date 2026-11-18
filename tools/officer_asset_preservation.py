"""Check the exact permitted differences from the accepted officer mesh."""
import ast
import struct


def mesh_records(raw):
    at = 8
    bones = []
    for _ in range(raw[7]):
        end = raw.index(0, at)
        bones.append((raw[at:end].decode(), raw[end + 1:end + 65]))
        at = end + 65
    bounds = at
    at += 111
    count = raw[at]
    at += 1
    for _ in range(count):
        at = raw.index(0, at) + 2
    size = struct.unpack_from('<I', raw, at)[0]
    at += 4
    rows = [raw[at + i * 80:at + (i + 1) * 80] for i in range(size // 20)]
    return bones, raw[bounds:at], rows, raw[at + size * 4:]


def verify_preservation(accepted, final, build):
    ab, ah, ar, tail = mesh_records(accepted)
    fb, fh, fr, final_tail = mesh_records(final)
    assert len(ar) == len(fr) == 892 * 3 and tail == final_tail
    assert ab[:28] == fb[:28], 'Original skeleton bind changed'
    assert [n for n, _ in ab] == [n for n, _ in fb]
    assert ah == fh, 'Mesh layout or bounds changed'
    for name, matrix in fb[28:]:
        attachment = next(a for a in build['attachments'].values() if a['bone'] == name)
        expected = struct.pack('<16f', *(attachment['anchor_bind'][r][c] for c in range(4) for r in range(4)))
        assert matrix == expected, name
    moves = {tuple(ast.literal_eval(key)): value for key, value in build['armhole_vertex_changes'].items()}
    changed_faces = set()
    moved_points = set()
    for i, (old, new) in enumerate(zip(ar, fr)):
        p = struct.unpack_from('<3f', old)
        key = next((key for key in moves if max(abs(a-b) for a,b in zip(key,p)) < .0001), None)
        if key is not None:
            assert max(abs(a-b) for a,b in zip(struct.unpack_from('<3f',new), moves[key])) < .0001
            changed_faces.add(i // 3)
            moved_points.add(key)
        else:
            assert old[:12] == new[:12], ('Unexpected geometry change', i)
        assert old[44:52] == new[44:52], ('UV changed', i)
        assert old[76:80] == new[76:80], ('Tangent handedness changed', i)
    for i, (old, new) in enumerate(zip(ar, fr)):
        if i // 3 not in changed_faces:
            assert old[52:76] == new[52:76], ('Unrelated shading changed', i)
    assert moved_points == set(moves)
    return {'original_bind_frames_preserved': 28, 'triangles': 892,
            'fitted_armhole_positions': len(moved_points), 'reshaded_triangles': len(changed_faces),
            'topology_and_uvs_preserved': True, 'hand_geometry_preserved': True}
