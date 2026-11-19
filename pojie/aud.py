# 大字快答模板 · 配音与对拍：python3 aud.py <文案单目录名>
# 读 ep/<名>/spec.json，逐句送火山配音（audio_params 里开 enable_subtitle，随音频带回逐字起止时间），排成时间线，
# 产出 ep/<名>/tm.json（给网页对拍）和 voice.wav（整条人声）。配过的句子按“音色＋语速＋语气＋文字＋锁读”存在 ep/<名>/aud/，改哪句只重配哪句。
# 读音照锁读表（本目录的 tts_lock.py 和 phon.tsv，phon.tsv 是共享盘 技能/yikong-wenzi-yujian/references/配音拼音锁读表.tsv 的拷贝，要常换新；
# 环境变量 YK_DP 可以指到别的目录），文案单里 lock 一栏可以再加本条专用的锁读。
# 密钥只从环境变量 VOLC_TTS_KEY 取，不落盘、不打印。
import os, sys, json, base64, re, wave, hashlib, time, requests
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
sys.path.insert(0, os.environ.get('YK_DP') or HERE)      # 锁读模块和锁读表：默认用本目录里带的那份，环境变量 YK_DP 可以指到别处
import tts_lock as T
for _s in (sys.stdout, sys.stderr):      # 在 Windows 的计划任务里输出也用 UTF-8，免得中文变乱码
    try: _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
SPK, SR = os.environ.get('KD_SPEAKER') or 'zh_male_lubanqihao_uranus_bigtts', 48000      # 主人 11-18 定的热点片音色
RATE_ADD = int(os.environ.get('KD_RATE_ADD') or 25)      # 鲁班七号音色天生慢（同稿比原音色慢约三成），整体再提速，全片回到 26—29 秒
# 七个说话人（主人 11-18：“六位全轮，人物按照他们各自长片中的音色，恰当调整好语速”）：音色照工坊 角色固定声线-v1/声线注册表.json；
# 语速是在同一份稿上量出来的，让全片都落在 26—29 秒（RATE_ADD 是加在各句默认语速上的）
VOICES = {'dog': ('zh_male_lubanqihao_uranus_bigtts', 25), 'youli': ('ICL_uranus_zh_male_zifuqingnian_tob', 10), 'zhaojin': ('zh_female_lingling_uranus_bigtts', 30),
          'shouzhuo': ('zh_male_fanjuanqingnian_uranus_bigtts', -3), 'luchuan': ('zh_male_gaolengchenwen_uranus_bigtts', 21), 'liuqi': ('zh_female_jiaochuannv_uranus_bigtts', 60),
          'shahela': ('zh_female_gaolengyujie_uranus_bigtts', 10)}
def voice(who):
    """按说话人定音色和整体语速；环境变量 KD_SPEAKER、KD_RATE_ADD 优先（试音用）"""
    global SPK, RATE_ADD
    spk, ra = VOICES.get(who or 'dog', VOICES['dog'])
    SPK = os.environ.get('KD_SPEAKER') or spk; RATE_ADD = int(os.environ.get('KD_RATE_ADD') or ra)
# 七句口播各归哪张卡（背景那一句可以不要）；没写语气、语速的用这里的默认
ROLES = [('ask', 1), ('hook', 1), ('story', 2), ('quote', 2), ('gloss', 3), ('twist', 4), ('view', 5)]
TONE = dict(ask='发问，带一点扎心', hook='带一点悬念', story='讲故事', quote='念原文，一句一顿，有分量', gloss='讲解，干脆', twist='先问，停一下；末句点破', view='像对朋友说，末句稳')
RATE = dict(quote=14)
HAN = re.compile(r'[一-鿿0-9A-Za-z]'); NUM = '零一二三四五六七八九十'      # 能对拍的字：汉字、数字、字母
han = lambda s: ''.join(HAN.findall(s))
dsp = lambda c: re.sub(r'@.*', '', c)                                   # “屏上字@口播里的字”只取屏上字
plain = lambda x: re.sub(r'[/*]', '', ''.join(dsp(c) for c in x) if isinstance(x, list) else dsp(x))
end = lambda s: s if s[-1] in '。？！…' else s + '。'
num = lambda n: NUM[n] if n <= 10 else ('十' + NUM[n - 10] if n < 20 else str(n))
wide = lambda s: sum(.56 if ord(c) < 128 else 1 for c in plain(s))     # 一行字有多宽（按汉字算，数字字母算半个多一点）

