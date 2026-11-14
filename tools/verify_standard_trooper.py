from pathlib import Path
import bpy,json,hashlib
R=Path(__file__).resolve().parents[1];O=R/'model-workbench/Penal-Legion-Standard-Trooper';p=O/'verification.json';r=json.loads(p.read_text());bpy.ops.wm.open_mainfile(filepath=str(O/'Standard-Trooper.blend'));head=bpy.data.objects['Penal Legion bald Guardsman head'];im=next(n.image for n in head.data.materials[0].node_tree.nodes if n.type=='TEX_IMAGE' and n.image);pixel=im.pixels[0]
assert tuple(im.size)==(512,512) and im.packed_file and im.has_data
assert r['geometry_unchanged'] and r['body_uv_unchanged'] and r['triangles']==1293
assert all(x['degenerate_faces']==0 for x in r['meshes'])
assert hashlib.sha256((R/'model-workbench/Penal-Legion-Trooper/Penal-Legion-Trooper.blend').read_bytes()).hexdigest()==r['source_user_edit_sha256']
r['source_reopened']={'atlas_loaded':im.has_data,'atlas_packed':bool(im.packed_file),'atlas_size':list(im.size),'rig_present':'Guardsman_rig' in bpy.data.objects,'actions':len(bpy.data.actions)}
r['visual_review']='Viewed source head and reimported static preview; minor UV cleanup accepted within user-approved geometry. Static preview shader differences are documented; game integration remains unvalidated.';p.write_text(json.dumps(r,indent=2));print(json.dumps(r['source_reopened']))
