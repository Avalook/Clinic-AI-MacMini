// Chỉ định cũ đã đưa vào hôm nay ([Làm hôm nay]) phải luôn trả về được — không
// chỉ trong vài giây của thông báo — và KHÔNG bằng lệnh huỷ (huỷ chỉ định khách
// đã trả hôm trước biến tiền thành tiền thừa). Bấm staging 29/10/2026.
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const doc = (p: string) => readFileSync(new URL(p, import.meta.url), "utf8");

test("thẻ chỉ định: phiếu nháp mà chưa thu tiền không gọi là 'Đang làm'", () => {
  const the = doc("../app/(dashboard)/_lam-viec/phieu-kham/KetQuaChiDinh.tsx");
  assert.match(the, /if \(nhapChuaThu\) return \{ nhan: "Chờ thu tiền · phiếu nháp", tone: "warning" \};/);
  assert.ok(the.indexOf("if (nhapChuaThu)") < the.indexOf('"Đã gửi đối tác" : "Đang làm"'));
});

test("khung chỉ định cũ tự nạp lại khi chỉ định đổi ở chỗ khác (Để lần sau trên thẻ)", () => {
  const k = doc("../app/(dashboard)/_lam-viec/phieu-kham/ChiDinhCuChuaLam.tsx");
  assert.match(k, /useNgheBang\(\["service_order"\], nap\)/);
});

test("thẻ chỉ định mang sang: nút Để lần sau (về lượt cũ) thay cho Hoàn tác chỉ định", () => {
  const the = doc("../app/(dashboard)/_lam-viec/phieu-kham/KetQuaChiDinh.tsx");
  assert.match(the, /\{d\.mang_sang && onTraVeLuotCu && !chiXem \? \(\s*<NutHoanTac\s+nhan="Để lần sau"/);
  // Nhánh huỷ chỉ là nhánh CÒN LẠI, không bao giờ cùng hiện với Trả về.
  assert.match(the, /\) : onBoChiDinh && !chiXem \? \(\s*<NutHoanTac\s+nhan="Hoàn tác chỉ định"/);
  const luot = doc("../app/(dashboard)/_lam-viec/phieu-kham/PhieuKhamLuot.tsx");
  assert.match(luot, /lenhHoanTac\("tra-ve-luot-cu", id, \{ visit_id: visitId \}\)/);
});