def roles(S):
    return [(r, c) for r, c in ROLES if r != 'story' or (S.get('story') and S['story'].get('say') is not False)]

def say(S, role):
    """口播稿：文案单里写了 say 就用它，没写就照屏上的字拼"""
    d = S[role]
    if d.get('say'): return d['say']
    if role == 'hook': return end(plain(d['show']))
    if role == 'story': return end((d['when'] + '，' if d.get('when') else '') + plain(d['show']))
    if role == 'quote': return end((d['lead'] + '：' if d.get('lead') else '') + '，'.join(d['key']))
    if role == 'gloss': return end('；'.join(plain(r) for r in d['rows']))
    if role == 'twist': return end(plain(d['head']) + d['big'] + '：' + plain(d['show']))
    if role == 'view': return end('一孔录的看法是：' + plain(d['show']))
    raise SystemExit(f'{role} 要写 say')

def check(S):
    """文案单的硬规矩（不过就停）和提醒（只打印）"""
    bad, warn = [], []; key = S['quote']['key']; n = len(''.join(key)); g = len(key)
    if not 2 <= len(S['ask']['big']) <= 3: bad.append('开头大字要两到三行')
    if max(wide(x) for x in S['ask']['big']) > 6.01: bad.append('开头大字每行不超过六个字（标点也算一个字）')
    if any(re.search(r'[^一-鿿]', k) for k in key): bad.append('金句的每一组只能是汉字（标点不要写进去）')
    if n > 16 or g > 4 or max(len(k) for k in key) > 5: bad.append(f'金句太长：现在 {n} 个字、{g} 组；上限是十六个字、四组、每组五个字')
    if len(S['gloss']['rows']) != g or len(S['view']['rows']) != g: bad.append('金句分了几组，白话和收藏卡就要有几行')
    if not 1 <= len(S['twist']['big']) <= 6 or re.search(r'[^一-鿿]', S['twist']['big']): bad.append('反转的大词要一到六个汉字')
    if num(n) + '个字' not in say(S, 'hook'): warn.append(f'钩子里没有“{num(n)}个字”（金句是 {n} 个字），字牌的数目和口播对不上号')
    if S['twist'].get('src') and S['twist']['big'] not in S['twist']['src']: warn.append('反转的大词不在注家原话里')
    if '一孔录的看法是' not in say(S, 'view'): warn.append('最后一句没有“一孔录的看法是”（防搬运的自指句）')
    return bad, warn

def locks(S):
    """文案单里本条专用的锁读：[["几席", "ji1 xi2"], ["不可以(行)", "xing2"]]；括号里是要锁的字，括号外是上下文，没括号就整段都锁"""
    own = []
    for pat, py in S.get('lock') or []:
        m = re.fullmatch(r'([^()（）]*)[(（]([^()（）]+)[)）]([^()（）]*)', pat)
        rx = re.escape(m.group(1)) + '(?P<t>' + re.escape(m.group(2)) + ')' + re.escape(m.group(3)) if m else '(?P<t>' + re.escape(pat) + ')'
        own.append((re.compile(rx), py))
    T._PH[:0] = own
    return own

def key():
    """配音密钥：先看环境变量 VOLC_TTS_KEY、VOLCENGINE_SPEECH_API_KEY，再看工坊 .secrets/volcengine-tts.env（往上找三层；YK_SECRETS 可以指到别处）。只读不打印"""
    for n in ('VOLC_TTS_KEY', 'VOLCENGINE_SPEECH_API_KEY'):
        if os.environ.get(n): return os.environ[n]
    for d in [os.environ.get('YK_SECRETS')] + [os.path.join(HERE, *['..'] * k, '.secrets') for k in (1, 2, 3)]:
        f = d and os.path.join(d, 'volcengine-tts.env')
        if f and os.path.exists(f):
            for l in open(f, encoding='utf-8-sig'):
                k, _, v = l.strip().partition('=')
                if k.strip() == 'VOLCENGINE_SPEECH_API_KEY' and v.strip(): return v.strip().strip('"\'')
    return ''

