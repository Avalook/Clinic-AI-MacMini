import assert from "node:assert/strict";
import test from "node:test";

import {
  moDongTheoHien,
  taoNhipLamMoi,
  TRE_MAC_DINH,
  type Go,
  type Hen,
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

test("tab mở lần đầu trong lúc đang ẩn: không mở dòng, và không bắt kịp oan", () => {
  const dong = taoDong();
  const man = taoMan();
  man.s.an = true;
  const tab = taoTab(dong, man);

  assert.equal(dong.soDangMo(), 0);
  assert.equal(tab.batKip.so, 0);

  man.doiHien(false);
  assert.equal(dong.soDangMo(), 1);
  assert.equal(
    tab.batKip.so,
    0,
    "đây vẫn là lần mở ĐẦU của tab này, chưa từng mù nên chưa có gì để bắt kịp",
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
