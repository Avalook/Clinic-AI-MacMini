const { chromium } = require("/Users/quangdang/Projects/Dr4Women-MacMini/src/dashboard/node_modules/playwright");
const url = "file:///Users/quangdang/Projects/Dr4Women-MacMini/.claude/worktrees/clever-thompson-45b9eb/docs/kiem-toan-2026-10-19/BAO-CAO-DAY-DU.html";
(async () => {
  const b = await chromium.launch({ headless: true, executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" });
  const out = {};
  for (const mode of ["reduce", "no-preference"]) {
    const p = await b.newPage(); await p.emulateMedia({ reducedMotion: mode });
    for (const [w, h] of [[1280, 900], [375, 812]]) {
      await p.setViewportSize({ width: w, height: h }); await p.goto(url);
      const links = await p.$$eval("nav.toc a", as => as.map(a => a.getAttribute("href"))); const bad = [];
      for (const href of links) {
        await p.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }));
        await p.click(`nav.toc a[href="${href}"]`);
        await p.waitForFunction(() => true); 
        let prev = -1, stable = 0;
        for (let i = 0; i < 60 && stable < 4; i++) { await p.waitForTimeout(100); const y = await p.evaluate(() => Math.round(window.scrollY)); stable = (y === prev) ? stable + 1 : 0; prev = y; }
        const r = await p.evaluate(h => { const t = document.querySelector(h).getBoundingClientRect().top; return Math.round(t); }, href);
        if (Math.abs(r - 16) > 6 && !(r >= 0 && r < 40)) bad.push(href + " top=" + r);
      }
      out[mode + "_w" + w] = { links: links.length, notAtTop: bad };
    }
    await p.close();
  }
  console.log(JSON.stringify(out, null, 1)); await b.close();
})();
