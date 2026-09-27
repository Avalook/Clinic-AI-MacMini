"use client";

// Vẽ MỘT nhóm ô của phiếu khám: ô lẻ và bảng, theo đúng khung máy chủ trả.
//
// Không biết phiếu nào đang vẽ. Nội tiết hay Hiếm muộn chỉ khác nhau ở DỮ LIỆU
// khung — thêm ô ở khung là màn tự có ô, không sửa tệp này.
//
// Giá trị luôn là MÃ: ô nhiều-chọn lưu `nt_endo_hist_2`, không lưu chữ "Tuyến
// giáp". Nhãn chỉ để in ra.

import Button from "@/components/ui/Button";
import { vnYmd } from "@/lib/datetime";
import { INPUT, LABEL, TBL_DIV, TBL_HEAD, TBL_WRAP } from "../../form-ui";
import {
  batTatLuaChon,
  HEN_NHANH,
  laONgayTaiKham,
  ngayHenTaiKham,
  type GiaTriO,
  type NhomVe,
  type OPhieu,
} from "@/lib/phieu-kham";

type Doi = (ma: string, v: GiaTriO) => void;

export function NhomOPhieu({
  nhom,
  gia,
  onDoi,
  chiDoc,
}: {
  nhom: NhomVe;
  gia: Record<string, GiaTriO>;
  onDoi: Doi;
  chiDoc: boolean;
}) {
  return (
    <div className="space-y-3">
      {nhom.tieu_de ? (
        <h4 className="text-body font-semibold text-ink">{nhom.tieu_de}</h4>
      ) : null}
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        {nhom.don_vi.map((d) =>
          d.loai === "o" ? (
            <div
              key={d.o.ma}
              className={
                d.o.kieu === "doan_van" || d.o.kieu === "nhieu_chon"
                  ? "md:col-span-2"
                  : ""
              }
            >
              <ONhap o={d.o} gia={gia[d.o.ma]} onDoi={onDoi} chiDoc={chiDoc} />
            </div>
          ) : (
            // Bảng rộng: cuộn ngang TRONG khung, thân trang không cuộn ngang
            // (DESIGN.md §7). Chỉ kẻ ngang (§6.1).
            <div key={d.bang.ma} className={`md:col-span-2 overflow-x-auto ${TBL_WRAP}`}>
              <table className="w-full text-body">
                <thead className={TBL_HEAD}>
                  <tr>
                    <th scope="col" className="px-3 py-2 text-left">
                      {d.bang.ten}
                    </th>
                    {d.bang.cot.map((c) => (
                      <th key={c} scope="col" className="px-3 py-2 text-left">
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className={TBL_DIV}>
                  {d.hang.map((h) => (
                    <tr key={h.hang}>
                      <th scope="row" className="px-3 py-2 text-left font-normal text-ink">
                        {h.hang}
                      </th>
                      {h.o.map((o, i) => (
                        <td key={o?.ma ?? i} className="px-3 py-1.5">
                          {o ? (
                            <input
                              aria-label={o.ten}
                              type={kieuInput(o)}
                              value={chu(gia[o.ma])}
                              disabled={chiDoc}
                              onChange={(e) => onDoi(o.ma, e.target.value)}
                              className={INPUT}
                            />
                          ) : null}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ),
        )}
      </div>
    </div>
  );
}

function kieuInput(o: OPhieu): string {
  return o.kieu === "so" ? "number" : o.kieu === "ngay" ? "date" : "text";
}

function chu(v: GiaTriO | undefined): string {
  return typeof v === "string" ? v : "";
}

export function ONhap({
  o,
  gia,
  onDoi,
  chiDoc,
}: {
  o: OPhieu;
  gia: GiaTriO | undefined;
  onDoi: Doi;
  chiDoc: boolean;
}) {
  const nhan = (
    <span className={LABEL}>
      {o.ten}
      {o.ten_tu_dat ? (
        <span className="ml-1 font-normal text-ink-faint">(nhãn tạm)</span>
      ) : null}
    </span>
  );

  if (o.kieu === "nhieu_chon") {
    const dang = Array.isArray(gia) ? gia : [];
    return (
      <fieldset>
        <legend className={LABEL}>{o.ten}</legend>
        <div className="grid grid-cols-1 gap-x-4 gap-y-2 sm:grid-cols-2 lg:grid-cols-3">
          {(o.lua_chon ?? []).map((l) => (
            <label key={l.ma} className="flex min-h-10 items-center gap-2 text-body text-ink">
              <input
                type="checkbox"
                checked={dang.includes(l.ma)}
                disabled={chiDoc}
                onChange={() => onDoi(o.ma, batTatLuaChon(dang, l.ma, o.lua_chon ?? []))}
                className="size-4 accent-brand-600"
              />
              {l.ten}
            </label>
          ))}
        </div>
      </fieldset>
    );
  }

  if (o.kieu === "chon") {
    return (
      <label className="block">
        {nhan}
        <select
          value={chu(gia)}
          disabled={chiDoc}
          onChange={(e) => onDoi(o.ma, e.target.value)}
          className={INPUT}
        >
          <option value="">— chưa chọn —</option>
          {(o.lua_chon ?? []).map((l) => (
            <option key={l.ma} value={l.ma}>
              {l.ten}
            </option>
          ))}
        </select>
      </label>
    );
  }

  if (o.kieu === "doan_van") {
    return (
      <label className="block">
        {nhan}
        <textarea
          value={chu(gia)}
          rows={3}
          disabled={chiDoc}
          placeholder={o.goi_y ?? ""}
          onChange={(e) => onDoi(o.ma, e.target.value)}
          className={INPUT}
        />
      </label>
    );
  }

  const oNhap = (
    <label className="block">
      {nhan}
      <input
        type={kieuInput(o)}
        value={chu(gia)}
        disabled={chiDoc}
        placeholder={o.goi_y ?? ""}
        onChange={(e) => onDoi(o.ma, e.target.value)}
        className={INPUT}
      />
    </label>
  );
  if (o.kieu !== "ngay" || !laONgayTaiKham(o.ma) || chiDoc) return oNhap;

  // Mục G "Ngày tái khám": chip chọn nhanh (bản giao diện mẫu 27/09/2026). Ngày
  // tính ở hàm thuần theo HÔM NAY giờ VN — không theo đồng hồ múi giờ máy.
  const homNay = vnYmd();
  return (
    <div className="space-y-2">
      {oNhap}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-meta text-ink-muted">Chọn nhanh</span>
        {HEN_NHANH.map((h) => {
          const ngay = ngayHenTaiKham(homNay, h);
          return (
            <Button
              key={h.nhan}
              type="button"
              size="sm"
              variant={ngay && ngay === chu(gia) ? "soft" : "secondary"}
              aria-pressed={ngay !== "" && ngay === chu(gia)}
              disabled={!ngay}
              onClick={() => onDoi(o.ma, ngay)}
            >
              {h.nhan}
            </Button>
          );
        })}
      </div>
    </div>
  );
}
