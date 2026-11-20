import assert from "node:assert/strict";
import test from "node:test";

import { HangDoiLuu, type DongHo } from "../lib/tu-luu.ts";
import {
  doiPhieu,
  dongCanGui,
  luuTay,
  taoGuiDem,
  type DongGui,
  type ManDem,
} from "../app/(dashboard)/pharmacy/inventory/gui-dem.ts";

// Tự lưu số đếm kiểm kê ca (20/11/2026) — ba lỗi soát chỉ ra ở bản đầu, chạy trên
// HÀNG ĐỢI THẬT (`HangDoiLuu`) + máy chủ giả trả lời CHẬM (giữ lời hứa tới khi thả).

const nghi = () => new Promise<void>((r) => setImmediate(r));

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
    bayGio: () => new Date(Date.UTC(2026, 10, 20, 5, 0, 0) + bay),
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
  return { dh, troi };
}

/** Máy chủ giả: ghi theo phiếu; mỗi lần POST treo tới khi `tha()`. */
function mayChu() {
  const so: Record<string, Record<string, string | null>> = {};
  const lanGui: Array<{ pid: string; dong: DongGui[] }> = [];
  const cho: Array<() => void> = [];
  return {
    so,
    lanGui,
    post: (pid: string, dong: DongGui[]) =>
      new Promise<{ status: number; data: unknown }>((ok) => {
        lanGui.push({ pid, dong });
        cho.push(() => {
          so[pid] ??= {};
          for (const d of dong) {
            if (d.dem === null) delete so[pid][d.drug_catalog_id];
            else so[pid][d.drug_catalog_id] = d.dem;
          }
          ok({ status: 200, data: { id: pid } });
        });
      }),
    tha: async () => {
      while (cho.length) {
        cho.shift()!();
        await nghi();
      }
    },
  };
}

const HANG = [
  { khoa: "t1|viên", thuoc: "t1", dv: "viên" },
  { khoa: "t2|viên", thuoc: "t2", dv: "viên" },
];

function dung(m: ManDem | null, mc: ReturnType<typeof mayChu>) {
  const { dh, troi } = dongHoGia();
  let thuCong = false;
  const tuChoi: string[] = [];
  const man = { m };
  const q = new HangDoiLuu({
    gui: taoGuiDem({
      doc: () => man.m,
      laThuCong: () => thuCong,
      post: (pid, dong) => mc.post(pid, dong),
      daLuu: () => {},
      tuChoi: (pid) => tuChoi.push(pid),
    }),
    choMs: 1500,
    dongHo: dh,
  });
  const go = (khoa: string, v: string) => {
    man.m = { ...man.m!, nhap: { ...man.m!.nhap, [khoa]: v } };
    q.danhDau();
  };
  return { q, man, go, troi, tuChoi, datThuCong: (b: boolean) => (thuCong = b) };
}

const phieu = (pid: string, nhap: Record<string, string> = {}): ManDem => ({
  pid,
  laBanSua: false,
  hang: HANG,
  nhap,
  gioGo: {},
});

test("Lưu nháp / Chốt trong lúc tự lưu đang bay: không bao giờ đè số MỚI bằng số cũ", async () => {
  const mc = mayChu();
  const s = dung(phieu("A"), mc);
  s.go("t1|viên", "5");
  await s.troi(1500); // tự lưu "5" đang bay (máy chủ chưa trả lời)
  s.go("t1|viên", "6"); // gõ tiếp trong lúc bay
  const xong = luuTay(s.q, s.datThuCong); // bấm "Lưu nháp"
  await mc.tha();
  await nghi();
  await mc.tha();
  assert.equal(await xong, true);
  assert.equal(mc.so.A["t1"], "6", "máy chủ phải giữ số mới nhất");
  const cuoi = mc.lanGui[mc.lanGui.length - 1].dong.find((d) => d.drug_catalog_id === "t1");
  assert.equal(cuoi?.dem, "6", "lần gửi cuối không được mang số cũ");
});

