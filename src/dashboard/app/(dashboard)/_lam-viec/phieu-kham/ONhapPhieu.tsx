"use client";

// Vẽ MỘT nhóm ô của phiếu khám: ô lẻ và bảng, theo đúng khung máy chủ trả.
//
// Không biết phiếu nào đang vẽ. Nội tiết hay Hiếm muộn chỉ khác nhau ở DỮ LIỆU
// khung — thêm ô ở khung là màn tự có ô, không sửa tệp này.
//
// Giá trị luôn là MÃ: ô nhiều-chọn lưu `nt_endo_hist_2`, không lưu chữ "Tuyến
// giáp". Nhãn chỉ để in ra.
//
// BỐ CỤC Y HỆT BẢN GIAO DIỆN MẪU (27/09/2026, mục 6 — `veNhom`, `.nhom-tick`,
// `.luoi.o3`, `.tk`, `.in.so` ở M/app.js + M/style.css):
//   · nhóm có ô chọn → ô chọn dạng CHIP (tick = nhiều lựa chọn, radio = một) dồn
//     trái, các ô ghi kèm ("Chi tiết", "Dị ứng thuốc"…) ở cột phải, không nét dọc;
//   · nhóm không có ô chọn → lưới 3 cột ở màn rộng (mỗi cột ≤ 260px), đoạn văn
//     và bảng trải hết hàng;
//   · ô số rộng 96px + đơn vị (`components/ui/OSo`). Khung CHƯA có `don_vi` →
//     đơn vị tách từ nhãn ("Chu kỳ kinh nguyệt (ngày)") chỉ để hiển thị.
// `ma` ô và dữ liệu lưu KHÔNG đổi.

import ChipChon from "@/components/ui/ChipChon";
import OSo from "@/components/ui/OSo";
import { nhanVaDonVi } from "@/lib/o-so";
import {
  batTatLuaChon,
  type DonViVe,
  type GiaTriO,
  type NhomVe,
  type OPhieu,
} from "@/lib/phieu-kham";
import { INPUT, TBL_DIV, TBL_HEAD, TBL_WRAP } from "../../form-ui";

type Doi = (ma: string, v: GiaTriO) => void;

/** Nhãn ô — bản mẫu `.f > span`: 12px, chữ phụ. */
const NHAN = "mb-1 block text-meta text-ink-muted";

