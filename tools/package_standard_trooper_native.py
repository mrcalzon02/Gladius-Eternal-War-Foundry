"""Finish engine-compatible atlases for the approved Penal Legion trooper."""
from pathlib import Path
import sys,json,hashlib
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/'tools/_resource_deps'))
from PIL import Image,ImageDraw,ImageFilter
O=R/'assets/standard-trooper-runtime';D=O/'2525618649/Data'
G=Path(r'C:\Program Files (x86)\Steam\steamapps\common\Warhammer 40000 Gladius - Relics of War\Data')
report=json.loads((O/'EXPORT.json').read_text(encoding='utf-8'))
def srgb(x):return round(255*(12.92*x if x<=.0031308 else 1.055*x**(1/2.4)-.055))
for role in ('Diffuse','Normal','SIC'):
 atlas=Image.new('RGBA',(1024,1024),(128,128,255,255) if role=='Normal' else (0,0,0,255))
 if role=='Diffuse':source=R/'model-workbench/Penal-Legion-Standard-Trooper/Standard-Trooper-Diffuse512.png'
 else:source=G/('Video/Textures/Units/AstraMilitarum/Guardsman'+role+'.dds')
 with Image.open(source) as native:atlas.paste(native.convert('RGBA'),(0,0))
 draw=ImageDraw.Draw(atlas)
 for index,color in enumerate(report['palette_linear_rgb']):
  rgb=tuple(map(srgb,color)) if role=='Diffuse' else ((128,128,255) if role=='Normal' else ((20,180,20)[index],0,0))
  draw.rectangle((512,int((2-index)*1024/3),1023,int((3-index)*1024/3)),fill=(*rgb,255))
 if role!='Diffuse':
  mask=Image.new('L',(1024,1024));mask_draw=ImageDraw.Draw(mask)
  for triangle in report['head_uv_triangles']:
   mask_draw.polygon([(round(u*1024),round(v*1024)) for u,v in triangle],fill=255)
  # DXT blocks and bilinear sampling reach beyond UV triangle edges. Padding
  # prevents the donor's team mask/normal map from leaking onto the bald scalp.
  mask=mask.filter(ImageFilter.MaxFilter(9))
  atlas.paste((128,128,255,255) if role=='Normal' else (20,0,0,255),(0,0,1024,1024),mask)
 path=D/('Video/Textures/Units/Foundry/PenalStandardTrooper'+role+'.dds');atlas.save(path,pixel_format='DXT5')
 assert path.read_bytes()[84:88]==b'DXT5'
 with Image.open(path) as check:check.load();assert check.size==(1024,1024)
manifest={'mod':'2525618649','unit':'AstraMilitarum/Guardsman','source_sha256':report['source_sha256'],'body_triangles':1090,'native_bones':28,'native_animations_retained':True,'gameplay_signature':report['gameplay_signature'],'files':{p.relative_to(O).as_posix():hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n') if p.suffix=='.xml' else p.read_bytes()).hexdigest() for p in D.rglob('*') if p.is_file()},'runtime_hash_format':'XML CRLF normalized to LF; other files raw SHA-256','live_combat_verified':False}
(O/'MANIFEST.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print('Packaged',len(manifest['files']),'runtime files directly for Penal Legion 2525618649.')
