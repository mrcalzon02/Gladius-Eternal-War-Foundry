"""Export the approved standard trooper into the existing Penal Legion package.

The approved blend is read-only. Native Guardsman skeleton/animations and all
gameplay are retained. No standalone mod is created.
"""
from pathlib import Path
import bpy,bmesh,struct,json,math,hashlib,sys,xml.etree.ElementTree as E,re
from mathutils import Matrix
R=Path(__file__).resolve().parents[1]
SOURCE=R/'model-workbench/Penal-Legion-Standard-Trooper/Standard-Trooper.blend'
OUT=R/'assets/standard-trooper-runtime'
D=OUT/'2525618649/Data'
G=Path(r'C:\Program Files (x86)\Steam\steamapps\common\Warhammer 40000 Gladius - Relics of War\Data')
B=Path(r'C:\GITS\Gladius-Eternal-War-Foundry/2525618649/Data')
sys.path.insert(0,str(R/'tools'))
from native_gladius import read_mesh,read_animation
for sub in ('Video/Meshes/Units/Foundry','Video/Textures/Units/Foundry','Video/Materials/Units/Foundry','World/Units/AstraMilitarum'):
 (D/sub).mkdir(parents=True,exist_ok=True)
source_sha=hashlib.sha256(SOURCE.read_bytes()).hexdigest()
bpy.ops.wm.open_mainfile(filepath=str(SOURCE))
if bpy.context.object and bpy.context.object.mode!='OBJECT':bpy.ops.object.mode_set(mode='OBJECT')
rig=bpy.data.objects['Guardsman_rig'];rig.data.pose_position='REST'
names=[b.name for b in sorted((b for b in rig.data.bones if not b.get('gladius_pivot')),key=lambda b:b['gladius_source_index'])]
native=(G/'Video/Meshes/Units/AstraMilitarum/Guardsman.msh').read_bytes()
assert names==read_mesh(native)['bones']
objects=sorted((o for o in bpy.context.scene.objects if o.type=='MESH' and any(m.type=='ARMATURE' and m.object==rig for m in o.modifiers)),key=lambda o:o.name)
assert len(objects)==21,len(objects)
native_atlas={'Penal Legion bald Guardsman head','Low poly ragged tunic','Right low poly cloth sleeve','Left low poly cloth sleeve','Original Guardsman trousers boots and rifle hands'}
palette={'Old brown belt and boots':0,'Dull knife steel':1,'Faded repairs':2}
records=[];head_uv=[];object_ranges={};degenerate=0
for obj in objects:
 assert all(abs(obj.matrix_world[r][c]-(1 if r==c else 0))<1e-6 for r in range(4) for c in range(4)),obj.name
 me=obj.data
 if any(len(p.vertices)>4 for p in me.polygons):
  bm=bmesh.new();bm.from_mesh(me);bmesh.ops.triangulate(bm,faces=[f for f in bm.faces if len(f.verts)>4]);bm.to_mesh(me);bm.free();me.update()
 me.calc_loop_triangles();me.calc_tangents(uvmap=me.uv_layers.active.name)
 start=len(records)
 for tri in me.loop_triangles:
  if tri.area<1e-7:
   degenerate+=1
   continue
  material=me.materials[me.polygons[tri.polygon_index].material_index]
  face_uv=[]
  for li in tri.loops:
   loop=me.loops[li];v=me.vertices[loop.vertex_index];uv=me.uv_layers.active.data[li].uv
   if obj.name in native_atlas and material.name not in palette:
    u,w=uv.x*.5,.5+uv.y*.5
   else:
    index=palette[material.name];u,w=.75,(index+.5)/3
   face_uv.append([u,1-w])
   influences=[(names.index(obj.vertex_groups[g.group].name),g.weight) for g in v.groups if g.weight>1e-5 and obj.vertex_groups[g.group].name in names]
   influences.sort(key=lambda i:-i[1]);assert 0<len(influences)<=4,(obj.name,v.index,influences)
   total=sum(w for _,w in influences);weights=[w/total for _,w in influences]+[0]*(4-len(influences));indices=[i for i,_ in influences]+[0]*(4-len(influences))
   records.append((*v.co,*weights,*indices,u,1-w,*loop.normal,*loop.tangent,loop.bitangent_sign))
  if obj.name=='Penal Legion bald Guardsman head':head_uv.append(face_uv)
 object_ranges[obj.name]=[start,len(records)]
