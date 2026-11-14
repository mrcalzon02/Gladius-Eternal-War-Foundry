"""Finish the local Gladius mod package without changing installed files."""
from pathlib import Path
import sys,json,hashlib,re,xml.etree.ElementTree as ET
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'tools/_resource_deps'))
from PIL import Image
OUT=R/'game-ready/Foundry Veteran Sergeant';DATA=OUT/'Data'
GAME=Path(r'C:\Program Files (x86)\Steam\steamapps\common\Warhammer 40000 Gladius - Relics of War\Data')
WORKSHOP=GAME.parents[2]/'workshop/content/489630/2525618649/Data'
for role in ('Diffuse','Normal','SIC'):
    if role=='Normal':atlas=Image.new('RGBA',(1024,1024),(128,128,255,255))
    else:atlas=Image.open(OUT/('kit-'+role+'.png')).convert('RGBA')
    native=Image.open(GAME/('Video/Textures/Units/AstraMilitarum/Guardsman'+role+'.dds')).convert('RGBA')
    assert native.size==(512,512)
    atlas.paste(native,(0,0));dest=DATA/('Video/Textures/Units/Foundry/VeteranSergeant'+role+'.dds');atlas.save(dest)
    atlas.save(OUT/('atlas-'+role+'.png'))
    with Image.open(dest) as loaded:assert loaded.size==(1024,1024)
material=ET.Element('material');textures=ET.SubElement(material,'textures')
for role in ('Diffuse','Normal','SIC'):ET.SubElement(textures,'texture',name='Units/Foundry/VeteranSergeant'+role)
ET.SubElement(textures,'texture',name='ShadowMapColor')
ET.indent(material);ET.ElementTree(material).write(DATA/'Video/Materials/Units/Foundry/VeteranSergeant.xml',encoding='utf-8',xml_declaration=True)
source=R/'2525618649/Data/World/Units/AstraMilitarum/Sargent.xml'
if not source.exists():source=WORKSHOP/'World/Units/AstraMilitarum/Sargent.xml'
tree=ET.parse(source);unit=tree.getroot();model=unit.find('model/unit')
model.set('mesh','Units/Foundry/VeteranSergeant');model.set('material','Units/Foundry/VeteranSergeant');model.set('idleAnimation','Units/Foundry/VeteranSergeantIdle');model.set('idleAnimationCount','1')
sword=unit.find("weapons/weapon[@name='Chainsword']/model/weapon")
sword.set('mesh','Weapons/Foundry/VeteranChainsword');sword.set('bone','LeftHandBone')
pistol=unit.find("weapons/weapon[@name='BoltPistol']/model/projectileWeapon")
pistol.set('mesh','Weapons/Foundry/VeteranBoltPistol');pistol.set('bone','RightHandBone');pistol.set('fireInterval','0.25')
attack=unit.find('actions/attack/model/action');attack.set('animation','Units/Foundry/VeteranSergeantRanged');attack.set('beginFire',str(16/24));attack.set('endFire','1.18')
attack.set('meleeAnimation','Units/Foundry/VeteranSergeantMelee');attack.set('meleeBeginSwing',str(16/24));attack.set('meleeEndSwing',str(28/24))
unit.find('actions/move/model/action').set('animation','Units/Foundry/VeteranSergeantMove')
# Compare gameplay sections before writing the visual override.
original=ET.parse(source).getroot()
for section in ('modifiers','strategyModifiers','traits','group'):
    assert ET.tostring(unit.find(section))==ET.tostring(original.find(section)),section
raw=source.read_text(encoding='utf-8')
def replace_element(pattern,values):
    global raw
    match=re.search(pattern,raw,re.S)
    if match is None:raise ValueError('Source unit element not found: '+pattern)
    element=match.group(0)
    for name,value in values.items():
        attr=re.compile(r'\b'+re.escape(name)+r'="[^"]*"')
        if attr.search(element):element=attr.sub(lambda _:name+'="'+value+'"',element,count=1)
        else:element=element[:-2]+'\n\t\t\t\t\t\t'+name+'="'+value+'"/>'
    raw=raw[:match.start()]+element+raw[match.end():]
replace_element(r'<unit\s+mesh="[^"]*".*?/>',{k:model.get(k) for k in ('mesh','material','idleAnimation','idleAnimationCount')})
replace_element(r'<weapon\s+mesh="Weapons/(?:AstraMilitarum/SargentHipChainsword|Foundry/VeteranChainsword)".*?/>',{k:sword.get(k) for k in ('mesh','bone')})
replace_element(r'<projectileWeapon\s+mesh="Weapons/(?:AstraMilitarum/LordCommissarBoltPistol|Foundry/VeteranBoltPistol)".*?/>',{k:pistol.get(k) for k in ('mesh','bone','fireInterval')})
replace_element(r'<action\s+animation="Units/(?:AstraMilitarum/GuardsmanAttack|Foundry/VeteranSergeantRanged)".*?/>',dict(attack.attrib))
move=unit.find('actions/move/model/action')
replace_element(r'<action\s+animation="Units/(?:AstraMilitarum/GuardsmanMove|Foundry/VeteranSergeantMove)".*?/>',{'animation':move.get('animation')})
def signature(root):return [(n.tag,sorted(n.attrib.items()),(n.text or '').strip()) for n in root.iter()]
assert signature(ET.fromstring(raw))==signature(unit)
(DATA/'World/Units/AstraMilitarum/Sargent.xml').write_text(raw,encoding='utf-8')
(OUT/'README.txt').write_text('''FOUNDRY VETERAN SERGEANT

Local visual override for Penal Legion's Astra Militarum Sargent (Workshop 2525618649).
Load after Penal Legion. Existing recruitment, costs, stats, traits and weapon rules
are retained. Mesh, textures, attachment placement, visual firing cadence and
idle/move/ranged/melee animation references are replaced.

Includes the user-edited backpack, cigar with emissive red tip, pistol fire and
the corrected stepping chainsword lunge. Original death and grenade animations
remain compatible references to the installed Guardsman assets.

Disable this local mod to restore the Workshop appearance. No Workshop file or
base-game file is overwritten by installation. No SteamID/publication is assigned.
''',encoding='utf-8')
manifest=dict(name='Foundry Veteran Sergeant',depends_on_workshop='2525618649',
              unit='AstraMilitarum/Sargent',original_unit_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
              gameplay_sections_preserved=True,files={p.relative_to(OUT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in DATA.rglob('*') if p.is_file()})
(OUT/'MANIFEST.json').write_text(json.dumps(manifest,indent=2))
print('PACKAGED',len(manifest['files']),'game files',OUT)
