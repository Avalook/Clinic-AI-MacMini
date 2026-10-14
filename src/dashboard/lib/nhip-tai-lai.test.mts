// Gom tải lại đồng loạt (14/10/2026) — lệch ngẫu nhiên, trần chờ, nối lại có lùi,
// nhịp dự phòng thưa. Phần cơ bản của `taoNhipLamMoi` (gộp nhịp, tab ẩn, bắt kịp)
// nằm ở `nhip-lam-moi.test.mts`.

import assert from "node:assert/strict";
import test from "node:test";

import {
  canHoiDuPhong,
  taoNhipLamMoi,
  taoNoiLai,
  TRE_MAC_DINH,
  type Hen,
} from "./nhip-lam-moi.ts";

/** Đồng hồ giả có THỜI GIAN: hẹn nổ theo `tien()`, ghi lại số ms mỗi hẹn xin. */
function taoDongHo() {
  let bay = 0;
  let dem = 0;
  const hens = new Map<number, { luc: number; fn: () => void }>();
  const xin: number[] = [];
  return {
    bayGio: () => bay,
    hen: (fn: () => void, ms: number): Hen => {
      xin.push(ms);
      const k = ++dem;
      hens.set(k, { luc: bay + ms, fn });
      return k;
    },
    huy: (h: Hen) => {
      hens.delete(h as number);
    },
    /** Tiến `ms`, nổ mọi hẹn tới hạn theo thứ tự. */
    tien: (ms: number) => {
      const dich = bay + ms;
      for (;;) {
        const toi = [...hens.entries()]
          .filter(([, h]) => h.luc <= dich)
          .sort((a, b) => a[1].luc - b[1].luc)[0];
        if (!toi) break;
        bay = toi[1].luc;
        hens.delete(toi[0]);
        toi[1].fn();
      }
      bay = dich;
    },
    xin,
    dangCho: () => hens.size,
  };
}

function taoMan() {
  const s = { an: false, soLanLamMoi: 0 };
  return {
    s,
    lamMoi: () => {
      s.soLanLamMoi += 1;
    },
    dangAn: () => s.an,
  };
}

// ---------------------------------------------------- lệch ngẫu nhiên -------

test("lệch ngẫu nhiên: hẹn = 250ms + 0..jitter, không bao giờ vượt", () => {
  const man = taoMan();
  for (const [r, mong] of [
    [0, 250],
    [0.5, 450],
    [0.9999, 650],
  ] as const) {
    const dh = taoDongHo();
    const nhip = taoNhipLamMoi({
      ...man,
      hen: dh.hen,
      huy: dh.huy,
      bayGio: dh.bayGio,
      jitter: 400,
      rand: () => r,
    });
    nhip.nhan();
    assert.equal(dh.xin.at(-1), mong);
  }
});

test("mặc định KHÔNG lệch: nhịp gộp vẫn đúng 250ms", () => {
  const dh = taoDongHo();
  const nhip = taoNhipLamMoi({ ...taoMan(), hen: dh.hen, huy: dh.huy, bayGio: dh.bayGio });
  nhip.nhan();
  assert.deepEqual(dh.xin, [TRE_MAC_DINH]);
});

test("hai máy cùng nhận một tin KHÔNG nổ cùng một tích tắc", () => {
  // Chính là cái đỉnh CPU đồng loạt đo trên prod: cùng tin, cùng hẹn 250ms.
  const nhanBaoNhieu = (r: number) => {
    const dh = taoDongHo();
    taoNhipLamMoi({
      ...taoMan(),
      hen: dh.hen,
      huy: dh.huy,
      bayGio: dh.bayGio,
      jitter: 400,
      rand: () => r,
    }).nhan();
    return dh.xin[0];
  };
  assert.notEqual(nhanBaoNhieu(0.1), nhanBaoNhieu(0.8));
});

test("tin dồn dập (mỗi 100ms) vẫn làm mới trong ~1 giây, không bị hẹn lại mãi", () => {
  const dh = taoDongHo();
  const man = taoMan();
  const nhip = taoNhipLamMoi({
    ...man,
    hen: dh.hen,
    huy: dh.huy,
    bayGio: dh.bayGio,
    choToiDa: 600,
    jitter: 400,
    rand: () => 0.9999, // xấu nhất: lệch tối đa
  });

  let lanDau = -1;
  for (let t = 0; t <= 5000 && lanDau < 0; t += 100) {
    nhip.nhan();
    dh.tien(100);
    if (man.s.soLanLamMoi > 0) lanDau = t + 100;
  }
  assert.ok(lanDau > 0, "phải làm mới dù tin chảy liên tục");
  assert.ok(lanDau <= 1000, `làm mới muộn nhất ~1 giây kể từ tin đầu, thực tế ${lanDau}ms`);
});

test("đối chứng: debounce thuần (không trần) bị dòng tin dồn dập làm đói", () => {
  const dh = taoDongHo();
  const man = taoMan();
  const nhip = taoNhipLamMoi({ ...man, hen: dh.hen, huy: dh.huy, bayGio: dh.bayGio });
  for (let t = 0; t < 5000; t += 100) {
    nhip.nhan();
    dh.tien(100);
  }
  assert.equal(man.s.soLanLamMoi, 0, "đây là lỗi mà `choToiDa` sinh ra để chữa");
});

