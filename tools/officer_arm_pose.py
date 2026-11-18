"""Anatomical officer arms: two-bone IK, a physical cuff joint and bounded wrists."""
import math,struct
from collections import Counter
from mathutils import Vector,Matrix,Quaternion
from officer_animation import frame,smooth
from officer_skinning import point_key,matching_key

def center(ob,ids):return sum((ob.data.vertices[i].co for i in ids),Vector())/len(ids)

def measure_hands(objects,attachments):
    """Measure the accepted hands without changing their geometry or UVs."""
    result={};moved={}
    for side in ('Left','Right'):
        ob=objects[side];counts=Counter()
        for face in ob.data.polygons:
            ids=list(face.vertices)
            for a,b in zip(ids,ids[1:]+ids[:1]):counts[tuple(sorted((a,b)))]+=1
        original_points={point_key(v.co) for v in ob.data.vertices};cuff_ids=sorted({i for edge,count in counts.items() if count==1 for i in edge});assert len(cuff_ids)==6
        cuff=center(ob,cuff_ids)
        if side=='Left':
            grip=attachments['sword'];basis=grip['grip_placement']['grip_frame'];shaft=Vector(basis['shaft_axis_hand_rest']).normalized();up=Vector(basis['thumb_side_hand_rest']).normalized()
            mcp_ids=list(range(6,16));mcp=center(ob,mcp_ids);thumb=up
        else:
            mcp_ids=list(range(14,22));mcp=center(ob,mcp_ids);thumb=center(ob,[30,31])-mcp
        forward=(mcp-cuff).normalized();thumb=(thumb-forward*thumb.dot(forward)).normalized()
        result[side]={'cuff':cuff,'cuff_ids':cuff_ids,'palm_center':mcp,'forward':forward,'thumb':thumb,'hand_object':ob,'original_points':original_points,'frame':attachments['sword']['grip_placement']['grip_frame'] if side=='Left' else None}
    return result,moved

def fit_pistol(attachment,hand,native_forward,native_up):
    rotation=frame(hand['forward'],hand['thumb'])@frame(native_forward,native_up).transposed()
    grip=Vector(attachment['rest_hand_grip'])+hand['thumb']*1.10+hand['forward']*.40
    matrix=(rotation*attachment['uniform_scale']).to_4x4();matrix.translation=grip-matrix.to_3x3()@Vector(attachment['local_grip'])
    attachment['anchor_bind']=[list(row) for row in matrix];attachment['rest_hand_grip']=list(grip);attachment.pop('grip_adjustment',None)

class ArmController:
    def __init__(self,rest,hands):
        self.rest=rest;self.hands=hands;self.metrics=[]

    def solve(self,pose,side,target,pole,desired_hand_q,max_wrist_degrees=16.):
        """Solve shoulder → elbow → cuff; rotate the hand about the cuff.

        The native HandBone origin sits inside the palm. Its translation is
        derived from the actual cuff joint, rather than mistaking it for the
        physical wrist. The elbow pole is an explicit input in every pose.
        """
        r=self.rest;h=self.hands[side];un=side+'UpperArmBone';ln=side+'LowerArmBone';hn=side+'HandBone';sn='LeftSoulderBone' if side=='Left' else 'RightShoulderBone'
        s=pose[un][0].copy();ur=r[ln]-r[un];lr=h['cuff']-r[ln];l1=ur.length;l2=lr.length
        delta=Vector(target)-s;distance=min(max(delta.length,abs(l1-l2)+.08),l1+l2-.08);axis=delta.normalized();w=s+axis*distance
        guide=Vector(pole)-s;guide-=axis*guide.dot(axis)
        if guide.length<.05:raise ValueError('Elbow pole is parallel to arm target')
        guide.normalize();along=(l1*l1-l2*l2+distance*distance)/(2*distance);height=math.sqrt(max(0,l1*l1-along*along));e=s+axis*along+guide*height
        upper=(e-s).normalized();lower=(w-e).normalized();
        # The humerus follows the chest plus the shortest shoulder swing.
        # Using the moving elbow plane as its roll frame spun the sleeve around
        # the upper arm during an otherwise simple raising motion.
        chest_base=pose['ChestBone'][1];qu=(chest_base@ur).rotation_difference(upper)@chest_base
        qh=Quaternion(desired_hand_q).normalized();palm=(qh@h['forward']).normalized();bend=palm.angle(lower);limit=math.radians(max_wrist_degrees)
        if bend>limit:
            rotation=palm.rotation_difference(lower);correct=Quaternion().slerp(rotation,(bend-limit)/bend);qh=correct@qh
        radial=qh@h['thumb'];ql=(frame(lower,radial)@frame(lr,h['thumb']).transposed()).to_quaternion()
        pose[un]=[s,qu];pose[ln]=[e,ql]
        hand_origin=w+qh@(r[hn]-h['cuff'])
        for n in pose:
            if n.startswith(side) and any(part in n for part in ('HandBone','FingerBone','ThumbBone')):pose[n]=[hand_origin+qh@(r[n]-r[hn]),qh.copy()]
        # Shoulder armor has a bounded hinge, rather than inheriting wrist roll.
        chest_q=pose['ChestBone'][1];swing=(chest_q@ur).rotation_difference(e-s);pad_q=Quaternion().slerp(swing,.55)@chest_q
        pose[sn]=[pose['ChestBone'][0]+chest_q@(r[sn]-r['ChestBone']),pad_q]
        actual_bend=math.degrees((qh@h['forward']).angle(lower));self.metrics.append({'side':side,'wrist_bend_degrees':actual_bend,'length_error':max(abs((e-s).length-l1),abs((w-e).length-l2)),'pole_alignment':(e-s-axis*along).normalized().dot(guide)})
        return w,e

