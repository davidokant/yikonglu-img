# 大字快答模板 · 把热点采集线程的条目转成文案单：python3 caiji2spec.py <采集单.json> [编号 …]
# 采集单里“条目”的每一条 → ep/<编号>/spec.json。不写编号就全转。转的时候顺手查一遍，读不懂、不合规矩的地方打印出来。
# 采集单要给的栏：编号、热点标题原文、屏上大字、意群、说话人、篇章、背景、逐组白话、反转{问句, 注家原话, 注家, 大词, 大白话}、
# 收藏句、评论句、口播（七句：事件、桥句、原句、白话、问句加注家原话、大白话、一孔之见）、锁读。
# 可选：热度暗示（盖在开头的一小条，不超过 12 个字，只用笼统说法，如“又上热搜了”“全网都在聊”；不写就是“热搜话题”）、
#       屏上标题（顶上那行原题想换个写法时给，比如不点名；不写就用热点标题原文）、日期和出处与榜位（只留底，不上屏）。
# 主人 2026-11-18 定：片子里不写是哪个榜、第几名、哪一天（容易过时）。热度暗示里带了这些就换回“热搜话题”，屏上大字和口播里带了就打印提醒。
# 反转的问句里可以用“/”标出当海报排两行时断在哪（如“远虑要/想多远？”），不标就由网页自己找词缝。
import sys, os, json, re
HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
for _s in (sys.stdout, sys.stderr):      # 在 Windows 的计划任务里输出也用 UTF-8，免得中文变乱码
    try: _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
