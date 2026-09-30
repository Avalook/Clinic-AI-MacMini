import assert from "node:assert/strict";
import test from "node:test";

import {
  CUA_SO_BAT_KIP_MS,
  nhipKhiHien,
  taoGopBatKip,
  type CongNhipKhiHien,
  type GoBo,
  type HenLap,
} from "./nhip-khi-hien.ts";

// ---------------------------------------------------------------- đồ giả ----

/** Tab giả + đồng hồ lặp giả: `tick()` = mọi nhịp đang chạy nổ một lần. */
function taoTab(anLucDau = false) {
  const s = { an: anLucDau };
  let dem = 0;
  const laps = new Map<number, () => void>();
  const nghe: Array<() => void> = [];
  const cong: CongNhipKhiHien = {
    dangAn: () => s.an,
    ngheDoiHien: (fn): GoBo => {
      nghe.push(fn);
      return () => {
        const i = nghe.indexOf(fn);
        if (i >= 0) nghe.splice(i, 1);
      };
    },
    henLap: (fn): HenLap => {
      const k = ++dem;
      laps.set(k, fn);
      return k;
    },
    huyLap: (h) => {
      laps.delete(h as number);
    },
  };
  return {
    s,
    cong,
    tick: () => {
      for (const f of [...laps.values()]) f();
    },
    soNhip: () => laps.size,
    soNguoiNghe: () => nghe.length,
    /** Đổi trạng thái RỒI báo — đúng thứ tự của trình duyệt. */
    doiHien: (an: boolean) => {
      s.an = an;
      for (const f of [...nghe]) f();
    },
  };
}

// --------------------------------------------------------- nhipKhiHien ------

test("tab hiện: chạy theo nhịp, KHÔNG chạy ngay lúc bắt đầu", () => {
  const tab = taoTab();
  let n = 0;
  nhipKhiHien(() => n++, 20_000, { cong: tab.cong });
  assert.equal(n, 0, "lượt đầu là việc của màn, không phải của nhịp");
  tab.tick();
  tab.tick();
  assert.equal(n, 2);
});

test("tab ẩn: HUỶ hẳn nhịp — không còn hẹn nào chạy nền", () => {
  const tab = taoTab();
  let n = 0;
  nhipKhiHien(() => n++, 20_000, { cong: tab.cong });
  tab.doiHien(true);
  assert.equal(tab.soNhip(), 0, "tab ẩn không được giữ setInterval nào");
  tab.tick();
  assert.equal(n, 0);
});

test("hiện lại: hỏi đúng MỘT lần ngay rồi chạy nhịp tiếp", () => {
  const tab = taoTab();
  let n = 0;
  nhipKhiHien(() => n++, 20_000, { cong: tab.cong });
  tab.doiHien(true);
  tab.doiHien(false);
  assert.equal(n, 1, "một lần ngay khi hiện lại");
  assert.equal(tab.soNhip(), 1, "đúng một nhịp, không chồng thêm");
  tab.tick();
  assert.equal(n, 2);
});

test("tin 'hiện' lặp lại khi chưa từng ẩn: không hỏi thêm", () => {
  const tab = taoTab();
  let n = 0;
  nhipKhiHien(() => n++, 20_000, { cong: tab.cong });
  tab.doiHien(false);
  tab.doiHien(false);
  assert.equal(n, 0);
  assert.equal(tab.soNhip(), 1);
});

test("hoiKhiHien:false — hiện lại chỉ đặt lại nhịp, để useNgheBang lo lần bắt kịp", () => {
  const tab = taoTab();
  let n = 0;
  nhipKhiHien(() => n++, 60_000, { cong: tab.cong, hoiKhiHien: false });
  tab.doiHien(true);
  tab.doiHien(false);
  assert.equal(n, 0, "tin null của RealtimeRefresher đã làm lần hỏi lại");
  assert.equal(tab.soNhip(), 1);
  tab.tick();
  assert.equal(n, 1);
});

test("mở trong tab nền: không đặt nhịp tới khi được nhìn", () => {
  const tab = taoTab(true);
  let n = 0;
  nhipKhiHien(() => n++, 20_000, { cong: tab.cong });
  assert.equal(tab.soNhip(), 0);
  tab.doiHien(false);
  assert.equal(n, 1);
  assert.equal(tab.soNhip(), 1);
});

test("nhịp nổ đúng lúc tab vừa ẩn (lỡ tin): bỏ lượt", () => {
  const tab = taoTab();
  let n = 0;
  nhipKhiHien(() => n++, 20_000, { cong: tab.cong });
  tab.s.an = true; // chưa kịp báo
  tab.tick();
  assert.equal(n, 0);
});

test("gỡ: thôi nghe và huỷ nhịp", () => {
  const tab = taoTab();
  let n = 0;
  const go = nhipKhiHien(() => n++, 20_000, { cong: tab.cong });
  go();
  assert.equal(tab.soNhip(), 0);
  assert.equal(tab.soNguoiNghe(), 0);
  tab.doiHien(true);
  tab.doiHien(false);
  assert.equal(n, 0);
});

