import assert from "node:assert/strict";
import test from "node:test";

import {
  moDongTheoHien,
  NHIP_NGHE_TIN,
  taoKhoTrangThai,
  taoNhipLamMoi,
  TRE_MAC_DINH,
  type Go,
  type Hen,
  type TrangThaiDong,
} from "./nhip-lam-moi.ts";

// ---------------------------------------------------------------- đồ giả ----

/** Đồng hồ giả: `no()` cho mọi cái hẹn đang chờ nổ ngay. */
function taoDongHo() {
  let dem = 0;
  const hens = new Map<number, () => void>();
  return {
    hen: (fn: () => void, ms: number): Hen => {
      assert.equal(ms, TRE_MAC_DINH, "nhịp gộp phải là 250ms");
      const k = ++dem;
      hens.set(k, fn);
      return k;
    },
    huy: (h: Hen) => {
      hens.delete(h as number);
    },
    no: () => {
      const cho = [...hens.values()];
      hens.clear();
      for (const f of cho) f();
    },
    dangCho: () => hens.size,
  };
}

/** Màn hình giả: bật/tắt trạng thái ẩn, đếm lượt dựng lại trang, phát tín hiệu. */
function taoMan() {
  const s = { an: false, soLanLamMoi: 0 };
  const nghe: Array<() => void> = [];
  return {
    s,
    lamMoi: () => {
      s.soLanLamMoi += 1;
    },
    dangAn: () => s.an,
    ngheDoiHien: (fn: () => void): Go => {
      nghe.push(fn);
      return () => {
        const i = nghe.indexOf(fn);
        if (i >= 0) nghe.splice(i, 1);
      };
    },
    /** Người dùng chuyển tab: đổi trạng thái RỒI báo, đúng thứ tự của trình duyệt. */
    doiHien: (an: boolean) => {
      s.an = an;
      for (const f of [...nghe]) f();
    },
    soNguoiNghe: () => nghe.length,
  };
}

/** Nhà máy dòng SSE giả — đếm bao nhiêu dòng THẬT SỰ đang mở. */
function taoDong() {
  const ds: Array<{ nhanTin: (t: string | null) => void; dongRoi: boolean }> = [];
  return {
    moDong: (nhanTin: (t: string | null) => void): Go => {
      const d = { nhanTin, dongRoi: false };
      ds.push(d);
      return () => {
        d.dongRoi = true;
      };
    },
    soDangMo: () => ds.filter((d) => !d.dongRoi).length,
    soDaMo: () => ds.length,
    banTin: (t: string | null) => {
      for (const d of [...ds]) if (!d.dongRoi) d.nhanTin(t);
    },
  };
}

// ------------------------------------------------------- taoNhipLamMoi ------

test("gộp nhịp: một tràng thay đổi chỉ dựng lại trang MỘT lần", () => {
  const dh = taoDongHo();
  const man = taoMan();
  const nhip = taoNhipLamMoi({ ...man, hen: dh.hen, huy: dh.huy });

  for (let i = 0; i < 5; i++) nhip.nhan();
  assert.equal(man.s.soLanLamMoi, 0, "chưa tới nhịp thì chưa dựng");
  assert.equal(dh.dangCho(), 1, "năm lần gọi chỉ để lại MỘT cái hẹn");

  dh.no();
  assert.equal(man.s.soLanLamMoi, 1);
});

test("tab đang ẩn: không dựng lại trang, cũng không đặt hẹn", () => {
  const dh = taoDongHo();
  const man = taoMan();
  const nhip = taoNhipLamMoi({ ...man, hen: dh.hen, huy: dh.huy });

  man.s.an = true;
  nhip.nhan();
  nhip.nhan();

  assert.equal(dh.dangCho(), 0, "tab nền không được để lại hẹn cho lúc quay lại");
  dh.no();
  assert.equal(man.s.soLanLamMoi, 0);
});

