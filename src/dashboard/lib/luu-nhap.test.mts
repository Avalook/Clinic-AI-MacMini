import assert from "node:assert/strict";
import test from "node:test";

import {
  HAN_MS,
  docNhap,
  donNhapCu,
  ghiNhap,
  khoaNhap,
  moTaLuc,
  xoaNhap,
  type KhoNhap,
} from "./luu-nhap.ts";

/** Kho giả — đủ dùng cho phần logic, không cần trình duyệt. */
function khoGia(): KhoNhap & { data: Map<string, string>; chan?: boolean } {
  const data = new Map<string, string>();
  return {
    data,
    get length() {
      return data.size;
    },
    key(i: number) {
      return Array.from(data.keys())[i] ?? null;
    },
    getItem(k: string) {
      return data.get(k) ?? null;
    },
    setItem(k: string, v: string) {
      if ((this as { chan?: boolean }).chan) throw new Error("QuotaExceeded");
      data.set(k, v);
    },
    removeItem(k: string) {
      data.delete(k);
    },
  };
}

const T0 = 1_760_000_000_000; // mốc cố định: test không được phụ thuộc đồng hồ

test("khoaNhap: thiếu người đăng nhập hoặc thiếu hồ sơ thì KHÔNG lưu", () => {
  // Máy ở quầy dùng chung. Không biết ai đang ngồi thì không được để lại gì.
  assert.equal(khoaNhap(null, "benh-an", "appt-1"), null);
  assert.equal(khoaNhap("", "benh-an", "appt-1"), null);
  assert.equal(khoaNhap("staff-1", "benh-an", null), null);
  assert.equal(khoaNhap("staff-1", "benh-an", "appt-1"), "clinicai:nhap:staff-1:benh-an:appt-1");
});

test("khoaNhap: hai người khác nhau trên cùng một hồ sơ ra hai khoá khác nhau", () => {
  const a = khoaNhap("staff-A", "benh-an", "appt-9");
  const b = khoaNhap("staff-B", "benh-an", "appt-9");
  assert.notEqual(a, b);
});

test("ghi rồi đọc lại đúng nội dung", () => {
  const kho = khoGia();
  const k = khoaNhap("staff-1", "benh-an", "appt-1")!;
  ghiNhap(kho, k, { chan_doan: "Viêm họng", ghi_chu: "dị ứng Penicillin" }, T0);
  const b = docNhap<{ chan_doan: string; ghi_chu: string }>(kho, k, T0 + 1000);
  assert.equal(b?.giaTri.chan_doan, "Viêm họng");
  assert.equal(b?.giaTri.ghi_chu, "dị ứng Penicillin");
});

test("nháp quá 24 giờ coi như không có, và bị xoá luôn khi đọc", () => {
  const kho = khoGia();
  const k = khoaNhap("staff-1", "benh-an", "appt-1")!;
  ghiNhap(kho, k, { a: 1 }, T0);
  assert.equal(docNhap(kho, k, T0 + HAN_MS - 1000)?.giaTri !== undefined, true, "trong hạn thì còn");
  assert.equal(docNhap(kho, k, T0 + HAN_MS + 1000), null, "quá hạn thì mất");
  assert.equal(kho.data.size, 0, "và bị dọn khỏi máy, không nằm lại");
});

test("nội dung hỏng thì bỏ qua, không làm sập màn hình", () => {
  const kho = khoGia();
  const k = khoaNhap("staff-1", "benh-an", "appt-1")!;
  kho.data.set(k, "{ đây không phải JSON");
  assert.equal(docNhap(kho, k, T0), null);
});

test("xoá sau khi lưu thành công thì không còn gì trên máy", () => {
  const kho = khoGia();
  const k = khoaNhap("staff-1", "benh-an", "appt-1")!;
  ghiNhap(kho, k, { a: 1 }, T0);
  xoaNhap(kho, k);
  assert.equal(kho.data.size, 0);
});

test("donNhapCu: chỉ dọn bản quá hạn, giữ bản còn hạn, không đụng khoá của app khác", () => {
  const kho = khoGia();
  const cu = khoaNhap("staff-1", "benh-an", "cu")!;
  const moi = khoaNhap("staff-1", "benh-an", "moi")!;
  ghiNhap(kho, cu, { a: 1 }, T0 - HAN_MS - 5000);
  ghiNhap(kho, moi, { a: 2 }, T0);
  kho.data.set("thu-cua-app-khac", "giu-nguyen");

  assert.equal(donNhapCu(kho, T0), 1);
  assert.equal(kho.getItem(cu), null);
  assert.notEqual(kho.getItem(moi), null);
  assert.equal(kho.getItem("thu-cua-app-khac"), "giu-nguyen");
});

test("kho bị chặn (chế độ riêng tư, hết chỗ) thì KHÔNG được ném", () => {
  // Ném ở đây là làm hỏng chính cái nó định cứu: người dùng đang gõ dở.
  const kho = khoGia();
  kho.chan = true;
  const k = khoaNhap("staff-1", "benh-an", "appt-1")!;
  assert.doesNotThrow(() => ghiNhap(kho, k, { a: 1 }, T0));
  assert.equal(docNhap(kho, k, T0), null);
});

test("moTaLuc: nói được nháp cũ tới mức nào", () => {
  assert.equal(moTaLuc(T0, T0 + 5_000), "vừa xong");
  assert.equal(moTaLuc(T0, T0 + 120_000), "2 phút trước");
  assert.equal(moTaLuc(T0, T0 + 2 * 3_600_000), "2 giờ trước");
});
