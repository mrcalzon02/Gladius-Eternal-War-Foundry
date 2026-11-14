"""Compare the existing Penal Legion baseline with the staged contribution."""
from pathlib import Path
import json,re,sys,xml.etree.ElementTree as E
R=Path(__file__).resolve().parents[1];B=Path(r'C:\GITS\Gladius-Eternal-War-Foundry/2525618649');S=R/'publication/yarrick/2525618649'
sys.path.insert(0,str(R/'tools'));from integrate_yarrick import merge_language,merge_heroes
checks=[]
for p in (S/'Data/Core/Languages/English').glob('*.xml'):
 prior=B/p.relative_to(S)
 original=prior.read_text(encoding='utf-8-sig') if prior.exists() else '<language>\n</language>\n'
 merged=p.read_text(encoding='utf-8-sig')
 # Existing language markup is deliberately not strict XML. Preserve every
 # complete original entry line, including embedded markup and unrelated keys.
 original_entries=re.findall(r'^\s*(<entry .*?/>)\s*$',original,re.M)
 assert all(entry in merged for entry in original_entries),p
 keys=re.findall(r'<entry\s+name="([^"]+)"',merged)
 assert len(keys)==len(set(keys)),p
 assert merge_language(merged,(R/'assets/yarrick-build'/p.relative_to(S)).read_text(encoding='utf-8-sig'))==merged
 checks.append({'file':str(p.relative_to(S)),'original_entries_preserved':len(original_entries)})
rel=Path('Data/World/Buildings/AstraMilitarum/Heroes.xml');old=E.parse(B/rel).getroot();new=E.parse(S/rel).getroot()
def signature(root):return [(n.tag,sorted(n.attrib.items())) for n in root.iter()]
copy=E.fromstring(E.tostring(new));actions=copy.find('actions');actions.remove(actions.find("produceUnit[@unit='AstraMilitarum/CommissarYarrick']"))
old_actions=old.find('actions');prior_yarrick=old_actions.find("produceUnit[@unit='AstraMilitarum/CommissarYarrick']")
if prior_yarrick is not None:old_actions.remove(prior_yarrick)
assert signature(old)==signature(copy),'Existing hero building changed'
assert len(new.findall("actions/produceUnit[@unit='AstraMilitarum/CommissarYarrick']"))==1
assert merge_heroes((S/rel).read_text())==(S/rel).read_text()
assert not (S/'SteamID.txt').exists(),'Contribution must not introduce a new mod identity'
report={'status':'passed','existing_workshop_id':'2525618649','hero_roster_preserved':True,'single_yarrick_recruitment_entry':True,'idempotent_merge':True,'languages':checks,'new_mod_identity':False}
(R/'publication/yarrick/merge-validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
