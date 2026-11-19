# 大字快答模板 · 合音：python3 mix.py <文案单目录名> [music|both]
# 人声 ep/<名>/voice.wav ＋ 照网页给的音效清单 out/sfx.json 现合成的动效声（全是程序算出来的，不用外来素材）→ out/a.wav，再和无声视频 out/v.mp4 合成 out/<名>.mp4
# 后面加 music：成片 out/<名>.mp4 就带配乐（配乐也是程序现算的）；加 both：不带配乐的 out/<名>.mp4 和带配乐的 out/<名>-配乐版.mp4 各出一条，给人对比着听
# 成片的声音是左右一样的双声道，整条响度拉到 -15 LUFS 上下（手机上刷到的短视频大多在 -14 前后，太轻了显得没劲），峰值压在 -2 dBFS 以下（转成 AAC 以后会冒高一点，留出余量）
import sys, os, re, json, wave, subprocess
import numpy as np
from scipy.signal import butter, lfilter
from scipy.ndimage import minimum_filter1d
SR = 48000; rng = np.random.default_rng(7); HERE = os.path.dirname(os.path.abspath(__file__)) + '/'
TARGET, CEIL = -15.0, 0.79
for _s in (sys.stdout, sys.stderr):      # 在 Windows 的计划任务里输出也用 UTF-8，免得中文变乱码
    try: _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
def bp(x, lo, hi): b, a = butter(2, [lo / (SR / 2), min(hi / (SR / 2), .99)], 'band'); return lfilter(b, a, x)
def lp(x, f): b, a = butter(2, min(f / (SR / 2), .99)); return lfilter(b, a, x)
def T(d): return np.arange(int(d * SR)) / SR
def hit(p):      # 重音：下坠的低频“咚”加一下短促的敲击
    t = T(.36); f = 42 * p + 110 * p * np.exp(-t / .03); x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / .1)
    return x + .5 * bp(rng.standard_normal(len(t)), 900, 5000) * np.exp(-t / .006)
def boom(p):     # 大爆点：更长更沉的一声，带一阵闷响
    t = T(.8); f = 34 * p + 80 * p * np.exp(-t / .08); x = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / .26)
    return x + .4 * lp(rng.standard_normal(len(t)), 380) * np.exp(-t / .14)
def tick(p): t = T(.05); return .6 * np.sin(2 * np.pi * 1500 * p * t) * np.exp(-t / .007) + .5 * bp(rng.standard_normal(len(t)), 3000, 9000) * np.exp(-t / .003)
def clack(p):    # 牌落桌面
    t = T(.12); return bp(rng.standard_normal(len(t)), 1500 * p, 4200 * p) * np.exp(-t / .011) * 1.4 + .7 * np.sin(2 * np.pi * 210 * p * t) * np.exp(-t / .028)
def flip(p):     # 翻牌：一声短促的扇风加落定
    t = T(.2); w = bp(rng.standard_normal(len(t)), 500, 2600) * np.sin(np.pi * np.minimum(t / .1, 1)) ** 2 * .5; c = np.zeros(len(t)); k = clack(p * 1.15); n0 = int(.095 * SR); c[n0:n0 + len(k)] = k[:len(t) - n0]
    return w + c
def whoosh(p):   # 甩镜、冲击波
    t = T(.36 / p); n = rng.standard_normal(len(t)); env = np.sin(np.pi * t / t[-1]) ** 2; a = lp(n, 900); b = bp(n, 1200, 5200)
    m = np.clip(t / t[-1] * 2, 0, 1); return (a * (1 - m) + b * m) * env * 1.6
def riser(p):
    t = T(.45); n = rng.standard_normal(len(t)); m = (t / t[-1]) ** 2; return (lp(n, 600) * (1 - m) + bp(n, 2000, 9000) * m) * m * 1.5
def shutter(p):
    t = T(.2); x = np.zeros(len(t))
    for d, g in ((0, 1), (.075, .8)):
        k = bp(rng.standard_normal(int(.03 * SR)), 2500, 9000) * np.exp(-np.arange(int(.03 * SR)) / SR / .005); n0 = int(d * SR); x[n0:n0 + len(k)] += g * k
    return x * 1.6