test("ẩn đi GIỮA lúc chờ nhịp: tới giờ vẫn không dựng", () => {
  const dh = taoDongHo();
  const man = taoMan();
  const nhip = taoNhipLamMoi({ ...man, hen: dh.hen, huy: dh.huy });

  nhip.nhan(); // lúc này còn hiện → có hẹn
  assert.equal(dh.dangCho(), 1);
  man.s.an = true; // người dùng chuyển tab trong 250ms ấy
  dh.no();

  assert.equal(man.s.soLanLamMoi, 0, "phải kiểm lại lúc nổ, không tin lúc đặt");
});

test("bắt kịp: làm mới NGAY, không chờ nhịp, và nuốt luôn hẹn đang chờ", () => {
  const dh = taoDongHo();
  const man = taoMan();
  const nhip = taoNhipLamMoi({ ...man, hen: dh.hen, huy: dh.huy });

  nhip.nhan();
  nhip.batKip();
  assert.equal(man.s.soLanLamMoi, 1, "làm mới trong chính lượt gọi");
  assert.equal(dh.dangCho(), 0, "hẹn cũ phải bị nuốt, không thành lượt dựng thứ hai");

  dh.no();
  assert.equal(man.s.soLanLamMoi, 1);
});

test("bắt kịp lúc tab vẫn đang ẩn: không dựng gì", () => {
  const dh = taoDongHo();
  const man = taoMan();
  const nhip = taoNhipLamMoi({ ...man, hen: dh.hen, huy: dh.huy });

  man.s.an = true;
  nhip.batKip();
  assert.equal(man.s.soLanLamMoi, 0);
});

test("dừng: cái hẹn đang chờ bị huỷ, không dựng trang sau khi gỡ", () => {
  const dh = taoDongHo();
  const man = taoMan();
  const nhip = taoNhipLamMoi({ ...man, hen: dh.hen, huy: dh.huy });

  nhip.nhan();
  nhip.dung();
  dh.no();

  assert.equal(man.s.soLanLamMoi, 0);
  assert.equal(dh.dangCho(), 0);
});

// ------------------------------------------------------ moDongTheoHien ------

/** Dựng một "tab": dòng sự kiện theo tầm nhìn, ghi lại tin và số lần bắt kịp. */
function taoTab(dong: ReturnType<typeof taoDong>, man: ReturnType<typeof taoMan>) {
  const nhanDuoc: Array<string | null> = [];
  const batKip = { so: 0 };
  const go = moDongTheoHien({
    moDong: dong.moDong,
    dangAn: man.dangAn,
    ngheDoiHien: man.ngheDoiHien,
    xuLy: (t) => nhanDuoc.push(t),
    khiMoLai: () => {
      batKip.so += 1;
    },
  });
  return { nhanDuoc, batKip, go };
}

test("tab ẩn KHÔNG giữ kết nối — đây là cả bài toán", () => {
  const dong = taoDong();
  const man = taoMan();
  const tab = taoTab(dong, man);

  assert.equal(dong.soDangMo(), 1, "đang hiện thì có dòng");

  man.doiHien(true);
  assert.equal(
    dong.soDangMo(),
    0,
    "ẩn đi phải NHẢ kết nối — mỗi dòng còn giữ là một trong sáu chỗ của trình duyệt",
  );

  man.doiHien(false);
  assert.equal(dong.soDangMo(), 1, "hiện lại thì nối lại");
  tab.go();
});

test("mười tab mở, một tab đang nhìn: MỘT kết nối", () => {
  const dong = taoDong();
  const mans = Array.from({ length: 10 }, (_, i) => {
    const m = taoMan();
    m.s.an = i !== 0; // chỉ tab đầu đang hiện
    return m;
  });
  const tabs = mans.map((m) => taoTab(dong, m));

  assert.equal(
    dong.soDangMo(),
    1,
    "mười tab phải là một kết nối, còn năm chỗ trống cho việc bấm nút",
  );

  // Người dùng chuyển từ tab 0 sang tab 3: vẫn đúng một kết nối.
  mans[0].doiHien(true);
  mans[3].doiHien(false);
  assert.equal(dong.soDangMo(), 1);

  for (const t of tabs) t.go();
  assert.equal(dong.soDangMo(), 0);
});