def anatomical_sleeves(objects,rest,hands,regions):
    """Coherent elbow rings with a smooth join to the native shoulder and torso."""
    uniform=next(o for o in objects if o.name=='Native Guardsman body - officer uniform')
    originals={point_key(v.co):{uniform.vertex_groups[g.group].name:g.weight for g in v.groups} for v in uniform.data.vertices};changes={};report={};graph={key:{} for key in originals}
    for edge in uniform.data.edges:
        a,b=(point_key(uniform.data.vertices[i].co) for i in edge.vertices)
        if a!=b:graph[a][b]=graph[b][a]=1/max(.1,(Vector(a)-Vector(b)).length)**2
    collar={key for key,weights in originals.items() if key[2]>54 and abs(key[1])<4 and any('Shoulder' in n or 'Soulder' in n for n in weights)}
    for key in collar:changes[key]={'ChestBone':1.}
    # Blend the jacket out of the leg influences before its armhole is solved.
    for key,row in originals.items():
        if 20<key[2]<42 and any('HipBone' in n for n in row):
            amount=smooth((key[2]-20.)/14.);weights={n:w*(1.-amount) for n,w in row.items()};weights['AbdomenBone']=weights.get('AbdomenBone',0.)+amount;changes[key]={n:w for n,w in weights.items() if w>1e-6}
    for side in ('Left','Right'):
        un=side+'UpperArmBone';ln=side+'LowerArmBone';sn='LeftSoulderBone' if side=='Left' else 'RightShoulderBone';anchors={key:dict(value) for key,value in originals.items()};anchors.update(changes);cloth={matching_key(p,originals) for p in regions[side]['cloth']}-{None};pads={matching_key(p,originals) for p in regions[side]['shoulder']}-{None};fixed=set()
        for key in pads-collar:anchors[key]={sn:1.};changes[key]={sn:1.}
        for ring_index,ring in enumerate(regions[side]['rings'][:5]):
            for point in ring:
                key=matching_key(point,originals)
                if key is None:continue
                weights={side+'HandBone':1.} if ring_index==0 else {ln:1.} if ring_index in (1,2) else {ln:.5,un:.5}
                anchors[key]=weights;changes[key]=weights;fixed.add(key)
        free=cloth-fixed
        for _ in range(3):free|={n for key in free for n in graph[key] if n[2]>38 and (n[1]>2.5 if side=='Left' else n[1]<-2.5)}
        free-=fixed|pads|collar
        values={key:dict(row) for key,row in anchors.items()}
        def clean(row):
            result={}
            for n,w in row.items():
                if 'HipBone' in n:n='AbdomenBone'
                if 'HandBone' in n or 'FingerBone' in n or 'ThumbBone' in n:n=ln
                result[n]=result.get(n,0)+w
            return result
        for _ in range(250):
            updated={}
            for key in free:
                row={n:w*.015 for n,w in clean(originals[key]).items()};total=sum(graph[key].values())
                for neighbor,inverse_length in graph[key].items():
                    for n,w in clean(values[neighbor]).items():row[n]=row.get(n,0)+w*.985*inverse_length/total
                updated[key]=row
            values.update(updated)
        for key in free:
            row=dict(sorted(values[key].items(),key=lambda pair:-pair[1])[:4]);total=sum(row.values());changes[key]={n:w/total for n,w in row.items() if w>1e-6}
        for vertex in hands[side]['hand_object'].data.vertices:changes[point_key(vertex.co)]={side+'HandBone':1.}
        hip=side+'HipBone';shin=side+'ShinBone';knee=rest[shin].z
        for key,original in originals.items():
            if key[2]<22 and any(n in original for n in (hip,shin)):
                u=smooth((key[2]-knee+4)/8);foot=original.get(side+'FootBone',0.);changes[key]={hip:u*(1-foot),shin:(1-u)*(1-foot),side+'FootBone':foot}
        report[side]={'wrist_limit_degrees':16,'cuff_bone':side+'HandBone','forearm_uses_hand_or_chest_weights':False,'elbow_rings_share_weights':True,'armhole_positions_smoothed':len(free),'native_torso_weights_preserved_outside_armhole':True}
    for ob in objects:
        for vertex in ob.data.vertices:
            key=matching_key(vertex.co,changes)
            if key is None:continue
            for group in list(vertex.groups):ob.vertex_groups[group.group].remove([vertex.index])
            for name,weight in changes[key].items():(ob.vertex_groups.get(name) or ob.vertex_groups.new(name=name)).add([vertex.index],weight,'REPLACE')
    return changes,report

