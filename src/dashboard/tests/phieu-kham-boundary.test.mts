// BẢY PHIẾU KHÁM — phép biến đổi thuần của màn vẽ phiếu.
//
// Chạy trên CHÍNH bảy khung JSON mà máy chủ nạp (src/clinicai/phieu_kham/
// dinh_nghia), không trên khung giả: nếu bộ trích đổi hình khung mà màn không
// theo kịp, bài này đỏ trước khi bác sĩ thấy một ô biến mất.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  batTatLuaChon,
  donTuDong,
  dongTuDon,
  dongTuMau,
  dungGoiLuu,
  ghiDuoc,
  giaTriDoc,
  gomNhom,
  hienThi,
  locMauThuoc,
  oDangHien,
  oThuGonDangAn,
  type MauThuoc,
  type MucPhieu,
  type OPhieu,
  tenPhieuKetQua,
} from "../lib/phieu-kham.ts";

const FORM_IDS = ["NT", "HMVS", "PK", "SK", "NK", "THU_THUAT", "SAN_CHAU"];

function khung(formId: string): MucPhieu[] {
  const url = new URL(
    `../../clinicai/phieu_kham/dinh_nghia/${formId}.json`,
    import.meta.url,
  );
  return JSON.parse(readFileSync(url, "utf8")).khung as MucPhieu[];
}

function oTrongKetQuaGom(block: OPhieu[]): string[] {
  const ra: string[] = [];
  for (const n of gomNhom(block)) {
    for (const d of n.don_vi) {
      if (d.loai === "o") ra.push(d.o.ma);
      else for (const h of d.hang) for (const o of h.o) if (o) ra.push(o.ma);
    }
  }
  return ra;
}

test("gom nhóm không làm rơi hay nhân đôi ô nào — cả bảy phiếu", () => {
  for (const f of FORM_IDS) {
    for (const muc of khung(f)) {
      const goc = muc.block.map((o) => o.ma);
      assert.deepEqual(oTrongKetQuaGom(muc.block).sort(), [...goc].sort(), `${f}.${muc.ma}`);
    }
  }
});

test("tinh dịch đồ: một bảng, 9 hàng × 2 lần, không ô nào hụt", () => {
  const b = khung("HMVS").find((m) => m.ma === "B")!;
  const nhom = gomNhom(b.block).find((n) => n.tieu_de === "10. Cận lâm sàng")!;
  const bang = nhom.don_vi.find((d) => d.loai === "bang" && d.bang.ma === "hmvs_semen");
  assert.ok(bang && bang.loai === "bang");
  assert.equal(bang.hang.length, 9);
  assert.deepEqual(bang.bang.cot, ["Kết quả lần 1", "Kết quả lần 2"]);
  assert.ok(bang.hang.every((h) => h.o.length === 2 && h.o.every((o) => o !== null)));
  assert.equal(bang.hang[2].o[1]!.ma, "hmvs_semen_3_2");
});

test("bật/tắt lựa chọn giữ thứ tự khung, không theo thứ tự bấm", () => {
  const o = khung("NT")
    .flatMap((m) => m.block)
    .find((x) => x.ma === "nt_endo_hist")!;
  let chon: string[] = [];
  chon = batTatLuaChon(chon, "nt_endo_hist_4", o.lua_chon!);
  chon = batTatLuaChon(chon, "nt_endo_hist_1", o.lua_chon!);
  assert.deepEqual(chon, ["nt_endo_hist_1", "nt_endo_hist_4"]);
  chon = batTatLuaChon(chon, "nt_endo_hist_4", o.lua_chon!);
  assert.deepEqual(chon, ["nt_endo_hist_1"]);
});

test("gói tự lưu giữ nguồn của ô không ai đụng", () => {
  const goc = {
    nt_ly_do: { gia_tri: "Đau bụng", nguon: "PATIENT_CONTEXT" },
    nt_para: { gia_tri: "1001", nguon: "USER" },
  };
  const goi = dungGoiLuu(
    { nt_ly_do: "Đau bụng", nt_para: "2002", nt_history: "", nt_family: [] },
    goc,
  );
  assert.deepEqual(goi, {
    nt_ly_do: { gia_tri: "Đau bụng", nguon: "PATIENT_CONTEXT" },
    nt_para: { gia_tri: "2002", nguon: "USER" },
  });
});