def land(p):     # 破界“小屏撑满”的撑开声：56 赫兹一声闷响加一阵粉噪（照 11-19 主人听过的样片）
    t = T(.5); x = np.sin(2 * np.pi * 56 * p * t) * np.clip(1 - (t - .02) / .48, 0, 1)
    n = np.cumsum(rng.standard_normal(int(.3 * SR))); n = lp(n - lp(n, 20), 1200); n /= max(1e-9, np.abs(n).max()); x[:len(n)] += .5 * n * (1 - np.arange(len(n)) / len(n)); return x
def cnt(p): t = T(.07); return np.sin(2 * np.pi * 1500 * p * t) * (1 - t / .07)      # 破界“主持人按停”的倒数：1500 赫兹短“嘀”
REL = dict(land=.6, cnt=.21)      # 这两种不跟整条一起调响度，按成片里的绝对峰值放（照主人 11-19 听过的样片量的：撑开声约 0.6、倒数约 -13.5 dBFS）
GEN = dict(land=land, cnt=cnt, hit=(hit, .3), boom=(boom, .34), tick=(tick, .07), clack=(clack, .14), flip=(flip, .15), whoosh=(whoosh, .15), riser=(riser, .12), shutter=(shutter, .22))

# ———— 配乐（可选）：也是程序现算的，不用外来素材。五声音阶的拨弦（像筝）加一层轻鼓点，照换卡时刻分五段，翻牌时一块牌一个音往上走 ————
BEAT = 60 / 112                                                        # 每分钟 112 拍
SCALE = [220.00, 246.94, 293.66, 329.63, 369.99, 440.00, 493.88, 587.33, 659.25, 739.99, 880.00, 987.77, 1174.66, 1318.51, 1479.98, 1760.00]   # D 宫调五声，从 A3 往上
D4, E4, Fs4, A4, B4, D5, Fs5, A5, D6 = 293.66, 329.63, 369.99, 440.00, 493.88, 587.33, 739.99, 880.00, 1174.66
def pluck(f, d=1.1, bright=.55):                                       # 拨弦：一圈噪声来回滤着转（Karplus-Strong），先按整数周期算，再拉回准音高
    n = max(2, int(round(SR / f))); r = (n + .5) * f / SR; g = np.exp(-1 / (.9 * f)); N = int(d * SR * r) + 2 * n   # 来回滤一次多绕半个采样点，算音高时要算进去；衰减按时间定，高音低音收得一样快
    buf = lp(rng.uniform(-1, 1, 3 * n), 1500 + 7000 * bright)[n:2 * n]; buf -= buf.mean(); out = np.empty(N)
    for i in range(0, N, n): m = min(n, N - i); out[i:i + m] = buf[:m]; buf = g * .5 * (buf + np.roll(buf, 1))
    x = np.interp(np.arange(int(d * SR)) * r, np.arange(N), out); return x / max(1e-9, np.abs(x).max()) * np.minimum(1, np.arange(len(x)) / (.003 * SR))
def kick(): t = T(.3); return np.sin(2 * np.pi * np.cumsum(48 + 90 * np.exp(-t / .035)) / SR) * np.exp(-t / .12)
def hat(): t = T(.06); return bp(rng.standard_normal(len(t)), 7000, 12000) * np.exp(-t / .012)
def bass(f): t = T(.42); return (np.sin(2 * np.pi * f * t) + .35 * np.sin(4 * np.pi * f * t) + .15 * np.sin(6 * np.pi * f * t)) * np.exp(-t / .17) * np.minimum(1, t / .005)
def pad(fs, d):                                                        # 铺底的长音：每个音三条略微错开的正弦，慢起慢收
    t = T(d); x = sum(np.sin(2 * np.pi * f * t) + .8 * np.sin(2 * np.pi * f * 1.003 * t + 1.7) + .8 * np.sin(2 * np.pi * f * .997 * t + 3.1) + .25 * np.sin(4 * np.pi * f * t + .5) for f in fs)
    a = int(min(.5, d / 3) * SR); e = np.ones(len(t)); e[:a] = np.sin(np.linspace(0, np.pi / 2, a)) ** 2; e[-a:] = np.cos(np.linspace(0, np.pi / 2, a)) ** 2; return x * e / len(fs)
