import assert from "node:assert/strict";
import test from "node:test";

import {
  choThuLaiMs,
  gopTrangThai,
  HangDoiLuu,
  LOI_MAT_KET_NOI,
  nenThuLai,
  TRANG_THAI_DAU,
  type DongHo,
  type KetQuaGui,
} from "./tu-luu.ts";

// Đồng hồ giả: hẹn giờ chỉ chạy khi test gọi `troi(ms)`.
function dongHoGia() {
  let bay = 0;
  let so = 0;
  const hen = new Map<number, { luc: number; fn: () => void }>();
  const dh: DongHo = {
    hen: (fn, ms) => {
      so += 1;
      hen.set(so, { luc: bay + ms, fn });
      return so;
    },
    huy: (h) => {
      hen.delete(h as number);
    },
    bayGio: () => new Date(Date.UTC(2026, 8, 27, 3, 0, 0) + bay),
  };
  const troi = async (ms: number) => {
    const den = bay + ms;
    for (;;) {
      const sap = [...hen.entries()].filter(([, h]) => h.luc <= den).sort((a, b) => a[1].luc - b[1].luc)[0];
      if (!sap) break;
      hen.delete(sap[0]);
      bay = sap[1].luc;
      sap[1].fn();
      await nghi();
    }
    bay = den;
    await nghi();
  };
  return { dh, troi, soHen: () => hen.size };
}

/** Nhường vòng sự kiện vài nhịp để promise kịp chạy. */
async function nghi() {
  for (let i = 0; i < 5; i += 1) await Promise.resolve();
}

/** Máy chủ giả: mỗi lần gửi trả một promise test tự quyết lúc nào xong. */
function mayChuGia() {
  const cho: { keepalive: boolean; xong: (k: KetQuaGui) => void }[] = [];
  let dangBay = 0;
  let bayToiDa = 0;
  const gui = (keepalive: boolean) =>
    new Promise<KetQuaGui>((resolve) => {
      dangBay += 1;
      bayToiDa = Math.max(bayToiDa, dangBay);
      cho.push({
        keepalive,
        xong: (k) => {
          dangBay -= 1;
          resolve(k);
        },
      });
    });
  return { gui, cho, bayToiDa: () => bayToiDa };
}

test("nenThuLai: mạng / 5xx thử lại, 4xx nghiệp vụ không", () => {
  assert.equal(nenThuLai(0), true);
  assert.equal(nenThuLai(502), true);
  assert.equal(nenThuLai(503), true);
  assert.equal(nenThuLai(429), true);
  assert.equal(nenThuLai(408), true);
  assert.equal(nenThuLai(400), false);
  assert.equal(nenThuLai(409), false);
  assert.equal(nenThuLai(422), false);
  assert.equal(nenThuLai(401), false);
  // rác → coi như mạng
  assert.equal(nenThuLai(undefined), true);
  assert.equal(nenThuLai("500"), true);
  assert.equal(nenThuLai(Number.NaN), true);
});

test("choThuLaiMs: giãn 2-4-8-16-30s, trần 30s, rác = lần đầu", () => {
  assert.deepEqual([1, 2, 3, 4, 5, 6, 50].map(choThuLaiMs), [2000, 4000, 8000, 16000, 30000, 30000, 30000]);
  assert.equal(choThuLaiMs(0), 2000);
  assert.equal(choThuLaiMs(-3), 2000);
  assert.equal(choThuLaiMs("x"), 2000);
  assert.equal(choThuLaiMs(null), 2000);
  assert.equal(choThuLaiMs(Number.POSITIVE_INFINITY), 2000);
});

