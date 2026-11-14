"""Build Yarrick's contribution for the existing Penal Legion mod."""
from pathlib import Path
import copy, json, shutil, sys, xml.etree.ElementTree as E
R=Path(__file__).resolve().parents[1]
G=Path(r'C:\Program Files (x86)\Steam\steamapps\common\Warhammer 40000 Gladius - Relics of War\Data')
O=R/'assets/yarrick-build';D=O/'Data'
def write(path,root):
 p=D/path;p.parent.mkdir(parents=True,exist_ok=True);E.indent(root);E.ElementTree(root).write(p,encoding='utf-8',xml_declaration=True)
def effects(parent):return E.SubElement(E.SubElement(E.SubElement(parent,'modifiers'),'modifier'),'effects')
def area(target,affects='Unit',**attrs):return E.SubElement(E.SubElement(target,'areas'),'area',affects=affects,**attrs)
def condition(parent,kind,**entries):
 c=E.SubElement(E.SubElement(parent,'conditions'),kind)
 for k,v in entries.items():E.SubElement(c,k,**v)
 return c
def shout(action):
 E.SubElement(E.SubElement(action,'model'),'action',animation='Units/AstraMilitarum/LordCommissarShout',bone='ChestBone',sound='Actions/AstraMilitarumBuff')
def action(tag,name,icon,cooldown,**attrs):
 a=E.Element(tag,name='Foundry/'+name,icon=icon,cooldown=str(cooldown),**attrs);shout(a);return a
u=E.parse(G/'World/Units/AstraMilitarum/LordCommissar.xml').getroot()
u.find('model/unit').set('mesh','Units/Foundry/Yarrick')
u.find('model/unit').set('material','Units/Foundry/Yarrick')
w=u.find('weapons');w.remove(w.find("weapon[@name='PowerSword']"))
claw=E.SubElement(w,'weapon',name='PowerKlaw');E.SubElement(E.SubElement(claw,'model'),'weapon',mesh='Weapons/Foundry/YarrickClaw',material='Weapons/Foundry/YarrickKit',bone='LeftHandBone',fireInterval='1.0')
eye=E.SubElement(w,'weapon',name='Foundry/BaleEye');E.SubElement(E.SubElement(eye,'model'),'beamWeapon',muzzleBone='YarrickEyeMuzzle',fireInterval='0.5')
laser=E.parse(G/'World/Weapons/Lasgun.xml').getroot();write(Path('World/Weapons/Foundry/BaleEye.xml'),laser)
acts=u.find('actions')
for a in list(acts):
 if a.tag in ('auraOfDiscipline','bringItDown','summaryExecution','ironWill'):acts.remove(a)
# Four hero skills. The morale skill is already trained when recruited.
morale=action('bringItDown','OldManOfArmageddon','Actions/SummaryExecution',3,rank='0',rankMax='2',requiredActionPoints='0',consumedActionPoints='0',consumedMovement='0')
t=E.SubElement(E.SubElement(morale,'beginTargets'),'selfTarget');ar=area(t,radius='3')
ef=effects(ar);mod=ar.find('modifiers/modifier');condition(mod,'unit',allied={})
E.SubElement(ef,'morale',addMin='9',addMax='15');acts.append(morale)
# Two separate shell resolutions preserve Basilisk armour penetration and ordnance.
strike=action('orbitalStrike','TargetedBasiliskStrike','Actions/OrbitalStrike',5,rank='-1',rankMax='2')
t=E.SubElement(E.SubElement(strike,'beginTargets'),'target',rangeMax='6',rangeMin='1');condition(t,'unit',enemy={})
ef=effects(area(t))
for _ in range(2):E.SubElement(ef,'weaponDamage',weapon='Foundry/YarrickEarthshaker')
acts.append(strike)
shell=E.parse(G/'World/Weapons/EarthshakerCannon.xml').getroot()
# A call-in uses the Basilisk's BS3, rather than inheriting the commissar's BS5.
shell.set('attributesModifiedByUnit','0')
E.SubElement(shell.find('modifiers/modifier/effects'),'accuracy',min='6',max='6')
shell.remove(shell.find('model'))
E.SubElement(E.SubElement(shell,'model'),'weapon',explosionsBlueprint='Effects/MissileExplosions',explosionsEmitterBlueprint='Effects/BombardmentExplosionsEmitter',fireSound='Weapons/EarthshakerCannon',fireSoundCount='3')
write(Path('World/Weapons/Foundry/YarrickEarthshaker.xml'),shell)
# Native addUnit cannot relocate a second unit from an occupied tile. Use a
# paired placement command: the tank is reserved by the first call, then placed
# for free. No duplicate call or second cooldown is incurred.
def spawn_target(a,unit,experience=0):
 b=E.SubElement(a,'beginTargets');t=E.SubElement(b,'target',rangeMin='1',rangeMax='2')
 condition(t,'tile',land={},noUnit={},noEnemyCity={},noFeature={'name':'GravityWaves'})
 E.SubElement(effects(area(t,'Tile')),'addUnit',name='AstraMilitarum/'+unit,consumedAction='0',consumedMovement='0',levelMin=str(experience),levelMax=str(experience))
 return b