def tts(text, out, ctx, rate):
    add = {'context_texts': ['用' + ctx + '的语气说']} if ctx else {}
    rp = {"text": text}; sp = T.phon_spans(text)
    if sp: rp = {"ssml": T.phon_ssml(text, sp)}; print('  锁读', [text[a:b] + ':' + p for a, b, p in sp])
    body = {"user": {"uid": "yk"}, "req_params": {**rp, "speaker": SPK,
            "audio_params": {"format": "pcm", "sample_rate": SR, "speech_rate": rate, "enable_subtitle": True},
            "additions": json.dumps(add, ensure_ascii=False)}}
    h = {"X-Api-Key": key(), "X-Api-Resource-Id": "seed-tts-2.0", "Content-Type": "application/json"}
    try: r = requests.post(T.URL, headers=h, json=body, stream=True, timeout=120)
    except requests.RequestException as e: print('  接口连不上：', type(e).__name__); return 0, []
    pcm = b''; words = []; done = False
    for line in r.iter_lines():
        if not line: continue
        try: j = json.loads(line)
        except ValueError: print('  接口回了一行看不懂的（状态码 %s），这一句重配' % r.status_code); return 0, []
        if j.get('code') == 20000000: done = True
        if j.get('data'): pcm += base64.b64decode(j['data'])
        w = (j.get('sentence') or {}).get('words')
        if w: words += w
        if j.get('code') not in (0, 20000000, None): print('  接口报错', j.get('code'), j.get('message'))
    if not done: return 0, []
    with wave.open(out, 'wb') as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm)
    return len(pcm) / (2 * SR), words

def chars(text, words):
    """把接口给的词（可能带标点、可能一词多字）摊回一个个能对拍的字：[[字, 起, 止], …]，并和稿子逐字核对。
    数字那一词接口给的止点不准（常常只有几十毫秒），所以一个词的止点取“自己的止点”和“下一个词的起点”里晚的那个。"""
    ws = [(HAN.findall(w['word']), w['startTime'], w['endTime']) for w in words]; ws = [w for w in ws if w[0]]; out = []
    for i, (hs, a, b) in enumerate(ws):
        if len(hs) > 1 and i + 1 < len(ws): b = max(b, ws[i + 1][1])
        for k, c in enumerate(hs): out.append([c, round(a + (b - a) * k / len(hs), 3), round(a + (b - a) * (k + 1) / len(hs), 3)])
    assert ''.join(c for c, _, _ in out) == han(text), ('逐字时间和稿对不上', ''.join(c for c, _, _ in out), han(text))
    return out

def main(ep):
    D = HERE + 'ep/' + ep + '/'; AUD = D + 'aud/'; os.makedirs(AUD, exist_ok=True)
    S = json.load(open(D + 'spec.json', encoding='utf-8')); bad, warn = check(S); voice(S.get('who'))
    for w in warn: print('提醒：' + w)
    if bad: raise SystemExit('文案单不合规矩：\n  ' + '\n  '.join(bad))
    base = list(T._PH); own = locks(S); res = []
    try: res = synth(S, AUD, own)
    finally: T._PH[:] = base                         # 本条专用的锁读用完就撤，免得一次跑几条时串到下一条
    return line(S, D, res)

