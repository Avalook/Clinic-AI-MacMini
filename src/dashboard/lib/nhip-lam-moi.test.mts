import assert from "node:assert/strict";
import test from "node:test";

import {
  moDongSuKien,
  taoNhipLamMoi,
  TRE_MAC_DINH,
  type Go,
  type Hen,
  type Kenh,
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

/** Màn hình giả: bật/tắt được trạng thái ẩn, đếm số lượt dựng lại trang. */
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

/**
 * Web Locks giả. Giữ đúng hai tính chất thật:
 *   - mỗi lúc chỉ MỘT người giữ khoá,
 *   - người giữ nhả ra thì người xếp hàng kế tiếp lên thay.
 */
function taoKhoaGia() {
  type Muc = { duoc: () => void };
  const hangCho: Muc[] = [];
  let dangGiu: Muc | null = null;

  function thu() {
    if (dangGiu || hangCho.length === 0) return;
    dangGiu = hangCho[0];
    dangGiu.duoc();
  }

  function xinLamChu(duoc: () => void): Go {
    const muc: Muc = { duoc };
    hangCho.push(muc);
    thu();
    return () => {
      const i = hangCho.indexOf(muc);
      if (i >= 0) hangCho.splice(i, 1);
      if (dangGiu === muc) {
        dangGiu = null;
        thu();
      }
    };
  }

  return { xinLamChu, soXepHang: () => hangCho.length };
}

/**
 * BroadcastChannel giả. Giữ tính chất dễ quên nhất của bản thật: kênh vừa gửi
 * KHÔNG nhận lại tin của chính mình. Nếu giả sai chỗ này thì tab chủ sẽ xử lý
 * mỗi tin hai lần mà test vẫn xanh.
 */
function taoBus() {
  const nghe: Array<(t: string | null) => void> = [];
  return {
    moKenh: (nhan: (t: string | null) => void): Kenh => {
      nghe.push(nhan);
      return {
        gui: (t) => {
          for (const f of [...nghe]) if (f !== nhan) f(t);
        },
        dong: () => {
          const i = nghe.indexOf(nhan);
          if (i >= 0) nghe.splice(i, 1);
        },
      };
    },
    soKenh: () => nghe.length,
  };
}

/** Nhà máy dòng SSE giả — đếm xem có bao nhiêu dòng THẬT SỰ đang mở. */
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

/** Một "tab": mở dòng sự kiện, ghi lại mọi tin nó nhận được. */
function taoTab(
  dong: ReturnType<typeof taoDong>,
  khoa: ReturnType<typeof taoKhoaGia> | null,
  bus: ReturnType<typeof taoBus> | null,
) {
  const nhanDuoc: Array<string | null> = [];
  const go = moDongSuKien({
    moDong: dong.moDong,
    xinLamChu: khoa ? khoa.xinLamChu : null,
    moKenh: bus ? bus.moKenh : null,
    xuLy: (t) => nhanDuoc.push(t),
  });
  return { nhanDuoc, go };
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

test("quay lại tab: có bỏ lỡ thì làm mới NGAY, không chờ nhịp", () => {
  const dh = taoDongHo();
  const man = taoMan();
  const nhip = taoNhipLamMoi({ ...man, hen: dh.hen, huy: dh.huy });

  man.s.an = true;
  nhip.nhan();
  man.s.an = false;
  nhip.hienLai();

  assert.equal(man.s.soLanLamMoi, 1, "làm mới ngay trong lượt gọi, không qua hẹn");
  assert.equal(dh.dangCho(), 0);
});

test("quay lại tab mà KHÔNG bỏ lỡ gì: không dựng lại trang", () => {
  const dh = taoDongHo();
  const man = taoMan();
  const nhip = taoNhipLamMoi({ ...man, hen: dh.hen, huy: dh.huy });

  nhip.hienLai();
  assert.equal(man.s.soLanLamMoi, 0);

  // Và một lượt làm mới bình thường xong thì cũng hết nợ.
  nhip.nhan();
  dh.no();
  assert.equal(man.s.soLanLamMoi, 1);
  nhip.hienLai();
  assert.equal(man.s.soLanLamMoi, 1, "chuyển tab qua lại không được sinh lượt dựng");
});

test("nợ chỉ trả MỘT lần dù quay lại tab nhiều lần", () => {
  const dh = taoDongHo();
  const man = taoMan();
  const nhip = taoNhipLamMoi({ ...man, hen: dh.hen, huy: dh.huy });

  man.s.an = true;
  nhip.nhan();
  man.s.an = false;
  nhip.hienLai();
  nhip.hienLai();
  nhip.hienLai();

  assert.equal(man.s.soLanLamMoi, 1);
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

// -------------------------------------------------------- moDongSuKien ------

test("mười tab dùng CHUNG một dòng SSE", () => {
  const dong = taoDong();
  const khoa = taoKhoaGia();
  const bus = taoBus();

  const tabs = Array.from({ length: 10 }, () => taoTab(dong, khoa, bus));

  assert.equal(
    dong.soDangMo(),
    1,
    "đây là cả bài toán: 10 tab phải là 1 kết nối, không phải 10",
  );
  assert.equal(bus.soKenh(), 10, "mọi tab đều nghe kênh phát lại");

  for (const t of tabs) t.go();
});

test("tin của tab chủ tới được MỌI tab, mỗi tab đúng một lần", () => {
  const dong = taoDong();
  const khoa = taoKhoaGia();
  const bus = taoBus();

  const tabs = Array.from({ length: 3 }, () => taoTab(dong, khoa, bus));
  dong.banTin("appointment");

  for (const [i, t] of tabs.entries()) {
    assert.deepEqual(
      t.nhanDuoc,
      ["appointment"],
      `tab ${i} phải nhận đúng một lần — hai lần nghĩa là dựng trang hai lượt`,
    );
  }

  for (const t of tabs) t.go();
});

test("tab chủ đóng: tab khác lên thay và mở dòng mới", () => {
  const dong = taoDong();
  const khoa = taoKhoaGia();
  const bus = taoBus();

  const a = taoTab(dong, khoa, bus);
  const b = taoTab(dong, khoa, bus);
  const c = taoTab(dong, khoa, bus);
  assert.equal(dong.soDaMo(), 1);

  a.go(); // người dùng đóng tab chủ

  assert.equal(dong.soDaMo(), 2, "phải có tab lên thay");
  assert.equal(dong.soDangMo(), 1, "nhưng vẫn chỉ MỘT dòng sống");

  dong.banTin("visit");
  assert.deepEqual(b.nhanDuoc, ["visit"]);
  assert.deepEqual(c.nhanDuoc, ["visit"]);
  assert.deepEqual(a.nhanDuoc, [], "tab đã đóng thì thôi nhận");

  b.go();
  c.go();
});

test("thiếu Web Locks hoặc BroadcastChannel: quay về cách cũ, mỗi tab một dòng", () => {
  for (const [ten, coKhoa, coBus] of [
    ["không Web Locks", false, true],
    ["không BroadcastChannel", true, false],
    ["không cả hai", false, false],
  ] as const) {
    const dong = taoDong();
    const khoa = coKhoa ? taoKhoaGia() : null;
    const bus = coBus ? taoBus() : null;

    const tabs = [taoTab(dong, khoa, bus), taoTab(dong, khoa, bus)];
    assert.equal(dong.soDangMo(), 2, `${ten}: chậm hơn, nhưng phải CHẠY`);

    dong.banTin("payment");
    for (const t of tabs) assert.deepEqual(t.nhanDuoc, ["payment"], ten);

    for (const t of tabs) t.go();
    assert.equal(dong.soDangMo(), 0, `${ten}: gỡ bỏ phải đóng dòng`);
  }
});

test("gỡ bỏ: đóng dòng, rời kênh, và thôi xếp hàng chờ làm chủ", () => {
  const dong = taoDong();
  const khoa = taoKhoaGia();
  const bus = taoBus();

  const a = taoTab(dong, khoa, bus);
  const b = taoTab(dong, khoa, bus);
  assert.equal(khoa.soXepHang(), 2);

  b.go(); // tab đang XẾP HÀNG đóng lại
  assert.equal(khoa.soXepHang(), 1, "không được để lại một chỗ xếp hàng chết");
  assert.equal(bus.soKenh(), 1);
  assert.equal(dong.soDangMo(), 1, "tab chủ vẫn giữ dòng");

  a.go(); // tab CHỦ đóng lại, không còn ai
  assert.equal(dong.soDangMo(), 0);
  assert.equal(bus.soKenh(), 0);
  assert.equal(khoa.soXepHang(), 0);
});
