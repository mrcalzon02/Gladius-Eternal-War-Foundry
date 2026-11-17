"""Refine sleeve weights without altering the accepted mesh or texture records."""
import struct
from mathutils import Vector

def point_key(p):return tuple(round(c,5) for c in p)

def matching_key(p,keys):
    p=point_key(p)
    if p in keys:return p
    candidates=[(sum((a-b)**2 for a,b in zip(p,k)),k) for k in keys if all(abs(a-b)<.002 for a,b in zip(p,k))]
    return min(candidates)[1] if candidates else None

def sleeve_weights(objects,rest,regions):
    changes={};summary={};uniform=next(o for o in objects if o.name=='Native Guardsman body - officer uniform')
    originals={point_key(v.co):{uniform.vertex_groups[w.group].name:w.weight for w in v.groups} for v in uniform.data.vertices}
    for side in ('Left','Right'):
        cloth={matching_key(p,originals) for p in regions[side]['cloth']}-{None};pad={matching_key(p,originals) for p in regions[side]['shoulder']}-{None};torso={matching_key(p,originals) for p in regions[side]['torso']}-{None}
        fist=next(o for o in objects if o.name=='Officer '+side+' closed weapon fist')
        cuff={matching_key(v.co,cloth) for v in fist.data.vertices}-{None}
        upper=side+'UpperArmBone';lower=side+'LowerArmBone';hand=side+'HandBone';s,e,w=(rest[n] for n in (upper,lower,hand))
        graph={key:{} for key in cloth}
        for edge in uniform.data.edges:
            a,b=(point_key(uniform.data.vertices[i].co) for i in edge.vertices)
            if a in cloth and b in cloth and a!=b:graph[a][b]=graph[b][a]=1/max(.1,(Vector(a)-Vector(b)).length)
        anchors={};targets={}
        for key in cloth:
            p=Vector(key);candidates=[]
            for index,(a,b) in enumerate(((s,e),(e,w))):
                axis=b-a;t=max(0.,min(1.,(p-a).dot(axis)/axis.length_squared));candidates.append(((p-a-axis*t).length,index+t))
            u=min(candidates)[1]
            if key in cuff:weights={hand:1.};anchors[key]=weights
            elif key in torso:
                weights={'ChestBone':1.};anchors[key]=weights
            elif key in pad:weights={'LeftSoulderBone' if side=='Left' else 'RightShoulderBone':1.};anchors[key]=weights
            else:
                # Broad elbow blend; wrist cloth smoothly meets the closed fist.
                f=max(0.,min(1.,(u-.65)/.70));f=f*f*(3-2*f)
                h=max(0.,min(1.,(u-1.60)/.40));h=h*h*(3-2*h)
                weights={upper:(1-f)*(1-h),lower:f*(1-h),hand:h}
                weights={n:v for n,v in weights.items() if v>1e-6}
            targets[key]=weights
        values={key:dict(weights) for key,weights in targets.items()}
        for _ in range(100):
            updated={}
            for key,neighbors in graph.items():
                if key in anchors:updated[key]=anchors[key];continue
                row={n:v*.10 for n,v in targets[key].items()};total=sum(neighbors.values())
                for neighbor,inverse_length in neighbors.items():
                    for n,v in values[neighbor].items():
                        if n in ('LeftSoulderBone','RightShoulderBone','AbdomenBone'):n='ChestBone'
                        row[n]=row.get(n,0)+v*.90*inverse_length/total
                updated[key]=row
            values=updated
        for key,weights in values.items():
            weights=dict(sorted(weights.items(),key=lambda pair:-pair[1])[:4]);total=sum(weights.values());changes[key]={n:v/total for n,v in weights.items() if v>1e-6}
        summary[side]={'sleeve_positions_refined':len(cloth),'cuff_positions':len(cuff),'cuff_bone':hand,'shoulder_boundary_positions_preserved':len(cloth&pad),'torso_boundary_positions_preserved':len(cloth&torso)}
        hip=side+'HipBone';shin=side+'ShinBone';knee=rest[shin].z;count=0
        for v in uniform.data.vertices:
            key=point_key(v.co)
            if v.co.z<22 and any(n in originals[key] for n in (hip,shin)):
                t=max(0.,min(1.,(v.co.z-knee+4)/8));t=t*t*(3-2*t);foot=originals[key].get(side+'FootBone',0.);changes[key]={hip:t*(1-foot),shin:(1-t)*(1-foot),side+'FootBone':foot};count+=1
        summary[side]['knee_positions_blended']=count
    for v in uniform.data.vertices:
        if v.co.z>54 and abs(v.co.y)<4 and any('Shoulder' in uniform.vertex_groups[w.group].name or 'Soulder' in uniform.vertex_groups[w.group].name for w in v.groups):changes[point_key(v.co)]={'ChestBone':1.}
        # The native inner armpit contains stray lower-arm/hip influences.
        # Keep the jacket seam on the torso, like its adjacent torso vertices.
        if 39.5<v.co.z<42 and abs(v.co.y)<11 and v.co.x<0:changes[point_key(v.co)]={'AbdomenBone':.98,'ChestBone':.02}
        key=point_key(v.co);old=originals[key]
        if 20<v.co.z<42 and any(n in old for n in ('LeftHipBone','RightHipBone','HipBone')):
            t=max(0.,min(1.,(v.co.z-20)/14));t=t*t*(3-2*t);row={n:w*(1-t) for n,w in changes.get(key,old).items()};row['AbdomenBone']=row.get('AbdomenBone',0)+t;changes[key]=row
    for ob in objects:
        for v in ob.data.vertices:
            weights=changes.get(matching_key(v.co,changes))
            if weights is None:continue
            for group in list(v.groups):ob.vertex_groups[group.group].remove([v.index])
            for n,w in weights.items():
                group=ob.vertex_groups.get(n) or ob.vertex_groups.new(name=n);group.add([v.index],w,'REPLACE')
    return changes,summary

def refine_native_weights(raw,changes):
    data=bytearray(raw);at=8;names=[]
    for _ in range(data[7]):
        end=data.index(0,at);names.append(data[at:end].decode());at=end+65
    at+=111;count=data[at];at+=1;layout=[]
    for _ in range(count):
        end=data.index(0,at);name=data[at:end].decode();at=end+1;layout.append((name,data[at]));at+=1
    assert layout==[('vertexPosition',3),('vertexBoneWeights',4),('vertexBoneIndices',4),('vertexTextureCoordinate',2),('vertexNormal',3),('vertexTangent',4)]
    size=struct.unpack_from('<I',data,at)[0];at+=4;changed=0
    for i in range(size//20):
        cursor=at+i*80;key=matching_key(struct.unpack_from('<3f',data,cursor),changes);weights=changes.get(key)
        if weights is None:continue
        influences=sorted(weights.items(),key=lambda pair:-pair[1]);values=[v for _,v in influences]+[0.]*(4-len(influences));indices=[float(names.index(n)) for n,_ in influences]+[0.]*(4-len(influences))
        struct.pack_into('<8f',data,cursor+12,*values,*indices);changed+=1
    # All positions, triangle order, UVs, tangents, normals, bounds and bind
    # frames must remain byte-for-byte equal to the accepted runtime artifact.
    for i in range(size//20):
        cursor=at+i*80;assert data[cursor:cursor+12]==raw[cursor:cursor+12] and data[cursor+44:cursor+80]==raw[cursor+44:cursor+80]
    assert data[:at]==raw[:at] and data[at+size*4:]==raw[at+size*4:]
    return bytes(data),changed