assert degenerate==7 and len(records)//3==1090,(degenerate,len(records)//3)
raw=bytearray(b'MSH1.0\0'+bytes([len(names)]))
for name in names:
 a=rig.data.bones[name]['gladius_source_bind'];matrix=Matrix([a[:4],a[4:8],a[8:12],a[12:16]])
 raw+=name.encode()+b'\0'+struct.pack('<16f',*(matrix[r][c] for c in range(4) for r in range(4)))
at=8
for _ in range(native[7]):at=native.index(0,at)+65
metadata=bytearray(native[at:at+111]);lo=[min(v[i] for v in records) for i in range(3)];hi=[max(v[i] for v in records) for i in range(3)]
struct.pack_into('<3f',metadata,5,*lo);struct.pack_into('<3f',metadata,21,*hi);struct.pack_into('<3f',metadata,91,*[(a+b)/2 for a,b in zip(lo,hi)]);struct.pack_into('<f',metadata,107,math.sqrt(sum((a-b)**2 for a,b in zip(lo,hi)))/2)
raw+=metadata
layout=[('vertexPosition',3),('vertexBoneWeights',4),('vertexBoneIndices',4),('vertexTextureCoordinate',2),('vertexNormal',3),('vertexTangent',4)]
raw+=bytes([len(layout)])
for name,width in layout:raw+=name.encode()+b'\0'+bytes([width])
raw+=struct.pack('<I',len(records)*20)
for record in records:
 assert all(math.isfinite(v) for v in record)
 raw+=struct.pack('<20f',*record)
raw+=struct.pack('<I',0)
mesh=D/'Video/Meshes/Units/Foundry/PenalStandardTrooper.msh';mesh.write_bytes(raw)
parsed=read_mesh(bytes(raw));assert parsed['triangles']==1090 and len(parsed['bones'])==28
mat=E.Element('material');textures=E.SubElement(mat,'textures')
for role in ('Diffuse','Normal','SIC'):E.SubElement(textures,'texture',name='Units/Foundry/PenalStandardTrooper'+role)
E.SubElement(textures,'texture',name='ShadowMapColor');E.indent(mat)
E.ElementTree(mat).write(D/'Video/Materials/Units/Foundry/PenalStandardTrooper.xml',encoding='utf-8',xml_declaration=True)
unit_source=B/'World/Units/AstraMilitarum/Guardsman.xml';unit=unit_source.read_text(encoding='utf-8-sig')
unit=unit.replace('mesh="Units/AstraMilitarum/Guardsman"','mesh="Units/Foundry/PenalStandardTrooper"',1).replace('material="Units/AstraMilitarum/Guardsman"','material="Units/Foundry/PenalStandardTrooper"',1)
# The accepted model carries a belt knife and the native lasgun. Hide the old
# chainsword attachment used as a bayonet visual, preserving its gameplay rule.
unit,n=re.subn(r'<weapon\s+mesh="Weapons/SpaceMarines/Chainsword"\s+material="Weapons/SpaceMarines/Chainsword"\s+bone="LeftHandBone"\s*/>','<weapon/>',unit);assert n==1
def gameplay(root):
 return [root.tag,sorted(root.attrib.items()),(root.text or '').strip(),[gameplay(c) for c in root if c.tag!='model']]
assert gameplay(E.fromstring(unit))==gameplay(E.parse(unit_source).getroot())
(D/'World/Units/AstraMilitarum/Guardsman.xml').write_text(unit,encoding='utf-8')
report={'source_sha256':source_sha,'source':str(SOURCE),'body':parsed,'source_assembled_triangle_count':1293,'zero_area_triangulation_artifacts_omitted':degenerate,'assembled_triangles_with_native_lasgun':1286,'object_ranges':object_ranges,'head_uv_triangles':head_uv,'palette_linear_rgb':[[.034,.024,.018],[.24,.26,.25],[.25,.205,.12]],'gameplay_signature':hashlib.sha256(json.dumps(gameplay(E.fromstring(unit)),separators=(',',':')).encode()).hexdigest(),'native_animations_retained':True,'source_unmodified':hashlib.sha256(SOURCE.read_bytes()).hexdigest()==source_sha,'surface_plan':'Approved native-size head/cloth atlas retained in a 512-square tile; constant leather, steel and patch swatches; head normal and team masks neutralized; native cloth normal and SIC retained.'}
(OUT/'EXPORT.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
assert report['source_unmodified']
print('EXPORTED_PENAL_STANDARD_TROOPER',parsed['triangles'],'triangles;',len(names),'native bones; gameplay preserved; source unchanged')
