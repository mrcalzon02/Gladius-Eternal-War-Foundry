"""Pack approved 1024-pixel colour maps and material masks into native mipmapped DDS."""
import argparse
import json
import struct
from io import BytesIO
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import distance_transform_edt


def write_dds(image, path, codec):
    """Pillow encodes each BC level. Assemble the standard DDS mip-chain container."""
    levels = []
    while True:
        dst = BytesIO()
        image.save(dst, 'DDS', pixel_format=codec)
        raw = dst.getvalue()
        if not levels:
            header = bytearray(raw[:128])
        assert raw[84:88] == codec.encode()
        levels.append(raw[128:])
        if image.size == (1, 1):
            break
        next_size = tuple(max(1, n // 2) for n in image.size)
        image = image.resize(next_size,Image.Resampling.BOX)
    flags = struct.unpack_from('<I',header,8)[0] | 0x20000 | 0x80000
    struct.pack_into('<I',header,8,flags)
    struct.pack_into('<I',header,20,len(levels[0]))
    struct.pack_into('<I',header,28,len(levels))
    struct.pack_into('<I',header,108,0x401008)
    path.write_bytes(header+b''.join(levels))
    with Image.open(path) as checked:
        checked.load()
        assert checked.size == (2048,2048)


def make_atlas(stage,out):
    objects=json.loads((stage/'objects.json').read_text())
    colour=Image.new('RGBA',(2048,2048),(39,43,32,255))
    sic=Image.new('RGB',(2048,2048),(12,0,0))
    locations={'mek':(0,0),'gunner':(1024,0),'cutter':(0,1024)}
    for role,(x,y) in locations.items():
        painted=Image.open(stage/f'{role}.png').convert('RGBA')
        if painted.size!=(1024,1024):raise ValueError(f'{role} diffuse paint must be 1024 square')
        colour.paste(painted,(x,y))
        # The source uses rough painted diffuse without tangent-space perturbation.
        # Preserve its authored vertex/corner normals with a neutral tangent normal.
        face_spec=Image.new('L',(1024,1024),0)
        draw=ImageDraw.Draw(face_spec)
        for ob in objects:
            if ob['role']!=role:continue
            for face in ob['uv_triangles']:
                draw.polygon([(u*1024,v*1024) for u,v in face],fill=ob['specular'])
        mask=np.asarray(face_spec)
        nearest=distance_transform_edt(mask==0,return_distances=False,return_indices=True)
        mask=mask[tuple(nearest)]
        # The red channel gives brighter exposed metal its authored specular response.
        luma=np.asarray(painted.convert('L'),dtype=float)/255
        red=np.round(mask*(.72+.43*luma)).astype(np.uint8)
        tile=np.zeros((1024,1024,3),dtype=np.uint8);tile[:,:,0]=red
        sic.paste(Image.fromarray(tile),(x,y))
    out.mkdir(parents=True,exist_ok=True)
    write_dds(colour,out/'GrotTrioDiffuse.dds','DXT5')
    write_dds(Image.new('RGB',(2048,2048),(128,128,255)),out/'GrotTrioNormal.dds','DXT1')
    write_dds(sic,out/'GrotTrioSIC.dds','DXT1')
    decoded=Image.open(out/'GrotTrioDiffuse.dds').convert('RGB')
    quality={}
    for role,(x,y) in locations.items():
        ref=Image.open(stage/f'{role}.png').convert('RGB')
        err=np.abs(np.asarray(decoded.crop((x,y,x+1024,y+1024)),dtype=np.int16)-np.asarray(ref,dtype=np.int16))
        quality[role]={'mean_error_8bit_rgb':float(err.mean()),'p99_error_8bit_rgb':float(np.percentile(err,99))}
    (stage/'texture-check.json').write_text(json.dumps(quality,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',type=Path);parser.add_argument('out',type=Path)
    a=parser.parse_args();make_atlas(a.stage,a.out)