D = '零一二三四五六七八九'
PUNC = '，。？！；：、,.?!;:'
wide = lambda s: sum(.56 if ord(c) < 128 else 1 for c in s)
def cn(n): return D[n] if n < 10 else ('十' + (D[n - 10] if n > 10 else '')) if n < 20 else D[n // 10] + '十' + (D[n % 10] if n % 10 else '')

NUM = r'[\d一二三四五六七八九十百两]+'
HEAT_BAD = re.compile(r'\d|第' + NUM + r'|' + NUM + r'月|' + NUM + r'[日号]|百度|微博|抖音|知乎|头条|快手|小红书|哔哩|B站|今天|昨天|前天|今日|昨日|本周|上周')      # 热度暗示里不能有的：数字、名次、日期、平台名、今天昨天
RANK = re.compile(r'(热搜|热榜|实时榜|热点榜|榜单)榜?第\s*' + NUM + r'|' + NUM + r'月' + NUM + r'[日号]')      # 屏上大字和口播里要提醒的：哪个榜第几名、几月几日
WARN = {}      # 编号 → 这一条转文案单时的提醒，kd.py 写进出片结果里

def clauses(s):
    """按标点拆成分句，标点留在分句尾巴上"""
    return [x for x in re.findall(r'[^，。？！；：、]+[，。？！；：、]*', s) if x.strip()]

def two_lines(cs):
    """几个分句排成两行：有分号就在分号后面断，没有就挑两行最接近一样长的断法。返回第二行从第几个分句开始"""
    if len(cs) < 2: return None
    for i, c in enumerate(cs[:-1]):
        if c[-1] == '；': return i + 1
    return min(range(1, len(cs)), key=lambda k: abs(wide(''.join(cs[:k])) - wide(''.join(cs[k:]))))

# 说话人轮换（主人 11-18：“每天7条，一人说一条”“六位全轮”）：编号尾号 01—07 依次是下面七位；采集单可填“角色”（中文名）改人。ROTATE_FROM 之前的编号一律柯基
WHO7 = ['dog', 'youli', 'zhaojin', 'shouzhuo', 'luchuan', 'liuqi', 'shahela']
WHO_CN = {'柯基': 'dog', '上官有理': 'youli', '有理': 'youli', '孔照今': 'zhaojin', '照今': 'zhaojin', '林守拙': 'shouzhuo', '守拙': 'shouzhuo', '陆川': 'luchuan',
          '阮流绮': 'liuqi', '流绮': 'liuqi', '莎赫拉': 'shahela', '莎赫拉公主': 'shahela'}
ROTATE_FROM = '20261119'
def speaker_of(it, warn):
    m = re.search(r'(\d{8})-(\d+)$', it['编号']); day, no = (m.group(1), int(m.group(2))) if m else ('', 1)
    if day and day < ROTATE_FROM: return 'dog'
    r = (it.get('角色') or '').strip()
    if r:
        if r in WHO_CN: return WHO_CN[r]
        warn.append(f'角色“{r}”不认识，按编号分')
    import datetime      # 按日错位轮换（主人 11-18 在周报线程点卡定）：角色和午晚批错开，周报才分得清是角色好还是时段好；11-19 日序为 0
    k = (datetime.date(int(day[:4]), int(day[4:6]), int(day[6:])) - datetime.date(2026, 11, 19)).days if day else 0
    return WHO7[(no - 1 + k) % 7]

# 破界两招（主人 11-19 点卡“两招稳版一起上，隔条对照”）：悬念处“主持人按停”、导入处“小屏撑满”。FX_FROM 起，北京日期单数日单号带、双数日双号带；
# 采集单可填 "破界": "带" 或 "不带" 改；带的条目 spec 里写 fx，配音时间线（aud.py）在钩子后插停顿，网页（kd.html）照它定格、撑开
FX_FROM = '20261120'; FX_PAUSE = 1.6
def fx_of(it, warn):
    m = re.search(r'(\d{8})-(\d+)$', it['编号']); day, no = (m.group(1), int(m.group(2))) if m else ('', 0)
    if not day or day < FX_FROM: return None
    r = str(it.get('破界') or '').strip()
    on = (int(day[-2:]) % 2) == (no % 2) if r not in ('带', '不带') else r == '带'
    return {'pause': FX_PAUSE, 'land': 1} if on else None

def conv(it, warn):
    key = it['意群']; n = len(''.join(key)); kb = it['口播']; fz = it['反转']
    if len(kb) != 7: raise SystemExit(f"{it['编号']}：口播要七句，现在是 {len(kb)} 句")
    # 开头：大字照给的行，最后一行高亮
    big = list(it['屏上大字']); big[-1] = '*' + big[-1]
    ask = ''.join(b if i == 0 or it['屏上大字'][i - 1][-1] in PUNC else '，' + b for i, b in enumerate(it['屏上大字']))
    # 桥句：谁（哪本书）＋几个字＋后半句。“几个字”那一块高亮，字牌跟着它砸下来
    br = kb[1].rstrip('：:。 '); mm = re.match(r'(.*?)((?:十[一二三四五六]|[一二三四五六七八九十两])个字)[，,]?(.*)$', br)
    if mm: hook = [x for x in (mm.group(1), '*' + mm.group(2), '/' + mm.group(3) if mm.group(3) else '') if x]
    else:
        cs = clauses(br); k = two_lines(cs)
        hook = ['*' + ''.join(cs[:k]).rstrip(PUNC), '/' + ''.join(cs[k:])] if k else (['*' + br] if wide(br) <= 9 else [br[:len(br) // 2], '/*' + br[len(br) // 2:]])
        warn.append(f'桥句“{kb[1]}”里没有“{cn(n)}个字”：字牌砸下来时口播没报数，钩子弱一截；一句没有逗号的长桥句只能从中间硬断行')
    if mm and mm.group(2) != (('两' if n == 2 else cn(n)) + '个字'): warn.append(f'桥句说的是“{mm.group(2)}”，金句其实是 {n} 个字')
    # 背景：只上屏不念，太长就在最靠中间的逗号断成两行
    bg = it.get('背景') or ''; cs = clauses(bg); k = two_lines(cs) if wide(bg) > 21 else None
    story = {'show': [''.join(cs[:k]), '/' + ''.join(cs[k:])] if k else [bg], 'say': False} if bg else None
    # 原句：孔子说的就标“子曰”，别人说的标“某某曰”；篇章号改成“第几章”
    who = re.sub(r'[（(].*?[)）]', '', it.get('说话人') or '').strip(); lead = '子曰' if who == '孔子' else who + '曰' if who else ''
    pm = re.match(r'《论语[·・ ]*(.+?)》\s*(\d+)\.(\d+)', it['篇章'])
    frm = f'《论语 · {pm.group(1)}》第{cn(int(pm.group(3)))}章' if pm else it['篇章']; cite = '古答 · ' + (f'《论语 · {pm.group(1)}》' if pm else re.sub(r'[\d. ]+$', '', it['篇章']))
    # 反转：大白话拆成两行，最后一个分句高亮
    cs = clauses(fz['大白话'].rstrip('。')); k = two_lines(cs) or 0
    show = [('/' if i == k and k else '') + ('*' if i == len(cs) - 1 else '') + c for i, c in enumerate(cs)]
    if len(cs) >= 3 and max(wide(''.join(cs[:k])), wide(''.join(cs[k:]))) > 9: show = [('/' if i else '') + ('*' if i == len(cs) - 1 else '') + c for i, c in enumerate(cs)]      # 两行排不下就一个分句一行
    if len(fz['问句'].replace('/', '')) > 11: warn.append(f"反转问句“{fz['问句']}”连问号超过 11 个字：顶上那行标题放不下，机检会拦")
    if fz['大词'] not in fz['注家原话']: warn.append(f"大词“{fz['大词']}”不在注家原话里：黑牌只能等原话念完再落，对不上拍")
    by = '—— ' + re.sub(r'^朱注', '朱熹《论语集注》', fz['注家'])
    # 一孔之见：冒号后面的话排两行，第二行标红
    v = kb[6].split('：', 1)[-1]; cs = clauses(v); k = two_lines(cs)
    view = [''.join(cs[:k]), '/*' + ''.join(cs[k:]) + '*'] if k else [v]
    if '一孔录的看法是' not in kb[6]: warn.append('最后一句没有“一孔录的看法是”')
    sv = it['收藏句'].rstrip('。'); sv = '*收藏这张*' + sv[4:] if sv.startswith('收藏这张') else sv
    talk = it['评论句'] + ('' if '评论区' in it['评论句'] else '评论区见')
    # 锁读：只认“字 拼音”“字 拼音（上下文）”这两种写法
    lock = []
    for s in it.get('锁读') or []:
        if isinstance(s, list): lock.append(s); continue      # 已经是 ["不可以(行)", "xing2"] 这种写法的，原样用
        lm = re.match(r'^([一-鿿]+)\s+((?:[a-zü]+[1-5]\s*)+)(?:[（(]([^）)]+)[)）])?\s*$', s)
        if not lm or len(lm.group(1)) != len(lm.group(2).split()): warn.append(f'锁读“{s}”机器读不懂，没用上。请写成“几席 ji1 xi2”或“行 xing2（不可以行）”'); continue
        zi, py, ctx = lm.group(1), ' '.join(lm.group(2).split()), lm.group(3)
        lock.append([ctx.replace(zi, '(' + zi + ')', 1) if ctx and zi in ctx else zi, py])
    for i, s in enumerate(kb):
        if re.search(r'\d', s): warn.append(f'口播第 {i + 1} 句里有阿拉伯数字“{s}”：念法交给了配音自己猜，最好写成汉字')
    for where, s in [('屏上大字', ''.join(it['屏上大字'])), ('顶上那行原题', it.get('屏上标题') or it['热点标题原文'])] + [(f'口播第 {i + 1} 句', s) for i, s in enumerate(kb)]:
        if RANK.search(s): warn.append(f'{where}“{s}”里有哪个榜第几名或几月几日：主人定了片子里不写这些（容易过时），请改成笼统说法')
    heat = (it.get('热度暗示') or '').strip()
    if heat and (len(heat) > 12 or HEAT_BAD.search(heat)):
        warn.append(f'热度暗示“{heat}”' + ('超过 12 个字' if len(heat) > 12 else '里有数字、名次、日期、平台名或“今天”“昨天”这类说法') + '，开头那一小条换回了“热搜话题”'); heat = ''
    S = {'id': it['编号'], 'hot': {'title': it['热点标题原文'], 'source': it.get('出处与榜位', ''), 'date': it.get('日期', ''), 'links': it.get('报道链接', [])},
         'lan': '今问古答', 'heat': heat or '热搜话题',
         'ask': {'full': it.get('屏上标题') or it['热点标题原文'], 'big': big, 'say': kb[0], 'tone': '讲新闻，干脆，带一点惊讶'},
         'hook': {'show': hook, 'say': kb[1], 'tone': '带一点悬念'},
         'quote': {'lead': lead, 'key': key, 'from': frm, 'say': kb[2], 'tone': '念原文，一句一顿，有分量', 'rate': 14},
         'gloss': {'rows': it['逐组白话'], 'say': kb[3], 'tone': '讲解，干脆', **({'basis': '释义据宋 · 朱熹《论语集注》'} if pm else {})},
         'twist': {'head': fz['问句'], 'src': fz['注家原话'], 'big': fz['大词'], 'show': show, 'by': by, 'say': kb[4] + kb[5], 'tone': '先问，停一下；念古人原话放慢一点；末句点破'},
         'view': {'tag': '热点', 'ask': ask, 'cite': cite, 'rows': [re.sub(r'[*/]', '', r) for r in it['逐组白话']], 'show': view, 'say': kb[6], 'tone': '像对朋友说，末句稳', 'save': sv, 'talk': talk},
         'lock': lock}
    if story: S['story'] = story
    S["who"] = speaker_of(it, warn)
    fx = fx_of(it, warn)
    if fx: S['fx'] = fx
    return S

def one(it):
    """一个条目 → ep/<编号>/spec.json，给回提醒"""
    warn = []; S = conv(it, warn); WARN[it['编号']] = warn; d = HERE + 'ep/' + it['编号'] + '/'; os.makedirs(d, exist_ok=True)
    json.dump(S, open(d + 'spec.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    try:
        import yyku; yyku.build(it, S, d, warn)          # 原页段备料（11-18 主人定乙）：出不了就照旧版，不耽误出片
    except Exception as e: warn.append(f'原页段备料出错（{type(e).__name__}：{e}），这条不放原页')
    print(it['编号'], '→ ep/' + it['编号'] + '/spec.json', '' if not warn else '\n  提醒：' + '\n  提醒：'.join(warn))
    return warn

def load(src):
    """读一份采集单：{"条目": [...]} 或者单独一个条目都认"""
    d = json.load(open(src, encoding='utf-8-sig'))
    return d['条目'] if isinstance(d, dict) and '条目' in d else [d] if isinstance(d, dict) and '编号' in d else d

def main(src, ids):
    done = []
    for it in load(src):
        if ids and it['编号'] not in ids: continue
        one(it); done.append(it['编号'])
    return done

if __name__ == '__main__': main(sys.argv[1], sys.argv[2:])