# Unit levels are zero-based internally. Select exactly one automatic stage;
# fixed spawn levels avoid the engine's rounded rank interpolation. The shared
# cooldown prevents an extra call when levelling switches the visible action.
for stage in range(1,6):
 experience=max(0,stage-2)
 call=action('livingIncubator','ArmageddonCalls'+('' if stage==1 else str(stage)),'Units/AstraMilitarum/Guardsman',10,useConditionsForVisiblity='1')
 c=condition(call,'unit',noTrait={'name':'Foundry/ArmourPending'})
 E.SubElement(c,'noTrait',name='Foundry/ArmageddonCallsCooldown')
 E.SubElement(c,'level',greater=str(stage-1.5),**({'less':str(stage-.5)} if stage<5 else {}))
 b=spawn_target(call,'Guardsman',experience);s=E.SubElement(b,'selfTarget');ef=effects(area(s))
 E.SubElement(ef,'addTrait',name='Foundry/ArmageddonCallsCooldown',duration='10')
 if stage>=2:
  E.SubElement(ef,'addTrait',name='Foundry/ArmourPending')
  E.SubElement(ef,'addTrait',name='Foundry/ArmourPendingTier'+str(experience))
 acts.append(call)
for experience in range(4):
 armour=action('livingIncubator','ArmageddonCallsArmour'+('' if experience==0 else str(experience)),'Units/AstraMilitarum/LemanRussBattleTank',0,requiredActionPoints='0',consumedActionPoints='0',consumedMovement='0',useConditionsForVisiblity='1')
 c=condition(armour,'unit',trait={'name':'Foundry/ArmourPending'})
 E.SubElement(c,'trait',name='Foundry/ArmourPendingTier'+str(experience))
 b=spawn_target(armour,'LemanRussBattleTank',experience);s=E.SubElement(b,'selfTarget');ef=effects(area(s))
 for name in ('Foundry/ArmourPending','Foundry/ArmourPendingTier'+str(experience)):E.SubElement(ef,'removeTrait',name=name)
 acts.append(armour)
ultimate=action('bringItDown','ThisEndsHere','Actions/BringItDown',5,rank='-1',rankMax='0',elite='1',levelUpPriority='1',requiredActionPoints='0',consumedActionPoints='0',consumedMovement='0')
t=E.SubElement(E.SubElement(ultimate,'beginTargets'),'target',rangeMax='3');condition(t,'unit',allied={})
E.SubElement(effects(area(t)),'addTrait',name='Foundry/ThisEndsHere',duration='2');acts.append(ultimate)
trait=E.Element('trait',category='Buff',icon='Actions/BringItDown');E.SubElement(effects(trait),'damage',mul='1.0');write(Path('World/Traits/Foundry/ThisEndsHere.xml'),trait)
trait=E.Element('trait',category='Buff',icon='Units/AstraMilitarum/LemanRussBattleTank');write(Path('World/Traits/Foundry/ArmourPending.xml'),trait)
for name in ['ArmageddonCallsCooldown']+['ArmourPendingTier'+str(i) for i in range(4)]:
 trait=E.Element('trait',category='Buff',icon='Units/AstraMilitarum/LemanRussBattleTank');write(Path('World/Traits/Foundry')/(name+'.xml'),trait)
for node in u.iter():
 for key in ('idleAnimation','animation','meleeAnimation','chargeAnimation'):
  value=node.get(key)
  if value and value.startswith('Units/AstraMilitarum/LordCommissar'):node.set(key,value.replace('Units/AstraMilitarum/LordCommissar','Units/Foundry/Yarrick'))
