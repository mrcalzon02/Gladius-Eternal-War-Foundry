"""Compare the current native officer with the actual game Guardsman."""
from pathlib import Path
from types import SimpleNamespace
import bpy,sys,json,os,hashlib,importlib.util,math
from mathutils import Vector
R=Path(__file__).resolve().parents[1];A=R/'model-workbench/Imperial-Officer/animation-production';D=R/'assets/imperial-officer-animated/Data';G=Path(os.environ.get('GLADIUS_DATA',r'C:/Program Files (x86)/Steam/steamapps/common/Warhammer 40000 Gladius - Relics of War/Data'))
q=json.loads((A/'animation-verification.json').read_text());assert q['status']=='passed';review=A/'Officer-Native-Animation-Review.blend';assert hashlib.sha256(review.read_bytes()).hexdigest()==q['native_review_blend_sha256']
spec=importlib.util.spec_from_file_location('officer_baseline_comparison',R/'references/import_gladius.py');g=importlib.util.module_from_spec(spec);sys.modules[spec.name]=g;spec.loader.exec_module(g)
bpy.ops.wm.open_mainfile(filepath=str(review));s=bpy.context.scene;officer=bpy.data.objects['ImperialOfficerGuardsman_rig'];body=bpy.data.objects['ImperialOfficerGuardsman'];cam=s.camera;s.cycles.samples=8
def root(ob):
    while ob.parent:ob=ob.parent
    return ob
oroot=root(officer);before=set(bpy.data.objects);g._import_animation_specs=lambda *a,**k:({},[],0.);oldroots=g._source_roots_for_xml;g._source_roots_for_xml=lambda p,prefs:list(dict.fromkeys(oldroots(p,prefs)+[str(G)]));messages=[]
op=SimpleNamespace(filepath=str(G/'World/Units/AstraMilitarum/Guardsman.xml'),frame_viewport=False,scale_preset='FULL',report=lambda *args:messages.append(str(args)));assert g.ImportGladiusUnitFromXml.execute(op,bpy.context)=={'FINISHED'},messages
guard=bpy.data.objects['Guardsman_rig'];groot=root(guard);guard_objects=set(bpy.data.objects)-before
for ob in guard_objects:
    if 'Bounding' in ob.name:ob.hide_render=True
idle,_=g._load_anm_to_rig(str(G/'Video/Animations/Units/AstraMilitarum/GuardsmanIdle0.anm'),guard,unit_name='Baseline',anim_type='Idle0');g._set_direct_animation(guard,idle)
def activate(suffix,t):
    a,_=g._load_anm_to_rig(str(D/('Video/Animations/Units/Foundry/ImperialOfficerGuardsman'+suffix+'.anm')),officer,unit_name='Officer comparison',anim_type=suffix);g._set_direct_animation(officer,a);frame=t*60;s.frame_set(math.floor(frame),subframe=frame%1);bpy.context.view_layer.update()
def render(name,loc,target,scale,res=(1100,850),gap=26):
    cam.location=loc;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale;right=cam.rotation_euler.to_matrix()@Vector((1,0,0));oroot.location=right*gap;groot.location=-right*gap;s.render.resolution_x,s.render.resolution_y=res;s.render.filepath=str(A/'native-previews'/(name+'.png'));bpy.ops.render.render(write_still=True)
activate('Idle0',0)
for name,loc in [('front',(200,0,42)),('right',(0,-200,42)),('left',(0,200,42)),('rear',(-200,0,42)),('overview',(180,-90,100))]:render('comparison-'+name,loc,(0,0,34),116)
render('comparison-gameplay',(180,-110,140),(0,0,34),460,(768,480),27)
render('comparison-close',(160,-55,77),(0,0,58),45,(1100,850),12)
for ob in guard_objects:
    if ob.type=='MESH':ob.hide_render=True
oroot.location=(0,0,0);activate('Attack',.45)
for name,target,scale in [('pistol-upright',(12,-8,48),53),('pistol-grip',(22,-13,51),24)]:
    cam.location=Vector(target)+Vector((4,-150,22));cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale;s.render.resolution_x=1000;s.render.resolution_y=700;s.render.filepath=str(A/'native-previews'/(name+'.png'));bpy.ops.render.render(write_still=True)
print('OFFICER_BASELINE_AND_PISTOL_COMPARISON_RENDERED',flush=True)
