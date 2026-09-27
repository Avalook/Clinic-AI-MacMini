// Bản in phiếu khám hai trang (27/09/2026): mục III và trang ảnh đọc qua hai
// hàm này — màn khám dùng CÙNG hàm, nên giấy và màn không lệch nhau.
import assert from "node:assert/strict";
import test from "node:test";

import { anhInDuoc, dongKetQua, type ChiDinhVaKetQua, type KetQuaMotChiDinh } from "./phieu-kham.ts";

const tep = (id: string, loai_tep: string, xac: string | null, luc: string): KetQuaMotChiDinh => ({
  loai: "TEP",
  tep_id: id,
  ten: id,
  loai_tep,
  xac_nhan_trang_thai: xac,
  tai_len_luc: luc,
});

test("anhInDuoc: chỉ ẢNH hợp lệ (NULL = tải ở phòng), theo thứ tự chụp", () => {
  const cd = {
    ket_qua: [
      tep("a2", "ANH", "HOP_LE", "2026-09-27T09:02:00Z"),
      tep("a1", "ANH", null, "2026-09-27T09:01:00Z"),
      tep("cho", "ANH", "CHO_XAC_NHAN", "2026-09-27T09:03:00Z"),
      tep("tu-choi", "ANH", "TU_CHOI", "2026-09-27T09:04:00Z"),
      tep("vid", "VIDEO", null, "2026-09-27T09:05:00Z"),
      tep("pdf", "PDF", null, "2026-09-27T09:06:00Z"),
    ],
  } as unknown as ChiDinhVaKetQua;
  assert.deepEqual(
    anhInDuoc(cd).map((k) => k.tep_id),
    ["a1", "a2"],
  );
});

test("dongKetQua: bỏ ô trống, tách Kết luận, gắn đơn vị cho số", () => {
  const k = {
    loai: "PHIEU",
    ten: "Siêu âm",
    khung: [
      {
        ma: "do",
        ten: "Số đo",
        block: [
          { ma: "tu_cung", ten: "Tử cung", kieu: "so", goi_y: "mm" },
          { ma: "trong", ten: "Ô trống", kieu: "text" },
          { ma: "ket_luan", ten: "Kết luận", kieu: "doan_van" },
        ],
      },
    ],
    du_lieu: {
      tu_cung: { gia_tri: "45" },
      trong: { gia_tri: "" },
      ket_luan: { gia_tri: "Bình thường" },
    },
  } as unknown as KetQuaMotChiDinh;
  const { dong, ketLuan } = dongKetQua(k);
  assert.deepEqual(dong, [{ nhan: "Tử cung", gia: "45 mm" }]);
  assert.equal(ketLuan, "Bình thường");
});
