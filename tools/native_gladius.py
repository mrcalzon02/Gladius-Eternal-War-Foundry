"""Small validators for the observed native MSH1.0 and ANM1.0 formats."""
import math
import struct

def _string(raw,offset):
    end=raw.index(0,offset);return raw[offset:end].decode('utf-8'),end+1

def read_mesh(raw):
    if raw[:7]!=b'MSH1.0\0':raise ValueError('Not MSH1.0')
    cursor=8;bones=[]
    for _ in range(raw[7]):
        name,cursor=_string(raw,cursor);matrix=struct.unpack_from('<16f',raw,cursor);cursor+=64
        if name in bones or not all(map(math.isfinite,matrix)):raise ValueError('Invalid mesh bind')
        bones.append(name)
    bounds=cursor
    if raw[cursor+37]!=1:raise ValueError('Validator supports exported type-1 bounds only')
    cursor+=111;count=raw[cursor];cursor+=1;layout=[]
    for _ in range(count):
        name,cursor=_string(raw,cursor);layout.append((name,raw[cursor]));cursor+=1
    size=struct.unpack_from('<I',raw,cursor)[0];cursor+=4;stride=sum(width for _,width in layout)
    if size%stride:raise ValueError('Invalid mesh vertex table length')
    vertex_count=size//stride
    values=struct.unpack_from('<'+str(size)+'f',raw,cursor);cursor+=size*4
    if not all(map(math.isfinite,values)):raise ValueError('Nonfinite mesh data')
    indices=struct.unpack_from('<I',raw,cursor)[0];cursor+=4
    if cursor+indices*4!=len(raw):raise ValueError('Unexpected mesh trailing bytes')
    if indices and max(struct.unpack_from('<'+str(indices)+'I',raw,cursor))>=vertex_count:raise ValueError('Invalid mesh index')
    triangles=(indices or vertex_count)//3
    if (indices or vertex_count)%3:raise ValueError('Nontriangle mesh')
    offsets={};offset=0
    for name,width in layout:offsets[name]=offset;offset+=width
    if 'vertexBoneWeights' in offsets:
        for vertex in range(vertex_count):
            at=vertex*stride;weights=values[at+offsets['vertexBoneWeights']:at+offsets['vertexBoneWeights']+4]
            bi=values[at+offsets['vertexBoneIndices']:at+offsets['vertexBoneIndices']+4]
            if abs(sum(weights)-1)>.0001:raise ValueError('Unnormalized skin weights')
            if any(w and (i!=int(i) or not 0<=i<len(bones)) for i,w in zip(bi,weights)):raise ValueError('Invalid skin bone index')
    return dict(bones=bones,vertices=vertex_count,triangles=triangles,bounds=[list(struct.unpack_from('<3f',raw,bounds+5)),list(struct.unpack_from('<3f',raw,bounds+21))])

def read_animation(raw):
    if raw[:7]!=b'ANM1.0\0':raise ValueError('Not ANM1.0')
    count,frames,fps=struct.unpack_from('<BII',raw,7);cursor=16;names=[]
    if not count or not frames or not fps:raise ValueError('Empty animation')
    for _ in range(count):
        name,cursor=_string(raw,cursor);names.append(name)
        for frame in range(frames):
            sample=struct.unpack_from('<10f',raw,cursor);cursor+=40
            if not all(map(math.isfinite,sample)):raise ValueError('Nonfinite animation')
            if abs(sum(v*v for v in sample[3:7])-1)>.001:raise ValueError('Invalid animation quaternion')
            if min(sample[7:])<=0:raise ValueError('Nonpositive scale')
    if cursor!=len(raw):raise ValueError('Unexpected animation trailing bytes')
    return dict(bones=names,frames=frames,fps=fps)
