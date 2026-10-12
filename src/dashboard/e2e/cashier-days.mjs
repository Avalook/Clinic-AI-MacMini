import assert from 'node:assert/strict';
import { chromium } from 'playwright';

const base = process.env.E2E_BASE_URL || 'http://127.0.0.1:3100';
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage({ viewport: { width: 375, height: 812 } });
const locationA = '11111111-1111-4111-8111-111111111111';
const locationB = '22222222-2222-4222-8222-222222222222';
const requests = [];
let populated = false;
const day = '2026-10-12';
const days = { quan_ly: false, thao_tac: false, dang_truc: [], next_cursor: null, items: [{
  ngay: day, cac_ca: ['SANG', 'CHIEU'], co_so_ids: [locationA, locationB],
  co_so_theo_ca: { SANG: [locationA], CHIEU: [locationB] },
  co_so: [{ id: locationA, ten: 'Kim Ngưu' }, { id: locationB, ten: 'Hào Nam' }],
}] };
try {
  await page.goto(`${base}/login`);
  await page.locator('input[name="email"]').fill('ql@dr4women.local');
  await page.locator('input[name="password"]').fill(process.env.TEST_PW || 'clinic-test-pw-123');
  await page.locator('button[type="submit"]').click();
  await page.waitForURL(url => !url.pathname.includes('login'));
  await page.route('**/api/cashier?**', async route => {
    const url = new URL(route.request().url());
    requests.push(url);
    const xem = url.searchParams.get('xem');
    if (xem === 'ngay-truc') return route.fulfill({ json: days });
    if (xem === 'giao-dich') return route.fulfill({ json: { giao_dich: [], co_quyen_hoan: false } });
    if (xem === 'lich-su') return route.fulfill({ json: { tong: { tong_thu: 0, tien_mat: 0, chuyen_khoan: 0, hoan: 0 }, khach: populated ? [{
      visit_id: 'demo-visit', ten: 'Khách DEMO', ma_bn: 'DEMO-TEST', so_booking: 1, so_tiep_don: 1,
      tong_goc: 100000, tong_hoan: 20000, con_lai: 80000, dau: `${day}T08:00:00+07:00`, cuoi: `${day}T09:00:00+07:00`, so_phieu: 1,
      ma_phieu_dau: 'PT-DEMO', hinh_thuc: ['TRANSFER'], nguoi_thu: ['Nhân viên DEMO'], co_hoan: true,
      su_kien: [{loai: 'thu', id: 'demo-cycle', luc: `${day}T08:00:00+07:00`, ma: 'PT-DEMO', so_tien: 100000, hinh_thuc: 'TRANSFER', nguoi: 'Nhân viên DEMO', dich_vu: ['Dịch vụ DEMO'], ly_do: null, cho: false,
        doi_hinh_thuc: { duoc: true }, hoan_tac: {duoc: true}, phan: [{hinh_thuc: 'TRANSFER', so_tien: 100000}], anh_ck: [{id: 'demo-proof'}]},
      {loai: 'hoan', id: 'demo-refund', luc: `${day}T09:00:00+07:00`, ma: 'HT-DEMO', so_tien: -20000, hinh_thuc: 'TRANSFER', nguoi: 'Trưởng ca DEMO', dich_vu: [], ly_do: 'Điều chỉnh DEMO', cho: false}],
    }] : [], nguoi_thu: [] } });
    return route.fulfill({ json: { items: [], paid: [], cho_xac_minh: [] } });
  });
  for (const width of [375, 768, 1280]) {
  await page.setViewportSize({ width, height: 812 });
  for (const quay of ['dich-vu', 'thuoc']) {
    requests.length = 0;
    await page.goto(`${base}/thu-ngan/${quay}?ngay=2000-01-01`);
    await page.getByRole('button', { name: 'Ca sáng', exact: true }).waitFor();
    assert.equal(await page.getByRole('tab', { name: 'Chờ thanh toán', exact: true }).count(), 0);
    await page.getByRole('button', { name: 'Ca chiều', exact: true }).click();
    await page.getByRole('tab', { name: /Đã thanh toán/ }).click();
    await page.getByText('Chưa có giao dịch nào trong khoảng này.').waitFor();
    const transaction = requests.findLast(u => u.searchParams.get('xem') === 'giao-dich');
    assert.equal(transaction.searchParams.get('tu'), day);
    assert.equal(transaction.searchParams.get('den'), day);
    assert.equal(transaction.searchParams.get('ca'), 'CHIEU');
    assert.equal(transaction.searchParams.get('co_so'), locationB);
    assert.ok(!requests.some(u => ['ngay', 'tu', 'den'].some(k => u.searchParams.get(k) === '2000-01-01')));
    await page.getByRole('tab', { name: 'Lịch sử giao dịch', exact: true }).click();
    assert.equal(await page.getByLabel('Từ ngày', { exact: true }).count(), 0);
    assert.equal(await page.getByLabel('Đến ngày', { exact: true }).count(), 0);
      await page.getByText('Không có lần thu nào trong khoảng này.').waitFor();
      assert.equal(await page.getByText('Tổng thu', { exact: true }).count(), 1);
      assert.equal(await page.locator('span').getByText('Tiền mặt', { exact: true }).count(), 1);
      const href = await page.getByRole('link', { name: 'Xuất Excel' }).getAttribute('href');
      const csv = new URL(href, base);
      assert.equal(csv.searchParams.get('ca'), 'CHIEU');
      assert.equal(csv.searchParams.get('co_so'), locationB);
      assert.equal(csv.searchParams.get('tu'), day);
      assert.equal(csv.searchParams.get('kind'), quay.replace('-', '_'));
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  }
  }
  populated = true;
  days.thao_tac = true;
  days.dang_truc = [{ca: 'SANG', co_so_id: locationA}];
  for (const quay of ['dich-vu', 'thuoc']) {
    await page.goto(`${base}/thu-ngan/${quay}/lich-su`);
    await page.getByRole('button', {name: /Khách DEMO/}).click();
    await page.getByText(/Trưởng ca DEMO/).waitFor();
    assert.equal(await page.getByRole('tab', {name: 'Chờ thanh toán', exact: true}).count(), 0);
    assert.equal(await page.getByRole('button', {name: 'Hoàn tác lần thu', exact: true}).count(), 0);
    assert.equal(await page.getByRole('button', {name: 'Đổi hình thức', exact: true}).count(), 0);
    assert.equal(await page.getByRole('button', {name: 'Gỡ ảnh', exact: true}).count(), 0);
    assert.equal(await page.locator('input[type="file"]').count(), 0);
    assert.equal(await page.getByRole('link', {name: 'In', exact: true}).count(), 2);
  }
  console.log('PASS both counters: off-shift hides waiting tab; assigned-day/shift/location, rejected URL fallback, shared totals and CSV kind/scope at 375/768/1280');
} finally { await browser.close(); }
