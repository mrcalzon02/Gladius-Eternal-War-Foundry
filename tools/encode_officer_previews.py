"""Encode native-render frames as compact GIFs and a motion contact sheet."""
from pathlib import Path
import json,hashlib,sys,shutil,subprocess
R=Path(__file__).resolve().parents[1];A=R/'model-workbench/Imperial-Officer/animation-production'
try:from PIL import Image,ImageDraw
except ImportError:
    sys.path.insert(0,str(R/'tools/_resource_deps'));from PIL import Image,ImageDraw

def main():
    manifest=json.loads((A/'motion-frames.json').read_text());out=A/'motion-previews';out.mkdir(exist_ok=True);hashes={}
    build=json.loads((A/'animation-build.json').read_text())
    order=['Idle0','Idle1','Idle2','MoveBegin','Move','MoveEnd','Attack','Melee','MeleeDefense','Charge','ChargeDefense','Grenade','Shout','Die']
    assert set(manifest)==set(order)==set(build['clips']), 'Render all 14 clips before encoding the full sweep'
    manifest={suffix:manifest[suffix] for suffix in order}
    assert all(row['native_clip_sha256']==build['clips'][suffix]['sha256'] for suffix,row in manifest.items())
    for suffix,row in manifest.items():
        frames=[Image.open(A/row['folder']/f'{i:03}.png').convert('RGB') for i in range(row['frames'])]
        fw,fh=frames[0].size;palette=Image.new('RGB',(fw,fh*min(8,len(frames))));step=max(1,len(frames)//8)
        for i,frame in enumerate(frames[::step][:8]):palette.paste(frame,(0,i*fh))
        palette=palette.quantize(colors=192,method=Image.Quantize.MEDIANCUT);encoded=[f.quantize(palette=palette,dither=Image.Dither.NONE) for f in frames];path=out/(suffix+'.gif')
        encoded[0].save(path,save_all=True,append_images=encoded[1:],duration=row['frame_duration_ms'],loop=0 if suffix!='Die' else 1,optimize=False,disposal=2);hashes[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
        for f in frames:f.close()
    width=5*240;sheet=Image.new('RGB',(width,len(manifest)*320),(35,40,46));draw=ImageDraw.Draw(sheet)
    for y,(suffix,row) in enumerate(manifest.items()):
        draw.text((8,y*320+5),suffix,fill='white')
        for x,fraction in enumerate([0,.25,.5,.75,1]):
            i=min(row['frames']-1,round(fraction*(row['frames']-1)));im=Image.open(A/row['folder']/f'{i:03}.png').convert('RGB');im.thumbnail((240,290));sheet.paste(im,(x*240,y*320+25));im.close()
    path=out/'Animation-Contact-Sheet.png';sheet.save(path);hashes[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
    # One continuous, labelled sweep supplements the individual native clips.
    samples=[]
    for row in manifest.values():
        for fraction in (0.,.25,.5,.75,1.):
            i=min(row['frames']-1,round(fraction*(row['frames']-1)));samples.append(Image.open(A/row['folder']/f'{i:03}.png').convert('RGB'))
    fw,fh=samples[0].size;pool=Image.new('RGB',(fw,fh*len(samples)))
    for i,frame in enumerate(samples):pool.paste(frame,(0,i*fh));frame.close()
    palette=pool.quantize(colors=192,method=Image.Quantize.MEDIANCUT);pool.close();encoded=[];segments=[];elapsed=0
    for index,(suffix,row) in enumerate(manifest.items(),1):
        segments.append({'clip':suffix,'start_ms':elapsed,'duration_ms':row['frames']*row['frame_duration_ms'],'native_clip_sha256':row['native_clip_sha256']})
        for i in range(row['frames']):
            image=Image.open(A/row['folder']/f'{i:03}.png').convert('RGB');frame=Image.new('RGB',(fw,fh+28),(28,32,38));frame.paste(image,(0,28));ImageDraw.Draw(frame).text((10,8),f'{index:02}/14  {suffix}',fill='white');encoded.append(frame.quantize(palette=palette,dither=Image.Dither.NONE));image.close();frame.close()
        elapsed+=row['frames']*row['frame_duration_ms']
    path=out/'Full-Animation-Sweep.gif';encoded[0].save(path,save_all=True,append_images=encoded[1:],duration=50,loop=0,optimize=False,disposal=2);hashes[path.name]=hashlib.sha256(path.read_bytes()).hexdigest()
    sweep={'status':'encoded from verified native export','clips':segments,'clip_count':len(segments),'frames':len(encoded),'duration_ms':elapsed,'gif_sha256':hashes[path.name],'mesh_sha256':hashlib.sha256((R/'assets/imperial-officer-animated/Data/Video/Meshes/Units/Foundry/ImperialOfficerGuardsman.msh').read_bytes()).hexdigest()}
    ffmpeg=shutil.which('ffmpeg')
    if ffmpeg:
        video=out/'Full-Animation-Sweep.mp4';subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-y','-i',str(path),'-vf','fps=20,format=yuv420p','-c:v','libx264','-crf','18','-movflags','+faststart','-an',str(video)],check=True);hashes[video.name]=hashlib.sha256(video.read_bytes()).hexdigest();sweep['mp4_sha256']=hashes[video.name]
    (A/'full-animation-sweep.json').write_text(json.dumps(sweep,indent=2))
    (A/'motion-preview-hashes.json').write_text(json.dumps(hashes,indent=2));print('OFFICER_MOTION_PREVIEWS_ENCODED',len(manifest),'clips;',len(encoded),'sweep frames')

if __name__=='__main__':main()
