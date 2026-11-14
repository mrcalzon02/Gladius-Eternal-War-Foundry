"""Reference-led proportions and facial surfacing, preserving triangle count."""
from pathlib import Path
import bpy,json,hashlib,math
import numpy as np
from mathutils import Vector,Matrix

def smooth(t):
 t=max(0,min(1,t));return t*t*(3-2*t)

def shape(point):
 p=Vector(point);x,y,z=p;side=abs(y)
 # Flatten the dome and narrow the nose into the source's long bony wedge.
 if z>25.7 and x>1 and side<3.1:p.z=25.7+(z-25.7)*.72
 nose=smooth((x-7.1)/2)*smooth((z-23.4)/1.4)
 p.y*=1-.19*nose;p.z+=.24*nose
 # Recess the painted eye into a bony socket and taper the cheek into the hinge.
 orbit=math.exp(-((x-6.65)/.80)**2-((z-24.95)/.46)**2)*smooth((side-1.25)/.8)
 p.y-=math.copysign(.19*orbit,y)
 hinge=math.exp(-((x-5.35)/.95)**2-((z-21.8)/.9)**2)
 p.y*=1-.09*hinge
 # The ears sweep rearward instead of presenting long sideways spikes.
 if side>3 and z>23.8:
  t=smooth((side-3)/2.8);p.y=math.copysign(3+(side-3)*.70,y);p.x-=.65*t;p.z-=.30*t
 # Lower the head onto the shoulders with a smooth neck transition.
 head=smooth((x-.3)/3.6)*smooth((z-18.3)/3)*smooth((6.7-side)/2.4)
 p.x+=.75*head;p.z-=1.25*head
 # Forward-leaning rib cage, with hips and feet remaining planted.
 lean=smooth((z-12.7)/7)*smooth((24-z)/3)*smooth((5.8-side)/2)
 p.x+=.9*lean
 return p

