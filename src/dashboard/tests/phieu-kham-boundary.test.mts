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
  dongTuMau,
  dungGoiLuu,
  ghiDuoc,
  giaTriDoc,
  gomNhom,
  hienThi,
  locMauThuoc,
  type MauThuoc,
  type MucPhieu,
  type OPhieu,
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
