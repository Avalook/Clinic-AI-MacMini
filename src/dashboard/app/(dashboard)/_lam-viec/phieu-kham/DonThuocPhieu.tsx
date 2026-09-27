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
import { INPUT } from "../../form-ui";
import {
  dongTuMau,
  locMauThuoc,
  type DongThuoc,
  type MauThuoc,
} from "@/lib/phieu-kham";

// CÁCH DÙNG CẦN CHỖ (Tuyền 27/09/2026: "cho thêm không gian cho cách dùng
// thuốc"). Bảng sáu cột chia đều cắt "Uống 1 viên sau ăn sáng, 1 viên sau ăn
// tối, trong 7 ngày" còn vài chữ — và cột trái phiếu khám chỉ rộng ~600–780px
// nên bảng MỘT hàng không bao giờ đủ chỗ. Mỗi thuốc nay HAI hàng: trên là thuốc
// · đường dùng · số lượng · đơn vị; dưới là Cách dùng (⅔) + Lưu ý (⅓), ô nhiều
// dòng tự giãn theo chữ. Điện thoại: mọi ô xếp dọc.
const COT: { ma: keyof DongThuoc; ten: string; o: string; dai?: boolean }[] = [
  { ma: "ten_thuoc", ten: "Thuốc", o: "sm:col-span-6" },
  { ma: "duong_dung", ten: "Đường dùng", o: "sm:col-span-2" },
  { ma: "so_luong", ten: "Số lượng", o: "sm:col-span-2" },
  { ma: "don_vi", ten: "Đơn vị", o: "sm:col-span-2" },
  { ma: "cach_dung", ten: "Cách dùng", o: "sm:col-span-8", dai: true },
  { ma: "luu_y", ten: "Lưu ý", o: "sm:col-span-4", dai: true },
];

/** Ô nhiều dòng tự giãn theo chữ (CSS field-sizing) — tối thiểu 2 dòng. */
const O_DAI = `${INPUT} min-h-16 resize-y [field-sizing:content] sm:min-h-16`;

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
      {dong.length > 0 ? (
        <ol className="space-y-2">
          {dong.map((d, i) => (
            <li
              key={`${d.mau_ma ?? "tu-do"}-${i}`}
              className="rounded-card border border-hairline bg-surface p-3"
            >
              <div className="mb-2 flex items-center gap-2">
                <span className="grid size-6 shrink-0 place-items-center rounded-full bg-brand-50 text-meta font-semibold text-brand-700">
                  {i + 1}
                </span>
                {!d.drug_catalog_id ? <Chip tone="warning">Chưa gắn thuốc kho</Chip> : null}
                {!chiDoc ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    className="ml-auto"
                    onClick={() => onDoi?.(dong.filter((_, j) => j !== i))}
                  >
                    Bỏ thuốc này
                  </Button>
                ) : null}
              </div>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-12">
                {COT.map((c) => (
                  <label key={c.ma} className={`block text-meta text-ink-muted ${c.o}`}>
                    {c.ten}
                    {c.dai ? (
                      <textarea
                        rows={2}
                        value={String(d[c.ma] ?? "")}
                        disabled={chiDoc}
                        onChange={(e) => sua(i, c.ma, e.target.value)}
                        className={O_DAI}
                      />
                    ) : (
                      <input
                        value={String(d[c.ma] ?? "")}
                        disabled={chiDoc}
                        onChange={(e) => sua(i, c.ma, e.target.value)}
                        className={INPUT}
                      />
                    )}
                  </label>
                ))}
              </div>
            </li>
          ))}
        </ol>
      ) : null}
    </div>
  );
}
