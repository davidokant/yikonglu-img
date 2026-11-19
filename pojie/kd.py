# 大字快答模板 · 一条命令批量出片：python kd.py <采集单.json 或放采集单的目录 …> [编号 …] [--out 出片目录] [--jobs 同时渲几条=2] [--music|--both] [--keep] [--tidy] [--force] [--no-tongbu]
# 每天用：python kd.py --daily <根目录> [--music --tidy]：读 <根>/收件/<北京日期>/ 里所有 json，出到 <根>/成片/<北京日期>/。计划任务每 10 分钟调一次即可：
#   已出过的不重渲，新来的才渲；上一轮还没跑完就直接退出（同一个出片目录里有“出片中.lock”且不到 40 分钟）。
# 出片目录里还写一份 发布单.json（标题、简介、话题、建议时刻、成片文件，给发布线程读）。
# 每条依次：转文案单（caiji2spec）→ 配音排时间线（aud）→ 机检 → 逐帧出片（render.js）→ 配声合成（mix）；全跑完打印一张总表。
# 哪条出错只停那一条，不耽误别的；有一条没出，退出码就是 1（计划任务据此报警）。给了 --out，总表另存一份 <出片目录>/出片结果.json，给后面的发布链读（每条带“提醒”：转文案单时查出的不合规矩处）。
# 中途断了重跑同一条命令：文案单、时间线、模板都没变的那几条不重渲（--force 一律重渲）。
# --music 成片带配乐；--both 不带配乐、带配乐各出一条（带配乐的叫 <编号>-配乐版.mp4，给人对比着听）；都不写就不带配乐。
# --keep 已经有 ep/<编号>/spec.json 的不被采集单覆盖；--tidy 出完片删掉这一条的中间文件（无声视频、合成音轨、截图），成片和配音缓存留着。
import sys, os, re, json, time, glob, shutil, hashlib, subprocess
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
sys.path.insert(0, HERE)
import aud, caiji2spec          # 这两个模块一进来就把输出改成 UTF-8 了
RUN = dict(capture_output=True, text=True, encoding='utf-8', errors='replace', cwd=HERE)
one = lambda r: (r.stdout + r.stderr).strip().replace('\n', ' ')

def stamp(ep, mode):
    """这一条出片用到的东西（文案单、时间线、页面和几个脚本、出哪种声音）合起来的指纹：指纹没变、成片还在，就不用重渲"""
    h = hashlib.sha1((mode or 'plain').encode())
    for f in [f'ep/{ep}/spec.json', f'ep/{ep}/tm.json', 'kd.html', 'dog.js', 'sg.js', 'chars.js', 'render.js', 'srv.js', 'mix.py']: h.update(open(HERE + f, 'rb').read())
    for f in [f'ep/{ep}/yy.json', f'ep/{ep}/yy.jpg']:
        if os.path.exists(HERE + f): h.update(open(HERE + f, 'rb').read())
    return h.hexdigest()

def render(job):
    """机检、出片、配声。给回 (编号, 成片路径们或 None, 没出的原因, 用了几秒)"""
    ep, mode, tidy, force, frozen = job; t0 = time.time(); o = f'{HERE}ep/{ep}/out/'; fs = [o + ep + '.mp4'] + ([o + ep + '-配乐版.mp4'] if mode == 'both' else [])
    try:
        st = stamp(ep, mode)
        if not force and all(os.path.exists(f) for f in fs) and os.path.exists(o + 'done.txt') and (frozen or open(o + 'done.txt').read() == st): return ep, fs, '', 0      # 出过片、条目没改：模板改了也不重渲（已交件的不换片）
        r = subprocess.run(['node', HERE + 'render.js', ep, 'check'], **RUN)
        if r.returncode: return ep, None, ('机检没过：' if r.returncode == 2 else '打不开页面：') + one(r), 0
        r = subprocess.run(['node', HERE + 'render.js', ep], **RUN)
        if r.returncode or not os.path.exists(o + 'v.mp4'): return ep, None, '出片失败：' + one(r), 0
        m = subprocess.run([sys.executable, HERE + 'mix.py', ep] + ([mode] if mode else []), **RUN)
        if m.returncode or not all(os.path.exists(f) for f in fs): return ep, None, '配声失败：' + one(m), 0
        z = subprocess.run([sys.executable, HERE + 'zicha_kd.py', ep], **RUN)      # 错题本自查（主人 11-19“自查没过的不出片”）：没过这条不交片，成片删掉免得被误取
        if z.returncode:
            for f in fs:
                if os.path.exists(f): os.remove(f)
            bad = [l.strip() for l in (z.stdout or '').splitlines() if l.strip().startswith(('不过', '回归', '进度条')) or l.startswith('      ')]
            return ep, None, '错题本自查没过：' + '；'.join(bad[:4]), 0
        if tidy:
            for f in [o + 'v.mp4', o + 'a.wav'] + glob.glob(o + 'f_*.png'):
                if os.path.exists(f): os.remove(f)
        open(o + 'done.txt', 'w').write(st); return ep, fs, '', time.time() - t0
    except Exception as e: return ep, None, f'{type(e).__name__}：{e}'.replace('\n', ' '), 0      # 比如这台电脑上没装 node

