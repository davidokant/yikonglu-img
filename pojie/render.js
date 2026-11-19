// 大字快答模板 · 逐帧出片：node render.js <文案单目录名> [秒,秒,…|check]
// 不带第二个参数＝出整条无声视频 ep/<名>/out/v.mp4 和音效清单 out/sfx.json；带“秒,秒”＝只截这几帧到 out/；带 check＝只做机检不出片。
// 网页服务自带（srv.js），不用另起；要装 playwright（带 chromium）和 ffmpeg。
const { chromium } = require('playwright'); const { spawn } = require('child_process'); const fs = require('fs'); const path = require('path'); const serve = require('./srv.js');
(async () => {
  const ep = process.argv[2], only = process.argv[3], fps = 30, out = path.join(__dirname, 'ep', ep, 'out'); fs.mkdirSync(out, { recursive: true });
  const srv = await serve(), b = await chromium.launch(), bye = async c => { await b.close(); srv.close(); process.exit(c); };
  const pg = await b.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
  pg.on('pageerror', e => console.log('[页面报错]', e.message)); pg.on('console', m => { if (m.type() === 'error') console.log('[控制台]', m.text()); });
  await pg.goto(`${srv.url}kd.html?ep=${encodeURIComponent(ep)}${process.env.KD_DOG ? '&dog=' + encodeURIComponent(process.env.KD_DOG) : ''}${process.env.KD_WHO ? '&who=' + process.env.KD_WHO : ''}${process.env.KD_YY ? '&yy=' + process.env.KD_YY : ''}`, { waitUntil: 'networkidle' });
  await pg.waitForFunction(() => window.READY || window.ERR, null, { timeout: 30000 });
  const err = await pg.evaluate(() => window.ERR); if (err) { console.log('出不了片：' + err); await bye(1); }
  await pg.evaluate(() => document.fonts.ready); await pg.waitForTimeout(300);
  const info = await pg.evaluate(() => window.INFO), chk = await pg.evaluate(() => window.CHK);
  console.log(`${ep}：全片 ${info.dur} 秒，金句 ${info.n} 个字分 ${info.g} 组，换卡在 ${info.cuts.map(x => x.toFixed(2)).join('、')} 秒`);
  const dn = await pg.evaluate(() => window.DOGNOTE || []); if (dn.length) console.log('柯基提醒：' + dn.join('；'));
  console.log(chk.length ? '机检有 ' + chk.length + ' 条要改：\n  ' + chk.join('\n  ') : '机检：字都放得下，都在安全区里');
  fs.writeFileSync(path.join(out, 'sfx.json'), JSON.stringify(await pg.evaluate(() => window.SFX)));
  fs.writeFileSync(path.join(out, 'fx.json'), JSON.stringify({ fx: info.fx || null, note: info.fxnote || [] })); if (info.fx && (info.fx.pause || info.fx.land)) console.log(`破界：${info.fx.land ? '小屏撑满 ' + info.fx.land.t.toFixed(2) + ' 秒' : '不带小屏撑满'}；${info.fx.pause ? '按停 ' + info.fx.pause.t.toFixed(2) + ' 秒起停 ' + info.fx.pause.dur + ' 秒，字“' + info.fx.pause.cap + '”' : '不带按停'}${(info.fxnote || []).length ? '（' + info.fxnote.join('；') + '）' : ''}`);
  if (only === 'check') await bye(chk.length ? 2 : 0);
  if (only) { for (const t of only.split(',')) { await pg.evaluate(t => window.seek(t), +t); await pg.screenshot({ path: path.join(out, `f_${(+t).toFixed(2)}.png`) }); } await bye(0); }
  const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'mjpeg', '-i', '-', '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p', path.join(out, 'v.mp4')]);
  ff.stderr.on('data', d => process.stdout.write(d)); ff.on('error', e => { console.log('起不了 ffmpeg：' + e.message); bye(1); });
  const n = Math.round(info.dur * fps), t0 = Date.now();
  for (let f = 0; f < n; f++) { await pg.evaluate(t => window.seek(t), f / fps); const buf = await pg.screenshot({ type: 'jpeg', quality: 96 }); if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r)); }
  ff.stdin.end(); const code = await new Promise(r => ff.on('close', r)); console.log(`出了 ${n} 帧，用时 ${((Date.now() - t0) / 1000).toFixed(0)} 秒`); await bye(code ? 1 : 0);
})();
