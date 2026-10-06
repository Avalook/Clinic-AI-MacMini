import assert from "node:assert/strict";
import test from "node:test";

import {
  chipGon,
  dongDoSinhHieu,
  dongLanLam,
  dongPhuGon,
  ghiChuKham,
  gio,
  nhanThe,
  noiGon,
  phut,
  thoiGian,
  type BuocHanhTrinh,
  type HanhTrinhGon,
  type TheDichVu,
} from "./hanh-trinh-khach.ts";

// 10:00 giờ VN = 03:00 UTC.
const luc = (p: number) => new Date(Date.UTC(2026, 8, 29, 3, p)).toISOString();
const bay = (p: number) => Date.UTC(2026, 8, 29, 3, p);

const gon = (k: Partial<HanhTrinhGon>): HanhTrinhGon => ({
  trang_thai: "DANG_O",
  nhan: "Đang ở",
  noi: "Phòng siêu âm 1",
  tu_luc: luc(58),
  stt: null,
  xong_buoi: false,
  doan: [],
  dv_xong: 2,
  dv_tong: 3,
  con_cho: ["Lấy mẫu", "KQ đối tác"],
  ...k,
});

test("chip dòng gọn: đang làm từ HH:MM · N′", () => {
  assert.deepEqual(chipGon(gon({}), bay(64)), { nhan: "đang làm từ 10:58 · 6′", tone: "run" });
});

test("chip dòng gọn: chờ N′ · STT k", () => {
  const c = chipGon(gon({ trang_thai: "DANG_CHO", nhan: "Đang chờ", tu_luc: luc(40), stt: 2 }), bay(52));
  assert.deepEqual(c, { nhan: "chờ 12′ · STT 2", tone: "warning" });
});

test("đã về: xong buổi, tên chỗ là giờ check-out", () => {
  const g = gon({ trang_thai: "DA_VE", nhan: "Đã về", noi: "Check-out", tu_luc: luc(80) });
  assert.deepEqual(chipGon(g, bay(200)), { nhan: "xong buổi", tone: "success" });
  assert.equal(noiGon(g), "Check-out 11:20");
});

test("hồ sơ cũ (Notion): không in giờ check-out giả", () => {
  const g = gon({ trang_thai: "DA_VE", nhan: "Đã về", noi: "Check-out", tu_luc: null, ho_so_cu: true });
  assert.equal(noiGon(g), "Hồ sơ cũ · không rõ giờ");
  assert.deepEqual(chipGon(g, bay(200)), { nhan: "xong buổi", tone: "success" });
});

test("dòng phụ: x/y dịch vụ xong · còn chờ", () => {
  assert.equal(dongPhuGon(gon({})), "2/3 dịch vụ xong · còn chờ: Lấy mẫu · KQ đối tác");
  assert.equal(dongPhuGon(gon({ dv_tong: 0, dv_xong: 0, con_cho: [] })), "");
});

test("thời gian một thẻ xong: vào · chờ · bắt đầu · làm · xong", () => {
  assert.equal(
    thoiGian({ vao: luc(57), bat_dau: luc(62), xong: luc(65) }, bay(90)),
    "vào 10:57 · chờ 5′ · bắt đầu 11:02 · làm 3′ · xong 11:05",
  );
});

test("đang làm / đang chờ chạy theo đồng hồ; khách về thì dừng", () => {
  assert.equal(
    thoiGian({ vao: luc(57), bat_dau: luc(58), xong: null }, bay(64)),
    "vào 10:57 · chờ 1′ · bắt đầu 10:58 · đang làm 6′",
  );
  assert.equal(thoiGian({ vao: luc(40), bat_dau: null, xong: null }, bay(52)), "vào 10:40 · đang chờ 12′");
  assert.equal(thoiGian({ vao: luc(40), bat_dau: null, xong: null }, bay(52), true), "vào 10:40");
});

test("mốc một thời điểm chỉ ghi một giờ", () => {
  assert.equal(thoiGian({ vao: null, bat_dau: luc(27), xong: luc(27) }, bay(90)), "10:27");
});

test("ghi chú khám: chỉ định + thu tiền (người thu)", () => {
  const b = {
    so_chi_dinh: 3,
    thu_luc: luc(56),
    nguoi_thu: "Vũ Thu Hà",
  } as BuocHanhTrinh;
  assert.equal(ghiChuKham(b), "Chỉ định 3 dịch vụ · thu tiền 10:56 (Vũ Thu Hà)");
  assert.equal(ghiChuKham({ so_chi_dinh: 2, cho_thu: 2 } as BuocHanhTrinh), "Chỉ định 2 dịch vụ · chờ thu tiền 2 dịch vụ");
});

