"use client";

// Mục E — CHỈ ĐỊNH ĐIỀU TRỊ (đơn thuốc).
//
// Nguồn: *"E là nơi duy nhất ghi thuốc thực tế của đơn"*. Đơn thuốc đã có chỗ
// giữ riêng (bảng `prescription`, có luồng bác sĩ duyệt bản nháp của thư ký và
// có kho cấp phát). Phiếu KHÔNG giữ bản sao thứ hai — nên component này ĐIỀU
// KHIỂN TỪ NGOÀI: nó nhận `dong` và báo `onDoi`, còn ghi xuống đâu là việc của
// Bàn khám (đường ghi đơn thuốc sẵn có). Không truyền `onDoi` = chỉ đọc.
//
// Chọn thuốc từ danh mục gợi ý thì cách dùng / lưu ý được điền sẵn, bác sĩ sửa
// được. Danh mục gợi ý là NHÃN của tài liệu nguồn: dòng nào chưa gắn thuốc kho
// (`drug_catalog_id` trống) thì nói ra — chưa thu tiền, chưa cấp được — chứ
// không tự dò tên để gắn.

import { useMemo, useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import { INPUT, TBL_DIV, TBL_HEAD, TBL_WRAP } from "../../form-ui";
import {
  dongTuMau,
  locMauThuoc,
  type DongThuoc,
  type MauThuoc,
} from "@/lib/phieu-kham";

const COT: { ma: keyof DongThuoc; ten: string }[] = [
  { ma: "ten_thuoc", ten: "Thuốc" },
  { ma: "duong_dung", ten: "Đường dùng" },
  { ma: "so_luong", ten: "Số lượng" },
  { ma: "don_vi", ten: "Đơn vị" },
  { ma: "cach_dung", ten: "Cách dùng" },
  { ma: "luu_y", ten: "Lưu ý" },
];

export default function DonThuocPhieu({
  dong,
  mauThuoc,
  onDoi,
}: {
  dong: DongThuoc[];
  mauThuoc: MauThuoc[];
  /** Không truyền = chỉ đọc (hồ sơ đã chốt, hoặc chưa nối đường ghi đơn). */
  onDoi?: (dong: DongThuoc[]) => void;
}) {
  const [tu, setTu] = useState("");
  const [moDanhMuc, setMoDanhMuc] = useState(false);
  const loc = useMemo(() => locMauThuoc(mauThuoc, tu), [mauThuoc, tu]);
  const chiDoc = !onDoi;

  const sua = (i: number, ma: keyof DongThuoc, v: string) =>
    onDoi?.(dong.map((d, j) => (j === i ? { ...d, [ma]: v } : d)));

  return (
    <div className="space-y-3">
      {!chiDoc ? (
        <div className="space-y-2">
          <Button
            type="button"
            size="sm"
            variant="secondary"
            aria-expanded={moDanhMuc}
            onClick={() => setMoDanhMuc(!moDanhMuc)}
          >
            Danh mục thuốc ({mauThuoc.length})
          </Button>
          {moDanhMuc ? (
            <div className="space-y-2 rounded-card border border-hairline p-3">
              <input
                type="search"
                value={tu}
                onChange={(e) => setTu(e.target.value)}
                placeholder="Tìm tên thuốc / đường dùng…"
                className={INPUT}
              />
              <ul className="grid max-h-64 grid-cols-1 gap-1 overflow-y-auto sm:grid-cols-2">
                {loc.map((m) => (
                  <li key={m.ma}>
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      className="w-full"
                      onClick={() => onDoi?.([...dong, dongTuMau(m)])}
                    >
                      <span className="font-medium text-ink">{m.nhan_nguon}</span>
                      <span className="ml-2 text-ink-muted">{m.type}</span>
                    </Button>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}

      {dong.length === 0 ? (
        <p className="text-body text-ink-faint">Chưa chọn thuốc.</p>
      ) : null}
      {/* ĐIỆN THOẠI: mỗi thuốc một thẻ. Bảng sáu cột ở khổ 375 kéo cả trang tràn
          ngang dù đã bọc khung cuộn (bấm thật 23/09) — và sáu ô 40px thì không
          ai gõ được. Từ sm trở lên vẫn là bảng. */}
      {dong.length > 0 ? (
        <ul className="space-y-2 sm:hidden">
          {dong.map((d, i) => (
            <li
              key={`the-${d.mau_ma ?? "tu-do"}-${i}`}
              className="space-y-2 rounded-card border border-hairline bg-surface p-3"
            >
              {COT.map((c) => (
                <label key={c.ma} className="block text-meta text-ink-muted">
                  {c.ten}
                  <input
                    value={String(d[c.ma] ?? "")}
                    disabled={chiDoc}
                    onChange={(e) => sua(i, c.ma, e.target.value)}
                    className={INPUT}
                  />
                </label>
              ))}
              {!d.drug_catalog_id ? <Chip tone="warning">Chưa gắn thuốc kho</Chip> : null}
              {!chiDoc ? (
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  onClick={() => onDoi?.(dong.filter((_, j) => j !== i))}
                >
                  Bỏ thuốc này
                </Button>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}
      {dong.length === 0 ? null : (
        <div className={`hidden overflow-x-auto sm:block ${TBL_WRAP}`}>
          <table className="w-full text-body">
            <thead className={TBL_HEAD}>
              <tr>
                {COT.map((c) => (
                  <th key={c.ma} scope="col" className="px-3 py-2 text-left">
                    {c.ten}
                  </th>
                ))}
                {!chiDoc ? (
                  <th scope="col" className="px-3 py-2">
                    <span className="sr-only">Bỏ dòng</span>
                  </th>
                ) : null}
              </tr>
            </thead>
            <tbody className={TBL_DIV}>
              {dong.map((d, i) => (
                <tr key={`${d.mau_ma ?? "tu-do"}-${i}`}>
                  {COT.map((c) => (
                    <td key={c.ma} className="px-3 py-1.5 align-top">
                      <input
                        aria-label={c.ten}
                        value={String(d[c.ma] ?? "")}
                        disabled={chiDoc}
                        onChange={(e) => sua(i, c.ma, e.target.value)}
                        className={INPUT}
                      />
                      {c.ma === "ten_thuoc" && !d.drug_catalog_id ? (
                        <Chip tone="warning" className="mt-1">
                          Chưa gắn thuốc kho
                        </Chip>
                      ) : null}
                    </td>
                  ))}
                  {!chiDoc ? (
                    <td className="px-3 py-1.5 align-top">
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => onDoi?.(dong.filter((_, j) => j !== i))}
                      >
                        Bỏ
                      </Button>
                    </td>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