test("xoá chữ một ô đã có vẫn phải gửi đi — không thì xoá không bao giờ lưu", () => {
  const goi = dungGoiLuu(
    { nt_para: "" },
    { nt_para: { gia_tri: "1001", nguon: "USER" } },
  );
  assert.deepEqual(goi, { nt_para: { gia_tri: "", nguon: "USER" } });
});

test("đọc giá trị theo MÃ lựa chọn ra nhãn", () => {
  const o = khung("NT")
    .flatMap((m) => m.block)
    .find((x) => x.ma === "nt_endo_hist")!;
  assert.equal(
    giaTriDoc(o, { gia_tri: ["nt_endo_hist_2", "nt_endo_hist_4"], nguon: "USER" }),
    "Tuyến giáp, PCOS",
  );
  assert.equal(giaTriDoc(o, undefined), "—");
  assert.equal(hienThi(null), "—");
  assert.equal(hienThi(0), "0");
});

function mauThuoc(): MauThuoc[] {
  const url = new URL(
    "../../clinicai/phieu_kham/dinh_nghia/tham_chieu_nguon.json",
    import.meta.url,
  );
  return JSON.parse(readFileSync(url, "utf8")).mau_thuoc as MauThuoc[];
}

test("chọn thuốc gợi ý → dòng đơn điền sẵn, CHƯA gắn thuốc kho", () => {
  const m = mauThuoc().find((x) => x.nhan_nguon === "Betmiga")!;
  const d = dongTuMau(m);
  assert.equal(d.duong_dung, "Uống");
  assert.equal(d.cach_dung, m.dosage);
  assert.equal(d.so_luong, "");
  // Không ai dò tên để gắn mã kho: dòng mang null cho tới khi danh mục gắn.
  assert.equal(d.drug_catalog_id, null);
  assert.equal(d.mau_ma, m.ma);
});

test("tìm thuốc không phân biệt dấu", () => {
  const ds = mauThuoc();
  assert.ok(locMauThuoc(ds, "dat am dao").length > 0);
  assert.deepEqual(
    locMauThuoc(ds, "BETMIGA").map((m) => m.nhan_nguon),
    ["Betmiga"],
  );
  assert.equal(locMauThuoc(ds, "").length, ds.length);
});

test("chế độ nhận từ clinical shell: lạ hoặc thiếu = chỉ đọc", () => {
  assert.equal(ghiDuoc("editable"), true);
  assert.equal(ghiDuoc("amendment_mode"), true);
  assert.equal(ghiDuoc("finalized_locked"), false);
  for (const la of [undefined, null, "", "EDITABLE", "locked"]) {
    assert.equal(ghiDuoc(la), false, String(la));
  }
});

// Đơn thuốc mục E ↔ bảng prescription (không có cột đường dùng/đơn vị): ghép
// rồi tách lại phải ra đúng ô. Bấm thật 23/09: lần tự lưu đầu (chưa có số
// lượng) ghi "hộp" → đọc lại nhét vào ô số lượng → gõ "2" thành "hộp2".
test("đơn thuốc: ghép rồi tách lại đúng ô, kể cả khi chưa có số lượng", () => {
  const goc = {
    id: "x",
    drug_catalog_id: null,
    ten_thuoc: "Duphaston",
    duong_dung: "Uống",
    so_luong: "",
    don_vi: "hộp",
    cach_dung: "Ngày 2 lần",
    luu_y: "",
    mau_ma: null,
  };
  for (const sl of ["", "2", "1.5", "1/2"]) {
    const ghi = donTuDong({ ...goc, so_luong: sl });
    const doc = dongTuDon({
      id: "x",
      drug_catalog_id: null,
      drug_name_raw: ghi.drug_name,
      quantity: ghi.quantity,
      dosage_instructions: ghi.dosage,
      caution: ghi.caution,
    });
    assert.equal(doc.so_luong, sl);
    assert.equal(doc.don_vi, "hộp");
    assert.equal(doc.duong_dung, "Uống");
    assert.equal(doc.cach_dung, "Ngày 2 lần");
  }
});

