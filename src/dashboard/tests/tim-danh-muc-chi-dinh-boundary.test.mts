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

// C21 (02/10/2026): bác sĩ phụ khoa tìm "Ghế điện từ trường" ở Chỉ định cận lâm
// sàng không thấy (nó chỉ nằm ở danh sách thủ thuật phiếu Sàn chậu). Máy chủ nay
// gửi MỌI dịch vụ ở mục C; màn: ô tìm + nút Tìm luôn hiện, danh mục mở sẵn.
test("gõ 'ghe dien' ra Ghế điện từ trường; ô tìm luôn hiện + nút Tìm + mở sẵn", async () => {
  const ds: NhomCls[] = [
    ...DS,
    {
      nhom: `Dịch vụ khác${HAU_TO_DANH_MUC_PK}`,
      muc: [muc("Ghế điện từ trường", "CLS_GHE_DTT", { nhom_hang: "Dịch vụ khác" })],
    },
    {
      nhom: `Phí khám${HAU_TO_DANH_MUC_PK}`,
      muc: [muc("Khám nam khoa", "KHAM_NAM_KHOA", { nhom_hang: "Phí khám" })],
    },
  ];
  assert.deepEqual(
    timDanhMucChiDinh(ds, "ghe dien").flatMap((n) => n.muc.map((m) => m.service_code)),
    ["CLS_GHE_DTT"],
  );
  assert.equal(timDanhMucChiDinh(ds, "kham nam").flatMap((n) => n.muc).length, 1);

  const { readFileSync } = await import("node:fs");
  const src = readFileSync(
    new URL("../app/(dashboard)/_lam-viec/phieu-kham/DanhMucChiDinh.tsx", import.meta.url),
    "utf8",
  );
  assert.match(src, /\{!chiDoc \|\| hienDanhMuc \? \(\s*<form/, "ô tìm hiện cả khi danh mục gập");
  assert.match(src, /<Button type="submit" variant="secondary">\s*Tìm\s*<\/Button>/);
  assert.match(src, /useState\(true\)/, "danh mục mở sẵn");
  assert.match(src, /<NganGap\s+moSan/, "ngăn Dịch vụ khác mở sẵn");
});

// C21: dịch vụ nằm dưới NHÃN PHIẾU GIẤY cũ ("Đo cơ lực âm đạo bằng máy (sàng
// lọc)") phải tìm được và hiện bằng TÊN THẬT của bảng giá.
test("tìm theo tên thật bảng giá; tên thật là tên chính, nhãn phiếu giấy là dòng phụ", async () => {
  const { tenHienMuc } = await import("../lib/phieu-kham.ts");
  const bio = muc("Đo cơ lực âm đạo bằng máy (sàng lọc)", "CLS_DO_CO_LUC_AM_DAO", {
    ten_dich_vu: "Đo trương lực cơ sàn chậu máy Bio (ko bao gồm đầu dò)",
  });
  const ds: NhomCls[] = [{ nhom: "Sàn chậu — đánh giá", muc: [bio] }];
  for (const tu of ["truong luc", "may bio", "co luc am dao"]) {
    assert.equal(timDanhMucChiDinh(ds, tu).flatMap((n) => n.muc).length, 1, tu);
  }
  assert.deepEqual(tenHienMuc(bio), {
    chinh: "Đo trương lực cơ sàn chậu máy Bio (ko bao gồm đầu dò)",
    phieuGiay: "Đo cơ lực âm đạo bằng máy (sàng lọc)",
  });
  assert.deepEqual(tenHienMuc(muc("Siêu âm ổ bụng", "X", { ten_dich_vu: "Siêu âm ổ bụng" })), {
    chinh: "Siêu âm ổ bụng",
    phieuGiay: null,
  });
  assert.deepEqual(tenHienMuc(muc("Ghế ĐTT", null)), { chinh: "Ghế ĐTT", phieuGiay: null });
});