def paint_folds(body,dest):
 nodes=body.data.materials[0].node_tree.nodes;colour=next(n.image for n in nodes if n.type=='TEX_IMAGE' and n.image and n.image.name=='Grot skin colour');normal=next(n.image for n in nodes if n.type=='TEX_IMAGE' and n.image and n.image.name=='Grot skin normal')
 w,h=colour.size;pixels=np.array(colour.pixels[:],dtype=np.float32).reshape(h,w,4);normalpixels=np.array(normal.pixels[:],dtype=np.float32).reshape(h,w,4);uv=body.data.uv_layers.active.data
 body.data.calc_loop_triangles();world=np.array([body.matrix_world@v.co for v in body.data.vertices]);painted=0
 for tri in body.data.loop_triangles:
  pts=world[list(tri.vertices)]
  if pts[:,0].max()<3.2 or pts[:,0].min()>10 or pts[:,2].max()<19 or pts[:,2].min()>26.5:continue
  coords=np.array([uv[i].uv[:] for i in tri.loops])*[w,h];lo=np.maximum(np.floor(coords.min(axis=0)).astype(int),0);hi=np.minimum(np.ceil(coords.max(axis=0)).astype(int),[w-1,h-1])
  if (hi<lo).any():continue
  xx,yy=np.meshgrid(np.arange(lo[0],hi[0]+1),np.arange(lo[1],hi[1]+1));q=np.stack([xx+.5,yy+.5],axis=-1);a,b,c=coords;den=(b[1]-c[1])*(a[0]-c[0])+(c[0]-b[0])*(a[1]-c[1])
  if abs(den)<1e-9:continue
  u=((b[1]-c[1])*(q[...,0]-c[0])+(c[0]-b[0])*(q[...,1]-c[1]))/den;v=((c[1]-a[1])*(q[...,0]-c[0])+(a[0]-c[0])*(q[...,1]-c[1]))/den;t=1-u-v
  valid=(u>=0)&(v>=0)&(t>=0);p=u[...,None]*pts[0]+v[...,None]*pts[1]+t[...,None]*pts[2];x,y,z=p[...,0],p[...,1],p[...,2];col=pixels[yy,xx,:3].copy()
  eye=(abs(x-6.8)<.7)&(abs(z-24.95)<.3)
  side=np.clip((abs(y)-1.2)/.7,0,1);face=valid&~eye&(x>3.5)&(x<8)&(z>21.5)&(z<26)
  # A curved under-eye fold and a diagonal cheek-to-mouth crease; highlights sit above.
  cheek_z=24.00-.24*(x-5.5)-.18*(x-5.5)**2
  fold=np.exp(-((z-cheek_z)/.09)**2)*np.exp(-((x-5.9)/1.55)**4)*side*face
  ridge=np.exp(-((z-cheek_z-.18)/.14)**2)*np.exp(-((x-5.9)/1.55)**4)*side*face
  col*=1-.26*fold[...,None];col+=ridge[...,None]*np.array([.020,.017,.005])
  temple=np.exp(-((z-(25.25-.10*(x-5.5)))/.095)**2)*np.exp(-((x-5.4)/1.3)**4)*side*face;col*=1-.22*temple[...,None]
  # Encode the crease's slope into the actual portable normal map.
  delta=z-cheek_z;dhz=.055*fold*2*delta/(.09*.09);dhx=dhz*(.24+.36*(x-5.5));grad=np.stack([dhx,np.zeros_like(x),dhz],axis=-1)
  e1,e2=pts[1]-pts[0],pts[2]-pts[0];duv1,duv2=coords[1]-coords[0],coords[2]-coords[0];det=duv1[0]*duv2[1]-duv1[1]*duv2[0]
  if abs(det)>1e-9:
   tangent=(e1*duv2[1]-e2*duv1[1])/det;bitangent=(-e1*duv2[0]+e2*duv1[0])/det;tangent/=max(1e-9,np.linalg.norm(tangent));bitangent/=max(1e-9,np.linalg.norm(bitangent))
   normals=normalpixels[yy,xx,:3]*2-1;normals[...,0]-=np.sum(grad*tangent,axis=-1);normals[...,1]-=np.sum(grad*bitangent,axis=-1);normals/=np.maximum(1e-9,np.linalg.norm(normals,axis=-1))[...,None];normalpixels[yy,xx,:3]=normals*.5+.5
  # Outer lips stay green; red remains concentrated around the dental roots.
  redness=np.clip((col[...,0]-col[...,1]*1.8)/.085,0,1)*valid
  outer=redness*np.maximum(np.clip((z-23.13)/.28,0,1)*((z>23)&(z<23.7)),np.clip((19.95-z)/.25,0,1)*((z>19)&(z<20)))
  col=col*(1-.72*outer[...,None])+np.array([.095,.115,.030])*(.72*outer[...,None])
  pixels[yy,xx,:3]=np.clip(col,0,1);painted+=int(np.count_nonzero(fold>.05))
 for im,px in [(colour,pixels),(normal,normalpixels)]:im.pixels[:]=px.ravel();im.save();im.pack()
 return painted