def bgm(tm, ev, n):
    L = {l['role']: l for l in tm['lines']}; PZ = (tm.get('fx') or {}).get('pause'); X = [L['hook']['t1'] - .06 + (PZ[1] if PZ else 0), L['gloss']['t0'] - .28, L['gloss']['t1'] - .02, L['twist']['t1'] - .02]; dur = n / SR
    S = [.07, X[0], X[1], X[2] + .21, X[3], dur]; b = np.zeros(n + 3 * SR)
    def put(t, x, g=1):
        n0 = int(t * SR)
        if 0 <= n0 < n: b[n0:n0 + len(x)] += x * g
    K, H = kick(), hat(); riff = [D5, 0, A4, 0, B4, A4, 0, Fs4, E4, 0, Fs4, 0, A4, 0, D5, 0]; root = [146.83] * 4 + [123.47, 123.47, 110.0, 110.0]
    def groove(s, e):                                                  # 带鼓点的段落：每拍一脚底鼓、反拍一下镲、贝斯跟根音、筝在八分音符上走一句两小节的小调子
        k = 0
        while s + k * BEAT / 2 < e - .12:
            t = s + k * BEAT / 2
            if k % 2 == 0: put(t, K, .32); put(t, bass(root[k // 2 % 8]), .22)
            else: put(t, H, .1)
            if riff[k % 16]: put(t, pluck(riff[k % 16], .9), .42 if k % 8 else .55)
            k += 1
    groove(S[0], S[1]); groove(S[2], S[3])
    # 念原文那一段：鼓点收掉，只留一个空五度长音；每翻一块牌拨一个音，顺着五声音阶往上走；全翻开时拨一个和弦
    put(S[1], pad([146.83, 220.0, 329.63], S[2] - S[1] + .3), .08); fl = [e['t'] for e in ev if e['type'] == 'flip']; i0 = 2 if len(fl) <= 10 else 0
    for i, t in enumerate(fl): put(t + .1, pluck(SCALE[min(i0 + i, len(SCALE) - 1)], 1.2), .55)
    tb = [e['t'] for e in ev if e['type'] == 'boom' and fl and e['t'] > fl[-1]]
    if tb:
        for f in (D4, A4, D5, Fs5): put(tb[0], pluck(f, 1.6), .4)
    # 反转那一段：换成低一点的长音（羽调），鼓点减半，筝隔两拍落一个音往下走
    put(S[3], pad([123.47, 185.0, 246.94], S[4] - S[3] + .3), .08); down = [B4, A4, Fs4, E4, D4, E4, Fs4, A4]; k = 0
    while S[3] + k * BEAT / 2 < S[4] - .12:
        t = S[3] + k * BEAT / 2
        if k % 4 == 0: put(t, K, .28); put(t, bass(123.47 if k % 16 < 8 else 110.0), .2)
        if k % 2: put(t, H, .07)
        if k % 4 == 0: put(t, pluck(down[k // 4 % 8], 1.3, .4), .38)
        k += 1
    # 收藏卡那一段：回到明亮的长音，筝往上爬一串，“收藏这张”砸下来时拨一个和弦，放着它响完
    put(S[4], pad([146.83, 220.0, 369.99], S[5] - S[4]), .09); up = [D4, Fs4, A4, D5, Fs5, A5, D6]; sh = [e['t'] for e in ev if e['type'] == 'shutter']; te = sh[0] if sh else S[5] - 1.8; k = 0
    while S[4] + k * BEAT / 2 < te - .3:
        t = S[4] + k * BEAT / 2
        if k % 2 == 0: put(t, K, .28); put(t, bass(146.83), .2)
        else: put(t, H, .09)
        put(t, pluck(up[k % 7], 1.0), .36); k += 1
    for f in (D4, A4, D5, Fs5): put(te, pluck(f, 2.2), .45)
    b = b[:n]; b[-int(.5 * SR):] *= np.linspace(1, 0, int(.5 * SR)); return b

def loud(path):
    """整条响度（LUFS），用 ffmpeg 自带的响度表量"""
    r = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', path, '-af', 'ebur128', '-f', 'null', '-'], capture_output=True, text=True, encoding='utf-8', errors='replace').stderr
    I = re.findall(r'I:\s*(-?[\d.]+) LUFS', r); return float(I[-1]) if I else None

def limiter(x, look=.010):
    """先看后压的限幅：只在超过上限的那一瞬把音量按下去，别处不动。给回 (压过的声音, 最多压了多少分贝)"""
    need = np.minimum(1.0, CEIL / np.maximum(np.abs(x), 1e-9)); n = int(look * SR)
    g = minimum_filter1d(need, 2 * n + 1, mode='nearest'); w = np.hanning(n | 1); w /= w.sum()
    g = np.convolve(np.pad(g, len(w) // 2, mode='edge'), w, 'valid'); return x * g, float(20 * np.log10(g.min()))

def main(ep, mode=''):
    D = HERE + 'ep/' + ep + '/'; w = wave.open(D + 'voice.wav'); v = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float64) / 32768
    ev = json.load(open(D + 'out/sfx.json', encoding='utf-8')); s = np.zeros(len(v) + SR)
    PZ = (json.load(open(D + 'tm.json', encoding='utf-8')).get('fx') or {}).get('pause')
    def gate(x):     # 主持人按停：这一段动效声、配乐全掐掉（两头各 20 毫秒淡出淡入），停完接着放
        if not PZ: return x
        a, b = int(PZ[0] * SR), int((PZ[0] + PZ[1]) * SR); f = int(.02 * SR); g = np.ones(len(x)); g[a:b] = 0
        g[max(0, a - f):a] = np.linspace(1, 0, len(g[max(0, a - f):a])); g[b:b + f] = np.linspace(0, 1, len(g[b:b + f])); return x * g
    for e in ev:
        if e['type'] in REL: continue
        f, g = GEN[e['type']]; x = f(e.get('p', 1)) * g * e.get('g', 1); n0 = int(e['t'] * SR)
        if 0 <= n0 < len(s): s[n0:n0 + len(x)] += x[:len(s) - n0]
    s = gate(s)
    fa = np.zeros(len(v))      # 破界两声：响度调完再加，电平和样片一样
    for e in ev:
        if e['type'] not in REL: continue
        x = GEN[e['type']](e.get('p', 1)); x = x / max(1e-9, np.abs(x).max()) * REL[e['type']] * e.get('g', 1); n0 = int(e['t'] * SR)
        if 0 <= n0 < len(fa): fa[n0:n0 + len(x)] += x[:len(fa) - n0]
    print('人声峰值 %.2f 有效值 %.3f；音效峰值 %.2f 有效值 %.3f' % (np.abs(v).max(), np.sqrt((v ** 2).mean()), np.abs(s).max(), np.sqrt((s ** 2).mean())))
    m = v * 1.25 + s[:len(v)] * .58      # 音效压在人声下面：没人监听过，响度是照数值配的
    def wav(m):
        x = (np.clip(m, -1, 1) * 32767).astype(np.int16)
        with wave.open(D + 'out/a.wav', 'wb') as o: o.setnchannels(2); o.setsampwidth(2); o.setframerate(SR); o.writeframes(np.stack([x, x], 1).tobytes())
    def out(m, name):
        # 先照原样写一遍量整条响度，再整条提到 TARGET；提完冒过上限的那几下由限幅按住
        wav(m); a = loud(D + 'out/a.wav')
        if a is None: print('  量不出响度，这一条不调音量'); wav(m + fa)
        else:
            m, gr = limiter(m * 10 ** ((TARGET - a) / 20) + fa); wav(m); print('  整条响度 %.1f → %.1f LUFS，限幅最多压了 %.1f 分贝' % (a, loud(D + 'out/a.wav') or 0, -gr))
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', D + 'out/v.mp4', '-i', D + 'out/a.wav', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', '-shortest', D + f'out/{name}.mp4'], check=True)
    from collections import Counter
    print(len(ev), '个音效', dict(Counter(e['type'] for e in ev)), '；全片', round(len(v) / SR, 2), '秒')
    if mode != 'music': out(m, ep); print('不带配乐的一版 →', f'ep/{ep}/out/{ep}.mp4')
    if mode in ('music', 'both'):
        # 配乐整条压到有效值 0.02 上下（比人声低十四分贝左右），人声响的时候再让一让
        b = gate(bgm(json.load(open(D + 'tm.json', encoding='utf-8')), ev, len(v))); b *= .02 / max(1e-9, np.sqrt((b ** 2).mean())); b = np.clip(b, -.3, .3)
        env = lp(np.abs(v), 6); duck = 1 - .4 * np.clip(env / max(1e-9, np.percentile(env, 90)), 0, 1); b *= duck
        print('配乐峰值 %.2f 有效值 %.3f（人声放大后有效值 %.3f）' % (np.abs(b).max(), np.sqrt((b ** 2).mean()), np.sqrt(((v * 1.25) ** 2).mean())))
        name = ep if mode == 'music' else ep + '-配乐版'; out(m + b, name); print('带配乐的一版 →', f'ep/{ep}/out/{name}.mp4')
if __name__ == '__main__': main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else '')
