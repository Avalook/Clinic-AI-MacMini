import assert from 'node:assert/strict';
import { chromium } from 'playwright';

const base = process.env.TEST_BASE_URL || 'http://127.0.0.1:3100';
const browser = await chromium.launch({ channel: 'chrome', headless: true });
try {
  const context = await browser.newContext();
  const page = await context.newPage();
  const errors = [];
  // Replacing serialized props intentionally regenerates the server-rendered tree.
  page.on("pageerror", error => { if (!error.message.startsWith("Hydration failed")) errors.push(error.message); });
  await page.goto(`${base}/login`);
  await page.locator('input[name="email"]').fill('ql@dr4women.local');
  await page.locator('input[name="password"]').fill(process.env.TEST_PW || 'clinic-test-pw-123');
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click();
  await page.waitForURL(u => !u.pathname.includes('login'));
  const location = 'b4607cb5-3ff1-4c20-9115-147f06aeac1b';
  const shifts = ['SANG', 'CHIEU', 'TOI', 'FULL'];
  const scopes = Object.fromEntries(shifts.map(s => [s, [location]]));
  const access = { quan_ly: false, ban_hang: true, co_the_mo: true,
    tai_chinh: true, tai_chinh_day_du: false, legacy: false,
    cac_ca: shifts, co_so_ids: [location], co_so_theo_ca: scopes,
    ngay_truc: ['2026-10-12', '2026-10-10'].map(ngay => ({ ngay, co_so_theo_ca: scopes })) };
  // Inject only serialized report props before hydration; auth remains real.
  await page.addInitScript(mockAccess => {
    let chunks;
    Object.defineProperty(window, "__next_f", {
      configurable: true,
      get() { return chunks; },
      set(value) {
        chunks = value;
        const push = value.push;
        value.push = function (...items) {
          const mapped = items.map(item => Array.isArray(item) && typeof item[1] === "string"
            ? [item[0], item[1].replace(/\{"quan_ly":true,.*?"co_so_theo_ca":\{\}\}/g, JSON.stringify(mockAccess))]
            : item);
          return push.apply(this, mapped);
        };
      },
    });
  }, access);
  await page.route('**/api/reports/access?**', route => route.fulfill({ json: access }));
  const requests = [];
  await page.route('**/api/reports/cuoi-ngay?**', async route => {
    const url = new URL(route.request().url()); requests.push(url.searchParams);
    await route.fulfill({ status: 403, json: { message: 'Báo cáo thử quyền theo ngày' } });
  });
  for (const width of [375, 1280]) {
    await page.setViewportSize({ width, height: 900 });
    for (const tab of ['cuoi-ngay', 'hang-hoa']) {
      await page.goto(`${base}/reports?tab=${tab}&ngay=2026-10-12`);
      const picker = page.getByRole('combobox', { name: 'Ngày trực báo cáo' });
      await picker.waitFor();
      assert.equal(await picker.locator('option').count(), 3);
      assert.equal(await page.locator('input[type="date"]:visible').count(), 0);
      await picker.selectOption('2026-10-10');
      await page.waitForFunction(() => document.querySelector('[aria-label="Ngày trực báo cáo"]')?.value === '2026-10-10');
      await page.getByRole('alert').filter({ hasText: 'Báo cáo thử quyền theo ngày' }).waitFor();
      const last = requests.at(-1);
      assert.equal(last.get('tu'), '2026-10-10');
      assert.equal(last.get('den'), '2026-10-10');
      assert.equal(last.get('co_so'), location);
      assert.equal(last.get('ca'), null, 'Head defaults to whole assigned day');
    }
  }
  let saved;
  await page.route('**/api/reports/settings', async route => {
    saved = route.request().postDataJSON();
    await route.fulfill({ json: saved });
  });
  await page.goto(`${base}/settings`);
  const settings = page.locator('section').filter({ has: page.getByRole('heading', { name: 'Thiết lập báo cáo', exact: true }) });
  await settings.waitFor();
  assert.equal(await settings.getByRole('checkbox').count(), 1);
  await settings.getByRole('button', { name: 'Lưu thiết lập', exact: true }).click();
  await settings.getByRole('status').filter({ hasText: 'Đã lưu' }).waitFor();
  assert.deepEqual(Object.keys(saved).sort(), ['nhan_vien_theo_ca', 'tai_chinh_day_du', 'truong_ca_theo_ngay']);
  assert.deepEqual(errors, []);
  console.log('PASS report head assigned-day picker: both tabs, 375/1280, no free date range, whole-day scoped requests');
} finally { await browser.close(); }