test("lướt tab mười lần: số lần hỏi = số lần hiện lại, không nhân lên", () => {
  const tab = taoTab();
  let n = 0;
  nhipKhiHien(() => n++, 20_000, { cong: tab.cong });
  for (let i = 0; i < 10; i++) {
    tab.doiHien(true);
    tab.doiHien(false);
  }
  assert.equal(n, 10);
  assert.equal(tab.soNhip(), 1);
});

// --------------------------------------------------------- taoGopBatKip -----

function taoDongHoGop() {
  const s = { bayGio: 0, an: false };
  let dem = 0;
  const hens = new Map<number, { luc: number; fn: () => void }>();
  return {
    s,
    bayGio: () => s.bayGio,
    dangAn: () => s.an,
    hen: (fn: () => void, ms: number): HenLap => {
      const k = ++dem;
      hens.set(k, { luc: s.bayGio + ms, fn });
      return k;
    },
    huy: (h: HenLap) => {
      hens.delete(h as number);
    },
    /** Tua đồng hồ tới `t`, cho nổ các hẹn tới hạn. */
    tuaToi: (t: number) => {
      s.bayGio = t;
      for (const [k, h] of [...hens]) {
        if (h.luc <= t) {
          hens.delete(k);
          h.fn();
        }
      }
    },
    soHen: () => hens.size,
  };
}

test("bắt kịp lần đầu: chạy ngay", () => {
  const dh = taoDongHoGop();
  let n = 0;
  const g = taoGopBatKip({ ...dh, viec: () => n++ });
  g.xin();
  assert.equal(n, 1);
});

test("hai lần xin cùng lúc (focus + visibilitychange): chỉ MỘT lần làm mới", () => {
  const dh = taoDongHoGop();
  let n = 0;
  const g = taoGopBatKip({ ...dh, viec: () => n++ });
  g.xin();
  g.xin();
  assert.equal(n, 1, "lần thứ hai không chạy ngay");
});

test("lướt A→B→A trong 2 giây: lần thứ hai HOÃN tới cuối cửa sổ, không vứt", () => {
  const dh = taoDongHoGop();
  let n = 0;
  const g = taoGopBatKip({ ...dh, viec: () => n++ });
  g.xin(); // t=0
  dh.tuaToi(800);
  g.xin(); // t=0.8s — vẫn trong cửa sổ
  assert.equal(n, 1);
  assert.equal(dh.soHen(), 1);
  dh.tuaToi(CUA_SO_BAT_KIP_MS - 1);
  assert.equal(n, 1, "chưa hết cửa sổ thì chưa chạy");
  dh.tuaToi(CUA_SO_BAT_KIP_MS);
  assert.equal(n, 2, "quãng mù 0.8s vẫn phải được bắt kịp");
});

test("nhiều lần xin trong cửa sổ gộp thành MỘT lần hoãn", () => {
  const dh = taoDongHoGop();
  let n = 0;
  const g = taoGopBatKip({ ...dh, viec: () => n++ });
  g.xin();
  for (let t = 100; t < 2000; t += 300) {
    dh.tuaToi(t);
    g.xin();
  }
  assert.equal(dh.soHen(), 1);
  dh.tuaToi(5000);
  assert.equal(n, 2);
});

test("ngoài cửa sổ: chạy ngay", () => {
  const dh = taoDongHoGop();
  let n = 0;
  const g = taoGopBatKip({ ...dh, viec: () => n++ });
  g.xin();
  dh.tuaToi(CUA_SO_BAT_KIP_MS + 1);
  g.xin();
  assert.equal(n, 2);
  assert.equal(dh.soHen(), 0);
});

test("tab ẩn lúc xin: bỏ; ẩn lại lúc tới giờ hoãn: bỏ", () => {
  const dh = taoDongHoGop();
  let n = 0;
  const g = taoGopBatKip({ ...dh, viec: () => n++ });
  dh.s.an = true;
  g.xin();
  assert.equal(n, 0);
  dh.s.an = false;
  g.xin(); // t=0 chạy
  dh.tuaToi(500);
  g.xin(); // hoãn
  dh.s.an = true;
  dh.tuaToi(3000);
  assert.equal(n, 1, "tab đã ẩn lại — lần hiện sau sẽ tự xin");
  dh.s.an = false;
  g.xin();
  assert.equal(n, 2);
});

test("dung(): huỷ lần hoãn", () => {
  const dh = taoDongHoGop();
  let n = 0;
  const g = taoGopBatKip({ ...dh, viec: () => n++ });
  g.xin();
  dh.tuaToi(100);
  g.xin();
  g.dung();
  dh.tuaToi(5000);
  assert.equal(n, 1);
});
