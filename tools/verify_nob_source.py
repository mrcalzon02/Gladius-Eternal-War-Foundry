from pathlib import Path
import bpy,json
R=Path(__file__).resolve().parents[1];D=R/'model-workbench/Ork-Nob-Crab-Claw';bpy.ops.wm.open_mainfile(filepath=str(D/'Ork-Nob-Crab-Claw.blend'))
images=[]
for im in bpy.data.images:
 if im.type=='IMAGE' and im.users:
  loaded=bool(len(im.pixels));images.append({'name':im.name,'packed':bool(im.packed_file),'loaded':loaded})
hats=[o for o in bpy.context.scene.objects if o.type=='MESH' and ('hat' in o.name.lower() or 'crown' in o.name.lower())]
r={'images':images,'actions':len(bpy.data.actions),'hat_parts':[o.name for o in hats],'hat_weights_all_head':all(len(o.vertex_groups)==1 and o.vertex_groups[0].name=='Head' for o in hats),'failures':[]}
if not all(i['packed'] and i['loaded'] for i in images):r['failures'].append('Unpacked or unreadable source images')
if not r['hat_weights_all_head']:r['failures'].append('Hat head weight mismatch')
(D/'source-verification.json').write_text(json.dumps(r,indent=2));print(r)
