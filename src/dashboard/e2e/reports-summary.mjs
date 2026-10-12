// Chạy với stack DEMO local; dữ liệu báo cáo giả lập chỉ ở lớp trình duyệt.
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { chromium } from 'playwright';

const base = process.env.E2E_BASE_URL || 'http://127.0.0.1:3100';
assert.ok(['localhost', '127.0.0.1'].includes(new URL(base).hostname));
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage();
const money = (thu = 0) => ({ thu, huy: 0, hoan: 0, thuc_thu: thu });
const data = (thu = 0) => ({
  tu: '2026-10-12', den: '2026-10-12',
  tong: { ...money(thu), hoan_cho: 0, so_phieu_thu: thu ? 8 : 0, so_phieu_huy: 0, so_phieu_hoan: 0 },
  theo_hinh_thuc: [{ ...money(thu ? 900000 : 0), ma: 'CASH', ten: 'Tiền mặt' }, { ...money(thu ? 7650000 : 0), ma: 'TRANSFER', ten: 'Chuyển khoản' }],
  theo_loai: [{...money(thu ? 8000000 : 0), ma: 'dich_vu', ten: 'Dịch vụ'}, {...money(thu ? 550000 : 0), ma: 'thuoc', ten: 'Thuốc / vật tư'}], theo_nguoi_thu: [], theo_ngay: [], hoan_huy: [], top_dich_vu: [],
  khach: { so_luot_kham: 0, so_luot_da_thu: 0, so_khach_da_thu: 0, so_luot_khong_chon_dich_vu_kham: 0 },
  doi_tac: { tong: 0, dong: [] },
  can_xu_ly: { tinh_den: '2026-10-12T18:00:00+07:00', pham_vi: 'Không theo ngày hoặc ca',
    cho_xac_minh: { so_phieu: 1, so_tien: 123000 },
    hoan_cho: { so_phieu: 1, so_tien: 456000 },
    tien_thua: { so_luot: 1, so_tien: 789000 },
    khach_con_no: { so_khach: 1, tong: 990000 },
  },
});
let state = 'loading';
let release;
try {
  await page.goto(`${base}/login`);
  await page.locator('input[name="email"]').fill('ql@dr4women.local');
  await page.locator('input[name="password"]').fill(process.env.TEST_PW || 'clinic-test-pw-123');
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click();
  await page.waitForURL(url => !url.pathname.includes('login'));
  await page.route('**/api/reports/cuoi-ngay?**', async route => {
    if (state === 'loading') await new Promise(resolve => { release = resolve; });
    await route.fulfill({ status: state === 'error' ? 500 : 200, json: state === 'error' ? { message: 'Lỗi báo cáo thử' } : data(state === 'populated' ? 8550000 : 0) });
  });
  await page.goto(`${base}/reports?tab=cuoi-ngay`);
  await page.getByRole('heading', { name: 'Tổng kết thu', exact: true }).waitFor({ timeout: 10000 });
  const summary = page.getByRole('region', { name: 'Tóm tắt báo cáo cuối ngày' });
  assert.match(await summary.innerText(), /Đang tải/);
  assert.doesNotMatch(await summary.innerText(), /0đ/);
  for (let n = 0; !release && n < 50; n++) await page.waitForTimeout(100);
  assert.ok(release, 'Client must send report request');
  state = 'empty'; release?.();
  await summary.getByText('Chưa có khoản thu trong khoảng đã chọn.', { exact: true }).waitFor();
  assert.match(await summary.innerText(), /0đ/);
  state = 'populated';
  await page.reload();
  await summary.getByText('8.550.000đ', { exact: true }).first().waitFor();
  assert.match(await summary.innerText(), /8\.000\.000đ/);
  assert.match(await summary.innerText(), /550\.000đ/);
  assert.equal(await page.getByText('Có khoản cần xử lý', { exact: true }).count(), 0);
  assert.equal(await page.getByText('Chi tiết giao dịch', { exact: true }).count(), 0);
  await page.evaluate(() => {
    const append = document.body.appendChild.bind(document.body);
    document.body.appendChild = node => {
      const result = append(node);
      if (node.tagName === 'IFRAME') node.contentWindow.print = () => { window.__printedReport = node.contentDocument.body.innerText; };
      return result;
    };
  });
  await page.getByRole('button', { name: 'In', exact: true }).click();
  const printed = await page.evaluate(() => window.__printedReport);
  assert.match(printed, /Tổng thu/);
  assert.match(printed, /8.550.000đ/);
  assert.doesNotMatch(printed, /Bộ lọc|Huỷ phiếu|Khách còn nợ|990.000/);
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Xuất Excel', exact: true }).click();
  const download = await downloadPromise;
  const stream = await download.createReadStream(); let csv = '';
  for await (const part of stream) csv += part.toString('utf8');
  assert.match(csv, /Tổng thu","8550000/);
  assert.match(csv, /Dịch vụ","8000000/);
  assert.doesNotMatch(csv, /Huỷ|Khách còn nợ|990000/);
  await mkdir('../../.dev-logs/reports-ui', { recursive: true });
  for (const width of [375, 768, 1280]) {
    await page.setViewportSize({ width, height: 900 });
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: `../../.dev-logs/reports-ui/${width}.png` });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `Overflow at ${width}`);
    if (width === 375) {
          for (const name of ['Xuất Excel', 'In']) assert.ok((await page.getByRole('button', { name, exact: true }).boundingBox()).height >= 40);
    }
  }
  state = 'error';
  await page.reload();
  await page.getByRole('alert').getByText('Lỗi báo cáo thử').waitFor();
  assert.doesNotMatch(await summary.innerText(), /8\.550\.000/);
  assert.match(await summary.innerText(), /—/);
  let unblockOld;
  await page.route('**/api/reports/cuoi-ngay?**', async route => {
    const old = new URL(route.request().url()).searchParams.get('loai') === 'dich_vu';
    if (old) await new Promise(resolve => { unblockOld = resolve; });
    await route.fulfill({ json: data(old ? 111000 : 8550000) });
  });
  await page.getByRole('tab', { name: 'Dịch vụ', exact: true }).click();
  for (let n = 0; !unblockOld && n < 50; n++) await page.waitForTimeout(100);
  assert.ok(unblockOld);
  await page.getByRole('tab', { name: 'Thuốc', exact: true }).click();
  await summary.getByText('8.550.000đ', { exact: true }).first().waitFor();
  unblockOld();
  await page.waitForTimeout(500);
  assert.doesNotMatch(await summary.innerText(), /111\.000/);
  await page.emulateMedia({ media: 'print' });
  assert.ok(await summary.isVisible());
  assert.ok(!await page.getByRole('button', { name: 'In', exact: true }).isVisible());
  console.log('PASS: loading / empty / populated / error; responsive 375 / 768 / 1280');
} finally {
  release?.();
  await browser.close();
}