// ── Khung v2 (đợt 3, 27/09/2026) trên CHÍNH JSON máy chủ nạp ───────────────
test("hien_khi của mọi phiếu trỏ một ô chọn có thật, đúng mã lựa chọn", () => {
  for (const f of FORM_IDS) {
    const o = new Map(khung(f).flatMap((m) => m.block.map((b) => [b.ma, b] as const)));
    for (const b of o.values()) {
      if (!b.hien_khi) continue;
      const dich = o.get(b.hien_khi.o);
      assert.ok(dich && (dich.kieu === "chon" || dich.kieu === "nhieu_chon"), `${f}.${b.ma}`);
      assert.ok(dich.lua_chon?.some((l) => l.ma === b.hien_khi!.la), `${f}.${b.ma}`);
    }
  }
});

test("phiếu mới NT: tiền sử chỉ còn chip, dị ứng chỉ còn Có/Không, bảng CLS gập", () => {
  const b = khung("NT").find((m) => m.ma === "B")!;
  const nhom = gomNhom(b.block);
  const tienSu = nhom.find((n) => n.tieu_de === "2. Tiền sử phụ khoa và sản khoa")!;
  const rong = new Set<string>();
  assert.equal(oThuGonDangAn(tienSu, {}, rong).length, 7);
  assert.equal(
    tienSu.don_vi.filter((d) => d.loai === "o" && oDangHien(d.o, {}, rong)).length,
    0,
  );
  const noiTiet = nhom.find((n) => n.tieu_de === "3. Tiền sử nội tiết")!;
  const hien = (gia: Record<string, string | string[]>) =>
    noiTiet.don_vi.flatMap((d) => (d.loai === "o" && oDangHien(d.o, gia, rong) ? [d.o.ma] : []));
  assert.deepEqual(hien({}), ["nt_endo_hist", "nt_endo_detail", "nt_allergy_co"]);
  assert.deepEqual(hien({ nt_allergy_co: "nt_allergy_co_2" }), [
    "nt_endo_hist",
    "nt_endo_detail",
    "nt_allergy_co",
  ]);
  assert.ok(hien({ nt_allergy_co: "nt_allergy_co_1" }).includes("nt_allergy"));
  // Phiếu cũ đã gõ dị ứng bằng chữ (chưa có ô Có/Không): chữ vẫn hiện.
  assert.ok(hien({ nt_allergy: "Penicillin" }).includes("nt_allergy"));
  assert.equal(nhom.find((n) => n.tieu_de === "6. Cận lâm sàng")!.gap, true);
  assert.equal(nhom.filter((n) => n.gap).length, 1);
});

test("bản in đọc ô Có/Không dị ứng ra chữ — 'Dị ứng thuốc: Không'", () => {
  for (const f of ["NT", "HMVS", "PK", "SK", "NK"]) {
    const t = f.toLowerCase();
    const o = khung(f)
      .flatMap((m) => m.block)
      .find((b) => b.ma === `${t}_allergy_co`)!;
    assert.equal(o.ten, "Dị ứng thuốc");
    assert.equal(giaTriDoc(o, { gia_tri: `${t}_allergy_co_2`, nguon: "USER" }), "Không");
    assert.equal(giaTriDoc(o, { gia_tri: `${t}_allergy_co_1`, nguon: "USER" }), "Có");
  }
});

test("hai phiếu không đổi (Thủ thuật, Sàn chậu) không có ô nào bị giấu", () => {
  for (const f of ["THU_THUAT", "SAN_CHAU"]) {
    for (const m of khung(f)) {
      for (const n of gomNhom(m.block)) {
        assert.equal(n.gap, false);
        for (const d of n.don_vi) if (d.loai === "o") assert.ok(oDangHien(d.o, {}, new Set()));
      }
    }
  }
});

test("phiếu tự do in theo TÊN DỊCH VỤ, không in chữ 'tự do' (28/09/2026)", () => {
  assert.equal(
    tenPhieuKetQua({ form_id: "KQ_CHUNG", ten: "Kết quả chung (nhập tự do)" }, "Đo cơ lực âm đạo"),
    "Kết quả Đo cơ lực âm đạo",
  );
  assert.equal(
    tenPhieuKetQua({ form_id: "KQ_SA_TC", ten: "Kết quả siêu âm tử cung" }, "Siêu âm 4D"),
    "Kết quả siêu âm tử cung",
  );
  // Không có tên dịch vụ: giữ tên mẫu thay vì để trống.
  assert.equal(
    tenPhieuKetQua({ form_id: "KQ_CHUNG", ten: "Kết quả chung (nhập tự do)" }, null),
    "Kết quả chung (nhập tự do)",
  );
});