def reference_pass(body,high,visible,dest):
 bpy.context.view_layer.update();painted=paint_folds(body,dest)
 for o in visible+[high]:
  inv=o.matrix_world.inverted()
  for v in o.data.vertices:v.co=inv@shape(o.matrix_world@v.co)
 # Broader yellowed teeth match the crowded irregular teeth in the close-up.
 for o in visible:
  if 'outward upper snag' not in o.name and 'outward lower snag' not in o.name:continue
  root=sum((v.co for v in list(o.data.vertices)[:-1]),Vector())/(len(o.data.vertices)-1)
  for v in list(o.data.vertices)[:-1]:v.co=root+(v.co-root)*1.28
 # The source pistol hangs barrel-down from the lowered hand.
 gun=next(o for o in visible if o.name=='Grot retained slugga');pivot=Vector((1.8,-8.6,11.8));rot=Matrix.Rotation(math.radians(31),4,'Y');inv=gun.matrix_world.inverted()
 for v in gun.data.vertices:v.co=inv@(pivot+(rot@((gun.matrix_world@v.co-pivot)*.90)))
 horn=next(m for m in bpy.data.materials if m.name=='Grot yellowed keratin')
 for n in horn.node_tree.nodes:
  if n.type=='TEX_IMAGE' and n.image:
   px=np.array(n.image.pixels[:],dtype=np.float32).reshape(-1,4);px[:,:3]=np.minimum(1,px[:,:3]*[1.24,1.32,1.5]);n.image.pixels[:]=px.ravel();n.image.save();n.image.pack()
 report={'triangle_count_changed':False,'head':'lowered onto shoulders, dome flattened, narrower bony nose, recessed eye sockets','body':'rib cage leans forward into the crouch; hips and feet retained','ears':'shortened sideways span and swept back','surface':'curved cheek folds, temple crease, green outer lips','teeth':'36 teeth retained, broadened roots and lighter ivory','pistol':'hangs downward from the same grip','painted_fold_pixels':painted}
 (dest/'reference-shape-pass.json').write_text(json.dumps(report,indent=2));return report

def update_contract(dest):
 def compact(z):return z if z<=13 else 13+(z-13)*.82 if z<21 else z-1.44
 upper=[];lower=[]
 for j in range(20):
  y=-1.97+3.94*j/19;upper.append(list(shape((7.2+2.75*.821*math.sqrt(max(0,1-(y/2.12)**2)),y,compact(24.50+.08*abs(y))))))
 for j in range(16):
  y=-1.82+3.64*j/15;lower.append(list(shape((6.4+2.4*math.sqrt(max(0,1-(y/1.9)**2)),y,compact(21.45+.65*(abs(y)/1.8)**1.5)))))
 samples=[shape((5.6,y,compact(z))) for y in [-1.25,-.65,0,.65,1.25] for z in [21.5,21.9,22.3,22.75,23.4,24.05]]
 data={'rear_mouth_wall':'part of unified skin; no separate lining or backing polygon','throat_samples':[[p.y,p.z] for p in samples],'upper_gum_roots':upper,'lower_gum_roots':lower,'teeth_direction':'outward, crowded and staggered along curved upper and lower gum arches','tooth_count':36,'reference_shape_pass_applied':True}
 (dest/'mouth-contract.json').write_text(json.dumps(data,indent=2))

if __name__=='__main__':
 import sys
 if '--contract-only' in sys.argv:
  update_contract(Path(__file__).resolve().parents[1]/'model-workbench/Grot-Sneak');sys.exit(0)
 root=Path(__file__).resolve().parents[1];dest=root/'model-workbench/Grot-Sneak';bpy.ops.wm.open_mainfile(filepath=str(dest/'Grot-Sneak.blend'));body=bpy.data.objects['Grot unified game body'];visible=[o for o in bpy.context.scene.objects if o.type=='MESH' and not o.hide_render]
 with bpy.data.libraries.load(str(dest/'Grot-Sneak-sculpt.blend'),link=False) as (src,target):target.objects=['Grot unified sculpt source']
 high=target.objects[0];bpy.context.scene.collection.objects.link(high);high.hide_render=True
 report=reference_pass(body,high,visible,dest)
 update_contract(dest)
 bpy.ops.file.pack_all();bpy.ops.wm.save_as_mainfile(filepath=str(dest/'Grot-Sneak-sculpt-reference.blend'));bpy.data.objects.remove(high,do_unlink=True);bpy.ops.wm.save_as_mainfile(filepath=str(dest/'Grot-Sneak.blend'))
 build=json.loads((dest/'build.json').read_text());build['source_sha256']=hashlib.sha256((dest/'Grot-Sneak.blend').read_bytes()).hexdigest();build['reference_shape_pass']=report;(dest/'build.json').write_text(json.dumps(build,indent=2));print(report)
