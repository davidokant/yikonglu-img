# 在主人电脑上跑：按 crop3.json（小图坐标）把原尺寸逐页图劈半、转平、切边，出网站用图。
# 用法 python apply_full.py <史料\论语诸家 目录> <crop3.json> <need.json> <输出目录>
import sys,os,json
from PIL import Image
root,cropf,needf,out=sys.argv[1:5];C=json.load(open(cropf,encoding='utf-8'));need=set(json.load(open(needf,encoding='utf-8')))
MAXW=1000;sizes={};n=0
for k,v in C.items():
    book,fn=k.split('/');base=fn[:-4]
    parts=[p for p in v['parts'] if f"{book}/{base}{p['half']}" in need]
    if not parts:continue
    im=Image.open(os.path.join(root,book,'pages',fn));sw,sh=v['size'];s=im.width/sw
    bg=tuple(int(c) for c in im.resize((1,1)).getpixel((0,0))) if im.mode=='RGB' else int(im.resize((1,1)).getpixel((0,0)))
    for p in parts:
        x0,x1=p['x'];h=im.crop((round(x0*s),0,round(x1*s),im.height))
        if p['rot']:h=h.rotate(p['rot'],resample=Image.BICUBIC,fillcolor=bg)
        l,t,r,b=p['box'];h=h.crop((round(l*s),round(t*s),round(r*s),round(b*s)))
        if h.width>MAXW:h=h.resize((MAXW,round(h.height*MAXW/h.width)),Image.LANCZOS)
        if h.mode not in('RGB','L'):h=h.convert('RGB')
        os.makedirs(os.path.join(out,book),exist_ok=True)
        u=base+p['half'];h.save(os.path.join(out,book,u+'.jpg'),quality=75,optimize=True,progressive=True)
        sizes[f'{book}/{u}']=[h.width,h.height];n+=1
json.dump(sizes,open(os.path.join(out,'sizes.json'),'w',encoding='utf-8'),ensure_ascii=False)
print(n,'张')
