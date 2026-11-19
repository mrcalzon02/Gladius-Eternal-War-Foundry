"""Stage a conflict-checked Yarrick contribution inside existing Penal Legion."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,xml.etree.ElementTree as E
R=Path(__file__).resolve().parents[1]
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
def merge_language(original,contribution):
 entries=re.findall(r'<entry\s+name="([^"]+)"[^\n]*?/>',contribution)
 result=original
 for key in entries:
  pattern=r'<entry\s+name="'+re.escape(key)+r'"[^\n]*?/>'
  addition=re.search(pattern,contribution).group(0)
  matches=list(re.finditer(pattern,result))
  if len(matches)>1:raise ValueError('Duplicate localization key '+key)
  if matches:
   m=matches[0];result=result[:m.start()]+addition+result[m.end():]
  else:result=result.replace('</language>','\t'+addition+'\n</language>')
 return result
def merge_heroes(original):
 root=E.fromstring(original)
 if root.find("actions/produceUnit[@unit='AstraMilitarum/CommissarYarrick']") is not None:return original
 if original.count('</actions>')!=1:raise ValueError('Unexpected hero recruitment layout')
 return original.replace('</actions>','\t<produceUnit unit="AstraMilitarum/CommissarYarrick"/>\n\t</actions>')
def merge_file(relative,contribution,original):
 if relative.startswith('Data/Core/Languages/English/'):
  return merge_language(original.decode('utf-8-sig'),contribution.decode('utf-8-sig')).encode('utf-8')
 if relative=='Data/World/Buildings/AstraMilitarum/Heroes.xml':
  return merge_heroes(original.decode('utf-8-sig')).encode('utf-8')
 return contribution
def stage(base,output):
 build=R/'assets/yarrick-build';manifest=json.loads((build/'MANIFEST.json').read_text())
 inventory=[]
 for relative,sha in manifest['files'].items():
  source=build/relative
  assert digest(source)==sha,relative
  prior=base/'2525618649'/relative
  data=merge_file(relative,source.read_bytes(),prior.read_bytes() if prior.exists() else b'<language>\n</language>\n')
  target=output/'2525618649'/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
  inventory.append({'source':str(target),'destination':'2525618649/'+relative,'sha256':digest(target),'expected_previous_sha256':digest(prior)})
 additional=[(R/'model-workbench/Yarrick/Yarrick.blend','model-workbench/Yarrick/Yarrick.blend'),(R/'model-workbench/Yarrick/Yarrick-native-preview.png','model-workbench/Yarrick/Yarrick-native-preview.png'),(R/'model-workbench/Yarrick/README.txt','model-workbench/Yarrick/README.txt'),(R/'docs/YARRICK.txt','docs/YARRICK.txt'),(build/'VALIDATION.json','docs/yarrick/validation.json'),(R/'model-workbench/Yarrick/native-review.json','docs/yarrick/native-review.json'),(output/'merge-validation.json','docs/yarrick/merge-validation.json')]
 for name in ('build_yarrick_rules.py','yarrick_call_progression.py','build_yarrick_model.py','package_yarrick.py','verify_yarrick.py','review_yarrick_native.py','prepare_yarrick.py','integrate_yarrick.py','verify_yarrick_integration.py'):
  additional.append((R/'tools'/name,'tools/'+name))
 for source,relative in additional:
  inventory.append({'source':str(source),'destination':relative,'sha256':digest(source),'expected_previous_sha256':digest(base/relative)})
 additional.append((R/'tools/tests/test_yarrick_call_progression.py','tools/tests/test_yarrick_call_progression.py'))
 readme=(base/'README.md').read_text(encoding='utf-8-sig')
 if '## Commissar Sebastian Yarrick' not in readme:
  readme+='\n\n## Commissar Sebastian Yarrick\n\nYarrick joins the existing Penal Legion mod (`2525618649`) with a red power\nclaw, bionic laser eye, Basilisk support and Armageddon reinforcements. See\n[the unit rules and validation notes](docs/YARRICK.txt) and\n[editable source](model-workbench/Yarrick/README.txt). Offline checks pass;\nlive combat validation is pending. No separate mod or Workshop ID is created.\n'
 target=output/'README.md';target.write_text(readme,encoding='utf-8')
 inventory.append({'source':str(target),'destination':'README.md','sha256':digest(target),'expected_previous_sha256':digest(base/'README.md')})
 (output/'files.json').write_text(json.dumps(inventory,indent=2))
 print('Staged',len(inventory),'files in existing Penal Legion library:',output)
 return inventory
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,default=Path(r'C:\GITS\Gladius-Eternal-War-Foundry'));p.add_argument('--output',type=Path,default=R/'publication/yarrick');args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True);stage(args.base,args.output)
