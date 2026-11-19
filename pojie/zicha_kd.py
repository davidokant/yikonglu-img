# 热点短片出片线接错题本自查（主人 11-19“自查没过的不出片”；协调者 11-19 交代接上 规范/错题本/zicha.py）
# 用法：python zicha_kd.py <编号>   退出码 0＝全过，1＝有不过（kd.py 据此不交这条片）
# zicha.py、锁读回归例句.tsv 从共享盘 规范/错题本/ 拷进本目录，原样不改；这里只把它读的锁读表指到本目录的 phon.tsv（电脑上没有共享盘路径），
# 再按“热点”只跑用得上的几支（进度条 CT-003、锁读表回归 CT-007、本文件自带的原页段夹字 CT-022h），其余缺输入的照 zicha 的规矩记“跳过（缺输入）”
import os, sys, types
HERE = os.path.dirname(os.path.abspath(__file__))
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
sys.path.insert(0, HERE)
import zicha
zicha.SK = os.path.join(HERE, 'phon.tsv'); zicha.HERE = HERE
def jiazi(a):
    """CT-022 热点版（11-20）：原页段一段一个红框，同一段里相邻两字之间空出半格以上＝框里夹着不讲的字（朱注、音注）。yyku.segs 已在夹缝处断段，这里兜底"""
    if not a.yy or not os.path.exists(a.yy): return None
    import json; Y = json.load(open(a.yy, encoding='utf-8')); C = Y['ch']; bad = []
    for s in Y['seg']:
        for i, j in zip(s, s[1:]):
            p, c = C[i], C[j]
            if c[2] - p[4] > .5 * (p[4] - p[2]): bad.append(f'原页段红框“{"".join(C[k][0] for k in s)}”里 {p[0]}、{c[0]} 之间夹着不讲的字')
    return bad
def main(ep):
    class NS(types.SimpleNamespace):
        def __getattr__(self, k): return None      # zicha 以后加的参数（比如 xe）热点线都没有，一律当“缺输入”
    a = NS(kind='热点', pb=os.path.join(HERE, 'ep', ep, 'out', 'pb.json'), yy=os.path.join(HERE, 'ep', ep, 'yy.json'))
    if not os.path.exists(a.pb): a.pb = None
    rc = 0
    for name, fn in zicha.CHECKS + [('CT-022h 红框夹字（原页段）', jiazi)]:
        try: r = fn(a)
        except Exception as e: r = [f'检查本身出错：{type(e).__name__} {e}']
        if r is None: print(f'跳过（缺输入） {name}'); continue
        print(('过   ' if not r else '不过 ') + name + ('' if not r else f'（{len(r)}）'))
        for x in r[:30]: print('     ', x)
        if r: rc = 1
    print('== 错题本自查', '全过' if not rc else '有不过，这条不出片'); return rc
if __name__ == '__main__': sys.exit(main(sys.argv[1]))