test("gõ liên tục chỉ lưu MỘT lần sau khoảng lặng", async () => {
  const { dh, troi } = dongHoGia();
  const mc = mayChuGia();
  const hd = new HangDoiLuu({ gui: mc.gui, choMs: 1500, dongHo: dh });
  hd.danhDau();
  await troi(1000);
  hd.danhDau();
  await troi(1000);
  hd.danhDau();
  assert.equal(mc.cho.length, 0);
  assert.equal(hd.trangThai.chua_luu, true);
  await troi(1500);
  assert.equal(mc.cho.length, 1);
  assert.equal(hd.trangThai.dang_luu, true);
  mc.cho[0].xong({ ok: true });
  await nghi();
  assert.equal(hd.trangThai.chua_luu, false);
  assert.equal(hd.trangThai.dang_luu, false);
  assert.ok(hd.trangThai.luu_luc);
});

test("tuần tự: gõ trong lúc đang bay thì đợi, rồi gửi bản mới nhất — không bao giờ 2 lần bay", async () => {
  const { dh, troi } = dongHoGia();
  const mc = mayChuGia();
  const hd = new HangDoiLuu({ gui: mc.gui, choMs: 1500, dongHo: dh });
  hd.danhDau();
  await troi(1500);
  assert.equal(mc.cho.length, 1);
  // Mạng chậm 3s: gõ thêm hai đợt, hẹn tới giờ trong lúc lần 1 còn bay.
  hd.danhDau();
  await troi(1500);
  hd.danhDau();
  await troi(1500);
  assert.equal(mc.cho.length, 1, "lần 2 phải đợi lần 1 về");
  mc.cho[0].xong({ ok: true });
  await nghi();
  assert.equal(mc.cho.length, 2, "lần 1 về → gửi ngay phần gõ thêm (gộp làm một)");
  assert.equal(hd.trangThai.chua_luu, true);
  mc.cho[1].xong({ ok: true });
  await nghi();
  assert.equal(hd.trangThai.chua_luu, false);
  assert.equal(mc.bayToiDa(), 1);
});

test("lỗi mạng: báo lỗi, tự thử lại giãn cách, thành công thì xoá lỗi", async () => {
  const { dh, troi } = dongHoGia();
  const mc = mayChuGia();
  const hd = new HangDoiLuu({ gui: mc.gui, choMs: 1000, dongHo: dh });
  hd.danhDau();
  await troi(1000);
  mc.cho[0].xong({ ok: false, loi: LOI_MAT_KET_NOI, thuLai: true });
  await nghi();
  assert.equal(hd.trangThai.loi, LOI_MAT_KET_NOI);
  assert.equal(hd.trangThai.tu_thu_lai, true);
  assert.equal(hd.trangThai.chua_luu, true);
  await troi(1999);
  assert.equal(mc.cho.length, 1, "chưa tới 2s thì chưa thử lại");
  await troi(1);
  assert.equal(mc.cho.length, 2);
  mc.cho[1].xong({ ok: false, loi: LOI_MAT_KET_NOI, thuLai: true });
  await nghi();
  await troi(3999);
  assert.equal(mc.cho.length, 2, "lần 2 giãn 4s");
  await troi(1);
  assert.equal(mc.cho.length, 3);
  mc.cho[2].xong({ ok: true });
  await nghi();
  assert.equal(hd.trangThai.loi, null);
  assert.equal(hd.trangThai.chua_luu, false);
  assert.equal(hd.trangThai.tu_thu_lai, false);
});

test("gui ném (fetch vỡ) = lỗi mạng, có thử lại", async () => {
  const { dh, troi } = dongHoGia();
  let lan = 0;
  const hd = new HangDoiLuu({
    gui: async () => {
      lan += 1;
      if (lan === 1) throw new TypeError("Failed to fetch");
      return { ok: true };
    },
    choMs: 500,
    dongHo: dh,
  });
  hd.danhDau();
  await troi(500);
  assert.equal(hd.trangThai.loi, LOI_MAT_KET_NOI);
  await troi(2000);
  assert.equal(lan, 2);
  assert.equal(hd.trangThai.loi, null);
  assert.equal(hd.trangThai.chua_luu, false);
});