test("lướt qua sáu tab không tích luỹ kết nối", () => {
  // Đây là cái bẫy của "quãng ân hạn trước khi đóng": lướt nhanh qua sáu tab
  // trong quãng ấy là sáu dòng cùng mở, tức trình duyệt đứng hình lần nữa.
  const dong = taoDong();
  const mans = Array.from({ length: 6 }, (_, i) => {
    const m = taoMan();
    m.s.an = i !== 0;
    return m;
  });
  const tabs = mans.map((m) => taoTab(dong, m));

  for (let i = 1; i < 6; i++) {
    mans[i - 1].doiHien(true);
    mans[i].doiHien(false);
    assert.equal(dong.soDangMo(), 1, `sau khi tới tab ${i} vẫn phải là 1 kết nối`);
  }
  assert.equal(dong.soDaMo(), 6, "sáu lượt nối lại — rẻ, và có trần");

  for (const t of tabs) t.go();
});

test("mở LẠI thì bắt kịp; lần mở ĐẦU thì không", () => {
  const dong = taoDong();
  const man = taoMan();
  const tab = taoTab(dong, man);

  assert.equal(
    tab.batKip.so,
    0,
    "trang vừa dựng xong, dữ liệu đang mới — bắt kịp ở đây là một lượt dựng thừa",
  );

  man.doiHien(true);
  man.doiHien(false);
  assert.equal(tab.batKip.so, 1, "quãng ẩn là quãng mù, nên mở lại là phải làm mới");

  man.doiHien(true);
  man.doiHien(false);
  assert.equal(tab.batKip.so, 2);
  tab.go();
});

test("tab mở trong lúc đang ẩn: không mở dòng; lúc được nhìn thì bắt kịp MỘT lần", () => {
  // Đổi 30/09/2026. Bản trước coi lần mở đầu (dù tới muộn) là "chưa từng mù".
  // Sai với Ctrl+bấm link: trang dựng lúc tải trong tab nền, rồi người ta nhìn
  // nó sau năm phút — suốt năm phút ấy không có dòng nào. Trước đây
  // `LiveBoardSync` tự nghe `visibilitychange` nên che được lỗ này ở các màn
  // điều phối; nay nó thôi nghe để một lần đổi tab chỉ còn một lần dựng trang.
  const dong = taoDong();
  const man = taoMan();
  man.s.an = true;
  const tab = taoTab(dong, man);

  assert.equal(dong.soDangMo(), 0);
  assert.equal(tab.batKip.so, 0, "đang ẩn thì chưa làm gì cả");

  man.doiHien(false);
  assert.equal(dong.soDangMo(), 1);
  assert.equal(
    tab.batKip.so,
    1,
    "quãng từ lúc tải tới lúc được nhìn là quãng mù — phải bắt kịp đúng một lần",
  );
  tab.go();
});

test("báo tầm nhìn nhiều lần cùng một trạng thái: không nối lại vô ích", () => {
  const dong = taoDong();
  const man = taoMan();
  const tab = taoTab(dong, man);

  man.doiHien(false);
  man.doiHien(false);
  assert.equal(dong.soDaMo(), 1, "đang mở rồi thì thôi");
  assert.equal(tab.batKip.so, 0);

  man.doiHien(true);
  man.doiHien(true);
  assert.equal(dong.soDangMo(), 0);
  tab.go();
});

test("tin tới được người xử lý, và thôi tới sau khi tab ẩn", () => {
  const dong = taoDong();
  const man = taoMan();
  const tab = taoTab(dong, man);

  dong.banTin("appointment");
  assert.deepEqual(tab.nhanDuoc, ["appointment"]);

  man.doiHien(true);
  dong.banTin("visit");
  assert.deepEqual(tab.nhanDuoc, ["appointment"], "dòng đã đóng thì không nhận nữa");

  man.doiHien(false);
  dong.banTin("payment");
  assert.deepEqual(tab.nhanDuoc, ["appointment", "payment"]);
  tab.go();
});

