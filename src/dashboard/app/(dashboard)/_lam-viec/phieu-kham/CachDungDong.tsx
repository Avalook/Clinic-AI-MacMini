"use client";

// Cách dùng có cấu trúc của MỘT dòng đơn (PR E, kế hoạch đơn vị mẹ/con mục 2, 6, 10).
// Bác sĩ chọn kiểu (mỗi ngày / mỗi tuần / cách ngày / chu kỳ kinh / chỉ ghi chữ), mỗi
// lần, số lần; danh mục ghi KHOẢNG thì phải chọn một số. Câu in trên đơn, số ngày,
// ngày hết, gợi ý số lượng đều do MÁY CHỦ tính (`useTinhCachDung`) — ở đây chỉ vẽ.

import Button from "@/components/ui/Button";
import OChon from "@/components/ui/OChon";
import ONhap from "@/components/ui/ONhap";
import {
  NHAN_KIEU,
  dongKetQua,
  so,
  soTrongKhoang,
  type CachDungCT,
  type KetQuaCachDung,
  type KieuDung,
} from "@/lib/cach-dung";

const NHAN = "block text-meta text-ink-muted";

function soHoacRong(v: string): number | null {
  return v.trim() === "" ? null : so(v);
}

export default function CachDungDong({
  ct,
  kq,
  donVi,
  soLuong,
  chiDoc,
  onCt,
  onSoLuong,
}: {
  ct: CachDungCT | null;
  kq: KetQuaCachDung | null;
  donVi: string;
  soLuong: string;
  chiDoc: boolean;
  onCt: (ct: CachDungCT | null) => void;
  onSoLuong: (sl: string) => void;
}) {
  const kieu: KieuDung = ct?.kieu ?? "chu";
  const doi = (p: Partial<CachDungCT>) => onCt({ ...(ct ?? { kieu: "ngay" }), ...p });
  const chonKieu = (k: KieuDung) => {
    if (k === "chu") return onCt(ct ? { ...ct, kieu: "chu" } : null);
    doi({ kieu: k });
  };
  const lieu = ct?.don_vi_lieu || "viên";
  const goiY = kq?.goi_y_so_luong;
  const tone = !kq ? "text-ink-faint" : kq.tinh_duoc ? "text-success" : "text-ink-muted";

  return (
    <div className="space-y-2 sm:col-span-12">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-6">
        <label className={`${NHAN} col-span-2 sm:col-span-2`}>
          Kiểu dùng
          <OChon
            className="w-full"
            value={kieu}
            disabled={chiDoc}
            onChange={(e) => chonKieu(e.target.value as KieuDung)}
          >
            {NHAN_KIEU.map(([v, t]) => (
              <option key={v} value={v}>
                {t}
              </option>
            ))}
          </OChon>
        </label>
        {ct && kieu !== "chu" ? (
          <>
            <label className={NHAN}>
              Mỗi lần ({lieu})
              {ct.khoang_lan ? (
                <OChon
                  className="w-full"
                  value={ct.moi_lan == null ? "" : String(so(ct.moi_lan))}
                  disabled={chiDoc}
                  onChange={(e) => doi({ moi_lan: soHoacRong(e.target.value) })}
                >
                  <option value="">chọn</option>
                  {soTrongKhoang(ct.khoang_lan).map((x) => (
                    <option key={x} value={x}>
                      {String(x).replace(".", ",")}
                    </option>
                  ))}
                </OChon>
              ) : (
                <ONhap
                  className="w-full"
                  type="number"
                  min={0.5}
                  step={0.5}
                  value={ct.moi_lan == null ? "" : String(so(ct.moi_lan))}
                  disabled={chiDoc}
                  onChange={(e) => doi({ moi_lan: soHoacRong(e.target.value) })}
                />
              )}
            </label>
            {kieu !== "cach_ngay" ? (
              <label className={NHAN}>
                Số lần/{kieu === "tuan" ? "tuần" : "ngày"}
                {ct.khoang_so_lan ? (
                  <OChon
                    className="w-full"
                    value={ct.so_lan == null ? "" : String(ct.so_lan)}
                    disabled={chiDoc}
                    onChange={(e) => doi({ so_lan: soHoacRong(e.target.value) })}
                  >
                    <option value="">chọn</option>
                    {soTrongKhoang(ct.khoang_so_lan).map((x) => (
                      <option key={x} value={x}>
                        {x}
                      </option>
                    ))}
                  </OChon>
                ) : (
                  <ONhap
                    className="w-full"
                    type="number"
                    min={1}
                    step={1}
                    value={ct.so_lan == null ? "" : String(ct.so_lan)}
                    disabled={chiDoc}
                    onChange={(e) => doi({ so_lan: soHoacRong(e.target.value) })}
                  />
                )}
              </label>
            ) : null}
            {kieu === "chu_ky" ? (
              <label className={`${NHAN} col-span-2`}>
                Từ ngày → đến ngày chu kỳ
                <span className="flex items-center gap-1">
                  <ONhap
                    className="w-16"
                    type="number"
                    min={1}
                    aria-label="Từ ngày chu kỳ"
                    value={ct.tu_ngay ?? ""}
                    disabled={chiDoc}
                    onChange={(e) => doi({ tu_ngay: soHoacRong(e.target.value) })}
                  />
                  →
                  <ONhap
                    className="w-16"
                    type="number"
                    min={1}
                    aria-label="Đến ngày chu kỳ"
                    value={ct.den_ngay ?? ""}
                    disabled={chiDoc}
                    onChange={(e) => doi({ den_ngay: soHoacRong(e.target.value) })}
                  />
                </span>
              </label>
            ) : (
              <label className={NHAN}>
                Dùng trong (ngày)
                <ONhap
                  className="w-full"
                  type="number"
                  min={1}
                  value={ct.trong_ngay ?? ""}
                  disabled={chiDoc}
                  onChange={(e) => doi({ trong_ngay: soHoacRong(e.target.value) })}
                />
              </label>
            )}
            <label className={`${NHAN} col-span-2 sm:col-span-6`}>
              Thời điểm / ghi thêm (in sau câu)
              <ONhap
                className="w-full"
                value={ct.thoi_diem ?? ""}
                placeholder="vd: sau ăn sáng"
                disabled={chiDoc}
                onChange={(e) => doi({ thoi_diem: e.target.value })}
              />
            </label>
          </>
        ) : null}
      </div>
      {ct && kieu !== "chu" ? (
        <p className="text-body text-ink">
          <span className="text-meta text-ink-muted">Câu in trên đơn: </span>
          {kq?.cau ?? "…"}
        </p>
      ) : null}
      {kq && (kieu !== "chu" || kq.tinh_duoc) ? (
        <div className="flex flex-wrap items-center gap-2">
          <p className={`text-meta ${tone}`} role="status">
            {dongKetQua(kq)}
          </p>
          {!chiDoc && goiY && String(goiY) !== soLuong.trim() ? (
            <Button type="button" size="sm" variant="secondary" onClick={() => onSoLuong(String(goiY))}>
              Gợi ý SL: {goiY} {donVi}
            </Button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

/** Kinh lần cuối + chu kỳ cho thuốc theo chu kỳ kinh — để trống = lấy từ phiếu khám. */
export function KinhCuoiCung({
  kinh,
  tuPhieu,
  onDoi,
}: {
  kinh: { kinh_lan_cuoi: string; chu_ky: string };
  tuPhieu: { kinh_lan_cuoi: string | null; chu_ky: string | null } | null;
  onDoi: (k: { kinh_lan_cuoi: string; chu_ky: string }) => void;
}) {
  return (
    <div className="grid grid-cols-2 gap-2 rounded-card border border-hairline p-3 sm:grid-cols-4">
      <p className="col-span-2 text-meta text-ink-muted sm:col-span-4">
        Thuốc theo chu kỳ kinh: ngày lịch chỉ là ƯỚC TÍNH từ kinh lần cuối + chu kỳ (để trống =
        lấy từ phiếu khám; không có thì không ước tính).
      </p>
      <label className={NHAN}>
        Kinh lần cuối
        <ONhap
          className="w-full"
          placeholder={tuPhieu?.kinh_lan_cuoi || "dd/mm/yyyy"}
          value={kinh.kinh_lan_cuoi}
          onChange={(e) => onDoi({ ...kinh, kinh_lan_cuoi: e.target.value })}
        />
      </label>
      <label className={NHAN}>
        Chu kỳ (ngày)
        <ONhap
          className="w-full"
          inputMode="numeric"
          placeholder={tuPhieu?.chu_ky || "28"}
          value={kinh.chu_ky}
          onChange={(e) => onDoi({ ...kinh, chu_ky: e.target.value })}
        />
      </label>
    </div>
  );
}
