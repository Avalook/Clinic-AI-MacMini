import { test, expect } from 'playwright/test';

const BASE_URL = process.env.E2E_BASE_URL || 'http://127.0.0.1:3100';
const RECEPTION_EMAIL = process.env.E2E_RECEPTION_EMAIL || 'letan@dr4women.local';
const DOCTOR_EMAIL = process.env.E2E_DOCTOR_EMAIL || 'bs.a@dr4women.local';
const MAT_KHAU = process.env.E2E_TEST_PW || ['clinic', 'test', 'pw', '123'].join('-');

test.describe('Luồng 2: Khám chính (Bác sĩ khám → chỉ định CLS → Hoàn tất khám)', () => {
  test('Bác sĩ nhận khám, chỉ định siêu âm 2D tử cung buồng trứng và hoàn tất khám', async ({ page }) => {
    const ts = Date.now().toString().slice(-6);
    const patientName = `E2E-Khach-${ts}`;
    const phone = `09${Math.floor(10000000 + Math.random() * 90000000)}`;

    // --- BƯỚC 1: LỄ TÂN TẠO KHÁCH, CHECK-IN VÀ ĐO SINH HIỆU ---
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' });
    await page.fill('input#email', RECEPTION_EMAIL);
    await page.fill('input#password', MAT_KHAU);
    await page.click('button[type="submit"]');
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

    // Tạo bệnh nhân & đặt lịch
    await page.goto(`${BASE_URL}/patients/new`, { waitUntil: 'domcontentloaded' });
    await expect(page.locator('input[placeholder="Nguyễn Thị A"]').first()).toBeVisible({ timeout: 10000 });
    await page.locator('input[placeholder="Nguyễn Thị A"]').first().fill(patientName);

    const yearOnlyLabel = page.locator('label').filter({ hasText: 'Chỉ biết năm' });
    if ((await yearOnlyLabel.count()) > 0) {
      await yearOnlyLabel.first().click();
      await page.locator('input[placeholder="VD: 1990"]').first().fill('1995');
    }
    await page.locator('input[placeholder*="10 chữ số"]').first().fill(phone);

    const svcSelect = page.locator('select').filter({ hasText: /Phụ khoa|Sản khoa/ }).first();
    await svcSelect.selectOption({ value: 'PK' });

    const chanSelect = page.locator('select').filter({ hasText: /Điện thoại|Trực tiếp/ }).first();
    await chanSelect.selectOption({ value: 'DIEN_THOAI' });

    await page.waitForSelector('thead th.text-brand-700', { timeout: 10000 });
    const todayIndex = await page.locator('thead th').evaluateAll((ths) =>
      ths.findIndex((th) => th.classList.contains('text-brand-700'))
    );
    expect(todayIndex).toBeGreaterThan(0);

    // Ưu tiên chọn đúng hàng của BS A local
    const targetRow = page.locator('tbody tr').filter({ hasText: /BS A local|Bác sĩ A/i }).first();
    const rows = (await targetRow.count()) > 0 ? targetRow : page.locator('tbody tr');
    const rowCount = await rows.count();
    let pickedSlot = false;

    const now = new Date();
    const vnH = (now.getUTCHours() + 7) % 24;
    const vnM = now.getUTCMinutes();

    for (let r = 0; r < Math.max(1, rowCount); r++) {
      const cellBtn = rows.nth(r).locator(`td:nth-child(${todayIndex + 1}) button`);
      if ((await cellBtn.count()) === 0) continue;

      await cellBtn.click();
      const slotDialog = page.locator('div[role="dialog"]');
      await expect(slotDialog).toBeVisible({ timeout: 5000 });

      try {
        await slotDialog.locator('ul button').first().waitFor({ state: 'visible', timeout: 5000 });
      } catch {
        // bỏ qua nếu ko có slot
      }

      const slotButtons = slotDialog.locator('ul button:not([disabled])');
      const count = await slotButtons.count();

      for (let i = 0; i < count; i++) {
        const btn = slotButtons.nth(i);
        const text = await btn.innerText();
        if (text.includes('Đã đầy') || text.includes('Đã qua') || text.includes('đã đặt')) {
          continue;
        }
        const match = text.match(/^(\d{2}):(\d{2})/);
        if (match) {
          const slotH = parseInt(match[1], 10);
          const slotM = parseInt(match[2], 10);
          if (slotH > vnH || (slotH === vnH && slotM > vnM + 5)) {
            await btn.click();
            pickedSlot = true;
            break;
          }
        }
      }
      if (pickedSlot) break;
      const closeBtn = slotDialog.locator('button[aria-label="Đóng"]');
      if ((await closeBtn.count()) > 0) await closeBtn.click();
    }
    expect(pickedSlot).toBe(true);

    const submitBtn = page.locator('button').filter({ hasText: /Tạo bệnh nhân|Nhập thông tin/ }).first();
    await submitBtn.click();
    await page.waitForURL((url) => !url.pathname.includes('/patients/new'), { timeout: 15000 });

    // Check-in tiếp đón
    if (!page.url().includes('/reception/queue')) {
      await page.goto(`${BASE_URL}/reception/queue`, { waitUntil: 'domcontentloaded' });
    }
    await page.waitForTimeout(1000);
    const patientRow = page.locator('li').filter({ hasText: new RegExp(patientName, 'i') }).first();
    await expect(patientRow).toBeVisible({ timeout: 10000 });

    const checkinBtn = patientRow.locator('button').filter({ hasText: /Check-in/i }).first();
    await Promise.all([
      page.waitForResponse(
        (res) => res.url().includes('/api/appointments') && res.request().method() === 'PATCH' && res.status() === 200,
      ),
      checkinBtn.click(),
    ]);
    await page.waitForTimeout(1000);

    // Đo sinh hiệu
    await page.goto(`${BASE_URL}/do-sinh-hieu`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1000);
    const vitalsPatientBtn = page.locator('li button').filter({ hasText: new RegExp(patientName, 'i') }).first();
    await expect(vitalsPatientBtn).toBeVisible({ timeout: 10000 });
    await vitalsPatientBtn.click();

    await page.locator('input[title="Huyết áp tâm thu"]').fill('120');
    await page.locator('input[title="Huyết áp tâm trương"]').fill('80');
    await page.locator('input[title="Mạch"]').fill('75');
    await page.locator('input[title="Chiều cao"]').fill('160');
    await page.locator('input[title="Cân nặng"]').fill('50');

    const skipConsultLabel = page.locator('label').filter({ hasText: /Bỏ qua bác sĩ tư vấn/i });
    if ((await skipConsultLabel.count()) > 0) {
      const skipCheckbox = skipConsultLabel.locator('input[type="checkbox"]');
      if ((await skipCheckbox.count()) > 0 && !(await skipCheckbox.isChecked())) {
        await skipCheckbox.click();
      }
    }

    const saveVitalsBtn = page.locator('button').filter({ hasText: /Đo xong/i }).first();
    await saveVitalsBtn.click();
    await expect(page.getByRole('status')).toBeVisible({ timeout: 10000 });

    // --- BƯỚC 2: BÁC SĨ KHÁM CHÍNH TẠI /ban-kham ---
    // Đăng xuất hoặc đăng nhập với tài khoản Bác sĩ
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' });
    await page.fill('input#email', DOCTOR_EMAIL);
    await page.fill('input#password', MAT_KHAU);
    await page.click('button[type="submit"]');
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

    await page.goto(`${BASE_URL}/ban-kham`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1500);

    // Tìm và chọn bệnh nhân trong hàng chờ bàn khám
    const docPatientBtn = page.locator('button').filter({ hasText: new RegExp(patientName, 'i') }).first();
    await docPatientBtn.waitFor({ state: 'attached', timeout: 10000 });
    await docPatientBtn.click({ force: true });
    await page.waitForTimeout(1000);

    // Bấm nút "Bắt đầu khám"
    const startExamBtn = page.locator('button:visible').filter({ hasText: /Bắt đầu khám/i }).first();
    if ((await startExamBtn.count()) > 0) {
      await startExamBtn.click();
      await page.waitForTimeout(1000);
    }

    // Chuyển sang Khối 2: Chỉ định cận lâm sàng bằng nút khối ở cột phải hoặc nút chuyển tiếp
    const block2RayBtn = page.locator('aside button').filter({ hasText: /Chỉ định cận lâm sàng/i }).first();
    const nextBlockBtn = page.locator('button').filter({ hasText: /Sang:.*Chỉ định cận lâm sàng/i }).first();
    if ((await block2RayBtn.count()) > 0 && (await block2RayBtn.isVisible())) {
      await block2RayBtn.click();
    } else if ((await nextBlockBtn.count()) > 0) {
      await nextBlockBtn.click();
    }
    await page.waitForTimeout(1000);

    // Mở ngăn gập Dịch vụ khác trong bảng giá nếu có
    const otherGroupBtn = page.locator('button').filter({ hasText: /Dịch vụ khác trong bảng giá/i }).first();
    if ((await otherGroupBtn.count()) > 0) {
      await otherGroupBtn.click();
      await page.waitForTimeout(500);
    }

    // Tìm ô tick cho dịch vụ Siêu âm 2D tử cung buồng trứng (hoặc Siêu âm tử cung buồng trứng)
    const ultrasoundOption = page.locator('label').filter({ hasText: /Siêu âm.*tử cung|Siêu âm 2D/i }).first();
    await expect(ultrasoundOption).toBeVisible({ timeout: 10000 });
    await ultrasoundOption.scrollIntoViewIfNeeded();
    await ultrasoundOption.click();
    await page.waitForTimeout(500);

    // Bấm nút xác nhận chỉ định
    const orderBtn = page.locator('button:visible').filter({ hasText: /Chỉ định \d+ mục|Chỉ định/i }).first();
    await expect(orderBtn).toBeEnabled({ timeout: 10000 });
    await orderBtn.click();
    await page.waitForTimeout(2000);

    // Bấm nút "Hoàn tất" ở cột phải
    const finishBtn = page.locator('button:visible').filter({ hasText: /^Hoàn tất$/ }).first();
    await expect(finishBtn).toBeVisible({ timeout: 10000 });
    await finishBtn.scrollIntoViewIfNeeded();
    await finishBtn.click();
    await page.waitForTimeout(1500);

    // Xác nhận tại chỗ nếu có popup/dải xác nhận
    const confirmDialogBtn = page.locator('button:visible').filter({ hasText: /^Hoàn tất$/ });
    if ((await confirmDialogBtn.count()) > 1) {
      await confirmDialogBtn.last().click();
      await page.waitForTimeout(1500);
    }

    // Xác nhận đã hoàn tất khám: nhãn "Đã khám xong" hiển thị
    await expect(page.locator('text=Đã khám xong').first()).toBeVisible({ timeout: 15000 });
  });
});