test("nhãn thẻ dịch vụ", () => {
  const t = (k: Partial<TheDichVu>): TheDichVu => ({
    id: "x",
    ten: "",
    noi: "",
    doi_tac: false,
    trang_thai: "XONG",
    vao: null,
    bat_dau: null,
    xong: null,
    thu: null,
    lay_mau: null,
    stt: null,
    so_truoc: null,
    ...k,
  });
  assert.equal(nhanThe(t({ xong: luc(65) }), bay(90)), "Xong 11:05");
  assert.equal(nhanThe(t({ trang_thai: "DANG_LAM", bat_dau: luc(58) }), bay(64)), "Đang làm 6′");
  assert.equal(nhanThe(t({ trang_thai: "DOI_TAC" }), bay(64)), "Chờ kết quả đối tác");
  assert.equal(nhanThe(t({ trang_thai: "CHO_LAM", stt: 3 }), bay(64)), "Chờ làm · STT 3");
});

test("đầu vào rác: không ném, trả rỗng", () => {
  assert.equal(phut("rác", bay(1)), null);
  assert.equal(phut(luc(10), "không phải giờ"), null);
  assert.equal(phut(null, Number.NaN), null);
  assert.equal(phut(luc(10), bay(5)), 0, "giờ máy lệch không ra số âm");
  assert.equal(gio("rác"), "");
  assert.equal(thoiGian({ vao: "rác", bat_dau: null, xong: null }, bay(5)), "");
});

// ── GIỜ THẬT, KHÔNG LÀM MÉO (Tuyền duyệt 29/09/2026) ─────────────────────────

test("dòng gọn hiện rõ sinh hiệu đo lại + dịch vụ làm lại", () => {
  const g = gon({ do_lai: [luc(45)], lam_lai: [{ ten: "Siêu âm phụ khoa", lan: 2 }] });
  assert.equal(
    dongPhuGon(g),
    "2/3 dịch vụ xong · còn chờ: Lấy mẫu · KQ đối tác · sinh hiệu đo lại 10:45 · " +
      "làm lại: Siêu âm phụ khoa (lần 2)",
  );
});

test("sinh hiệu đo lại: dòng riêng có người đo mỗi lần", () => {
  assert.equal(
    dongDoSinhHieu({
      lan_do: [
        { luc: luc(33), ai: "ĐD Lan" },
        { luc: luc(45), ai: "ĐD Mai" },
      ],
    }),
    "Đo lần 1 10:33 (ĐD Lan) · đo lại 10:45 (ĐD Mai)",
  );
  assert.equal(dongDoSinhHieu({ lan_do: [{ luc: luc(33), ai: null }] }), "", "một lần: không dòng riêng");
  assert.equal(dongDoSinhHieu({}), "");
});

test("mỗi lần làm đủ vào · bắt đầu · xong/dừng; chờ không âm", () => {
  assert.equal(
    dongLanLam(
      { so: 1, trang_thai: "INTERRUPTED", vao: luc(55), bat_dau: luc(60), xong: null, dung: luc(65) },
      bay(90),
    ),
    "Lần 1 · vào 10:55 · chờ 5′ · bắt đầu 11:00 · làm 5′ · dừng 11:05",
  );
  assert.equal(
    dongLanLam(
      { so: 2, trang_thai: "COMPLETED", vao: luc(66), bat_dau: luc(72), xong: luc(80), dung: null },
      bay(90),
    ),
    "Lần 2 · vào 11:06 · chờ 6′ · bắt đầu 11:12 · làm 8′ · xong 11:20",
  );
  assert.equal(
    dongLanLam({ so: 2, trang_thai: "PENDING", vao: luc(66), bat_dau: null, xong: null, dung: null }, bay(69)),
    "Lần 2 · vào 11:06 · đang chờ 3′",
  );
  // Máy chủ cũ trả vào muộn hơn bắt đầu → 0′, không âm.
  assert.equal(
    thoiGian({ vao: luc(70), bat_dau: luc(60), xong: null }, bay(80), true),
    "vào 11:10 · chờ 0′ · bắt đầu 11:00",
  );
});
