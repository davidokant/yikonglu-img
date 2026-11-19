# 热点短片出片线接错题本自查（主人 11-19“自查没过的不出片”；协调者 11-19 交代接上 规范/错题本/zicha.py）
# 用法：python zicha_kd.py <编号>   退出码 0＝全过，1＝有不过（kd.py 据此不交这条片）
# zicha.py、锁读回归例句.tsv 从共享盘 规范/错题本/ 拷进本目录，原样不改；这里只把它读的锁读表指到本目录的 phon.tsv（电脑上没有共享盘路径），
# 再按“热点”只跑用得上的几支（进度条 CT-003、锁读表回归 CT-007），其余缺输入的照 zicha 的规矩记“跳过（缺输入）”
import os, sys, types
HERE = os.path.dirname(os.path.abspath(__file__))
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
sys.path.insert(0, HERE)
import zicha
zicha.SK = os.path.join(HERE, 'phon.tsv'); zicha.HERE = HERE
def main(ep):
    a = types.SimpleNamespace(gao=None, ep=None, dv=None, kind='热点', pb=os.path.join(HERE, 'ep', ep, 'out', 'pb.json'), root=None, qi=None)
    if not os.path.exists(a.pb): a.pb = None
    rc = 0
    for name, fn in zicha.CHECKS:
        try: r = fn(a)
        except Exception as e: r = [f'检查本身出错：{type(e).__name__} {e}']
        if r is None: print(f'跳过（缺输入） {name}'); continue
        print(('过   ' if not r else '不过 ') + name + ('' if not r else f'（{len(r)}）'))
        for x in r[:30]: print('     ', x)
        if r: rc = 1
    print('== 错题本自查', '全过' if not rc else '有不过，这条不出片'); return rc
if __name__ == '__main__': sys.exit(main(sys.argv[1]))