test("lỗi nghiệp vụ 4xx: KHÔNG tự thử lại; gõ tiếp hoặc luuNgay mới gửi lại", async () => {
  const { dh, troi, soHen } = dongHoGia();
  const mc = mayChuGia();
  const hd = new HangDoiLuu({ gui: mc.gui, choMs: 1000, dongHo: dh });
  hd.danhDau();
  await troi(1000);
  mc.cho[0].xong({ ok: false, loi: "Cần lý do đính chính.", thuLai: false });
  await nghi();
  assert.equal(hd.trangThai.loi, "Cần lý do đính chính.");
  assert.equal(hd.trangThai.tu_thu_lai, false);
  assert.equal(soHen(), 0);
  await troi(60_000);
  assert.equal(mc.cho.length, 1, "không tự bắn lại");
  const p = hd.luuNgay();
  await nghi();
  assert.equal(mc.cho.length, 2);
  mc.cho[1].xong({ ok: true });
  assert.equal(await p, true);
  assert.equal(hd.trangThai.loi, null);
});

test("luuNgay: bỏ khoảng lặng, gửi ngay, đợi xong; không có gì thì trả true ngay", async () => {
  const { dh } = dongHoGia();
  const mc = mayChuGia();
  const hd = new HangDoiLuu({ gui: mc.gui, choMs: 1500, dongHo: dh });
  assert.equal(await hd.luuNgay(), true);
  assert.equal(mc.cho.length, 0);
  hd.danhDau();
  const p = hd.luuNgay();
  await nghi();
  assert.equal(mc.cho.length, 1);
  mc.cho[0].xong({ ok: true });
  assert.equal(await p, true);
});

test("luuNgay khi đang bay + có chữ mới: đợi lần đang bay rồi gửi nốt", async () => {
  const { dh, troi } = dongHoGia();
  const mc = mayChuGia();
  const hd = new HangDoiLuu({ gui: mc.gui, choMs: 1500, dongHo: dh });
  hd.danhDau();
  await troi(1500);
  hd.danhDau(); // gõ thêm khi lần 1 đang bay
  let xong: boolean | null = null;
  void hd.luuNgay().then((v) => {
    xong = v;
  });
  await nghi();
  assert.equal(mc.cho.length, 1);
  mc.cho[0].xong({ ok: true });
  await nghi();
  assert.equal(mc.cho.length, 2, "gửi nốt phần gõ thêm");
  assert.equal(xong, null, "chưa xong khi phần sau còn bay");
  mc.cho[1].xong({ ok: true });
  await nghi();
  assert.equal(xong, true);
  assert.equal(mc.bayToiDa(), 1);
});

test("luuNgay lỗi → false (Hoàn tất không được gửi)", async () => {
  const { dh } = dongHoGia();
  const mc = mayChuGia();
  const hd = new HangDoiLuu({ gui: mc.gui, choMs: 1500, dongHo: dh });
  hd.danhDau();
  const p = hd.luuNgay();
  await nghi();
  mc.cho[0].xong({ ok: false, loi: LOI_MAT_KET_NOI, thuLai: true });
  assert.equal(await p, false);
  assert.equal(hd.trangThai.chua_luu, true);
  hd.dung();
});

test("guiKhiRoiTrang: gửi keepalive khi còn chưa lưu, không gửi khi sạch", async () => {
  const { dh, soHen } = dongHoGia();
  const mc = mayChuGia();
  const hd = new HangDoiLuu({ gui: mc.gui, choMs: 1500, dongHo: dh });
  hd.guiKhiRoiTrang();
  assert.equal(mc.cho.length, 0);
  hd.danhDau();
  hd.guiKhiRoiTrang();
  assert.equal(mc.cho.length, 1);
  assert.equal(mc.cho[0].keepalive, true);
  assert.equal(soHen(), 0, "hẹn thường bị huỷ — không bắn lại lần nữa");
});

