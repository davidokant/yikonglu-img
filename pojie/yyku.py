# 原页段备料（主人 11-18 定“乙 只飞原页段”）：按采集单“篇章”里的章号，从 yyku/ 原页库取《论语集注》原页，
# 找出金句每个字的位置，切到版框（四边留 2.5%；跨页时下一页拼在左边），出 ep/<编号>/yy.jpg 和 yy.json。
# 库外的（不是《论语》、章号不认、金句在原页上找不到）不出，这条照旧版出片，只记一条提醒。
import os, re, json
import numpy as np
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__)) + '/'; LIB = HERE + 'yyku/'; _IDX = None
han = lambda s: ''.join(c for c in s if '一' <= c <= '鿿' or '㐀' <= c <= '䶿')

def _frame(a):
    d = a < 110; H, W = a.shape
    xs = np.where(d[int(H * .2):int(H * .8)].mean(0) > .55)[0]; ys = np.where(d[:, int(W * .2):int(W * .8)].mean(1) > .55)[0]
    if len(xs) < 2 or len(ys) < 2: return 0, 0, W - 1, H - 1
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())

def segs(cs):
    """金句的字按（页、列）分段，一段一个红框；同一列里两字之间空出半格以上（夹着朱注或别的字）也断开，免得框进不讲的字（错题本 CT-022，11-20 加）"""
    seg = []
    for k, c in enumerate(cs):
        p = cs[k - 1] if k else None
        if not seg or (p[1], p[2]) != (c[1], c[2]) or c[4] - p[6] > .5 * (p[6] - p[4]): seg.append([])
        seg[-1].append(k)
    return seg

def build(it, S, d, warn):
    for f in ('yy.json', 'yy.jpg'):
        if os.path.exists(d + f): os.remove(d + f)
    global _IDX
    mm = re.search(r'(\d{8})-(\d+)$', it.get('编号', ''))
    import time; bj = time.strftime('%Y%m%d%H', time.gmtime(time.time() + 8 * 3600))
    if mm and (mm.group(1) < '20261119' or (mm.group(1) == '20261119' and bj < '2026111913')): return False      # 11-19 晚批起用（北京 13 点后转的单），午批照旧版；晚批编号可能从 03 接着排
    pz = it.get('篇章', ''); m = re.search(r'(\d+)\.(\d+)', pz)
    if '论语' not in pz or not m: return False
    if _IDX is None:
        if not os.path.exists(LIB + 'index.json'): warn.append('没有原页库 yyku/，这条不放原页'); return False
        _IDX = json.load(open(LIB + 'index.json', encoding='utf-8'))
    ch = f'{int(m.group(1))}.{int(m.group(2))}'; e = _IDX.get(ch)
    if not e: warn.append(f'原页库里没有 {ch}，这条不放原页'); return False
    q = han(''.join(S['quote']['key'])); txt = ''.join(c[0] for c in e['ch']); i = txt.find(q)
    if i < 0: warn.append(f'金句“{q}”在 {ch} 原页上找不到（字不一样或章号不对），这条不放原页'); return False
    cs = e['ch'][i:i + len(q)]; pages = []
    for c in cs:
        if c[1] not in pages: pages.append(c[1])
    tiles = []
    for p in pages:
        im = Image.open(LIB + 'pages/' + e['pages'][p]['img']).convert('L'); a = np.asarray(im); x0, y0, x1, y1 = _frame(a); mg = int(.025 * max(x1 - x0, y1 - y0))
        box = (max(0, x0 - mg), max(0, y0 - mg), min(a.shape[1], x1 + mg), min(a.shape[0], y1 + mg)); tiles.append((p, im.crop(box), box))
    W = sum(t[1].width for t in tiles); H = max(t[1].height for t in tiles); out = Image.new('L', (W, H), 255); x = W; off = {}
    for p, c, box in tiles:
        x -= c.width; out.paste(c, (x, 0)); off[p] = (x - box[0], -box[1])
    pts = [[c[0], c[3] + off[c[1]][0], c[4] + off[c[1]][1], c[5] + off[c[1]][0], c[6] + off[c[1]][1]] for c in cs]
    if not all(0 <= p[1] < p[3] <= W and 0 <= p[2] < p[4] <= H for p in pts): warn.append(f'{ch} 金句有字切到版框外，这条不放原页'); return False
    seg = segs(cs)
    out.convert('RGB').save(d + 'yy.jpg', quality=88)
    json.dump({'chap': ch, 'w': W, 'h': H, 'ch': pts, 'seg': seg, 'pages': pages, 'src': '《论语集注》'}, open(d + 'yy.json', 'w', encoding='utf-8'), ensure_ascii=False)
    return True
