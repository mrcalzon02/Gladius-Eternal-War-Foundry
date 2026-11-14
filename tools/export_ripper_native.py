"""Build the low-triangle custom-rig ripper into a local Gladius override package."""
from pathlib import Path
import bpy,bmesh,ast,struct,json,math,hashlib,sys,os,tempfile,xml.etree.ElementTree as ET
from mathutils import Vector,Matrix
R=Path(__file__).resolve().parents[1];D=Path(os.environ.get('RIPPER_STAGE_DIR',R/'model-workbench/Ripper/low-poly'));OUT=Path(os.environ.get('RIPPER_NATIVE_DIR',R/'game-ready/Foundry Ripper'));DATA=OUT/'Data'
(D/'export-temp').mkdir(exist_ok=True);tempfile.tempdir=str(D/'export-temp')
GAME=Path('C:/Program Files (x86)/Steam/steamapps/common/Warhammer 40000 Gladius - Relics of War/Data')
for sub in ['Video/Meshes/Units/Foundry','Video/Animations/Units/Foundry','Video/Materials/Units/Foundry','Video/Textures/Units/Foundry','World/Units/Tyranids']:(DATA/sub).mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(R/'tools'));from native_gladius import read_mesh,read_animation
bpy.ops.wm.open_mainfile(filepath=str(D/'Ripper-LowPoly.blend'),use_scripts=False);scene=bpy.context.scene;rig=bpy.data.objects['Ripper Rig'];body=bpy.data.objects['Ripper']
bone_names=[b.name for b in rig.data.bones];binds={b.name:b.matrix_local@Matrix.Rotation(math.pi/2,4,'Z') for b in rig.data.bones}
# Reuse the repository's already round-trip-checked native binary writers, without its asset-specific side effects.
tree=ast.parse((R/'tools/export_sergeant_game_assets.py').read_text())
for node in tree.body:
 if isinstance(node,ast.FunctionDef) and node.name in {'template_header','write_mesh','mesh_records'}:exec(compile(ast.Module(body=[node],type_ignores=[]),'<shared native writer>','exec'),globals())
template=template_header((GAME/'Video/Meshes/Units/AstraMilitarum/Guardsman.msh').read_bytes())
layout=[('vertexPosition',3),('vertexBoneWeights',4),('vertexBoneIndices',4),('vertexTextureCoordinate',2),('vertexNormal',3),('vertexTangent',4)]
rig.animation_data.action=None
for p in rig.pose.bones:p.matrix_basis.identity()
scene.frame_set(1);bpy.context.view_layer.update()
records=mesh_records(body,bone_names);info=write_mesh(DATA/'Video/Meshes/Units/Foundry/Ripper.msh',bone_names,binds,records)
assert info['triangles']<=450,info
max_error=0;clips={}
def activate(action):
 rig.animation_data.action=None
 for p in rig.pose.bones:p.matrix_basis.identity()
 rig.animation_data.action=action;rig.animation_data.use_nla=False
for suffix in ['Idle','Move','Melee','Die']:
 action=bpy.data.actions['Ripper '+suffix];activate(action);start,end=map(int,action.frame_range);samples=[]
 for frame in range(start,end+1):
  scene.frame_set(frame);bpy.context.view_layer.update();samples.append({n:rig.pose.bones[n].matrix.copy() for n in bone_names})
 clips[suffix]=samples
def mix(a,b,t):
 al,ar,asc=a.decompose();bl,br,bsc=b.decompose();return Matrix.LocRotScale(al.lerp(bl,t),ar.slerp(br,t),asc.lerp(bsc,t))
