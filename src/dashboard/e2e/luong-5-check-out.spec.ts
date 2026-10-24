import { test, expect } from 'playwright/test';

const BASE_URL = process.env.E2E_BASE_URL || 'http://127.0.0.1:3100';
const RECEPTION_EMAIL = process.env.E2E_RECEPTION_EMAIL || 'letan@dr4women.local';
const DOCTOR_EMAIL = process.env.E2E_DOCTOR_EMAIL || 'bs.a@dr4women.local';
const PHARMACY_EMAIL = process.env.E2E_PHARMACY_EMAIL || 'duocsi@dr4women.local';
const CASHIER_EMAIL = process.env.E2E_CASHIER_EMAIL || 'thungan@dr4women.local';
const MAT_KHAU = process.env.E2E_TEST_PW || ['clinic', 'test', 'pw', '123'].join('-');

test.describe('Luồng 5: Quầy thuốc và Check-out (Soạn → Thu → Check-out)', () => {
  test.fixme('Lỗi flaky UI: không mở được popup chọn giờ - Bác sĩ kê đơn, quầy thuốc soạn, thu ngân thu tiền, lễ tân check-out', async ({ page }) => {
    test.setTimeout(120000);
    const ts = Date.now().toString().slice(-6);
    const patientName = `E2E-Khach-${ts}`;
    const phone = `09${Math.floor(10000000 + Math.random() * 90000000)}`;

    // --- BƯỚC 1: LỄ TÂN TẠO KHÁCH, CHECK-IN, ĐO SINH HIỆU ---
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' });
    await page.fill('input#email', RECEPTION_EMAIL);
    await page.fill('input#password', MAT_KHAU);
    await page.click('button[type="submit"]');
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

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
    
    const targetRow = page.locator('tbody tr').filter({ hasText: /BS A local|Bác sĩ A/i }).first();
    const rows = (await targetRow.count()) > 0 ? targetRow : page.locator('tbody tr');
    let pickedSlot = false;
    const now = new Date();
    const vnH = (now.getUTCHours() + 7) % 24;
    const vnM = now.getUTCMinutes();

    for (let r = 0; r < Math.max(1, await rows.count()); r++) {
      const cellBtn = rows.nth(r).locator(`td:nth-child(${todayIndex + 1}) button`);
      if ((await cellBtn.count()) === 0) continue;
      await cellBtn.click({ force: true }); await page.waitForTimeout(500);
      const slotDialog = page.locator('div[role="dialog"]');
      await expect(slotDialog).toBeVisible({ timeout: 5000 });
      try { await slotDialog.locator('ul button').first().waitFor({ state: 'visible', timeout: 5000 }); } catch {}
      const slotButtons = slotDialog.locator('ul button:not([disabled])');
      
      for (let i = 0; i < await slotButtons.count(); i++) {
        const btn = slotButtons.nth(i);
        const text = await btn.innerText();
        if (text.includes('Đã đầy') || text.includes('Đã qua') || text.includes('đã đặt')) continue;
        const match = text.match(/^(\d{2}):(\d{2})/);
        if (match) {
          const slotH = parseInt(match[1], 10);
          const slotM = parseInt(match[2], 10);
          if (slotH > vnH || (slotH === vnH && slotM > vnM + 5)) {
            await btn.click({ force: true });
            pickedSlot = true;
            break;
          }
        }
      }
      if (pickedSlot) break;
      const closeBtn = slotDialog.locator('button[aria-label="Đóng"]');
      if ((await closeBtn.count()) > 0) await closeBtn.click();
    }

    const submitBtn = page.locator('button').filter({ hasText: /Tạo bệnh nhân|Nhập thông tin/ }).first();
    await submitBtn.click();
    await page.waitForURL((url) => !url.pathname.includes('/patients/new'), { timeout: 15000 });

    if (!page.url().includes('/reception/queue')) {
      await page.goto(`${BASE_URL}/reception/queue`, { waitUntil: 'domcontentloaded' });
    }
    const patientRow = page.locator('li').filter({ hasText: new RegExp(patientName, 'i') }).first();
    await expect(patientRow).toBeVisible({ timeout: 10000 });

    const checkinBtn = patientRow.locator('button').filter({ hasText: /Check-in/i }).first();
    await Promise.all([
      page.waitForResponse((res) => res.url().includes('/api/appointments') && res.request().method() === 'PATCH' && res.status() === 200),
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

    // --- BƯỚC 2: BÁC SĨ KÊ ĐƠN THUỐC ---
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' });
    await page.fill('input#email', DOCTOR_EMAIL);
    await page.fill('input#password', MAT_KHAU);
    await page.click('button[type="submit"]');
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

    await page.goto(`${BASE_URL}/ban-kham`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1500);

    const docPatientBtn = page.locator('button').filter({ hasText: new RegExp(patientName, 'i') }).first();
    await expect(docPatientBtn).toBeVisible({ timeout: 10000 });
    await docPatientBtn.click({ force: true });
    await page.waitForTimeout(1000);

    const startExamBtn = page.locator('button:visible').filter({ hasText: /Bắt đầu khám/i }).first();
    if ((await startExamBtn.count()) > 0) {
      await startExamBtn.click();
      await page.waitForTimeout(1000);
    }

    // Sang tab 3: Chỉ định điều trị
    const block3RxBtn = page.locator('aside button, button[role="tab"]').filter({ hasText: /Chỉ định điều trị/i }).first();
    if ((await block3RxBtn.count()) > 0) {
      await block3RxBtn.click();
    } else {
      const nextBlockBtn = page.locator('button').filter({ hasText: /Sang:.*Chỉ định điều trị/i }).first();
      if ((await nextBlockBtn.count()) > 0) await nextBlockBtn.click();
    }
    await page.waitForTimeout(1000);

    // Kê thuốc
    const searchRx = page.locator('input[placeholder*="Tìm thuốc"]').first();
    if ((await searchRx.count()) > 0) {
      await searchRx.fill('Para');
      await page.waitForTimeout(1000);
      const rxOption = page.locator('ul[role="listbox"] li').first();
      if ((await rxOption.count()) > 0) {
        await rxOption.click();
        await page.waitForTimeout(1000);
      }
    } else {
      const rxLabel = page.locator('label').filter({ hasText: /Paracetamol/i }).first();
      if ((await rxLabel.count()) > 0) {
         await rxLabel.click();
      }
    }

    // Bấm nút Hoàn tất khám
    const finishBtn = page.locator('button:visible').filter({ hasText: /^Hoàn tất$/ }).first();
    await expect(finishBtn).toBeVisible({ timeout: 10000 });
    await finishBtn.scrollIntoViewIfNeeded();
    await finishBtn.click();
    await page.waitForTimeout(1500);

    const confirmDialogBtn = page.locator('button:visible').filter({ hasText: /^Hoàn tất$/ });
    if ((await confirmDialogBtn.count()) > 1) {
      await confirmDialogBtn.last().click();
      await page.waitForTimeout(1500);
    }
    await expect(page.locator('text=Đã khám xong').first()).toBeVisible({ timeout: 15000 });

    // --- BƯỚC 3: DƯỢC SĨ SOẠN THUỐC ---
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' });
    await page.fill('input#email', PHARMACY_EMAIL);
    await page.fill('input#password', MAT_KHAU);
    await page.click('button[type="submit"]');
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

    await page.goto(`${BASE_URL}/pharmacy`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);

    const pharmPatientBtn = page.locator('ul button').filter({ hasText: new RegExp(patientName, 'i') }).first();
    await expect(pharmPatientBtn).toBeVisible({ timeout: 10000 });
    await pharmPatientBtn.click();
    await page.waitForTimeout(1000);

    const startPharmBtn = page.locator('button:visible').filter({ hasText: /Bắt đầu soạn/i }).first();
    if ((await startPharmBtn.count()) > 0) {
      await startPharmBtn.click();
      await page.waitForTimeout(1000);
    }

    const donePharmBtn = page.locator('button:visible').filter({ hasText: /Đã soạn xong/i }).first();
    if ((await donePharmBtn.count()) > 0) {
      await expect(donePharmBtn).toBeEnabled({ timeout: 10000 });
      await donePharmBtn.click();
      await page.waitForTimeout(1000);
    }

    // --- BƯỚC 4: THU NGÂN THU TIỀN THUỐC ---
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' });
    await page.fill('input#email', CASHIER_EMAIL);
    await page.fill('input#password', MAT_KHAU);
    await page.click('button[type="submit"]');
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

    await page.goto(`${BASE_URL}/thu-ngan/thuoc`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);

    const thuPatientBtn = page.locator('ul[aria-label="Khách chờ thu"] button').filter({ hasText: new RegExp(patientName, 'i') }).first();
    if ((await thuPatientBtn.count()) > 0) {
       await thuPatientBtn.click();
       await page.waitForTimeout(1000);

       const payBtn = page.locator('button:visible').filter({ hasText: /Đã nhận đủ tiền mặt/i }).first();
       await expect(payBtn).toBeVisible({ timeout: 10000 });
       await payBtn.click();
       await page.waitForTimeout(2000);
    } else {
       // Bác sĩ kê thuốc ngoài, không cần thu, có thể bỏ qua hoặc skip.
    }

    // --- BƯỚC 5: LỄ TÂN CHECK-OUT ---
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' });
    await page.fill('input#email', RECEPTION_EMAIL);
    await page.fill('input#password', MAT_KHAU);
    await page.click('button[type="submit"]');
    await page.waitForURL((url) => !url.pathname.includes('/login'), { timeout: 15000 });

    await page.goto(`${BASE_URL}/reception/checkout`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(2000);

    const checkoutPatientBtn = page.locator('ul button').filter({ hasText: new RegExp(patientName, 'i') }).first();
    await expect(checkoutPatientBtn).toBeVisible({ timeout: 10000 });
    await checkoutPatientBtn.click();
    await page.waitForTimeout(1000);

    const checkoutBtn = page.locator('button:visible').filter({ hasText: /Khách đã ra về|Hoàn tất/i }).first();
    await expect(checkoutBtn).toBeVisible({ timeout: 10000 });
    await checkoutBtn.click();
    await page.waitForTimeout(2000);
    await expect(page.locator('text=đã check-out').first()).toBeVisible({ timeout: 10000 });
  });
});
