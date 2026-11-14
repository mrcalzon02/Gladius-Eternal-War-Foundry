"""Create teeth as connected gum extrusions, with interpolated jaw weights."""
import bmesh
from mathutils import Vector

def build_gum_fangs(body,orient):
 bm=bmesh.new();bm.from_mesh(body.data);bmesh.ops.triangulate(bm,faces=list(bm.faces));orient(bm)
 deform=bm.verts.layers.deform.verify();mask=bm.verts.layers.float.new('Ripper gum socket');tag=bm.faces.layers.int.new('Ripper tooth id');root_tag=bm.verts.layers.int.new('Ripper tooth root');tip_tag=bm.verts.layers.int.new('Ripper tooth tip')
 def weights(face,p):
  a,b,c=[v.co for v in face.verts];u=b-a;v=c-a;w=p-a;den=u.dot(u)*v.dot(v)-u.dot(v)**2
  wb=(v.dot(v)*w.dot(u)-u.dot(v)*w.dot(v))/den;wc=(u.dot(u)*w.dot(v)-u.dot(v)*w.dot(u))/den;wa=1-wb-wc;result={}
  for point,t in zip(face.verts,[wa,wb,wc]):
   for i,value in point[deform].items():result[i]=result.get(i,0)+t*value
  return result
 records=[]
 for side in [-1,1]:
  for row,x in [('Head',1.55),('Head',2.9),('Jaw',2.5)]:
   group=body.vertex_groups[row].index;target=Vector((x,side*1.3,7.0 if row=='Head' else 4.3));candidates=[]
   for f in bm.faces:
    if len(f.verts)!=3 or f[tag] or any(v[mask]>.01 for v in f.verts):continue
    center=f.calc_center_median();area=f.calc_area();edge=max(e.calc_length() for e in f.edges);weight=sum(v[deform].get(group,0) for v in f.verts)/3
    if weight<.55 or center.x<.3 or center.y*side<.15 or area<.045 or area/edge**2<.07:continue
    if row=='Head' and (f.normal.z>-.12 or center.z<6.3):continue
    if row=='Jaw' and (f.normal.z<.12 or center.z>5.6):continue
    candidates.append(f)
   if not candidates:raise RuntimeError('No weighted gum surface for '+row+' '+str(side))
   face=min(candidates,key=lambda f:(f.calc_center_median()-target).length);outer=list(face.verts);center=face.calc_center_median();normal=face.normal.copy();scale=min(.44,.29/max((v.co-center).length for v in outer));roots=[];number=len(records)+1
   for old in outer:
    p=center+(old.co-center)*scale;v=bm.verts.new(p)
    for i,value in weights(face,p).items():v[deform][i]=value
    v[mask]=1;v[root_tag]=number;roots.append(v)
   direction=(normal*.45+Vector((.08,-side*.08,-1 if row=='Head' else 1))*.55).normalized();tip=bm.verts.new(center+direction*(.82 if row=='Head' else .63));tip[tip_tag]=number
   for i,value in weights(face,center).items():tip[deform][i]=value
   material=face.material_index
   for old in outer:old[mask]=max(old[mask],.22)
   for k in range(3):
    j=(k+1)%3
    for points in [(outer[k],outer[j],roots[j]),(outer[k],roots[j],roots[k])]:
     f=bm.faces.new(points);f.material_index=material;f.smooth=True
    f=bm.faces.new((roots[k],roots[j],tip));f.material_index=3;f[tag]=number
   records.append({'id':number,'row':row,'side':side,'root_center':list(center),'tip':list(tip.co),'shared_root':True})
   bmesh.ops.delete(bm,geom=[face],context='FACES_ONLY')
 orient(bm);bm.to_mesh(body.data);bm.free();body.data.update();return records

def boost_mouth_uv(body,factor=1.8):
 """Give complete mouth UV islands more texel area without breaking shared edges."""
 me=body.data;uv=me.uv_layers.active.data;edges={};neighbors={p.index:set() for p in me.polygons}
 for p in me.polygons:
  ls=list(p.loop_indices)
  for i,li in enumerate(ls):
   nxt=ls[(i+1)%len(ls)];key=(me.loops[li].edge_index,tuple(sorted([tuple(round(x,5) for x in uv[li].uv),tuple(round(x,5) for x in uv[nxt].uv)])))
   if key in edges:neighbors[p.index].add(edges[key]);neighbors[edges[key]].add(p.index)
   else:edges[key]=p.index
 tag=me.attributes.get('Ripper tooth id');mask=me.attributes.get('Ripper gum socket');seen=set()
 for p in me.polygons:
  if p.index in seen:continue
  comp={p.index};seen.add(p.index);stack=[p.index]
  while stack:
   for other in neighbors[stack.pop()]:
    if other not in seen:seen.add(other);comp.add(other);stack.append(other)
  if not any((tag and tag.data[i].value>0) or (mask and any(mask.data[v].value>.01 for v in me.polygons[i].vertices)) for i in comp):continue
  loops=[li for i in comp for li in me.polygons[i].loop_indices];center=sum((uv[li].uv for li in loops),Vector((0,0)))/len(loops)
  for li in loops:uv[li].uv=center+(uv[li].uv-center)*factor

def clear_tooth_normal(body,pixels,size):
 """New enamel faces use their actual geometry normals, never an old sculpt's teeth."""
 tag=body.data.attributes['Ripper tooth id'];uv=body.data.uv_layers.active.data
 tongue=body.vertex_groups['Tongue'].index
 for p in body.data.polygons:
  is_tongue=all(any(g.group==tongue and g.weight>.9 for g in body.data.vertices[i].groups) for i in p.vertices)
  if tag.data[p.index].value<=0 and not is_tongue:continue
  points=[uv[i].uv*size for i in p.loop_indices]
  # Tongue quads are handled as fans in the same packed atlas.
  for fan in range(1,len(points)-1):
   _clear_triangle(points[0],points[fan],points[fan+1],pixels,size)

def _clear_triangle(a,b,c,pixels,size):
  den=(b.y-c.y)*(a.x-c.x)+(c.x-b.x)*(a.y-c.y)
  if abs(den)<1e-9:return
  for y in range(max(0,int(min(a.y,b.y,c.y))-2),min(size,int(max(a.y,b.y,c.y))+3)):
   for x in range(max(0,int(min(a.x,b.x,c.x))-2),min(size,int(max(a.x,b.x,c.x))+3)):
    u=((b.y-c.y)*(x+.5-c.x)+(c.x-b.x)*(y+.5-c.y))/den;v=((c.y-a.y)*(x+.5-c.x)+(a.x-c.x)*(y+.5-c.y))/den
    if u>=-.1 and v>=-.1 and u+v<=1.1:
     k=(y*size+x)*4;pixels[k:k+4]=[.5,.5,1,1]
