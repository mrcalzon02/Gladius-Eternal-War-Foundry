"""Import the installed commissar as Yarrick's editable, animated donor."""
from pathlib import Path
import bpy, json
R=Path(__file__).resolve().parents[1]
D=R/'model-workbench/Yarrick';D.mkdir(exist_ok=True)
scope={'__file__':str(R/'tools/prepare_model_starters.py')}
exec((R/'tools/prepare_model_starters.py').read_text().split('OUT.mkdir(exist_ok=True)')[0],scope)
bpy.ops.wm.read_factory_settings(use_empty=True)
source=scope['GAME']/'World/Units/AstraMilitarum/LordCommissar.xml'
xml,files=scope['collect'](source,D)
op=scope['SimpleNamespace'](filepath=str(xml),frame_viewport=False,scale_preset='FULL',report=lambda *x:print(x))
assert scope['imp'].ImportGladiusUnitFromXml.execute(op,bpy.context)=={'FINISHED'}
bpy.context.scene.world=bpy.data.worlds.new('Yarrick studio')
scope['setup_view']()
bpy.context.view_layer.update()
report={'files':files,'objects':{},'bones':{}}
for o in bpy.context.scene.objects:
 if o.type=='MESH':
  report['objects'][o.name]={'bounds':[[min((o.matrix_world@v.co)[i] for v in o.data.vertices) for i in range(3)],[max((o.matrix_world@v.co)[i] for v in o.data.vertices) for i in range(3)]]}
  if o.name=='LordCommissar':
   for group in o.vertex_groups:
    vs=[o.matrix_world@v.co for v in o.data.vertices if any(w.group==group.index and w.weight>.5 for w in v.groups)]
    if vs:report['bones'][group.name]={'bounds':[[min(p[i] for p in vs) for i in range(3)],[max(p[i] for p in vs) for i in range(3)]]}
bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=str(D/'Yarrick-donor.blend'))
(D/'donor.json').write_text(json.dumps(report,indent=2))
bpy.context.scene.render.filepath=str(D/'donor.png')
bpy.ops.render.render(write_still=True)
