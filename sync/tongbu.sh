#!/bin/bash
# 锁读表同步·容器端（11-20 热点破界线程建）：把共享盘最新的配音拼音锁读表、锁读回归例句先过错题本 CT-007 回归，过了推到
# yikonglu-img 分支 claude/project-thread-tzizrb 的 pojie/，并写 pojie/tongbu.json 记推送时刻。出片电脑上的 kd.py 每轮出片前从那里取。
# 没变也推一次 tongbu.json（电脑据推送时刻判断容器端是不是还活着，超过 16 小时没推就拦下新条）。
# 用法：bash tongbu.sh            定时任务和改完锁读表的线程都可以跑；退出码 0＝已推，1＝回归没过没推，2＝推不上去
# 只推数据（锁读表、回归例句），不推代码；zicha.py 改了要走“送电脑”那条路，由主人准。
set -u
SRC=/mnt/project-files/一孔学-内-自媒体
PH="$SRC/技能/yikong-wenzi-yujian/references/配音拼音锁读表.tsv"; HG="$SRC/规范/错题本/锁读回归例句.tsv"
BR=claude/project-thread-tzizrb; URL=${YK_TONGBU_URL:-https://github.com/davidokant/yikonglu-img.git}
LOG=${YK_TONGBU_LOG:-/mnt/project-files/.传输/redian-kd/sync/tongbu.log}
W=$(mktemp -d); trap 'rm -rf "$W"' EXIT
say(){ echo "$(TZ=Asia/Shanghai date '+%m-%d %H:%M') $*" | tee -a "$LOG"; }
git clone -q --depth 1 --filter=blob:none --no-checkout --single-branch -b $BR "$URL" "$W/r" || { say "推不上去：clone 失败"; exit 2; }
cd "$W/r" && git read-tree HEAD
mkdir "$W/c"; git show HEAD:pojie/zicha.py > "$W/c/zicha.py"     # 用电脑那边同一版 zicha 只跑 CT-007 锁读表回归
cp "$PH" "$W/c/phon.tsv"; cp "$HG" "$W/c/锁读回归例句.tsv"
if ! (cd "$W/c" && python3 -c "import sys, zicha; zicha.SK, zicha.HERE = 'phon.tsv', '.'; r = zicha.ct007(None); [print(x) for x in r[:5]]; sys.exit(1 if r else 0)" > out.txt 2>&1); then
  say "回归没过，没推：$(head -3 "$W/c/out.txt" | tr '\n' ' ')"; exit 1; fi
python3 - "$W/c" > "$W/c/tongbu.json" <<'EOF'
import sys, json, time, hashlib
d = sys.argv[1]
print(json.dumps({'推送': time.time(), '北京': time.strftime('%Y-%m-%d %H:%M', time.gmtime(time.time() + 8 * 3600)),
  'sha1': {f: hashlib.sha1(open(f'{d}/{f}', 'rb').read()).hexdigest()[:12] for f in ['phon.tsv', '锁读回归例句.tsv']}}, ensure_ascii=False))
EOF
for f in phon.tsv 锁读回归例句.tsv tongbu.json; do git update-index --add --cacheinfo 100644,$(git hash-object -w "$W/c/$f"),pojie/$f; done
CH=$(git -c core.quotePath=false diff --cached --name-only HEAD | grep -v tongbu.json | tr '\n' ' ')
git -c user.name="Claude" -c user.email="noreply@anthropic.com" commit -q -m "锁读表同步${CH:+（换了 $CH）}

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
for i in 1 2 3 4; do git push -q origin HEAD:$BR 2>/dev/null && { say "已推${CH:+，换了 $CH}（$(cut -c1-12 <<<"$(sha1sum "$W/c/phon.tsv")")）"; exit 0; }
  sleep $((i * 4)); git fetch -q --depth 1 origin $BR && git reset -q --soft FETCH_HEAD && git read-tree FETCH_HEAD &&
  for f in phon.tsv 锁读回归例句.tsv tongbu.json; do git update-index --add --cacheinfo 100644,$(git hash-object -w "$W/c/$f"),pojie/$f; done &&
  git -c user.name="Claude" -c user.email="noreply@anthropic.com" commit -q -m "锁读表同步" ; done
say "推不上去：push 四次都失败"; exit 2
