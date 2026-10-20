"use strict";
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const { pathToFileURL } = require("node:url");
const repo = path.resolve(__dirname, "../..");
const { chromium } = require(path.join(repo, "src/dashboard/node_modules/playwright"));

async function main() {
  const macChrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
  const executable = process.env.CLINICAI_AUDIT_CHROME
    || (fs.existsSync(macChrome) ? macChrome : undefined);
  const browser = await chromium.launch({ headless: true, executablePath: executable });
  try {
    const page = await browser.newPage();
    const errors = [];
    const requests = [];
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("request", (request) => requests.push(request.url()));
    const report = path.join(__dirname, "BAO-CAO.html");
    await page.setViewportSize({ width: 1280, height: 900 });
    await page.goto(pathToFileURL(report).href);
    await page.screenshot({ path: path.join(__dirname, "preview-desktop.png") });
    const desktop = await page.evaluate(() => ({
      width: innerWidth,
      scroll: document.documentElement.scrollWidth,
      cards: document.querySelectorAll(".finding").length,
      ledgerRows: document.querySelectorAll(".ledger tbody tr").length,
    }));
    await page.locator("#query").fill("CLIN-001");
    const search = await page.locator(".finding:visible").count();
    if (search !== 1) throw new Error(`Search count ${search}`);
    await page.locator("#query").fill("");
    await page.locator("#scope").selectOption("patched");
    const patched = await page.locator(".finding:visible").count();
    if (patched !== 2) throw new Error(`Patched count ${patched}`);
    await page.evaluate(() => window.dispatchEvent(new Event("beforeprint")));
    const printOpen = await page.locator(".finding details[open]").count();
    const printVisible = await page.locator(".finding:visible").count();
    if (printOpen !== desktop.cards || printVisible !== desktop.cards) {
      throw new Error("Print preparation omitted evidence or filtered cards");
    }
    await page.evaluate(() => window.dispatchEvent(new Event("afterprint")));
    if (await page.locator(".finding:visible").count() !== 2) {
      throw new Error("Print did not restore filters");
    }
    await page.locator("#scope").selectOption("all");
    await page.setViewportSize({ width: 375, height: 812 });
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: path.join(__dirname, "preview-mobile.png") });
    await page.locator("#CLIN-001 details").evaluate((element) => { element.open = true; });
    const mobile = await page.evaluate(() => ({
      width: innerWidth, scroll: document.documentElement.scrollWidth,
    }));
    if (mobile.scroll > mobile.width || desktop.scroll > desktop.width) {
      throw new Error(`Horizontal page overflow ${JSON.stringify({ desktop, mobile })}`);
    }
    if (errors.length) throw new Error(errors.join("\n"));
    const external = requests.filter((url) => !url.startsWith("file:"));
    if (external.length) throw new Error(`External resources: ${external.join(",")}`);
    const result = {
      checkedAt: new Date().toISOString(),
      reportSha256: crypto.createHash("sha256").update(fs.readFileSync(report)).digest("hex"),
      desktop, mobile, search, patched, printOpen, printVisible,
      pageErrors: errors, externalRequests: external,
      limitations: ["Validates report UI only, not the ClinicAI application", "No accessibility certification"],
    };
    fs.writeFileSync(path.join(__dirname, "HTML-QA.json"), JSON.stringify(result, null, 2) + "\n");
    console.log(JSON.stringify(result));
  } finally {
    await browser.close();
  }
}

main().catch((error) => { console.error(error.message); process.exitCode = 1; });
