import { test, expect } from 'playwright/test';

const BASE_URL = process.env.E2E_BASE_URL || 'http://127.0.0.1:3100';
const RECEPTION_EMAIL = process.env.E2E_RECEPTION_EMAIL || 'letan@dr4women.local';
const MAT_KHAU = process.env.E2E_TEST_PW || process.env.E2E_RECEPTION_PW || ['clinic', 'test', 'pw', '123'].join('-');

test.describe('Luồng 1: Đặt lịch → Check-in → Đo sinh hiệu', () => {
  test('Đặt lịch khám, tiếp đón check-in và hoàn tất đo sinh hiệu', async ({ page }) => {
    const ts = Date.now().toString().slice(-6);
    const patientName = `E2E-Khach-${ts}`;
    const phone = `09${Math.floor(10000000 + Math.random() * 90000000)}`;

    // 1. Đăng nhập Lễ tân
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' });
    await page.fill('input#email', RECEPTION_EMAIL);
    await page.fill('input#password', MAT_KHAU);
    await page.click('button[type="submit"]');
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

    // 2. Vào /patients/new để tạo hồ sơ và đặt lịch
    await page.goto(`${BASE_URL}/patients/new`, { waitUntil: 'domcontentloaded' });
    await expect(page.locator('input[placeholder="Nguyễn Thị A"]').first()).toBeVisible({ timeout: 10000 });

    // Điền họ tên
    await page.locator('input[placeholder="Nguyễn Thị A"]').first().fill(patientName);

    // Điền năm sinh
    const yearOnlyLabel = page.locator('label').filter({ hasText: 'Chỉ biết năm' });
    if ((await yearOnlyLabel.count()) > 0) {
      await yearOnlyLabel.click();
      await page.locator('input[placeholder="VD: 1990"]').fill('1995');
    }

    // Điền số điện thoại
    await page.locator('input[placeholder*="10 chữ số"]').first().fill(phone);

    // Chọn Dịch vụ khám: Phụ khoa (PK)
    const svcSelect = page.locator('select').filter({ hasText: /Phụ khoa|Sản khoa/ }).first();
    await svcSelect.selectOption({ value: 'PK' });

    // Chọn Kênh đặt: Điện thoại
    const chanSelect = page.locator('select').filter({ hasText: /Điện thoại|Trực tiếp/ }).first();
    await chanSelect.selectOption({ value: 'DIEN_THOAI' });

    // Tìm cột ngày hôm nay trên bảng Bác sĩ x tuần
    const todayIndex = await page.locator('thead th').evaluateAll((ths) =>
      ths.findIndex((th) => th.classList.contains('text-brand-700'))
    );
    expect(todayIndex).toBeGreaterThan(0);

    // Mở popup chọn khung giờ hôm nay
    const rows = page.locator('tbody tr');
    const rowCount = await rows.count();
    let pickedSlot = false;

    const now = new Date();
    const utcHours = now.getUTCHours();
    const vnH = (utcHours + 7) % 24;
    const vnM = now.getUTCMinutes();

    // Thử lần lượt các bác sĩ nếu bác sĩ đầu kín chỗ
    for (let r = 0; r < Math.max(1, rowCount); r++) {
      const cellBtn = rows.nth(r).locator(`td:nth-child(${todayIndex + 1}) button`);
      if ((await cellBtn.count()) === 0) continue;

      await cellBtn.click();
      const slotDialog = page.locator('div[role="dialog"]');
      await expect(slotDialog).toBeVisible({ timeout: 5000 });

      // Chờ API tải xong slots
      try {
        await slotDialog.locator('ul button').first().waitFor({ state: 'visible', timeout: 5000 });
      } catch {
        // Bác sĩ có thể không có slots
      }

      const slotButtons = slotDialog.locator('ul button:not([disabled])');
      const count = await slotButtons.count();

      for (let i = 0; i < count; i++) {
        const btn = slotButtons.nth(i);
        const text = await btn.innerText();

        // Bỏ qua nếu đã đầy, đã qua hoặc đã có lượt đặt
        if (text.includes('Đã đầy') || text.includes('Đã qua') || text.includes('đã đặt')) {
          continue;
        }

        const match = text.match(/^(\d{2}):(\d{2})/);
        if (match) {
          const slotH = parseInt(match[1], 10);
          const slotM = parseInt(match[2], 10);
          // Chọn khung giờ tương lai > hiện tại + 5 phút
          if (slotH > vnH || (slotH === vnH && slotM > vnM + 5)) {
            await btn.click();
            pickedSlot = true;
            break;
          }
        }
      }

      if (pickedSlot) break;

      // Nếu không tìm được slot hợp lệ ở bác sĩ này, đóng popup và thử bác sĩ kế tiếp
      const closeBtn = slotDialog.locator('button[aria-label="Đóng"]');
      if ((await closeBtn.count()) > 0) {
        await closeBtn.click();
      }
    }

    expect(pickedSlot).toBe(true);

    // Bấm nút Tạo bệnh nhân & đặt lịch
    const submitBtn = page.locator('button').filter({ hasText: /Tạo bệnh nhân|Nhập thông tin/ }).first();
    await expect(submitBtn).toBeEnabled();
    await submitBtn.click();

    // Chờ hệ thống tạo xong và điều hướng ra khỏi /patients/new
    await page.waitForURL((url) => !url.pathname.includes('/patients/new'), { timeout: 15000 });

    // 3. Quầy tiếp đón (/reception/queue) check-in cho bệnh nhân
    if (!page.url().includes('/reception/queue')) {
      await page.goto(`${BASE_URL}/reception/queue`, { waitUntil: 'domcontentloaded' });
    }
    await page.waitForTimeout(1500);

    // Tìm dòng bệnh nhân trong danh sách chờ tiếp đón
    const patientRow = page.locator('li').filter({ hasText: new RegExp(patientName, 'i') }).first();
    await expect(patientRow).toBeVisible({ timeout: 10000 });

    // Bấm nút Check-in
    const checkinBtn = patientRow.locator('button').filter({ hasText: /Check-in/i }).first();
    await expect(checkinBtn).toBeVisible();
    await checkinBtn.click();

    // Xác nhận nút Check-in đã biến mất (đã check-in thành công)
    await expect(patientRow.locator('button').filter({ hasText: /Check-in/i })).toHaveCount(0, { timeout: 10000 });

    // 4. Màn Đo sinh hiệu (/do-sinh-hieu)
    await page.goto(`${BASE_URL}/do-sinh-hieu`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1500);

    // Tìm và chọn bệnh nhân trong danh sách chờ đo sinh hiệu
    const vitalsPatientBtn = page.locator('li button').filter({ hasText: new RegExp(patientName, 'i') }).first();
    await expect(vitalsPatientBtn).toBeVisible({ timeout: 10000 });
    await vitalsPatientBtn.click();

    // Nhập các chỉ số sinh hiệu qua ô số có title tương ứng
    await page.locator('input[title="Huyết áp tâm thu"]').fill('120');
    await page.locator('input[title="Huyết áp tâm trương"]').fill('80');
    await page.locator('input[title="Mạch"]').fill('75');
    await page.locator('input[title="Chiều cao"]').fill('160');
    await page.locator('input[title="Cân nặng"]').fill('50');

    // Đánh dấu bỏ qua bác sĩ tư vấn (nếu có ô chọn) để chuyển thẳng bác sĩ chính
    const skipConsultLabel = page.locator('label').filter({ hasText: /Bỏ qua bác sĩ tư vấn/i });
    if ((await skipConsultLabel.count()) > 0) {
      const skipCheckbox = skipConsultLabel.locator('input[type="checkbox"]');
      if ((await skipCheckbox.count()) > 0 && !(await skipCheckbox.isChecked())) {
        await skipCheckbox.click();
      }
    }

    // Bấm nút Đo xong
    const saveVitalsBtn = page.locator('button').filter({ hasText: /Đo xong/i }).first();
    await expect(saveVitalsBtn).toBeEnabled();
    await saveVitalsBtn.click();

    // Kiểm tra trạng thái đã hoàn tất đo sinh hiệu
    await expect(page.getByRole('status')).toBeVisible({ timeout: 10000 });
    await expect(page.getByRole('status')).toContainText(/Đã lưu sinh hiệu/i);
  });
});