def synth(S, AUD, own):
    res = []
    for role, card in roles(S):
        text = say(S, role); ctx = S[role].get('tone', TONE[role]); rate = S[role].get('rate', RATE.get(role, 20)) + RATE_ADD; n = len(han(text))
        sig = ''.join(f'|{m.start("t")}:{py}' for rx, py in own for m in rx.finditer(text))      # 本条专用的锁读变了要重配
        key = hashlib.sha1(f'{SPK}|{rate}|{ctx}|{text}{sig}'.encode()).hexdigest()[:12]; wav = AUD + key + '.wav'; js = AUD + key + '.json'
        if not (os.path.exists(wav) and os.path.exists(js)):
            for k in range(4):      # 短句偶尔被合成截短、接口偶尔回坏行，不对就隔一会儿重配，最多四次
                d, words = tts(text, wav, ctx, rate)
                if d > 0.3 and d >= 0.13 * n and words: break
                time.sleep(1.5 * (k + 1))
            else: raise SystemExit(f'配音四次都没成（全是 403 多半是余额用完了，要请主人充值）：{text}')
            json.dump({'text': text, 'dur': d, 'ch': chars(text, words)}, open(js, 'w', encoding='utf-8'), ensure_ascii=False)
        m = json.load(open(js, encoding='utf-8')); res.append((role, card, text, m['dur'], m['ch'], wav))
        print('%-5s %.2f 秒 %2d 字 %.1f 字/秒  %s' % (role, m['dur'], n, n / m['dur'], text))
    return res

def line(S, D, res):
    # 排时间线：开头留 0.10 秒；同一张卡里两句间隔 0.08 秒；换卡间隔 0.24 秒；
    # 没有背景那一句时，钩子说完到念原文之间留 0.7 秒（换卡、字牌抖一下，再开念）；
    # 原文念完到讲白话之间留 0.58 秒（金句全翻开、光爆，停一拍让人看清整句）；末尾定格 1.8 秒
    t = 0.10; tl = []; buf = np.zeros(0, np.float32)
    YYGAP = os.path.exists(D + 'yy.json'); FX = S.get('fx') or {}; PZ = None
    for i, (role, card, text, d, ch, wav) in enumerate(res):
        if i: t += 0.7 if role == 'quote' and res[i - 1][0] == 'hook' else 0.58 if res[i - 1][0] == 'quote' else 0.24 if card != res[i - 1][1] else 0.08
        if i and FX.get('pause') and res[i - 1][0] == 'hook':      # 破界“主持人按停”：钩子念完、金句出来前整段停住（画面定格、全静音，再倒数三声）
            PZ = [round(tl[-1]['t1'] - .06, 3), FX['pause']]; t += FX['pause']
        if i and YYGAP and role == 'quote': t += 0.25          # 有原页段（ep/<名>/yy.json）：原页飞进来多留 0.25 秒
        if i and YYGAP and res[i - 1][0] == 'quote': t += 0.45   # 念完，字从原页飞到字牌上多留 0.45 秒
        tl.append({'role': role, 'card': card, 'text': text, 't0': round(t, 3), 't1': round(t + d, 3), 'ch': [[c, round(t + a, 3), round(t + b, 3)] for c, a, b in ch]})
        w = wave.open(wav); x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        n0 = int(round(t * SR)); buf = np.concatenate([buf, np.zeros(max(0, n0 + len(x) - len(buf)), np.float32)]); buf[n0:n0 + len(x)] += x
        t += d
    dur = round(t + 1.8, 3); buf = np.concatenate([buf, np.zeros(int(dur * SR) - len(buf), np.float32)])
    with wave.open(D + 'voice.wav', 'wb') as w: w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(buf, -1, 1) * 32767).astype(np.int16).tobytes())
    tm = {'dur': dur, 'lines': tl}
    if FX: tm['fx'] = {'pause': PZ, 'land': FX.get('land', 0)}
    json.dump(tm, open(D + 'tm.json', 'w', encoding='utf-8'), ensure_ascii=False)
    nh = sum(len(x['ch']) for x in tl); print('全片 %.1f 秒；口播 %d 个字' % (dur, nh))
    if dur - (PZ[1] if PZ else 0) > 32: print('提醒：全片（不算按停）超过 32 秒，大字快答要短，建议删字')
    return dur, nh

if __name__ == '__main__': main(sys.argv[1])