test("quá trần thì GIỮ hẹn đang chạy, không dời thêm", () => {
  const dh = taoDongHo();
  const nhip = taoNhipLamMoi({
    ...taoMan(),
    hen: dh.hen,
    huy: dh.huy,
    bayGio: dh.bayGio,
    choToiDa: 600,
    jitter: 400,
    rand: () => 0.9999,
  });
  nhip.nhan(); // t=0
  dh.tien(200);
  nhip.nhan(); // t=200: còn trong trần → hẹn lại
  dh.tien(400); // t=600: tới trần
  const soHenTruoc = dh.xin.length;
  nhip.nhan();
  assert.equal(dh.xin.length, soHenTruoc, "quá trần thì không đặt hẹn mới");
});

test("tab ẩn: vẫn không hẹn gì, kể cả có lệch và trần", () => {
  const dh = taoDongHo();
  const man = taoMan();
  const nhip = taoNhipLamMoi({
    ...man,
    hen: dh.hen,
    huy: dh.huy,
    bayGio: dh.bayGio,
    choToiDa: 600,
    jitter: 400,
  });
  man.s.an = true;
  nhip.nhan();
  assert.equal(dh.dangCho(), 0);
  dh.tien(5000);
  assert.equal(man.s.soLanLamMoi, 0, "tab ẩn không dựng lại trang");
});

test("ẩn đi GIỮA lúc chờ (kể cả đang lệch): tới giờ vẫn không dựng", () => {
  const dh = taoDongHo();
  const man = taoMan();
  const nhip = taoNhipLamMoi({
    ...man,
    hen: dh.hen,
    huy: dh.huy,
    bayGio: dh.bayGio,
    jitter: 400,
    rand: () => 0.9999,
  });
  nhip.nhan();
  man.s.an = true;
  dh.tien(5000);
  assert.equal(man.s.soLanLamMoi, 0);
});

test("bắt kịp KHÔNG bị lệch: làm mới ngay trong chính lượt gọi", () => {
  const dh = taoDongHo();
  const man = taoMan();
  const nhip = taoNhipLamMoi({
    ...man,
    hen: dh.hen,
    huy: dh.huy,
    bayGio: dh.bayGio,
    jitter: 400,
    rand: () => 0.9999,
  });
  nhip.batKip();
  assert.equal(man.s.soLanLamMoi, 1);
  assert.equal(dh.xin.length, 0);
});

// ------------------------------------------------ nối lại có lùi ------------

test("nối lại: chờ gấp đôi mỗi lần hỏng, có trần, và mở được thì quên", () => {
  const dh = taoDongHo();
  let soLanMoLai = 0;
  const nl = taoNoiLai({
    moLai: () => {
      soLanMoLai += 1;
    },
    hen: dh.hen,
    huy: dh.huy,
    rand: () => 1, // đầu trên của khoảng [nửa, đủ]
    coSoMs: 2_000,
    tranMs: 60_000,
  });

  const cho: number[] = [];
  for (let i = 0; i < 8; i++) {
    nl.loi();
    cho.push(dh.xin.at(-1)!);
    dh.tien(dh.xin.at(-1)!);
  }
  assert.deepEqual(cho, [2000, 4000, 8000, 16000, 32000, 60000, 60000, 60000]);
  assert.equal(soLanMoLai, 8);

  nl.thanhCong();
  nl.loi();
  assert.equal(dh.xin.at(-1), 2000, "mở được rồi thì lần hỏng sau lại bắt đầu từ đầu");
});

test("nối lại: lệch ngẫu nhiên nằm trong [nửa, đủ] thời lượng", () => {
  const dh = taoDongHo();
  taoNoiLai({ moLai: () => {}, hen: dh.hen, huy: dh.huy, rand: () => 0, coSoMs: 2_000 }).loi();
  assert.equal(dh.xin.at(-1), 1000);
  taoNoiLai({ moLai: () => {}, hen: dh.hen, huy: dh.huy, rand: () => 0.9999, coSoMs: 2_000 }).loi();
  assert.ok(dh.xin.at(-1)! <= 2000 && dh.xin.at(-1)! >= 1000);
});

test("nối lại: `error` bắn liền mấy lần chỉ để lại MỘT hẹn; dừng thì huỷ hẹn", () => {
  const dh = taoDongHo();
  let soLanMoLai = 0;
  const nl = taoNoiLai({
    moLai: () => {
      soLanMoLai += 1;
    },
    hen: dh.hen,
    huy: dh.huy,
  });
  nl.loi();
  nl.loi();
  nl.loi();
  assert.equal(dh.dangCho(), 1);
  nl.dung(); // tab ẩn / rời màn
  assert.equal(dh.dangCho(), 0);
  dh.tien(120_000);
  assert.equal(soLanMoLai, 0, "đã dừng thì không nối lại sau lưng người ta");
});

// ------------------------------------------- nhịp dự phòng thưa -------------

test("nhịp dự phòng: dòng đang sống thì thưa, chưa sống thì giữ nhịp 20s", () => {
  assert.equal(canHoiDuPhong("song", 20_000), false, "dòng sống: 20s chưa cần hỏi");
  assert.equal(canHoiDuPhong("song", 89_000), false);
  assert.equal(canHoiDuPhong("song", 90_000), true, "đủ 90s thì hỏi một lần cho chắc");
  assert.equal(canHoiDuPhong("dang-noi", 20_000), true, "đang nối: nhịp là nguồn tin");
  assert.equal(canHoiDuPhong("rot", 0), true, "dòng rớt: nhịp là nguồn tin duy nhất");
});
