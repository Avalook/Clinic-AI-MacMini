import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

// THAY CHO `cashier-reconciliation-ui-boundary.test.mts`. Bài cũ khoá ba vùng
// của màn "Đối soát chi phí" — một quy trình đối soát mà Tuyền chốt 16/09 là
// phòng khám không cần: "thu ngân thì cần gì đối soát, nó là thu ngân dịch vụ
// luôn, hiện các dịch vụ khách đó khám ra và tính tiền là xong á".
//
// Bài mới khoá thứ dễ hỏng hơn nhiều: CÁCH XỬ LÝ DÒNG CHƯA CÓ GIÁ.

const quay = readFileSync(
  new URL("../app/(dashboard)/cashier/board/QuayThuNgan.tsx", import.meta.url),
  "utf8",
);

test("giá trống hiện ra là trống, không hiện thành 0đ", () => {
  // Hôm nay bảng giá mới có 1/39 dịch vụ và 0/80 thuốc có giá. Một dòng "0đ"
  // trông như miễn phí; một dòng "chưa có giá" trông như thiếu dữ liệu. Chỉ
  // cái sau là sự thật, và chỉ cái sau khiến có người đi hỏi phòng khám.
  assert.match(quay, /chưa có giá/);
  // Không có `?? 0` / `|| 0` khi hiện giá của MỘT DÒNG: đó đúng là cách một
  // dòng thiếu giá lặng lẽ thành 0đ.
  assert.doesNotMatch(quay, /d\.price\s*(\?\?|\|\|)\s*0/);
});

test("còn dòng chưa có giá thì KHÔNG bấm thu được", () => {
  // Thu thiếu rồi ghi sổ là đã thu đủ thì sai lệch ấy không còn chỗ nào lộ ra.
  assert.match(quay, /disabled=\{[^}]*thieuGia\s*>\s*0/);
  assert.match(quay, /disabled=\{[^}]*tong\s*<=\s*0/);
});

test("cộng tiền bỏ qua dòng thiếu giá và đếm chúng lại", () => {
  assert.match(quay, /function congDong/);
  assert.match(quay, /thieuGia\s*\+=\s*1/);
});

test("quầy nào hiện ô nào là theo VAI, không theo URL", () => {
  const trang = readFileSync(
    new URL("../app/(dashboard)/cashier/board/page.tsx", import.meta.url),
    "utf8",
  );
  assert.match(trang, /getClinicRole/);
  assert.match(trang, /CASHIER_THUOC/);
  assert.match(trang, /CASHIER_DV/);
  // Không đọc quầy từ query string — gõ URL là đổi được quầy thì cái gác vô nghĩa.
  assert.doesNotMatch(trang, /searchParams/);
});
