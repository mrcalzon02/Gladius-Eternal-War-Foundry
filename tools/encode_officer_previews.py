"""Encode native-render frames as compact GIFs and a motion contact sheet."""
from pathlib import Path
import json,hashlib,sys
R=Path(__file__).resolve().parents[1];A=R/'model-workbench/Imperial-Officer/animation-production'
try:from PIL import Image,ImageDraw
except ImportError:
    sys.path.insert(0,str(R/'tools/_resource_deps'));from PIL import Image,ImageDraw

def main():
    manifest=json.loads((A/'motion-frames.json').read_text());out=A/'motion-previews';out.mkdir(exist_ok=True);hashes={}
    for suffix,row in manifest.items():
        frames=[Image.open(A/row['folder']/f'{i:03}.png').convert('RGB') for i in range(row['frames'])]
        palette=Image.new('RGB',(480,600*min(8,len(frames))));step=max(1,len(frames)//8)
        for i,frame in enumerate(frames[::step][:8]):palette.paste(frame,(0,i*600))
        palette=palette.quantize(colors=192,method=Image.Quantize.MEDIANCUT);encoded=[f.quantize(palette=palette,dither=Image.Dither.NONE) for f in frames];path=out/(suffix+'.gif')
        encoded[0].save(path,save_all=True,append_images=encoded[1:],duration=row['frame_duration_ms'],loop=0 if suffix!='Die' else 1,optimize=False,disposal=2);hashes[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
        for f in frames:f.close()
    width=5*240;sheet=Image.new('RGB',(width,len(manifest)*320),(35,40,46));draw=ImageDraw.Draw(sheet)
    for y,(suffix,row) in enumerate(manifest.items()):
        draw.text((8,y*320+5),suffix,fill='white')
        for x,fraction in enumerate([0,.25,.5,.75,1]):
            i=min(row['frames']-1,round(fraction*(row['frames']-1)));im=Image.open(A/row['folder']/f'{i:03}.png').convert('RGB');im.thumbnail((240,290));sheet.paste(im,(x*240,y*320+25));im.close()
    path=out/'Animation-Contact-Sheet.png';sheet.save(path);hashes[path.name]=hashlib.sha256(path.read_bytes()).hexdigest();(A/'motion-preview-hashes.json').write_text(json.dumps(hashes,indent=2));print('OFFICER_MOTION_PREVIEWS_ENCODED',len(manifest),'clips')

if __name__=='__main__':main()
