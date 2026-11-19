# 错题本自查（九接班 11-20 建；主人 11-19“自己找到的问题不能再犯”）
# 每条错题在这里落一支检查函数，名字带错题号。上台前、交片前、定版前都跑：
#   python3 zicha.py --gao <评审下的集目录> [--ep <episode.json所在目录>] [--dv <定版或dv目录>] [--kind 论语长片|道德经|三字经|孟子|热点|反常]
# 退出码 0＝全过；1＝有不过（不过的不许上台、不许交片）；未给输入的项记“跳过（缺输入）”，交片说明里要写明哪几项跳过、为什么。
# 新加错题：在 错题本.md 记一条，再在本文件加一支 ct_XXX 函数并登记进 CHECKS；能写脚本的一律写脚本，不靠人记。
import argparse,glob,json,os,re,subprocess,sys
HERE=os.path.dirname(os.path.abspath(__file__))
SK='/mnt/project-files/一孔学-内-自媒体/技能/yikong-wenzi-yujian/references/配音拼音锁读表.tsv'
REDV='/mnt/project-files/.传输/redv'
def load_rules(p):
    R=[];seen=set()
    for l in open(p,encoding='utf-8').read().splitlines():
        if l.startswith('#') or not l.strip():continue
        a=l.split('\t')
        if a[0] in seen:continue
        seen.add(a[0])
        try:R.append((re.compile(a[0]),a[1] if len(a)>1 else '',a[2] if len(a)>2 else ''))
        except re.error:pass
    return R
def lock_spans(t,R):
    sp=[]
    for rx,py,_ in R:
        for m in rx.finditer(t):
            a,b=m.span('t')
            if all(b<=x or a>=y for x,y,_ in sp):sp.append((a,b,py))
    return sp
def segs(gao):
    for f in sorted(glob.glob(gao+'/*配音分段*.json')):
        for s in json.load(open(f))['segments']:yield f,s
def ct001_lou(a):
    """CT-001 读音·漏锁：高危多音字表里的写法，送配文本里必须被锁读表锁住，且锁的读音一致"""
    if not a.gao:return None
    R=load_rules(SK);H=load_rules(os.path.join(HERE,'高危多音字.tsv'));bad=[]
    for f,s in segs(a.gao):
        t=s.get('send_text',s.get('text',''));sp=lock_spans(t,R)
        for rx,py,src in H:
            for m in rx.finditer(t):
                p=m.start('t');hit=[x for x in sp if x[0]<=p<x[1]]
                if not hit:bad.append(f"{s['id']} 漏锁「{t[max(0,p-6):p+6]}」应 {py}（{src}）")
                elif hit[0][2].split()[p-hit[0][0]]!=py:bad.append(f"{s['id']} 锁成 {hit[0][2]}「{t[max(0,p-6):p+6]}」应 {py}")
    return bad
def ct001_hou(a):
    """CT-001 读音·后加规则：配音早于某条锁读规则、该规则又命中本段 → 必须在 测调记录.tsv 里判过“对”或已补配"""
    if not a.gao:return None
    rec=os.path.join(HERE,'测调记录.tsv');ok=set()
    if os.path.exists(rec):
        for l in open(rec,encoding='utf-8'):
            x=l.rstrip('\n').split('\t')
            if len(x)>4 and (x[0].startswith('对') or x[0].startswith('已补配')):ok.add((x[1],x[2],x[3]))
    out=subprocess.run([sys.executable,os.path.join(HERE,'scan_after.py'),os.path.abspath(a.gao)],capture_output=True,text=True).stdout
    bad=[]
    for l in out.splitlines():
        n,d,f,seg,p,ch,py,ctx=l.split('\t')
        if (n,seg,ch) not in ok:bad.append(f"{seg} 配音早于规则「{ctx}」{ch}→{py}，未测调/未补配")
    return bad
def gate(script,a,key):
    if not a.ep:return None
    r=subprocess.run([sys.executable,os.path.join(REDV,script),a.ep],capture_output=True,text=True)
    o=r.stdout;m=re.search(r'甲 (\d+) 乙 (\d+) 丙 (\d+)',o)
    if not m:return [f'{script} 没跑出结果：'+(r.stderr or o)[-200:]]
    return [] if m.groups()==('0','0','0') else [l.strip() for l in o.splitlines() if l.strip()][:20]
def ct002(a):
    """CT-002 跨页红框只框前页：hongkuang.py 甲乙丙都要 0（丙＝一拍的字跨两页，原来只提示不拦，现在拦）"""
    return gate('hongkuang.py',a,'丙')
