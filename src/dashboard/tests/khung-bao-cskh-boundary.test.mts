// Khung báo dưới tên khách (Tuyền chốt 16/09/2026): mọi thay đổi ảnh hưởng lịch
// của khách hiện một chỗ, cái gấp lên trước, bấm được thì dẫn đúng việc.

import assert from "node:assert/strict";
import test from "node:test";

import { dungKhungBao, type DauVaoBao } from "../app/(dashboard)/customers/khung-bao.ts";

const NOW = Date.parse("2026-09-16T03:00:00Z"); // 10:00 giờ VN

function vao(p: Partial<DauVaoBao> = {}): DauVaoBao {
  return {
    homNay: "2026-09-16",
    nowMs: NOW,
    luot: {
      id: "a1",
      slot_start: "2026-09-23T02:00:00Z",
      doctor_name: "BS Thành",
    },
    viec: [],
    quanLyDoiGio: false,
    henGoiLai: [],
    taiKham: [],
    ...p,
  };
}

test("không có gì ảnh hưởng lịch thì khung báo rỗng", () => {
  assert.deepEqual(dungKhungBao(vao()), []);
});

test("vượt sức chứa nói rõ giờ + bác sĩ và bấm để đổi lịch", () => {
  const [d] = dungKhungBao(
    vao({ viec: [{ trang_thai: "VUOT_SUC_CHUA", qua_han: false, han_xu_ly: null }] }),
  );
  assert.ok(d);
  assert.equal(d.muc, "gap");
  assert.match(d.cau, /BS Thành/);
  assert.match(d.cau, /vượt sức chứa — ca đã đủ số lượng khám/);
  assert.deepEqual(d.hanhDong, { loai: "sua_lich" });
});

test("gấp đứng trước nhắc, dù nguồn đến theo thứ tự nào", () => {
  const ds = dungKhungBao(
    vao({
      viec: [
        { trang_thai: "CHO_XAC_NHAN", qua_han: false, han_xu_ly: null },
        { trang_thai: "KQ_CHUA_GUI", qua_han: false, han_xu_ly: null },
      ],
      luot: { id: "a1", slot_start: "2026-09-23T02:00:00Z", mat_bac_si: true },
    }),
  );
  assert.deepEqual(
    ds.map((d) => d.khoa),
    ["MAT_BAC_SI", "KQ_CHUA_GUI", "CHO_XAC_NHAN"],
  );
  assert.match(ds[2]!.cau, /Còn 7 ngày/);
});

test("hẹn gọi lại chỉ báo khi tới ngày; quá ngày là gấp", () => {
  const hen = (ngay_goi: string) => ({ id: ngay_goi, ngay_goi, gio_goi: null, ly_do: "khách bận" });
  const ds = dungKhungBao(
    vao({ henGoiLai: [hen("2026-09-20"), hen("2026-09-16"), hen("2026-09-10")] }),
  );
  assert.deepEqual(
    ds.map((d) => [d.khoa, d.muc]),
    [
      ["HEN_2026-09-10", "gap"],
      ["HEN_2026-09-16", "nhac"],
    ],
  );
});

test("theo dõi sau thủ thuật: báo khi còn ≤ 1 ngày, quá hạn là gấp, không bịa hạn", () => {
  const luot = (xong: string | null, theoDoi: string | null, n: number | null) => ({
    id: "a1",
    slot_start: "2026-09-10T02:00:00Z",
    thu_thuat_xong_luc: xong,
    theo_doi_thu_thuat: theoDoi,
    theo_doi_sau_ngay: n,
  });
  // Làm xong 14/09 + 1 ngày → hạn 15/09, đã qua.
  assert.equal(
    dungKhungBao(vao({ luot: luot("2026-09-14T03:00:00Z", "CAN", 1) }))[0]?.muc,
    "gap",
  );
  // Hạn còn 5 ngày → chưa báo.
  assert.deepEqual(dungKhungBao(vao({ luot: luot("2026-09-14T03:00:00Z", "CAN", 7) })), []);
  // Không cần / chưa làm xong → không có hạn nào để báo.
  assert.deepEqual(dungKhungBao(vao({ luot: luot("2026-09-01T03:00:00Z", "KHONG_CAN", null) })), []);
  assert.deepEqual(dungKhungBao(vao({ luot: luot(null, "CAN", 1) })), []);
});

test("kết quả về muộn chỉ báo khi QUÁ HẠN, và bấm dẫn đúng việc", () => {
  const chua = dungKhungBao(vao({ viec: [{ trang_thai: "CHO_KQ_XN", qua_han: false, han_xu_ly: null }] }));
  assert.deepEqual(chua, []);
  const [muon] = dungKhungBao(vao({ viec: [{ trang_thai: "CHO_KQ_XN", qua_han: true, han_xu_ly: null }] }));
  assert.deepEqual(muon?.hanhDong, { loai: "chon_viec", ma: "CHO_KQ_XN" });
});
