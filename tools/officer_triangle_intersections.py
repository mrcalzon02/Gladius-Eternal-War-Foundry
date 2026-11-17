"""Triangle tests including adjacent folds and coplanar overlap."""
from mathutils import Vector
from mathutils.geometry import intersect_ray_tri

def _area(poly):
    return abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(poly,poly[1:]+poly[:1])))*.5 if len(poly)>=3 else 0.

def _coplanar_overlap(a,b,normal):
    drop=max(range(3),key=lambda i:abs(normal[i]));keep=[i for i in range(3) if i!=drop]
    polygon=[tuple(p[i] for i in keep) for p in a];clip=[tuple(p[i] for i in keep) for p in b]
    winding=1 if sum(p[0]*q[1]-q[0]*p[1] for p,q in zip(clip,clip[1:]+clip[:1]))>0 else -1
    for p,q in zip(clip,clip[1:]+clip[:1]):
        def side(v):return winding*((q[0]-p[0])*(v[1]-p[1])-(q[1]-p[1])*(v[0]-p[0]))
        result=[]
        for prev,cur in zip(polygon[-1:]+polygon[:-1],polygon):
            dp,dc=side(prev),side(cur)
            if (dp>=0)!=(dc>=0):
                t=dp/(dp-dc);result.append(tuple(prev[i]+t*(cur[i]-prev[i]) for i in (0,1)))
            if dc>=0:result.append(cur)
        polygon=result
        if not polygon:return False
    return _area(polygon)>1e-9

def _intersect(a,b):
    na=(a[1]-a[0]).cross(a[2]-a[0]).normalized();nb=(b[1]-b[0]).cross(b[2]-b[0]).normalized()
    da=[na.dot(p-a[0]) for p in b];db=[nb.dot(p-b[0]) for p in a]
    if min(da)>1e-6 or max(da)<-1e-6 or min(db)>1e-6 or max(db)<-1e-6:return False
    if na.cross(nb).length<1e-5 and max(abs(d) for d in da)<2e-5:return _coplanar_overlap(a,b,na)
    for source,target in ((a,b),(b,a)):
        for p,q in zip(source,source[1:]+source[:1]):
            ray=q-p;hit=intersect_ray_tri(*target,ray,p,True)
            if hit is not None:
                t=(hit-p).dot(ray)/ray.length_squared
                if 1e-6<t<1-1e-6:return True
    return False

def proper_triangle_intersections(points,faces):
    # Separate legal shared edges/vertices by a tiny amount. Unlike ignoring
    # adjacent triangles, this still finds a fold through the adjacent surface.
    triangles=[];vertices=[];indices=[]
    for face in faces:
        assert len(face)==3
        tri=[Vector(points[i]) for i in face];c=sum(tri,Vector())/3;tri=[c+(p-c)*.999 for p in tri];triangles.append(tri);start=len(vertices);vertices.extend(tri);indices.append(tuple(range(start,start+3)))
    # Blender BVH overlap omits coplanar containment, so use explicit AABBs for
    # this small hand rather than accepting an incomplete candidate shortlist.
    bounds=[([min(p[k] for p in tri) for k in range(3)],[max(p[k] for p in tri) for k in range(3)]) for tri in triangles]
    return [(a,b) for a in range(len(triangles)) for b in range(a+1,len(triangles))
            if all(bounds[a][0][k]<=bounds[b][1][k] and bounds[b][0][k]<=bounds[a][1][k] for k in range(3))
            and _intersect(triangles[a],triangles[b])]