def ct004(a):
    """CT-004 原页没切白边：qiebian.py 甲乙丙都要 0（所有书、所有原页，含他书互见页）"""
    return gate('qiebian.py',a,'')
def ct003(a):
    """CT-003 进度条漏算原页段：kd 竖屏模板（热点、反常、课本）每张卡结束前 0.2 秒当前格白条 ≥95%，原页段后不跳格。脚本待选题实验线交，暂人工抽帧"""
    if a.kind not in ('热点','反常','课本','两面'):return []
    if not a.pb:return ['缺 out/pb.json（kd 新模板 render.js 每条都写；旧模板出的片要换新模板重出）']
    pn=json.load(open(a.pb))
    return [f'进度条提醒：{x}' for x in pn]
def ct005(a):
    """CT-005 前置版英文章节书序：发布单.json 里 YouTube 英文章节与中文章节逐行时间一致、章序同向"""
    if not a.dv:return None
    fs=glob.glob(os.path.join(a.dv,'发布单.json'))
    if not fs:return ['缺 发布单.json']
    d=json.load(open(fs[0]));bad=[]
    for it in d.get('youtube',{}).get('items',[])[:1]:
        zh=it.get('localizations',{}).get('zh-Hans',{}).get('description',it.get('description',''))
        en=it.get('localizations',{}).get('en',{}).get('description','')
        L=lambda s:re.findall(r'^(\d+:\d\d(?::\d\d)?) (.+)$',s,re.M)
        z,e=L(zh),L(en)
        if [x[0] for x in z]!=[x[0] for x in e]:bad.append(f'中英章节时间不一致：中 {[x[0] for x in z]} 英 {[x[0] for x in e]}')
        num=lambda s:[float(m.replace('–','.').split('.')[0])*1000+float(m.split('.')[1].split('–')[0]) for m in re.findall(r'\d+\.\d+',s)[:1]]
        zn=[]
        cn='〇一二三四五六七八九十'
        for t,x in z:
            m=re.match(r'第([一二三四五六七八九十百〇]+)',x)
            if m:
                s=m.group(1);v=0
                if '百' in s:v+=100*(cn.index(s.split('百')[0]) if s.split('百')[0] else 1);s=s.split('百')[1]
                if '十' in s:p,q=s.split('十');v+=10*(cn.index(p) if p else 1)+(cn.index(q) if q else 0)
                elif s:v+=cn.index(s[-1])
                zn.append((t,v))
        en_n=[(t,num(x)) for t,x in e if num(x)]
        zt={t:v for t,v in zn};et={t:v[0] for t,v in en_n}
        common=[t for t in zt if t in et]
        for i in range(len(common)):
            for j in range(i+1,len(common)):
                if (zt[common[i]]-zt[common[j]])*(et[common[i]]-et[common[j]])<0:bad.append(f'章序反了：{common[i]} 与 {common[j]} 中英先后不一致')
    return bad
def ct007(a):
    """CT-007 锁读表自身：每行正则都编得过（编不过的行会被配音脚本跳过或整批崩），回归例句全对（防规则写太宽误锁、写太窄漏锁）"""
    bad=[]
    for i,l in enumerate(open(SK,encoding='utf-8').read().splitlines(),1):
        if l.startswith('#') or not l.strip():continue
        try:re.compile(l.split('\t')[0])
        except re.error as e:bad.append(f'锁读表第 {i} 行编不过：{e}')
    R=load_rules(SK)
    for l in open(os.path.join(HERE,'锁读回归例句.tsv'),encoding='utf-8'):
        if l.startswith('#') or not l.strip():continue
        t,ch,k,want,src=(l.rstrip('\n').split('\t')+['']*5)[:5]
        pos=[i for i,c in enumerate(t) if c==ch][int(k)]
        hit=[x for x in lock_spans(t,R) if x[0]<=pos<x[1]]
        got=hit[0][2].split()[pos-hit[0][0]] if hit else '不锁'
        if got!=want:bad.append(f'回归例句「{t}」第 {k} 个{ch} 锁成 {got}，应 {want}（{src}）')
    return bad
CSV='/mnt/project-files/一孔学-内-自媒体/数据/网站素材/_原文/分章对照表.csv'
def zhu2tong():
    M={}
    for l in open(CSV,encoding='utf-8-sig').read().splitlines()[1:]:
        x=l.split(',');M[x[0]]=x[1].split('|')
    return M
