// Real local DEMO login; invoice responses mocked in browser only.
import assert from 'node:assert/strict';
import { mkdir } from 'node:fs/promises';
import { chromium } from 'playwright';

const base = process.env.E2E_BASE_URL || 'http://127.0.0.1:3240';
assert.ok(['localhost', '127.0.0.1'].includes(new URL(base).hostname));
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage();
const access = { quan_ly: true, ban_hang: true, co_the_mo: true, tai_chinh: true, legacy: false, cac_ca: ['FULL', 'SANG', 'CHIEU', 'TOI'], co_so_ids: [] };
const p = { id: 'demo-bill', ma: 'PT-DEMO', visit_id: 'demo-visit', kind: 'dich_vu', trang_thai: 'HOAN_MOT_PHAN', so_tien: 1000000, da_hoan: 200000, cho_hoan: 100000, thu_rong: 800000, hinh_thuc: 'Tiền mặt', lap_luc: '2026-10-13T08:00:00+07:00', thu_luc: '2026-10-13T08:01:00+07:00', huy_luc: null, nguoi_lap: 'Lễ tân DEMO', nguoi_thu: 'Thu ngân DEMO', nguoi_huy: null, ly_do_huy: null,
  dong: [{ id: 'demo-line', ten: 'Dịch vụ DEMO đầy đủ tên', so_luong: 1, thanh_tien: 1000000, da_bo: true }],
  hoan: [{ id: 'demo-refund', ma: 'HT-DEMO', so_tien: 200000, trang_thai: 'COMPLETED', lap_luc: '2026-10-13T09:00:00+07:00', hoan_luc: '2026-10-13T09:05:00+07:00', nguoi_lap: 'Trưởng ca DEMO', nguoi_hoan: 'Thu ngân DEMO', ly_do: 'Khách không làm dịch vụ', dong: [] }] };
const k = { id: 'demo-patient', ten: 'Khách DEMO', ma_bn: 'DEMO-001', so_dien_thoai: '0900000000', da_thu: 1000000, da_hoan: 200000, cho_hoan: 100000, thu_rong: 800000, so_phieu: 1, trang_thai: 'HOAN_MOT_PHAN', can_doi_soat: true, canh_bao: ['Có khoản hoàn thất bại'], phieu: [p] };
let mode = 'populated';
const requests = [];
const errors = [];
page.on('pageerror', e => errors.push(e.message));
try {
  await page.goto(`${base}/login`);
  await page.locator('input[name="email"]').fill('ql@dr4women.local');
  await page.locator('input[name="password"]').fill(process.env.TEST_PW || 'clinic-test-pw-123');
  await page.getByRole('button', { name: 'Đăng nhập', exact: true }).click();
  await page.waitForURL(u => !u.pathname.includes('login'));
  await page.route('**/api/reports/access?**', r => r.fulfill({ json: access }));
  await page.route('**/api/hoa-don?**', async r => {
    requests.push(new URL(r.request().url()).searchParams);
    await r.fulfill({ status: mode === 'error' ? 403 : 200, json: mode === 'error' ? { error: 'Không có quyền xem tài chính DEMO' } : { tu: '2026-10-13', den: '2026-10-13', access, tong: { ...k, so_khach: mode === 'empty' ? 0 : 1 }, khach: mode === 'empty' ? [] : [k] } });
  });
  await mkdir('e2e/out/hoa-don', { recursive: true });
  for (const width of [375, 768, 1280]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto(`${base}/hoa-don`);
    const open = page.getByRole('button', { name: 'Xem hoá đơn Khách DEMO' }).filter({ visible: true });
    await open.waitFor();
    await page.getByText('Có khoản hoàn thất bại', { exact: true }).filter({ visible: true }).waitFor();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.screenshot({ path: `e2e/out/hoa-don/list-${width}.png`, fullPage: true });
    await open.click();
    const dialog = page.getByRole('dialog');
    await dialog.getByText('Dịch vụ DEMO đầy đủ tên', { exact: false }).waitFor();
    assert.match(await dialog.innerText(), /Thu ngân DEMO/);
    assert.match(await dialog.innerText(), /Khách không làm dịch vụ/);
    assert.match(await dialog.innerText(), /Đã trả lại/);
    assert.equal(await dialog.evaluate(el => el.getBoundingClientRect().bottom <= innerHeight && el.getBoundingClientRect().top >= 0), true);
    await page.screenshot({ path: `e2e/out/hoa-don/detail-${width}.png`, fullPage: false });
    await page.keyboard.press('Escape');
    await dialog.waitFor({ state: 'detached' });
  }
  await page.getByRole('combobox', { name: 'Loại phiếu', exact: true }).selectOption('thuoc');
  await page.waitForTimeout(500);
  assert.equal(requests.at(-1).get('loai'), 'thuoc');
  await page.getByRole('combobox', { name: 'Trạng thái', exact: true }).selectOption('DA_HUY');
  await page.waitForTimeout(500);
  assert.equal(requests.at(-1).get('trang_thai'), 'DA_HUY');
  await page.getByRole('checkbox', { name: 'Chỉ cần kiểm tra', exact: true }).check();
  await page.waitForTimeout(500);
  assert.equal(requests.at(-1).get('can_kiem_tra'), 'true');
  const exportUrl = new URL(await page.getByRole('link', { name: 'Xuất Excel', exact: true }).getAttribute('href'), base);
  assert.equal(exportUrl.searchParams.get('xuat'), 'xlsx');
  assert.equal(exportUrl.searchParams.get('can_kiem_tra'), 'true');
  mode = 'empty';
  await page.getByRole('button', { name: 'Tải lại', exact: true }).click();
  await page.getByText('Không có hoá đơn trong phạm vi đã chọn.', { exact: true }).waitFor();
  mode = 'error';
  await page.getByRole('button', { name: 'Tải lại', exact: true }).click();
  await page.getByRole('alert').getByText('Không có quyền xem tài chính DEMO', { exact: true }).waitFor();
  assert.deepEqual(errors, []);
  console.log('PASS invoice list UI: responsive 375/768/1280, dialog, actor/reason, filters, empty, denied; mocked invoice API, real local auth');
} finally { await browser.close(); }