test("gỡ bỏ: đóng dòng và THÔI NGHE tầm nhìn", () => {
  const dong = taoDong();
  const man = taoMan();
  const tab = taoTab(dong, man);
  assert.equal(man.soNguoiNghe(), 1);

  tab.go();
  assert.equal(dong.soDangMo(), 0);
  assert.equal(
    man.soNguoiNghe(),
    0,
    "để lại tay nghe là để lại một component đã gỡ vẫn mở kết nối",
  );

  man.doiHien(true);
  man.doiHien(false);
  assert.equal(dong.soDaMo(), 1, "gỡ rồi thì chuyển tab không được mở dòng mới");
});

test("kho trạng thái dòng: đổi mới báo, trùng thì im, thôi nghe là thôi", () => {
  const kho = taoKhoTrangThai<TrangThaiDong>("dang-noi");
  let soLanBao = 0;
  const thoi = kho.nghe(() => {
    soLanBao += 1;
  });

  kho.dat("song");
  assert.equal(kho.doc(), "song");
  assert.equal(soLanBao, 1);

  kho.dat("song");
  assert.equal(soLanBao, 1, "giá trị không đổi thì không bắt người nghe render lại");

  thoi();
  kho.dat("rot");
  assert.equal(kho.doc(), "rot");
  assert.equal(soLanBao, 1, "đã thôi nghe thì không được gọi nữa");
});

// ------------------------------------------------- bão tin (prod 20/11) ----
//
// 11:20 chạy xoá lô giả + bù trừ kho: ~1.000 dòng ghi liền, tin realtime đổ về
// suốt vài chục giây. Nhịp cũ (gộp 250ms, trần 600ms) → mỗi tab dựng lại trang
// ~1 lần/giây, mỗi lần 6–7 API → /me 429 (trần 400/phút/tài khoản) → layout ném
// "Máy chủ đang bận". Đồng hồ ảo dưới đây chạy hẹn theo đúng thời điểm.

function taoThoiGian() {
  let bay = 0;
  let dem = 0;
  const hens = new Map<number, { luc: number; fn: () => void }>();
  return {
    bayGio: () => bay,
    hen: (fn: () => void, ms: number): Hen => {
      const k = ++dem;
      hens.set(k, { luc: bay + ms, fn });
      return k;
    },
    huy: (h: Hen) => {
      hens.delete(h as number);
    },
    /** Chạy tới thời điểm `t`, nổ mọi hẹn tới hạn theo đúng thứ tự. */
    toi: (t: number) => {
      for (;;) {
        const den = [...hens.entries()]
          .filter(([, h]) => h.luc <= t)
          .sort((a, b) => a[1].luc - b[1].luc)[0];
        if (!den) break;
        hens.delete(den[0]);
        bay = den[1].luc;
        den[1].fn();
      }
      bay = t;
    },
  };
}

function nhipThat(tg: ReturnType<typeof taoThoiGian>, lan: number[]) {
  return taoNhipLamMoi({
    lamMoi: () => lan.push(tg.bayGio()),
    dangAn: () => false,
    hen: tg.hen,
    huy: tg.huy,
    bayGio: tg.bayGio,
    rand: () => 0.5,
    ...NHIP_NGHE_TIN,
  });
}

test("bão tin 60 giây: mỗi tab dựng lại trang tối đa ~20 lần/phút, không phải ~100", () => {
  const tg = taoThoiGian();
  const lan: number[] = [];
  const nhip = nhipThat(tg, lan);
  for (let t = 0; t < 60_000; t += 100) {
    tg.toi(t);
    nhip.nhan();
  }
  tg.toi(70_000);
  // 7 API mỗi lượt × 21 lượt ≈ 150/phút — dưới ngưỡng cảnh báo 200, xa trần 400.
  assert.ok(lan.length <= 21, `dựng lại ${lan.length} lần trong 60 giây`);
  for (let i = 1; i < lan.length; i++) {
    assert.ok(lan[i] - lan[i - 1] >= 3_000, `hai lượt cách ${lan[i] - lan[i - 1]}ms`);
  }
  // Không bỏ sót: lượt cuối nổ SAU tin cuối → màn hiện số cuối cùng.
  assert.ok(lan[lan.length - 1] >= 59_900, "phải có một lượt sau tin cuối");
});