SLOTS = ['11:52', '12:26', '12:57', '18:43', '19:34', '20:16', '21:08']      # 建议发布时刻（北京），按条目顺序取，再按日子错开几分钟，不落整点
BAD = re.compile(r'(热搜|热榜|实时榜|热点榜|榜单)榜?第\s*[\d一二三四五六七八九十百两]+|[\d一二三四五六七八九十]+月[\d一二三四五六七八九十]+[日号]')

def pojie(ep):
    """破界两招（主人 11-19 定，隔条对照）：给出片结果、发布单记一栏，周报按撑开那一秒、按停那一秒比留存曲线。没有 out/fx.json 的（之前出的）记“不带”"""
    f = f'{HERE}ep/{ep}/out/fx.json'
    try: j = json.load(open(f, encoding='utf-8'))
    except Exception: return {'带': '不带'}
    x = j.get('fx') or {}; p, l = x.get('pause'), x.get('land')
    if not p and not l: return {'带': '不带'}
    return {'带': '两招' if p and l else '只带按停' if p else '只带撑满', '撑开秒': l and l['t'], '按停秒': p and p['t'], '按停多久': p and p['dur'], '说明': j.get('note') or []}

def pbwarn(ep):
    """进度条机检（11-19 加）：没过的在机检就拦下不出片；这里只把 out/pb.json 里记的并进“提醒”备查"""
    try: return ['进度条：' + x for x in json.load(open(f'{HERE}ep/{ep}/out/pb.json', encoding='utf-8'))]
    except Exception: return []

