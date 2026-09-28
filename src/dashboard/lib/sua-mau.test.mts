import assert from "node:assert/strict";
import test from "node:test";

import { donKhung, ganMaMoi, maMoi, maOTrongMau, nhacTruocXuatBan, slugMa, tenMucHien, type MucMau } from "./sua-mau.ts";

const MAU: MucMau[] = [
  {
    ma: "mo_ta",
    ten: "Mô tả",
    cot: [{ ma: "thai_a", ten: "Thai A" }],
    block: [
      { ma: "tim_thai", ten: "Tim thai", kieu: "text", mac_dinh: { thai_a: " dương tính ", la: "x" } },
      { ma: "crl", ten: "CRL", kieu: "chon", chon: [" Có ", ""], goi_y: "  " },
    ],
  },
  { ma: "ket_luan", ten: "Kết luận", block: [{ ma: "ket_luan", ten: "Kết luận", kieu: "doan_van" }] },
];

test("slugMa bỏ dấu, chữ đ, ký tự lạ", () => {
  assert.equal(slugMa("Buồng trứng trái (mm)"), "buong_trung_trai_mm");
  assert.equal(slugMa("Đường kính"), "duong_kinh");
  assert.equal(slugMa("!!!"), "o");
});

test("mã mới không trùng mã đang có trên CẢ mẫu", () => {
  const co = maOTrongMau(MAU);
  assert.equal(maMoi("Tim thai", co), "tim_thai_2");
  assert.equal(maMoi("Kết luận", co), "ket_luan_2");
  assert.equal(maMoi("Nhau thai", co), "nhau_thai");
});

test("đổi tên ô không đổi mã — donKhung giữ nguyên mã", () => {
  const sua = structuredClone(MAU);
  sua[0].block[0].ten = "Tim thai (FHR)";
  assert.equal(donKhung(sua)[0].block[0].ma, "tim_thai");
});

test("donKhung bỏ trường rỗng và mặc định cho cột lạ", () => {
  const d = donKhung(MAU);
  assert.deepEqual(d[0].block[0].mac_dinh, { thai_a: " dương tính " });
  assert.deepEqual(d[0].block[1].chon, ["Có"]);
  assert.equal(d[0].block[1].goi_y, undefined);
});

test("donKhung GIỮ cách vẽ ô tích nhanh của ô chọn; đổi sang kiểu khác thì bỏ", () => {
  // "Kết luận nhanh" phiếu đo mật độ xương (29/09/2026): sửa mẫu ở Cài đặt rồi
  // xuất bản lại không được làm ba ô tích biến thành hộp thả xuống.
  const k: MucMau[] = [
    {
      ma: "ket_luan",
      ten: "Kết luận",
      block: [
        {
          ma: "ket_luan_nhanh",
          ten: "Kết luận nhanh",
          kieu: "chon",
          chon: ["Bình thường", "Tiền loãng xương", "Loãng xương"],
          hien_thi: "o_tick",
        },
      ],
    },
  ];
  assert.equal(donKhung(k)[0].block[0].hien_thi, "o_tick");
  const doiKieu = structuredClone(k);
  doiKieu[0].block[0].kieu = "text";
  assert.equal(donKhung(doiKieu)[0].block[0].hien_thi, undefined);
});

test("nhắc: chọn không có lựa chọn, thiếu kết luận", () => {
  const k: MucMau[] = [{ ma: "a", ten: "A", block: [{ ma: "b", ten: "B", kieu: "chon", chon: [" "] }] }];
  const n = nhacTruocXuatBan(k);
  assert.ok(n.some((x) => x.includes("chưa có lựa chọn")));
  assert.ok(n.some((x) => x.includes("Kết luận")));
  assert.deepEqual(nhacTruocXuatBan(MAU), []);
});

test("ô / mục / cột mới nhận mã từ tên cuối cùng, không trùng; mã cũ giữ", () => {
  const k = structuredClone(MAU);
  k[0].block.push({ ma: "", ten: "Tim thai", kieu: "text" });
  k[0].cot!.push({ ma: "", ten: "Thai B" });
  k.push({ ma: "", ten: "Mô tả", block: [{ ma: "", ten: "Nhau thai", kieu: "text" }] });
  const r = ganMaMoi(k);
  assert.equal(r[0].block[0].ma, "tim_thai");
  assert.equal(r[0].block[2].ma, "tim_thai_2");
  assert.equal(r[0].cot![1].ma, "thai_b");
  assert.equal(r[2].ma, "mo_ta_2");
  assert.equal(r[2].block[0].ma, "nhau_thai");
});

test("tenMucHien: tên giữ chỗ / rỗng / rác → không vẽ tiêu đề mục", () => {
  assert.equal(tenMucHien("Kết quả soi"), "Kết quả soi");
  assert.equal(tenMucHien("  Đề nghị  "), "Đề nghị");
  assert.equal(tenMucHien("(không có tiêu đề mục)"), null);
  assert.equal(tenMucHien(" (Không có tiêu đề mục) "), null);
  assert.equal(tenMucHien("(không có tiêu đề mục)".normalize("NFD")), null);
  assert.equal(tenMucHien("không có tiêu đề"), null);
  assert.equal(tenMucHien(""), null);
  assert.equal(tenMucHien("   "), null);
  assert.equal(tenMucHien(null), null);
  assert.equal(tenMucHien(undefined), null);
  assert.equal(tenMucHien(42), null);
  // Tên thật có chữ "tiêu đề" vẫn giữ.
  assert.equal(tenMucHien("Tiêu đề phụ"), "Tiêu đề phụ");
});
