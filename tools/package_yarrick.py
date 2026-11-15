"""Create runtime DDS atlases for Yarrick's Penal Legion contribution."""
from pathlib import Path
import sys,xml.etree.ElementTree as E,json,hashlib,zipfile
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'tools/_resource_deps'))
from PIL import Image,ImageDraw
G=Path(r'C:\Program Files (x86)\Steam\steamapps\common\Warhammer 40000 Gladius - Relics of War\Data')
O=R/'assets/yarrick-build';D=O/'Data'
colors=[(173,22,29),(218,41,44),(60,66,72),(165,175,185),(185,142,72),(255,12,6)]
for role in ('Diffuse','Normal','SIC'):
 im=Image.new('RGBA',(1024,1024),(128,128,255,255) if role=='Normal' else (0,0,0,255));draw=ImageDraw.Draw(im)
 for i,color in enumerate(colors):
  value=(*color,255) if role=='Diffuse' else ((128,128,255,255) if role=='Normal' else (80,255 if i==5 else 0,0,255))
  draw.rectangle((512,int((5-i)*1024/6),1023,int((6-i)*1024/6)),fill=value)
 native=Image.open(G/('Video/Textures/Units/AstraMilitarum/LordCommissar'+role+'.dds')).convert('RGBA');assert native.size==(512,512);im.paste(native,(0,0))
 path=D/('Video/Textures/Units/Foundry/Yarrick'+role+'.dds');path.parent.mkdir(parents=True,exist_ok=True);im.save(path,pixel_format='DXT5')
for path in ('Units/Foundry/Yarrick','Weapons/Foundry/YarrickKit'):
 mat=E.Element('material');tex=E.SubElement(mat,'textures')
 for role in ('Diffuse','Normal','SIC'):E.SubElement(tex,'texture',name='Units/Foundry/Yarrick'+role)
 E.SubElement(tex,'texture',name='ShadowMapColor');p=D/('Video/Materials/'+path+'.xml');p.parent.mkdir(parents=True,exist_ok=True);E.indent(mat);E.ElementTree(mat).write(p,encoding='utf-8',xml_declaration=True)
manifest={'name':'Yarrick contribution to Penal Legion','workshop_id':'2525618649','unit':'AstraMilitarum/CommissarYarrick','status':'Native assets and rules validated locally; live combat verification pending','files':{p.relative_to(O).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in D.rglob('*') if p.is_file()}}
(O/'MANIFEST.json').write_text(json.dumps(manifest,indent=2))
print('Prepared',len(manifest['files']),'runtime files for existing Penal Legion mod:',O)