test("Đổi ca/ngày trong 1,5 giây sau khi gõ: bản chưa gửi về ĐÚNG phiếu cũ, không mất", async () => {
  const mc = mayChu();
  const s = dung(phieu("A"), mc);
  s.go("t1|viên", "3"); // chưa tới giờ tự lưu
  const doi = doiPhieu(s.q, () => {
    s.man.m = phieu("B"); // màn mở phiếu ca khác
  });
  await mc.tha();
  await doi;
  s.go("t2|viên", "9"); // gõ ngay ở phiếu B
  await s.troi(1500);
  await mc.tha();
  assert.equal(mc.so.A?.["t1"], "3", "số của phiếu A phải tới máy chủ");
  assert.equal(mc.so.B?.["t2"], "9");
  assert.ok(
    mc.lanGui.every((g) => g.pid !== "A" || !g.dong.some((d) => d.drug_catalog_id === "t2")),
    "không đổ số phiếu B sang phiếu A",
  );
});

test("Đổi phiếu lúc RỚT MẠNG: không đổi, nháp phiếu cũ còn nguyên và về đúng phiếu cũ khi có mạng", async () => {
  const mc = mayChu();
  let rot = true;
  const s = dung(phieu("A"), {
    ...mc,
    post: (pid: string, dong: DongGui[]) => (rot ? Promise.resolve(null) : mc.post(pid, dong)),
  } as ReturnType<typeof mayChu>);
  s.go("t1|viên", "3");
  let daDoi = false;
  const ok = await doiPhieu(s.q, () => {
    daDoi = true;
    s.man.m = phieu("B");
  });
  assert.equal(ok, false, "xả hỏng phải báo false");
  assert.equal(daDoi, false, "xả hỏng thì KHÔNG đổi phiếu");
  assert.equal(s.man.m?.pid, "A");
  rot = false; // có mạng lại — hàng đợi tự thử lại
  await s.troi(2_000);
  await mc.tha();
  assert.equal(mc.so.A?.["t1"], "3", "số phiếu A tới đúng phiếu A");
  assert.equal(mc.so.B, undefined);
});

test("409 mang câu máy chủ tới màn", async () => {
  const lan: Array<[string, string]> = [];
  const gui = taoGuiDem({
    doc: () => phieu("A", { "t1|viên": "2" }),
    laThuCong: () => false,
    post: async () => ({ status: 409, data: { message: "Phiếu đã chốt ở máy khác" } }),
    daLuu: () => {},
    tuChoi: (pid, cau) => lan.push([pid, cau]),
  });
  await gui(false);
  assert.deepEqual(lan, [["A", "Phiếu đã chốt ở máy khác"]]);
});

test("Xoá trống ô vừa gõ lúc lần lưu đầu còn bay: máy chủ bỏ dòng, không giữ số cũ", async () => {
  const mc = mayChu();
  const s = dung(phieu("A"), mc);
  s.go("t1|viên", "5");
  await s.troi(1500); // "5" đang bay
  s.go("t1|viên", ""); // xoá trước khi máy chủ trả lời
  await mc.tha();
  await s.troi(1500);
  await mc.tha();
  assert.equal(mc.so.A?.["t1"], undefined, "ô trống thì máy chủ không còn dòng");
});

test("Bản sửa: tự lưu không gửi ô trống (tránh 422 cả lô); Lưu nháp thì có", () => {
  const m: ManDem = { ...phieu("A", { "t1|viên": "", "t2|viên": "4" }), laBanSua: true };
  assert.deepEqual(dongCanGui(m, true).map((d) => d.drug_catalog_id), ["t2"]);
  assert.deepEqual(dongCanGui(m, false).map((d) => [d.drug_catalog_id, d.dem]), [["t1", null], ["t2", "4"]]);
});

test("409 (phiếu đã chốt ở máy khác): không tự thử lại, báo màn nạp lại", async () => {
  const s = (() => {
    const { dh } = dongHoGia();
    const tuChoi: string[] = [];
    const gui = taoGuiDem({
      doc: () => phieu("A", { "t1|viên": "2" }),
      laThuCong: () => false,
      post: async () => ({ status: 409, data: { message: "Phiếu đã chốt" } }),
      daLuu: () => {},
      tuChoi: (pid) => tuChoi.push(pid),
    });
    return { gui, tuChoi, dh };
  })();
  const kq = await s.gui(false);
  assert.deepEqual(kq, { ok: false, loi: "Phiếu đã chốt", thuLai: false });
  assert.deepEqual(s.tuChoi, ["A"]);
});