write(Path('World/Units/AstraMilitarum/CommissarYarrick.xml'),u)
# Extend the effective installed Penal Legion hero roster when available.
heroes=Path(r'C:\Program Files (x86)\Steam\steamapps\workshop\content\489630\2525618649\Data\World\Buildings\AstraMilitarum\Heroes.xml')
if not heroes.exists():heroes=G/'World/Buildings/AstraMilitarum/Heroes.xml'
h=E.parse(heroes).getroot();E.SubElement(h.find('actions'),'produceUnit',unit='AstraMilitarum/CommissarYarrick');write(Path('World/Buildings/AstraMilitarum/Heroes.xml'),h)
entries={
 'Units':{'AstraMilitarum/CommissarYarrick':'Commissar Sebastian Yarrick','AstraMilitarum/CommissarYarrickDescription':'The Old Man of Armageddon. Hero with bolt pistol, power claw, Bale Eye and Imperial support call-ins.','AstraMilitarum/CommissarYarrickFlavor':'The Old Man stands. Armageddon answers.'},
 'Actions':{'Foundry/OldManOfArmageddon':'Old Man of Armageddon','Foundry/OldManOfArmageddonDescription':'Restore 9 / 12 / 15 morale to allied units within 3 tiles. Starts trained at rank one. No execution required.','Foundry/TargetedBasiliskStrike':'Targeted Basilisk Strike','Foundry/TargetedBasiliskStrikeDescription':'Order two standard Earthshaker ordnance hits against one enemy within 6 tiles. Five-round cooldown.','Foundry/ArmageddonCalls':'Armageddon Calls','Foundry/ArmageddonCallsDescription':'Call one Guardsmen squad onto an empty land tile within 2 tiles, then use the free Armour placement command to deploy one Leman Russ nearby. Ten-round cooldown begins with the squad.','Foundry/ArmageddonCallsArmour':'Armageddon Calls — Place Tank','Foundry/ArmageddonCallsArmourDescription':'Complete the reserved reinforcement call: deploy one Leman Russ onto an empty land tile within 2 tiles. Free action; available until placed.','Foundry/ThisEndsHere':'This Ends Here','Foundry/ThisEndsHereDescription':'Grant one allied unit within 3 tiles +100% base weapon damage for 2 rounds. Five-round cooldown. Does not compound existing percentage bonuses.'},
 'Traits':{'Foundry/ThisEndsHere':'This Ends Here','Foundry/ThisEndsHereDescription':'+100% base weapon damage.','Foundry/ArmourPending':'Armageddon Armour Inbound','Foundry/ArmourPendingDescription':'One Leman Russ is reserved. Use Armageddon Calls — Place Tank to deploy it.'},
 'Weapons':{'Foundry/BaleEye':'Bale Eye','Foundry/BaleEyeDescription':'Bionic laser eye. Uses standard Lasgun attack statistics and upgrades.','Foundry/YarrickEarthshaker':'Yarrick’s Earthshaker Support','Foundry/YarrickEarthshakerDescription':'Standard Basilisk Earthshaker shell with Basilisk ranged accuracy.'}}
progression='Automatically improves with Yarrick: level 1 calls Guardsmen only; level 2 adds a Leman Russ; levels 3, 4 and 5 start both units with 1, 2 and 3 experience levels. Place units within 2 tiles. Shared ten-round cooldown.'
for stage in range(1,6):
 key='Foundry/ArmageddonCalls'+('' if stage==1 else str(stage))
 entries['Actions'][key]='Armageddon Calls'
 entries['Actions'][key+'Description']=progression
for experience in range(4):
 key='Foundry/ArmageddonCallsArmour'+('' if experience==0 else str(experience))
 entries['Actions'][key]='Armageddon Calls — Place Tank'
 entries['Actions'][key+'Description']=f'Complete the reserved reinforcement call: deploy one Leman Russ with {experience} experience levels within 2 tiles. Free action; experience is reserved when the call begins.'
 key='Foundry/ArmourPendingTier'+str(experience)
 entries['Traits'][key]='Reserved Armour Experience'
 entries['Traits'][key+'Description']=f'The incoming Leman Russ starts with {experience} experience levels.'
entries['Traits']['Foundry/ArmageddonCallsCooldown']='Armageddon Reinforcements Rearming'
entries['Traits']['Foundry/ArmageddonCallsCooldownDescription']='Armageddon Calls is on its shared ten-round cooldown, including after Yarrick levels up.'
for file,values in entries.items():
 lang=E.Element('language')
 for name,value in values.items():E.SubElement(lang,'entry',name=name,value=value)
 write(Path('Core/Languages/English')/(file+'.xml'),lang)
for sub,source,dest in [('Units/AstraMilitarum','LordCommissar','CommissarYarrick')]:
 src=G/('Video/Textures/Icons/'+sub+'/'+source+'.dds');dst=D/('Video/Textures/Icons/'+sub+'/'+dest+'.dds');dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
 src=G/('Video/Textures/Icons/Overlay/'+sub+'/'+source+'.dds');dst=D/('Video/Textures/Icons/Overlay/'+sub+'/'+dest+'.dds');dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
print('Built Yarrick rules:',O)