const laChon = (o: OPhieu) => o.kieu === "nhieu_chon" || o.kieu === "chon";

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
  const oLe = nhom.don_vi.flatMap((d) => (d.loai === "o" ? [d.o] : []));
  const oChon = oLe.filter(laChon);
  const kem = oLe.filter((o) => !laChon(o));
  const bang = nhom.don_vi.filter((d) => d.loai === "bang");
  // Nhãn ô chọn trùng tiêu đề nhóm ("3. Tiền sử nội tiết") thì chỉ để cho
  // trình đọc màn hình — đọc hai lần cùng một chữ là thừa.
  const anNhan = (o: OPhieu) => Boolean(nhom.tieu_de) && o.ten.trim() === nhom.tieu_de?.trim();

  return (
    <div className="border-t border-hairline pt-3 first:border-t-0 first:pt-0">
      {nhom.tieu_de ? (
        <h4 className="mb-2 text-emph font-semibold text-ink">{nhom.tieu_de}</h4>
      ) : null}
      {oChon.length > 0 ? (
        <div className="space-y-3">
          <div
            className={
              kem.length > 0
                ? "grid items-start gap-4 md:grid-cols-[fit-content(35rem)_minmax(17.5rem,1fr)] md:gap-x-8"
                : ""
            }
          >
            <div className="space-y-3">
              {oChon.map((o) => (
                <ONhap key={o.ma} o={o} gia={gia[o.ma]} onDoi={onDoi} chiDoc={chiDoc} anNhan={anNhan(o)} />
              ))}
            </div>
            {kem.length > 0 ? (
              <div className="flex min-w-0 flex-col gap-2">
                {kem.map((o) => (
                  <ONhap key={o.ma} o={o} gia={gia[o.ma]} onDoi={onDoi} chiDoc={chiDoc} />
                ))}
              </div>
            ) : null}
          </div>
          {bang.map((d) => (
            <BangO key={d.bang.ma} d={d} gia={gia} onDoi={onDoi} chiDoc={chiDoc} />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-[repeat(3,minmax(0,16.25rem))] lg:gap-x-6">
          {nhom.don_vi.map((d) =>
            d.loai === "o" ? (
              <div key={d.o.ma} className={d.o.kieu === "doan_van" ? "col-span-full" : "min-w-0"}>
                <ONhap o={d.o} gia={gia[d.o.ma]} onDoi={onDoi} chiDoc={chiDoc} />
              </div>
            ) : (
              <div key={d.bang.ma} className="col-span-full">
                <BangO d={d} gia={gia} onDoi={onDoi} chiDoc={chiDoc} />
              </div>
            ),
          )}
        </div>
      )}
    </div>
  );
}

/** Bảng rộng: cuộn ngang TRONG khung, thân trang không cuộn ngang (DESIGN.md
 *  §7). Chỉ kẻ ngang (§6.1). */
function BangO({
  d,
  gia,
  onDoi,
  chiDoc,
}: {
  d: Extract<DonViVe, { loai: "bang" }>;
  gia: Record<string, GiaTriO>;
  onDoi: Doi;
  chiDoc: boolean;
}) {
  return (
    <div className={`overflow-x-auto ${TBL_WRAP}`}>
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
                  {o && o.kieu === "so" ? (
                    <OSo
                      aria-label={o.ten}
                      rong="day"
                      value={chu(gia[o.ma])}
                      disabled={chiDoc}
                      onChange={(v) => onDoi(o.ma, v)}
                    />
                  ) : o ? (
                    <input
                      aria-label={o.ten}
                      type={o.kieu === "ngay" ? "date" : "text"}
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
  );
}

function chu(v: GiaTriO | undefined): string {
  return typeof v === "string" ? v : "";
}

export function ONhap({
  o,
  gia,
  onDoi,
  chiDoc,
  anNhan = false,
}: {
  o: OPhieu;
  gia: GiaTriO | undefined;
  onDoi: Doi;
  chiDoc: boolean;
  /** Nhãn chỉ cho trình đọc màn hình (đã có tiêu đề nhóm cùng chữ). */
  anNhan?: boolean;
}) {
  const tamNhan = o.ten_tu_dat ? (
    <span className="ml-1 font-normal text-ink-faint">(nhãn tạm)</span>
  ) : null;

  if (o.kieu === "nhieu_chon" || o.kieu === "chon") {
    const mot = o.kieu === "chon";
    const dsChon = Array.isArray(gia) ? gia : [];
    const motChon = chu(gia);
    return (
      <fieldset className="min-w-0">
        <legend className={anNhan ? "sr-only" : NHAN}>
          {o.ten}
          {tamNhan}
        </legend>
        <div className="flex flex-wrap gap-2">
          {(o.lua_chon ?? []).map((l) => (
            <ChipChon
              key={l.ma}
              kieu={mot ? "mot" : "tick"}
              ten={o.ma}
              chon={mot ? motChon === l.ma : dsChon.includes(l.ma)}
              disabled={chiDoc}
              onDoi={() =>
                onDoi(o.ma, mot ? l.ma : batTatLuaChon(dsChon, l.ma, o.lua_chon ?? []))
              }
              onBoChon={mot ? () => onDoi(o.ma, "") : undefined}
            >
              {l.ten}
            </ChipChon>
          ))}
        </div>
      </fieldset>
    );
  }

  if (o.kieu === "doan_van") {
    return (
      <label className="block">
        <span className={NHAN}>
          {o.ten}
          {tamNhan}
        </span>
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

  if (o.kieu === "so") {
    const { nhan, donVi } = nhanVaDonVi(o.ten, o.don_vi);
    return (
      <label className="block">
        <span className={NHAN}>
          {nhan}
          {tamNhan}
        </span>
        <OSo
          value={chu(gia)}
          donVi={donVi}
          disabled={chiDoc}
          placeholder={o.goi_y ?? ""}
          onChange={(v) => onDoi(o.ma, v)}
        />
      </label>
    );
  }

  return (
    <label className="block">
      <span className={NHAN}>
        {o.ten}
        {tamNhan}
      </span>
      <input
        type={o.kieu === "ngay" ? "date" : "text"}
        value={chu(gia)}
        disabled={chiDoc}
        placeholder={o.goi_y ?? ""}
        onChange={(e) => onDoi(o.ma, e.target.value)}
        className={INPUT}
      />
    </label>
  );
}