def fabu(items, R, out):
    """发布单：每条一项。标题、简介、话题采集单里给了（发布标题、发布简介、话题）就用，没给就照条目拼。标题不超过 20 个字（小红书的限）"""
    day = time.gmtime(time.time() + 8 * 3600); shift = day.tm_mday % 6; rows = []
    for n, (ep, it) in enumerate(items):
        r = R[ep]
        if not r['出片']: continue
        big = ''.join(b if i == 0 or it['屏上大字'][i - 1][-1] in '，。？！：、' else '，' + b for i, b in enumerate(it['屏上大字'])); q = it.get('经典原句') or ''.join(it['意群'])
        title = it.get('发布标题') or (big + '｜' + q if len(big + q) + 1 <= 18 else big)
        pm = re.match(r'《(.+?)》', it['篇章']); book = pm.group(1).replace('・', '·') if pm else it['篇章']
        fz = it['反转']; kb = it['口播']
        desc = it.get('发布简介') or '\n'.join([kb[0], f"{it.get('说话人') or '孔子'}说：{q}。（《{book}》）", f"{fz['问句'].replace('/', '')}{fz['注家'].replace('朱注', '朱熹')}说：{fz['注家原话']}", kb[6], it['评论句']])
        tags = it.get('话题') or ['#论语', '#国学', '#热点']
        tags = [t if t.startswith('#') else '#' + t for t in (tags.split() if isinstance(tags, str) else tags)]
        hh, mm = SLOTS[n % len(SLOTS)].split(':'); mm = int(mm) + shift
        warn = [w for w in [len(title) > 20 and f'标题超过 20 个字（{len(title)}）', BAD.search(title + desc) and '标题或简介里有哪个榜第几名或几月几日'] if w]
        cm = re.search(r'(\d+)\.(\d+)', it['篇章'])
        rows.append({'id': ep, 'chap': f'{cm.group(1)}.{cm.group(2)}' if cm else '', 'pian': book.split('·')[-1].strip(), 'title': title, 'desc': desc, 'tags': ' '.join(tags),
                     'when': f'{hh}:{mm:02d}', 'dur': r['秒'], 'zh': '简', 'url': it.get('网址', ''), 'grade': it.get('档', ''), 'approved': bool(it.get('approved') or it.get('主人点过')),
                     'files': {'成片': os.path.basename(r['成片'])}, 'pojie': r.get('破界') or {'带': '不带'}, 'warn': warn, 'hot': {'title': it['热点标题原文'], 'links': it.get('报道链接', []), 'risk': it.get('风险备注', '')}})
    json.dump(rows, open(os.path.join(out, '发布单.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

# 锁读表自动同步（11-20 加；协调者：锁读表常改，人手拷迟早漏）：每轮出片前从传输分支取共享盘最新的 phon.tsv、锁读回归例句.tsv。
# 分支上的版本由容器端定时任务（共享盘 .传输/redian-kd/sync/tongbu.sh）先过回归再推上来，另写 pojie/tongbu.json 记推送时刻。
# 拿到新版：先在临时目录跑错题本 CT-007 回归，过了才换进本目录（旧的备份到 _bak-tongbu\时刻\），不过就照旧并拦下新条。
# 拦下的情形：分支上的版本超过 TB_MAXH 小时没更新（容器端停了）；新版没过回归；取不到且本机上次取到已超过 TB_MAXH 小时。
# 拦下只拦还没配音的新条（出过片的照旧），原因写进出片结果，退出码 1，计划任务照常报警；下一轮（10 分钟后）自动再试。只同步数据，不同步代码。
TB_URL = os.environ.get('YK_TONGBU_URL') or 'https://github.com/davidokant/yikonglu-img.git'
TB_BR, TB_FILES, TB_MAXH = 'claude/project-thread-tzizrb', ['phon.tsv', '锁读回归例句.tsv'], 16
ZC7 = "import sys, zicha; zicha.SK, zicha.HERE = 'phon.tsv', '.'; r = zicha.ct007(None); [print(x) for x in r[:5]]; sys.exit(1 if r else 0)"      # 只跑错题本 CT-007 锁读表回归
def tongbu():
    """给回 (拦下的原因或 '', 一句说明)"""
    R, me, now = HERE + '_tongbu', HERE + 'tongbu.json', time.time()
    last = json.load(open(me, encoding='utf-8')).get('取到', 0) if os.path.exists(me) else 0
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0')
    g = lambda *a, **k: subprocess.run(['git', '-C', R] + list(a), capture_output=True, timeout=120, env=env, **k)
    try:
        if not os.path.isdir(R + '/.git'):
            shutil.rmtree(R, ignore_errors=True)
            r = subprocess.run(['git', 'clone', '-q', '--depth', '1', '--filter=blob:none', '--no-checkout', '--single-branch', '-b', TB_BR, TB_URL, R], capture_output=True, timeout=180, env=env)
            if r.returncode: raise RuntimeError('clone ' + r.stderr.decode('utf-8', 'replace').strip()[-200:])
        r = g('fetch', '-q', '--depth', '1', 'origin', TB_BR)
        if r.returncode: raise RuntimeError('fetch ' + r.stderr.decode('utf-8', 'replace').strip()[-200:])
        got = {}
        for f in TB_FILES + ['tongbu.json']:
            r = g('show', 'FETCH_HEAD:pojie/' + f)
            if r.returncode: raise RuntimeError(f'分支上没有 pojie/{f}')
            got[f] = r.stdout
        meta = json.loads(got.pop('tongbu.json').decode('utf-8'))
    except Exception as e:
        why = f'取不到最新锁读表（{type(e).__name__} {e}）'.replace('\n', ' ')
        if now - last < TB_MAXH * 3600: return '', why + f'，本机 {(now - last) / 3600:.1f} 小时前取到过，这轮照旧出'
        return why + ('，本机从没取到过' if not last else f'，本机上次取到已是 {(now - last) / 3600:.0f} 小时前'), ''
    age = (now - meta.get('推送', 0)) / 3600
    if age > TB_MAXH: return f'传输分支上的锁读表 {age:.0f} 小时没更新（容器端同步可能停了），怕不是最新', ''
    loc = {f: open(HERE + f, 'rb').read() if os.path.exists(HERE + f) else b'' for f in TB_FILES}
    ch = [f for f in TB_FILES if got[f] != loc[f]]
    if ch:
        T = HERE + '_tongbu_chk/'; shutil.rmtree(T, ignore_errors=True); os.makedirs(T)
        shutil.copy(HERE + 'zicha.py', T)
        for f in TB_FILES: open(T + f, 'wb').write(got[f])
        z = subprocess.run([sys.executable, '-c', ZC7], **dict(RUN, cwd=T))
        if z.returncode:
            bad = [l.strip() for l in ((z.stdout or '') + (z.stderr or '')).splitlines() if l.strip()]
            return '分支上的新锁读表没过回归，没换：' + '；'.join(bad[:3]), ''
        B = HERE + '_bak-tongbu/' + time.strftime('%Y%m%d-%H%M%S') + '/'; os.makedirs(B, exist_ok=True)
        for f in TB_FILES:
            if loc[f]: open(B + f, 'wb').write(loc[f])
            open(HERE + f, 'wb').write(got[f])
        import importlib; importlib.reload(aud.T)          # aud 一进来就读了锁读表，换了要重读
    json.dump({'取到': now, '推送': meta.get('推送'), 'sha1': {f: hashlib.sha1(got[f]).hexdigest()[:12] for f in TB_FILES}}, open(me, 'w', encoding='utf-8'), ensure_ascii=False)
    return '', ('锁读表换成最新：' + '、'.join(ch) + f'（旧的在 _bak-tongbu\\），' if ch else '锁读表已是最新，') + f'分支 {age:.1f} 小时前推送'

def main(argv):
    val = lambda k, d=None: argv[argv.index(k) + 1] if k in argv and argv.index(k) + 1 < len(argv) else d
    out, jobs = val('--out'), int(val('--jobs', 2)); mode = 'both' if '--both' in argv else 'music' if '--music' in argv else ''
    tidy, keep, force = '--tidy' in argv, '--keep' in argv, '--force' in argv
    if val('--daily'):
        d = time.strftime('%Y-%m-%d', time.gmtime(time.time() + 8 * 3600)); root = val('--daily')
        argv = [os.path.join(root, '收件', d)] + argv; out = os.path.join(root, '成片', d)
        if not os.path.isdir(argv[0]): print('今天（北京', d + '）还没有收件目录：', argv[0]); return 0
    lock = out and os.path.join(out, '出片中.lock')
    if lock and os.path.exists(lock) and time.time() - os.path.getmtime(lock) < 2400: print('上一轮还在出片（', lock, '），这轮跳过'); return 0
    if lock: os.makedirs(out, exist_ok=True); open(lock, 'w').write(time.strftime('%Y-%m-%d %H:%M:%S'))
    global TB_ERR
    TB_ERR, msg = tongbu() if '--no-tongbu' not in argv else ('', '这轮不同步锁读表（--no-tongbu）')
    print('锁读表同步：' + (msg or '拦下新条：' + TB_ERR))
    try: return run(argv, out, jobs, mode, tidy, keep, force)
    finally:
        if lock and os.path.exists(lock): os.remove(lock)

TB_ERR = ''
def run(argv, out, jobs, mode, tidy, keep, force):
    val = lambda k, d=None: argv[argv.index(k) + 1] if k in argv and argv.index(k) + 1 < len(argv) else d
    a = [x for i, x in enumerate(argv) if not x.startswith('--') and (i == 0 or argv[i - 1] not in ('--out', '--jobs', '--daily'))]
    if not a: print('用法：python kd.py <采集单.json> [编号 …] [--out 出片目录] [--jobs 2] [--music|--both] [--keep] [--tidy] [--force]'); return 2
    srcs = [f for x in a if os.path.exists(x) for f in (sorted(glob.glob(os.path.join(x, '*.json'))) if os.path.isdir(x) else [x])]; ids = [x for x in a if not os.path.exists(x)]
    IT, bad_src = {}, []
    for f in srcs:
        try:
            for it in caiji2spec.load(f): IT.setdefault(it['编号'], it)
        except Exception as e: bad_src.append(f'{os.path.basename(f)}：{type(e).__name__} {e}'.replace('\n', ' '))      # 多半是还没写完，下一轮再读
    src = '；'.join(srcs); have = list(IT); items = [x for x in have if not ids or x in ids] + [x for x in ids if x not in have]
    FROZEN = set()
    R = {ep: {'编号': ep, '出片': False, '秒': None, '字': None, '成片': None, '配乐版': None, '原因': '', '提醒': []} for ep in items}; ready = []
    for ep in items:                                  # 第一步、第二步：转文案单、配音（一条条来，配音很快）
        try:
            if ep not in have: raise SystemExit('采集单里没有这个编号')
            d = f'{HERE}ep/{ep}/'; h = hashlib.sha1(json.dumps(IT[ep], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
            if not force and os.path.exists(d + 'out/done.txt') and os.path.exists(d + 'tm.json'):      # 出过片、条目没改：不重转不重配（换了音色也不重配已出的）
                old = open(d + 'src.sha').read() if os.path.exists(d + 'src.sha') else h
                if old == h:
                    open(d + 'src.sha', 'w').write(h); tm = json.load(open(d + 'tm.json', encoding='utf-8'))
                    R[ep].update({'秒': round(tm['dur'], 1), '字': sum(len(aud.han(''.join(c[0] for c in L['ch']))) for L in tm['lines'])}); ready.append(ep); FROZEN.add(ep); continue
            if TB_ERR: raise SystemExit('锁读表不一定是最新，这条先不配音：' + TB_ERR)
            if not (keep and os.path.exists(f'{HERE}ep/{ep}/spec.json')): R[ep]['提醒'] = caiji2spec.one(IT[ep])
            dur, nh = aud.main(ep); R[ep].update({'秒': round(dur, 1), '字': nh}); ready.append(ep); open(d + 'src.sha', 'w').write(h)
        except (SystemExit, Exception) as e: R[ep]['原因'] = (str(e) or type(e).__name__).replace('\n', ' ')
    note = {}
    with ThreadPoolExecutor(max(1, jobs)) as ex:      # 第三步到第五步：机检、出片、配声（同时跑几条）
        for ep, fs, msg, sec in ex.map(render, [(ep, mode, tidy, force, ep in FROZEN) for ep in ready]):
            if not fs: R[ep]['原因'] = msg; continue
            if out:
                os.makedirs(out, exist_ok=True); fs = [shutil.copy(f, out) for f in fs]
            R[ep]['提醒'] = (R[ep]['提醒'] or []) + pbwarn(ep); R[ep].update({'破界': pojie(ep), '出片': True, '成片': os.path.abspath(fs[0]), '配乐版': os.path.abspath(fs[1]) if len(fs) > 1 else None}); note[ep] = f'出片 {sec:.0f} 秒' if sec else '没变，用上回出的'
    print('\n—— 总表 ——')
    for ep in items:
        r = R[ep]; print(ep, '｜', '｜'.join(([f"{r['秒']} 秒", f"{r['字']} 字"] if r['秒'] else ['—', '—']) + ([note[ep] + ' → ' + r['成片'] + ('（成片带配乐）' if mode == 'music' else '（另有配乐版）' if mode == 'both' else '')] if r['出片'] else ['没出：' + r['原因']])))
    bad = [ep for ep in items if not R[ep]['出片']]; print(f'{len(items) - len(bad)} 条出片，{len(bad)} 条没出' + ('：' + '、'.join(bad) if bad else ''))
    for b in bad_src: print('读不了的采集单：' + b)
    if out:
        os.makedirs(out, exist_ok=True)
        json.dump({'采集单': src, '读不了的采集单': bad_src, '出完时刻': time.strftime('%Y-%m-%d %H:%M:%S'), '声音': {'': '不带配乐', 'music': '带配乐', 'both': '两版都出'}[mode], '条目': [R[ep] for ep in items]},
                  open(os.path.join(out, '出片结果.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        fabu([(ep, IT[ep]) for ep in items if ep in IT], R, out)
    return 1 if bad or bad_src else 0

if __name__ == '__main__': sys.exit(main(sys.argv[1:]))