def export_refitted_mesh(raw,changes,moved,attachments):
    """Preserve topology/maps and the original 28 binds; refit the two sockets."""
    data=bytearray(raw);at=8;names=[]
    for index in range(data[7]):
        end=data.index(0,at);name=data[at:end].decode();names.append(name);at=end+1
        for attachment in attachments.values():
            if name==attachment['bone']:
                a=attachment['anchor_bind'];struct.pack_into('<16f',data,at,*(a[row][col] for col in range(4) for row in range(4)))
        if index<28:assert data[at:at+64]==raw[at:at+64]
        at+=64
    bounds=at;at+=111;count=data[at];at+=1
    for _ in range(count):at=data.index(0,at)+2
    size=struct.unpack_from('<I',data,at)[0];at+=4;rows=[list(struct.unpack_from('<20f',data,at+i*80)) for i in range(size//20)]
    changed_faces=set()
    for i,row in enumerate(rows):
        old=matching_key(row[:3],moved)
        if old is not None:row[:3]=moved[old];changed_faces.add(i//3)
        key=matching_key(row[:3],changes)
        if key is not None:
            inf=sorted(changes[key].items(),key=lambda item:-item[1]);row[3:7]=[w for _,w in inf]+[0.]*(4-len(inf));row[7:11]=[float(names.index(n)) for n,_ in inf]+[0.]*(4-len(inf))
    for face in changed_faces:
        tri=rows[face*3:face*3+3];p=[Vector(v[:3]) for v in tri];uv=[Vector(v[11:13]) for v in tri];normal=(p[1]-p[0]).cross(p[2]-p[0]).normalized();d1=uv[1]-uv[0];d2=uv[2]-uv[0];den=d1.x*d2.y-d1.y*d2.x
        tangent=((p[1]-p[0])*d2.y-(p[2]-p[0])*d1.y)/den;tangent=(tangent-normal*tangent.dot(normal)).normalized()
        for row in tri:row[13:16]=list(normal);row[16:19]=list(tangent)
    assert len(rows)//3==892
    lo=[min(row[k] for row in rows) for k in range(3)];hi=[max(row[k] for row in rows) for k in range(3)];struct.pack_into('<3f',data,bounds+5,*lo);struct.pack_into('<3f',data,bounds+21,*hi);struct.pack_into('<3f',data,bounds+91,*[(a+b)/2 for a,b in zip(lo,hi)]);struct.pack_into('<f',data,bounds+107,math.sqrt(sum((a-b)**2 for a,b in zip(lo,hi)))/2)
    data=data[:at];struct.pack_into('<I',data,at-4,len(rows)*20)
    for row in rows:data+=struct.pack('<20f',*row)
    data+=struct.pack('<I',0);return bytes(data)
