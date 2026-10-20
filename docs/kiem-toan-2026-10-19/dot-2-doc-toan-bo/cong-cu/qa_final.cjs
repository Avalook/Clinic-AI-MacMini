const { chromium } = require("/Users/quangdang/Projects/Dr4Women-MacMini/src/dashboard/node_modules/playwright");
const url = "file:///Users/quangdang/Projects/Dr4Women-MacMini/.claude/worktrees/clever-thompson-45b9eb/docs/kiem-toan-2026-10-19/BAO-CAO-DAY-DU.html";
(async () => {
  const b = await chromium.launch({ headless: true, executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" });
  const p = await b.newPage(); const errs = [], reqs = [];
  p.on("pageerror", e => errs.push(e.message)); p.on("request", r => reqs.push(r.url()));
  const out = {};
  for (const [w, h] of [[1280, 900], [375, 812]]) {
    await p.setViewportSize({ width: w, height: h });
    await p.goto(url);
    out[w] = await p.evaluate(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth, cards: document.querySelectorAll(".finding").length,
      wide: [...document.querySelectorAll("body *")].filter(e => e.getBoundingClientRect().right > document.documentElement.clientWidth + 1 && !e.closest(".tablewrap") && !e.closest("pre")).slice(0,4).map(e => e.tagName + "." + e.className) }));
  }
  await p.fill("#q", "SEC-020"); out.search = await p.evaluate(() => document.getElementById("cnt").textContent);
  await p.fill("#q", ""); await p.selectOption("#fs", "HIGH"); out.high = await p.evaluate(() => document.getElementById("cnt").textContent);
  await p.selectOption("#fs", ""); await p.selectOption("#fn", "1"); out.new = await p.evaluate(() => document.getElementById("cnt").textContent);
  await p.screenshot({ path: "final-top.png" });
  out.errors = errs; out.external = reqs.filter(u => !u.startsWith("file:") && !u.includes("fonts.g"));
  console.log(JSON.stringify(out, null, 1)); await b.close();
})();