clips['MoveBegin']=[{n:mix(clips['Idle'][0][n],clips['Move'][0][n],i/8) for n in bone_names} for i in range(9)]
clips['MoveEnd']=[{n:mix(clips['Move'][0][n],clips['Idle'][0][n],i/8) for n in bone_names} for i in range(9)]
for suffix,samples in clips.items():
 raw=bytearray(b'ANM1.0\0'+struct.pack('<BII',len(bone_names),len(samples),24))
 for name in bone_names:
  raw+=name.encode()+b'\0';rest=rig.data.bones[name].matrix_local;last=None
  for matrices in samples:
   pose=matrices[name];linear=pose.to_3x3()@rest.to_3x3().inverted();scale=Vector([linear.row[i].length for i in range(3)])
   rotation=Matrix([[linear[i][j]/scale[i] for j in range(3)] for i in range(3)]).to_quaternion().normalized()
   if last and rotation.dot(last)<0:rotation.negate()
   last=rotation.copy();position=pose.translation-rest.translation;reconstructed=Matrix.Diagonal(scale)@rotation.to_matrix()
   max_error=max(max_error,max(abs(linear[i][j]-reconstructed[i][j]) for i in range(3) for j in range(3)))
   raw+=struct.pack('<10f',*position,rotation.x,rotation.y,rotation.z,rotation.w,*scale)

 parsed=read_animation(raw);assert parsed['frames']==len(samples)
 (DATA/f'Video/Animations/Units/Foundry/Ripper{suffix}.anm').write_bytes(raw)
assert max_error<.0001,max_error
source=Path('C:/Program Files (x86)/Steam/steamapps/workshop/content/489630/2525618729/Data/World/Units/Tyranids/Ripperswarm.xml')
original=ET.parse(source).getroot();unit=ET.parse(source).getroot();model=unit.find('model/unit')
model.set('mesh','Units/Foundry/Ripper');model.set('material','Units/Foundry/Ripper');model.set('scale','1 1 1');model.set('idleAnimation','Units/Foundry/RipperIdle');model.set('idleAnimationCount','1');model.set('bloodBone','BloodBone')
attack=unit.find('actions/attack/model/action');attack.set('chargeAnimation','Units/Foundry/RipperMove');attack.set('meleeAnimation','Units/Foundry/RipperMelee')
die=unit.find('actions/die/model/action');die.set('animation','Units/Foundry/RipperDie');die.set('animationCount','1')
unit.find('actions/move/model/action').set('animation','Units/Foundry/RipperMove')
for section in ['group','weapons','modifiers','strategyModifiers','traits']:
 assert ET.tostring(unit.find(section))==ET.tostring(original.find(section)),section
ET.indent(unit);ET.ElementTree(unit).write(DATA/'World/Units/Tyranids/Ripperswarm.xml',encoding='utf-8',xml_declaration=True)
material=ET.Element('material');textures=ET.SubElement(material,'textures')
for role in ['Diffuse','Normal','SIC']:ET.SubElement(textures,'texture',name='Units/Foundry/Ripper'+role)
ET.SubElement(textures,'texture',name='ShadowMapColor');ET.indent(material);ET.ElementTree(material).write(DATA/'Video/Materials/Units/Foundry/Ripper.xml',encoding='utf-8',xml_declaration=True)
activate(None);scene.frame_set(1);bpy.context.view_layer.update();bpy.ops.object.select_all(action='DESELECT');body.select_set(True);rig.select_set(True);bpy.context.view_layer.objects.active=rig
opts={'filepath':str(D/'Ripper-LowPoly.glb'),'use_selection':True,'export_format':'GLB','export_animations':True}
props=bpy.ops.export_scene.gltf.get_rna_type().properties
if 'export_animation_mode' in props:opts['export_animation_mode']='ACTIONS'
bpy.ops.export_scene.gltf(**opts)
report={'mesh':info,'animation_frames':{k:len(v) for k,v in clips.items()},'max_animation_matrix_reconstruction_error':max_error,'source_sha256':hashlib.sha256((D/'Ripper-LowPoly.blend').read_bytes()).hexdigest(),'workshop_definition_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'group_and_gameplay_preserved':True,'installed':False,'in_game_verified':False}
(OUT/'EXPORT.json').write_text(json.dumps(report,indent=2));print('RIPPER_NATIVE_BUILT',json.dumps(report))