def key(c):a,b=c.split('.');return (int(a),int(b))
def ct006(a):
    """CT-006 章号朱注/通行本错位：稿首朱注章号经 分章对照表 换成通行本，发布单里“通行本 a—b”与英文 Analects a–b 都要对上"""
    if not (a.gao and a.dv):return None
    g=[f for f in glob.glob(a.gao+'/*-稿-v*.md') if '预检' not in f]
    if not g:return ['没找到稿']
    head=open(max(g,key=os.path.getmtime),encoding='utf-8').readline()
    m=re.search(r'(\d+\.\d+)\s*[—–-]\s*(\d+\.\d+)',head) or re.search(r'(\d+\.\d+)',head)
    if not m:return ['稿首第一行没写朱注章号']
    z1,z2=m.group(1),m.group(m.lastindex);M=zhu2tong()
    zs=[k for k in M if key(z1)<=key(k)<=key(z2)]
    ts=sorted({t for k in zs for t in M[k]},key=key)
    want=f'{ts[0]}—{ts[-1]}' if len(ts)>1 else ts[0]
    fs=glob.glob(os.path.join(a.dv,'发布单.json'))
    if not fs:return ['缺 发布单.json']
    txt=open(fs[0],encoding='utf-8').read();bad=[]
    for got in set(re.findall(r'通行本 ?(\d+\.\d+(?:—\d+\.\d+)?)',txt)):
        if got!=want:bad.append(f'发布单写通行本 {got}，稿首朱注 {z1}—{z2} 应为通行本 {want}')
    for got in set(re.findall(r'Analects (\d+\.\d+(?:–\d+\.\d+)?)',txt)):
        g2=got.replace('–','—')
        if g2!=want and not (len(ts)>1 and g2 in ts):bad.append(f'英文写 Analects {got}，应为 {want.replace("—","–")}')
    return bad
ZC='/mnt/project-files/一孔学-内-自媒体/规范/自查'
def ct008(a):
    """CT-008 繁体误转：定版目录里繁体字幕、标题简介跑回查线程 fanti_zha.py，命中须 0"""
    if not a.dv:return None
    r=subprocess.run([sys.executable,os.path.join(ZC,'fanti_zha.py'),a.dv],capture_output=True,text=True)
    return [l for l in r.stdout.splitlines() if l.strip() and not l.startswith('文件')][:20] if r.returncode else []
def ct009(a):
    """CT-009 发布单硬错（F01—F16）：成片根目录＋期名前缀跑 fabudan_zha.py，“错”须 0（--root 工坊 产出/Claude成片 --qi 期名）"""
    if not (a.root and a.qi):return None
    r=subprocess.run([sys.executable,os.path.join(ZC,'fabudan_zha.py'),a.root,a.qi],capture_output=True,text=True)
    return [l for l in r.stdout.splitlines() if '\t错\t' in l][:20]
def yujian(a):
    """常规·渲前预检：稿目录里最新稿要有不早于它的 预检.md"""
    if not a.gao:return None
    g=[f for f in glob.glob(a.gao+'/*-稿-v*.md') if '预检' not in f]
    if not g:return ['没找到稿']
    g=max(g,key=os.path.getmtime);p=glob.glob(a.gao+'/*预检*.md')
    p=[x for x in p if os.path.getmtime(x)>=os.path.getmtime(g)-60]
    return [] if p else [f'最新稿 {os.path.basename(g)} 没有不早于它的预检单']
CHECKS=[('CT-001a 读音漏锁',ct001_lou),('CT-001b 后加规则未测',ct001_hou),('CT-002 跨页红框',ct002),('CT-003 进度条',ct003),('CT-004 原页白边',ct004),('CT-005 英文章节书序',ct005),('CT-006 章号错位',ct006),('CT-007 锁读表回归',ct007),('CT-008 繁体误转',ct008),('CT-009 发布单',ct009),('常规 渲前预检',yujian)]
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--gao');ap.add_argument('--ep');ap.add_argument('--dv');ap.add_argument('--kind',default='论语长片');ap.add_argument('--pb');ap.add_argument('--root');ap.add_argument('--qi')
    a=ap.parse_args();rc=0
    for name,fn in CHECKS:
        r=fn(a)
        if r is None:print(f'跳过（缺输入） {name}');continue
        print(('过   ' if not r else '不过 ')+name+('' if not r else f'（{len(r)}）'))
        for x in r[:30]:print('     ',x)
        if r:rc=1
    print('== 错题本自查','全过' if not rc else '有不过，不许上台/交片');sys.exit(rc)