test("tin lẻ sau lúc yên: vẫn làm mới trong ~1 giây như cũ", () => {
  const tg = taoThoiGian();
  const lan: number[] = [];
  const nhip = nhipThat(tg, lan);
  tg.toi(10_000);
  nhip.nhan();
  tg.toi(20_000);
  assert.equal(lan.length, 1);
  assert.ok(lan[0] - 10_000 <= 1_000, `chờ ${lan[0] - 10_000}ms`);
  // Hai thao tác cách nhau 5 giây (người bấm thật): cả hai đều ~1 giây.
  nhip.nhan();
  tg.toi(30_000);
  assert.equal(lan.length, 2);
  assert.ok(lan[1] - 20_000 <= 1_000, `chờ ${lan[1] - 20_000}ms`);
});

test("bão DÀY kéo dài: khoảng nới lên 6 giây — 3 cửa sổ cùng tài khoản vẫn dưới trần", () => {
  const tg = taoThoiGian();
  const lan: number[] = [];
  const nhip = nhipThat(tg, lan);
  for (let t = 0; t < 60_000; t += 100) {
    tg.toi(t);
    nhip.nhan();
  }
  tg.toi(80_000);
  // ≤ 12 lượt × 7 API × 3 cửa sổ ≈ 250/phút < 400.
  assert.ok(lan.length <= 12, `dựng lại ${lan.length} lần trong 60 giây`);
  const giua = lan.slice(2).map((t, i) => t - lan[i + 1]);
  assert.ok(giua.every((d) => d >= 6_000), `khoảng sau khi nới: ${giua.join(", ")}`);
});

test("bão qua, yên lại: tin lẻ quay về ~1 giây; tin THƯA (người bấm) không làm nới", () => {
  const tg = taoThoiGian();
  const lan: number[] = [];
  const nhip = nhipThat(tg, lan);
  for (let t = 0; t < 20_000; t += 100) {
    tg.toi(t);
    nhip.nhan();
  }
  tg.toi(60_000);
  const truoc = lan.length;
  nhip.nhan();
  tg.toi(61_000);
  assert.equal(lan.length, truoc + 1);
  assert.ok(lan[lan.length - 1] - 60_000 <= 1_000, "yên rồi thì nhanh như cũ");
  // Quầy đông: 3 tin mỗi 2 giây suốt 60 giây — giữ khoảng 3 giây, không nới.
  const tu = lan.length;
  for (let t = 70_000; t < 130_000; t += 2_000) {
    for (const d of [0, 50, 100]) {
      tg.toi(t + d);
      nhip.nhan();
    }
  }
  tg.toi(140_000);
  const moi = lan.slice(tu);
  const giua = moi.slice(1).map((t, i) => t - moi[i]);
  assert.ok(giua.every((d) => d < 6_000), `quầy đông bị chậm: ${giua.join(", ")}`);
});

test("đồng hồ máy bị chỉnh lùi: không chờ quá một khoảng", () => {
  let bay = 100_000;
  const hens: Array<{ ms: number }> = [];
  const nhip = taoNhipLamMoi({
    lamMoi: () => {},
    dangAn: () => false,
    hen: (_fn, ms) => {
      hens.push({ ms });
      return hens.length;
    },
    huy: () => {},
    bayGio: () => bay,
    rand: () => 0,
    ...NHIP_NGHE_TIN,
  });
  nhip.batKip(); // lượt cuối ghi ở 100.000
  bay = 0; // NTP kéo lùi 100 giây
  nhip.nhan();
  assert.ok(hens[0].ms <= 6_000, `chờ ${hens[0].ms}ms`);
});

test("bắt kịp (quay lại tab) vẫn làm mới NGAY, kể cả ngay sau một lượt", () => {
  const tg = taoThoiGian();
  const lan: number[] = [];
  const nhip = nhipThat(tg, lan);
  nhip.nhan();
  tg.toi(2_000);
  nhip.batKip();
  assert.deepEqual(lan.length, 2, "người vừa nhìn vào màn hình không phải chờ");
});
