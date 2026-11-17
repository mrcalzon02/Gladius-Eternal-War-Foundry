"""Focused visual/animation bindings for the existing Penal Legion Officer."""
import re,xml.etree.ElementTree as E

def gameplay_signature(node):
    return [node.tag,sorted(node.attrib.items()),(node.text or '').strip(),[gameplay_signature(c) for c in node if c.tag!='model']]

def _attrs(tag,values):
    for name,value in values.items():
        pattern=r'(?<![\w:])'+re.escape(name)+r'="[^"]*"'
        if re.search(pattern,tag):tag,count=re.subn(pattern,lambda m:name+'="'+str(value)+'"',tag);assert count==1
        else:tag=tag[:-2]+' '+name+'="'+str(value)+'"/>'
    return tag

def bind_officer_unit(raw):
    text=raw.decode('utf-8-sig');before=E.fromstring(text)
    def replace(pattern,callback):
        nonlocal text
        text,count=re.subn(pattern,lambda m:callback(m.group()),text,flags=re.S);assert count==1,(pattern,count)
    replace(r'<unit\b(?=[^>]*\bmesh=)[^>]*?/>',lambda tag:_attrs(tag,{'mesh':'Units/Foundry/ImperialOfficerGuardsman','material':'Units/Foundry/ImperialOfficerGuardsman','idleAnimation':'Units/Foundry/ImperialOfficerGuardsmanIdle','idleAnimationCount':'3','idleContinuously':'1','normalWeight':'0.1','scale':'1 1 1','bloodBone':'ChestBone'}))
    replace(r'<projectileWeapon\b[^>]*?/>',lambda tag:_attrs(tag,{'mesh':'Weapons/AstraMilitarum/PrimarisPsykerLaspistol','material':'Weapons/AstraMilitarum/WyrdvanePsykerLaspistol','bone':'OfficerPistolGrip','muzzleBone':'Muzzle0'}))
    def sword(tag):
        tag=re.sub(r'^<powerWeapon\b','<weapon',tag);tag=re.sub(r'\s+effectBoundingVolume="[^"]*"','',tag)
        return re.sub(r'[ \t]+(?=\r?$)','',_attrs(tag,{'mesh':'Weapons/SpaceMarines/Chainsword','material':'Weapons/SpaceMarines/Chainsword','bone':'OfficerChainswordGrip'}),flags=re.M)
    replace(r'<(?:powerWeapon|weapon)\b(?=[^>]*\bmesh="Weapons/(?:AstraMilitarum/LordCommissarSword|SpaceMarines/Chainsword|Foundry/ImperialOfficerChainsword)")[^>]*?/>',sword)
    text=re.sub(r'\b(idleAnimation|animation|chargeAnimation|chargeDefenseAnimation|meleeAnimation|meleeDefenseAnimation)="Units/(?:AstraMilitarum/LordCommissar|Foundry/Officer|Foundry/ImperialOfficerGuardsman)([A-Za-z0-9]*)"',lambda m:m[1]+'="Units/Foundry/ImperialOfficerGuardsman'+m[2]+'"',text)
    replace(r'<action\b(?=[^>]*\bmeleeAnimation=)[^>]*?/>',lambda tag:_attrs(tag,{'beginFire':'0.4','endFire':'2.53','chargeBeginFire':'0.28','chargeEndFire':'0.92','chargeDefenseBeginFire':'0.22','chargeDefenseEndFire':'0.82','meleeBeginSwing':'0.30','meleeEndSwing':'0.70','meleeDefenseBeginSwing':'0.20','meleeDefenseEndSwing':'0.55'}))
    after=E.fromstring(text);assert gameplay_signature(before)==gameplay_signature(after),'Officer gameplay fields changed'
    return text.encode('utf-8')
