import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import { chromium } from "playwright";

const base = process.env.E2E_BASE_URL ?? "http://127.0.0.1:3251";
assert.ok(["127.0.0.1", "localhost"].includes(new URL(base).hostname), "Chỉ tạo DEMO trên local");
const browser = await chromium.launch({ channel: "chrome", headless: true });
const artifacts = process.env.E2E_ARTIFACT_DIR ?? "/tmp/clinicai-quick-intake";
await mkdir(artifacts, { recursive: true });
try {
  for (const width of [1280, 375]) {
    const context = await browser.newContext({ viewport: { width, height: 900 } });
    const page = await context.newPage();
    await page.goto(`${base}/login`);
    await page.getByRole("textbox", { name: "Tên đăng nhập" }).fill("cskh@dr4women.local");
    await page.getByRole("textbox", { name: "Mật khẩu" }).fill(process.env.E2E_PASSWORD ?? "clinic-test-pw-123");
    await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
    await page.waitForURL((url) => !url.pathname.includes("/login"));
    await page.goto(`${base}/patients/new`);
    const name = `DEMO-CSKH-${Date.now()}-${width}`;
    const input = page.getByPlaceholder("Nguyễn Thị A", { exact: true });
    await input.fill(name);
    const created = page.waitForResponse((r) => r.url().endsWith("/api/patients") && r.request().method() === "POST");
    if (width === 1280) await input.press("Enter");
    else await page.getByRole("button", { name: "Nhập thông tin khách hàng", exact: true }).click();
    const response = await created;
    assert.equal(response.status(), 200);
    const json = await response.json();
    const id = json.patient.clinic_patient_id;
    await page.waitForURL((url) => url.pathname === "/customers" && url.searchParams.get("selected") === id);
    await page.getByText("Gọi điện xác nhận", { exact: true }).first().waitFor();
    assert.ok(await page.getByRole("button", { name: "Đã liên hệ được", exact: true }).isVisible());
    await page.screenshot({ path: `${artifacts}/selected-${width}.png`, fullPage: true });
    await page.goto(`${base}/customers`);
    await page.getByRole("textbox", { name: "Tìm theo tên, số điện thoại, mã khách hàng" }).fill(name);
    const waiting = page.getByRole("button", { name: /Chờ xác nhận/ });
    await waiting.click();
    await page.getByText(json.patient.patient_code, { exact: true }).first().waitFor();
    await page.getByText("Gọi điện xác nhận", { exact: true }).first().waitFor();
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.screenshot({ path: `${artifacts}/waiting-${width}.png`, fullPage: true });
    console.log(`PASS ${width}: lưu ${width === 1280 ? "Enter" : "nút"} → customers chọn khách → Chờ xác nhận / Gọi điện xác nhận`);
    await context.close();
  }
} finally {
  await browser.close();
}
