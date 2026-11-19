"""Check Yarrick's gameplay contracts, references and native binary assets."""
from pathlib import Path
import xml.etree.ElementTree as E,json,struct,sys
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R/'tools'))
from native_gladius import read_mesh,read_animation
from audit_resource_integrity import audit
from audit_weapon_attachments import audit as attachments
G=Path(r'C:\Program Files (x86)\Steam\steamapps\common\Warhammer 40000 Gladius - Relics of War\Data')
O=R/'assets/yarrick-build';D=O/'Data'
u=E.parse(D/'World/Units/AstraMilitarum/CommissarYarrick.xml').getroot()
actions={a.get('name'):a for a in u.findall('actions/*') if a.get('name')}
def signature(node):return [(n.tag,sorted(n.attrib.items())) for n in node.iter()]
morale=actions['Foundry/OldManOfArmageddon'];assert morale.get('rank')=='0';assert morale.find('.//morale').get('addMin')=='9'
assert u.find("weapons/weapon[@name='BoltPistol']") is not None
assert u.find("weapons/weapon[@name='PowerKlaw']") is not None
assert signature(E.parse(D/'World/Weapons/Foundry/BaleEye.xml').getroot())==signature(E.parse(G/'World/Weapons/Lasgun.xml').getroot())
strike=actions['Foundry/TargetedBasiliskStrike'];assert len(strike.findall('.//weaponDamage'))==2
shell=E.parse(D/'World/Weapons/Foundry/YarrickEarthshaker.xml').getroot();original=E.parse(G/'World/Weapons/EarthshakerCannon.xml').getroot()
for stat in ('attacks','rangedArmorPenetration','rangedDamage','strengthDamage'):assert shell.find('.//'+stat).attrib==original.find('.//'+stat).attrib
assert signature(shell.find('traits'))==signature(original.find('traits'))
assert shell.get('attributesModifiedByUnit')=='0';assert shell.find('.//accuracy').attrib=={'min':'6','max':'6'}
boost=actions['Foundry/ThisEndsHere'];assert boost.get('cooldown')=='5';assert boost.find('.//addTrait').get('duration')=='2'
assert E.parse(D/'World/Traits/Foundry/ThisEndsHere.xml').find('.//damage').attrib=={'mul':'1.0'}
assert actions['Foundry/ArmageddonCalls'].find('.//addUnit').get('name')=='AstraMilitarum/Guardsman'
assert actions['Foundry/ArmageddonCallsArmour'].find('.//addUnit').get('name')=='AstraMilitarum/LemanRussBattleTank'
assert actions['Foundry/ArmageddonCallsArmour'].find('.//removeTrait').get('name')=='Foundry/ArmourPending'
assert actions['Foundry/ArmageddonCallsArmour'].get('consumedActionPoints')=='0'
from yarrick_call_progression import RANKS, CALL
calls=[a for name,a in actions.items() if name.startswith(CALL) and not name.startswith(CALL+'Armour')]
assert len(calls)==1
assert calls[0].get('rank')=='-1' and calls[0].get('rankMax')=='4'
assert calls[0].get('cooldown')=='10'
assert not any(a.find('.//conditions/unit/level') is not None for a in actions.values())
import unittest
suite=unittest.defaultTestLoader.discover(str(R/'tools/tests'),pattern='test_yarrick_call_progression.py')
assert unittest.TextTestRunner(verbosity=1).run(suite).wasSuccessful()
progression=list(RANKS)
resource=audit(R/'assets',G,['yarrick-build']);attach=attachments(R/'assets',G,['yarrick-build'])
assert not resource['findings'],resource['findings'];assert not attach['errors'],attach['errors']
files={p.relative_to(D).as_posix() for p in D.rglob('*') if p.is_file()};native={p.relative_to(G).as_posix() for p in G.rglob('*') if p.is_file()}
for p in D.rglob('*.xml'):
 root=E.parse(p).getroot()
 for node in root.iter():
  for key,folder,ext in [('mesh','Video/Meshes','.msh'),('material','Video/Materials','.xml'),('icon','Video/Textures/Icons','.dds'),('animation','Video/Animations','.anm'),('idleAnimation','Video/Animations','.anm'),('meleeAnimation','Video/Animations','.anm'),('chargeAnimation','Video/Animations','.anm')]:
   value=node.get(key)
   if not value:continue
   rel=folder+'/'+value+ext
   # Idle counts use numbered files in the native definition.
   if rel not in files|native and key=='idleAnimation':
    assert all(folder+'/'+value+str(i)+ext in files|native for i in range(int(node.get('idleAnimationCount','1')))),rel
   else:assert rel in files|native,rel
meshes={p.stem:read_mesh(p.read_bytes()) for p in (D/'Video/Meshes').rglob('*.msh')}
clips={}
for p in (D/'Video/Animations').rglob('*.anm'):
 raw=p.read_bytes();clips[p.stem]=read_animation(raw)
 src=G/('Video/Animations/Units/AstraMilitarum/'+p.name.replace('Yarrick','LordCommissar'));original=src.read_bytes()
 # Every original bone and every original frame stays byte-identical.
 assert raw[16:len(original)]==original[16:]
 assert raw[7]==original[7]+1 and 'YarrickEyeMuzzle' in clips[p.stem]['bones']
report={'status':'passed','gameplay_contracts':'passed','reinforcement_progression':progression,'progression_basis':'Purchased Call of Armageddon skill rank; one five-rank skill','resource_findings':resource['findings'],'attachment_errors':attach['errors'],'custom_attachment_reviews':attach['reviews'],'meshes':meshes,'animations':clips,'engine_in_game_verified':False}
(O/'VALIDATION.json').write_text(json.dumps(report,indent=2));print('YARRICK VALIDATED:',len(meshes),'meshes,',len(clips),'clips; gameplay contracts and resource references passed')
