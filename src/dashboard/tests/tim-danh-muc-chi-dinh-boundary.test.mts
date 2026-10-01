// TÌM TRONG DANH MỤC CHỈ ĐỊNH (Tuyền 01/10/2026: "danh sách chỉ định đang thiếu
// rất nhiều; KHÔNG được để dịch vụ nào bị lọt"). Gõ "PRP" / "NIPT" / "liên cầu"
// phải ra cả mục nằm trong ngăn gập "Dịch vụ khác trong bảng giá", gom theo nhóm
// hàng, mỗi dịch vụ một lần, không phân biệt dấu.

import assert from "node:assert/strict";
import test from "node:test";

import {
  HAU_TO_DANH_MUC_PK,
  boDauTim,
  gomTheoNhomGoc,
  timDanhMucChiDinh,
  type NhomCls,
} from "../lib/phieu-kham.ts";

const muc = (nhan: string, service_code: string | null, extra: object = {}) => ({
  nhan,
  cach_tra_ket_qua: "",
  form_id_ket_qua: null,
  service_code,
  ...extra,
});

const DS: NhomCls[] = [
  { nhom: "Siêu âm", muc: [muc("SÂ 2D TC-BT", "CLS_2D", { nhom_hang: "Siêu âm" })] },
  {
    nhom: `Dịch vụ khác${HAU_TO_DANH_MUC_PK}`,
    muc: [
      muc("Bơm PRP niêm mạc tử cung (Tropocel)", "KV_SP000140", { nhom_hang: "Dịch vụ khác" }),
      muc("Bơm PRP niêm mạc tử cung (Regenlab)", "KV_SP000136", { nhom_hang: "Dịch vụ khác" }),
    ],
  },
  {
    nhom: `XN thu hộ${HAU_TO_DANH_MUC_PK}`,
    muc: [
      muc("NIPT basic", "KV_SP000173", { nhom_hang: "XN thu hộ", gia: 0, doi_tac_thu: true }),
      muc("Liên cầu B", "KV_SP000172", { nhom_hang: "XN thu hộ", gia: 0, doi_tac_thu: true }),
    ],
  },
  // Cùng một dịch vụ xuất hiện hai lần (phiếu giấy + danh mục) → một kết quả.
  { nhom: "Lặp", muc: [muc("NIPT basic", "KV_SP000173", { nhom_hang: "XN thu hộ" })] },
];

test("gõ PRP / NIPT / liên cầu (không dấu) ra cả mục trong ngăn gập", () => {
  const prp = timDanhMucChiDinh(DS, "prp");
  assert.deepEqual(
    prp.flatMap((n) => n.muc.map((m) => m.service_code)),
    ["KV_SP000140", "KV_SP000136"],
  );
  assert.equal(prp[0].nhom, "Dịch vụ khác");

  const nipt = timDanhMucChiDinh(DS, "  NIPT ");
  assert.equal(nipt.flatMap((n) => n.muc).length, 1, "mỗi dịch vụ một lần");

  const lc = timDanhMucChiDinh(DS, "lien cau");
  assert.equal(lc[0].nhom, "XN thu hộ");
  assert.equal(lc[0].muc[0].gia, 0, "XN thu hộ 0đ vẫn là giá (không phải 'chưa có giá')");
});

test("tìm theo nhóm hàng; rỗng / rác không ném", () => {
  assert.equal(timDanhMucChiDinh(DS, "xn thu ho").flatMap((n) => n.muc).length, 2);
  assert.deepEqual(timDanhMucChiDinh(DS, ""), []);
  assert.deepEqual(timDanhMucChiDinh([], "abc"), []);
  assert.deepEqual(timDanhMucChiDinh(null as unknown as NhomCls[], "abc"), []);
  assert.equal(boDauTim("Siêu Âm Đầu Dò"), "sieu am dau do");
});

test("ngăn 'Dịch vụ khác' gom theo nhóm hàng, giữ thứ tự", () => {
  const g = gomTheoNhomGoc([
    { nhom_goc: "Siêu âm", x: 1 },
    { nhom_goc: "XN thu hộ", x: 2 },
    { nhom_goc: "Siêu âm", x: 3 },
  ]);
  assert.deepEqual(
    g.map(([ten, ds]) => [ten, ds.map((d) => d.x)]),
    [
      ["Siêu âm", [1, 3]],
      ["XN thu hộ", [2]],
    ],
  );
});