test("guiKhiRoiTrang: lần đang bay đã mang đủ thay đổi thì KHÔNG gửi trùng; có chữ mới hơn thì gửi", async () => {
  const { dh } = dongHoGia();
  const mc = mayChuGia();
  const hd = new HangDoiLuu({ gui: mc.gui, choMs: 1500, dongHo: dh });
  hd.danhDau();
  void hd.luuNgay();
  await nghi();
  assert.equal(mc.cho.length, 1);
  hd.guiKhiRoiTrang();
  assert.equal(mc.cho.length, 1, "không gửi trùng lần đang bay");
  hd.danhDau();
  hd.guiKhiRoiTrang();
  assert.equal(mc.cho.length, 2);
  assert.equal(mc.cho[1].keepalive, true);
});

test("datGui: lần gửi sau dùng hàm mới (closure mới nhất của màn)", async () => {
  const { dh } = dongHoGia();
  const goi: string[] = [];
  const hd = new HangDoiLuu({
    gui: async () => {
      goi.push("cu");
      return { ok: true };
    },
    choMs: 100,
    dongHo: dh,
  });
  hd.datGui(async () => {
    goi.push("moi");
    return { ok: true };
  });
  hd.danhDau();
  assert.equal(await hd.luuNgay(), true);
  assert.deepEqual(goi, ["moi"]);
});

test("lamSach: bỏ phần chưa lưu (đã nạp lại bản máy chủ), xoá lỗi, không gửi", async () => {
  const { dh, troi } = dongHoGia();
  const mc = mayChuGia();
  const hd = new HangDoiLuu({ gui: mc.gui, choMs: 1000, dongHo: dh });
  hd.danhDau();
  hd.lamSach();
  await troi(5000);
  assert.equal(mc.cho.length, 0);
  assert.deepEqual(
    { ...hd.trangThai, luu_luc: null },
    { ...TRANG_THAI_DAU },
  );
});

test("onDoi được gọi mỗi lần trạng thái đổi", async () => {
  const { dh, troi } = dongHoGia();
  const mc = mayChuGia();
  const ds: string[] = [];
  const hd = new HangDoiLuu({
    gui: mc.gui,
    choMs: 1000,
    dongHo: dh,
    onDoi: (t) => ds.push(t.dang_luu ? "bay" : t.chua_luu ? "chua" : "sach"),
  });
  hd.danhDau();
  await troi(1000);
  mc.cho[0].xong({ ok: true });
  await nghi();
  assert.deepEqual(ds, ["chua", "bay", "sach"]);
});

test("gopTrangThai: phiếu + đơn thuốc", () => {
  const luc1 = new Date(Date.UTC(2026, 8, 27, 3, 0));
  const luc2 = new Date(Date.UTC(2026, 8, 27, 3, 5));
  const a = { ...TRANG_THAI_DAU, luu_luc: luc1 };
  const b = { ...TRANG_THAI_DAU, chua_luu: true, luu_luc: luc2 };
  const g = gopTrangThai(a, b);
  assert.equal(g.chua_luu, true);
  assert.equal(g.dang_luu, false);
  assert.equal(g.luu_luc, luc2);
  const loiB = gopTrangThai(TRANG_THAI_DAU, { ...TRANG_THAI_DAU, loi: "Đơn lỗi", tu_thu_lai: true });
  assert.equal(loiB.loi, "Đơn lỗi");
  assert.equal(loiB.tu_thu_lai, true);
  const loiA = gopTrangThai({ ...TRANG_THAI_DAU, loi: "Phiếu lỗi" }, { ...TRANG_THAI_DAU, loi: "Đơn lỗi", tu_thu_lai: true });
  assert.equal(loiA.loi, "Phiếu lỗi");
  assert.equal(loiA.tu_thu_lai, false);
  assert.equal(gopTrangThai(TRANG_THAI_DAU, TRANG_THAI_DAU).luu_luc, null);
});
