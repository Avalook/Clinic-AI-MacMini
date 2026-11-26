"use client";

// Các đơn vị bán thêm của một thuốc, sửa ngay trong form Sửa ở Danh mục (31/10/2026).
// Đơn vị gốc và giá gốc nằm ở ô phía trên, đây là phần thêm: đơn vị, "1 hộp có bao
// nhiêu viên?", giá riêng, và đơn vị MẶC ĐỊNH KHI KÊ (26/11, PR C — bác sĩ kê không
// ghi đơn vị thì hiểu theo đơn vị này). Máy chủ đọc số, chặn trùng / rác / tên có
// chữ số, chặn tắt bán đơn vị đang là mặc định, và LƯU RÕ giá gợi ý khi ô giá để
// trống (hệ số × giá gốc) — ở đây không tính tiền.
//
// "Tắt" chứ không xoá: hệ số còn cần cho lô cũ và dòng đơn đang chờ. Dòng chưa lưu thì
// bỏ hẳn được.

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import { INPUT, LABEL } from "../../form-ui";
import ODonVi from "../../ODonVi";
import DoiTenGoc from "./DoiTenGoc";

export interface DongDonVi {
  don_vi: string;
  he_so: string;
  gia: number | string | null;
  dang_ban: boolean;
  /** Đơn vị bác sĩ kê mặc định (tối đa một; không dòng nào = đơn vị gốc). */
  mac_dinh_ke?: boolean;
  /** Dấu phiên bản máy chủ trả; rỗng = dòng mới chưa lưu. */
  phien?: string | null;
}

export default function SuaDonViBan({
  donViGoc,
  dong,
  onDoi,
  suaGiaDuoc = true,
  idThuoc = null,
}: {
  donViGoc: string;
  dong: DongDonVi[];
  onDoi: (dong: DongDonVi[]) => void;
  suaGiaDuoc?: boolean;
  /** Thuốc đã lưu — mới cho đổi tên đơn vị gốc. */
  idThuoc?: string | null;
}) {
  const goc = donViGoc.trim();
  const sua = (i: number, doi: Partial<DongDonVi>) =>
    onDoi(dong.map((d, j) => (j === i ? { ...d, ...doi } : d)));
  // Chọn mặc định khi kê: đúng một dòng bật, -1 = đơn vị gốc. Gửi cờ ở MỌI dòng để
  // máy chủ biết form có nói về mặc định (không gửi = giữ nguyên).
  const datMacDinh = (i: number) => onDoi(dong.map((d, j) => ({ ...d, mac_dinh_ke: j === i })));
  const macDinh = dong.findIndex((d) => d.mac_dinh_ke);

  return (
    <section aria-label="Đơn vị bán thêm" className="space-y-2 rounded-control border border-line p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="text-body font-semibold text-ink">Đơn vị bán thêm</h4>
        <Button
          type="button"
          size="sm"
          variant="secondary"
          disabled={!goc}
          onClick={() =>
            onDoi([...dong, { don_vi: "", he_so: "", gia: "", dang_ban: true, mac_dinh_ke: false }])
          }
        >
          + Thêm đơn vị
        </Button>
      </div>
      {!goc ? (
        <p role="status" className="text-meta text-warning">
          Thuốc này chưa khai đơn vị — khai đơn vị gốc ở ô phía trên trước.
        </p>
      ) : dong.length === 0 ? (
        <p className="text-meta text-ink-muted">
          Chỉ bán theo {goc}. Khách đòi mua đơn vị khác (hộp, vỉ…) thì thêm ở đây.
        </p>
      ) : (
        <fieldset className="flex flex-wrap items-center gap-x-4 gap-y-1 text-body text-ink">
          <legend className={LABEL}>Bác sĩ kê không ghi đơn vị thì hiểu là</legend>
          <label className="flex min-h-10 items-center gap-2">
            <input
              type="radio"
              name="mac-dinh-ke"
              aria-label={`Mặc định khi kê: ${goc}`}
              checked={macDinh < 0}
              onChange={() => datMacDinh(-1)}
            />
            {goc} (đơn vị gốc)
          </label>
          {dong.map((d, i) => (
            <label key={`md-${d.phien ?? i}`} className="flex min-h-10 items-center gap-2">
              <input
                type="radio"
                name="mac-dinh-ke"
                aria-label={`Mặc định khi kê: ${d.don_vi.trim() || `dòng ${i + 1}`}`}
                checked={macDinh === i}
                disabled={!d.dang_ban || !d.don_vi.trim()}
                onChange={() => datMacDinh(i)}
              />
              {d.don_vi.trim() || `đơn vị dòng ${i + 1}`}
            </label>
          ))}
        </fieldset>
      )}
      <ul className="space-y-2">
        {dong.map((d, i) => {
          const daLuu = !!d.phien;
          const ten = d.don_vi.trim() || "đơn vị";
          return (
            <li
              key={d.phien ?? `moi-${i}`}
              aria-label={`Đơn vị ${ten}`}
              className={`grid grid-cols-1 items-end gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)_auto] ${
                d.dang_ban ? "" : "opacity-70"
              }`}
            >
              <div className="block min-w-0">
                <span className={LABEL}>Đơn vị (chỉ tên, không ghi số)</span>
                {daLuu ? (
                  <p className={`${INPUT} flex items-center bg-surface-muted`}>{d.don_vi}</p>
                ) : (
                  <ODonVi
                    value={d.don_vi}
                    onChange={(v) => sua(i, { don_vi: v })}
                    ariaLabel={`Tên đơn vị dòng ${i + 1}`}
                  />
                )}
              </div>
              <label className="block min-w-0">
                <span className={LABEL}>
                  1 {ten} có bao nhiêu {goc}?
                </span>
                <input
                  value={d.he_so}
                  inputMode="decimal"
                  placeholder="vd 30"
                  onChange={(e) => sua(i, { he_so: e.target.value })}
                  className={INPUT}
                />
              </label>
              <label className="block min-w-0">
                <span className={LABEL}>Giá 1 {ten} (đ)</span>
                <input
                  value={d.gia == null ? "" : String(d.gia)}
                  inputMode="numeric"
                  placeholder="Trống = hệ số × giá gốc"
                  disabled={!suaGiaDuoc}
                  onChange={(e) => sua(i, { gia: e.target.value })}
                  className={INPUT}
                />
              </label>
              <div className="flex min-h-10 items-center gap-2">
                {daLuu ? (
                  <>
                    {d.mac_dinh_ke ? <Chip tone="brand">Mặc định khi kê</Chip> : null}
                    {d.dang_ban ? null : (
                      <Chip tone="neutral">{d.gia == null ? "Chỉ để nhập" : "Đã tắt"}</Chip>
                    )}
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      onClick={() => sua(i, { dang_ban: !d.dang_ban })}
                    >
                      {d.dang_ban ? "Tắt bán" : "Mở bán"}
                    </Button>
                  </>
                ) : (
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    onClick={() => onDoi(dong.filter((_, j) => j !== i))}
                  >
                    Bỏ
                  </Button>
                )}
              </div>
            </li>
          );
        })}
      </ul>
      {idThuoc && suaGiaDuoc ? <DoiTenGoc idThuoc={idThuoc} goc={goc} /> : null}
    </section>
  );
}
