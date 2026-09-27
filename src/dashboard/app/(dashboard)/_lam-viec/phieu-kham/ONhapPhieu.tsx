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
//
// ĐỢT 3 (27/09/2026, khung v2 — góp ý phòng khám): khung khai cách hiện, tệp
// này KHÔNG so tên nhóm:
//   · ô `thu_gon` → một hàng chip "+ tên ô"; bấm chip thì ô hiện + nhận con trỏ;
//   · ô `hien_khi` → chỉ hiện khi ô chọn kia đang chọn đúng mã;
//   · ô đã có giá trị LUÔN hiện (lib/phieu-kham.ts::oDangHien);
//   · nhóm `gap` → ngăn gập "Bảng kết quả theo phiếu gốc…", mặc định đóng, tự mở
//     khi có ô điền.

import { Plus } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import ChipChon from "@/components/ui/ChipChon";
import NganGap from "@/components/ui/NganGap";
import OSo from "@/components/ui/OSo";
import { vnYmd } from "@/lib/datetime";
import { nhanVaDonVi } from "@/lib/o-so";
import {
  batTatLuaChon,
  HEN_NHANH,
  laONgayTaiKham,
  ngayHenTaiKham,
  oCuaNhom,
  oDangHien,
  oThuGonDangAn,
  soODaDien,
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

/** Tiêu đề ngăn gập của bảng kết quả gõ tay (bản mẫu M/app.js ~:423). */
const TIEU_DE_GAP = "Bảng kết quả theo phiếu gốc — nhập tay kết quả làm ngoài";

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
  // Ô `thu_gon` người dùng đã bấm chip để mở — TRẠNG THÁI MÀN, không lưu. Tải
  // lại phiếu: ô đã có chữ vẫn hiện (oDangHien), ô trống lại về chip.
  const [daMo, setDaMo] = useState<ReadonlySet<string>>(() => new Set());
  const vung = useRef<HTMLDivElement>(null);
  const choFocus = useRef<string | null>(null);
  useEffect(() => {
    const ma = choFocus.current;
    if (!ma) return;
    choFocus.current = null;
    vung.current
      ?.querySelector<HTMLElement>(`[data-o="${ma}"] input, [data-o="${ma}"] textarea`)
      ?.focus();
  });
  const moO = (ma: string) => {
    choFocus.current = ma;
    setDaMo((cu) => new Set(cu).add(ma));
  };

  const hien = (o: OPhieu) => oDangHien(o, gia, daMo);
  const donVi = nhom.don_vi.filter((d) => d.loai !== "o" || hien(d.o));
  const chipAn = chiDoc ? [] : oThuGonDangAn(nhom, gia, daMo);
  const oLe = donVi.flatMap((d) => (d.loai === "o" ? [d.o] : []));
  const oChon = oLe.filter(laChon);
  const kem = oLe.filter((o) => !laChon(o));
  const bang = donVi.filter((d) => d.loai === "bang");
  // Nhãn ô chọn trùng tiêu đề nhóm ("3. Tiền sử nội tiết") thì chỉ để cho
  // trình đọc màn hình — đọc hai lần cùng một chữ là thừa.
  const anNhan = (o: OPhieu) => Boolean(nhom.tieu_de) && o.ten.trim() === nhom.tieu_de?.trim();
  const oBoc = (o: OPhieu, lop = "min-w-0") => (
    <div key={o.ma} data-o={o.ma} className={lop}>
      <ONhap o={o} gia={gia[o.ma]} onDoi={onDoi} chiDoc={chiDoc} anNhan={anNhan(o)} />
    </div>
  );

  const chipThuGon =
    chipAn.length > 0 ? (
      <div className="flex flex-wrap gap-2" role="group" aria-label={`Thêm ô ${nhom.tieu_de ?? ""}`.trim()}>
        {chipAn.map((o) => (
          <Button
            key={o.ma}
            type="button"
            size="sm"
            variant="secondary"
            className="max-sm:h-10"
            onClick={() => moO(o.ma)}
          >
            <Plus aria-hidden className="size-3.5" />
            {o.ten}
          </Button>
        ))}
      </div>
    ) : null;

  const than =
    oChon.length > 0 ? (
      <div className="space-y-3">
        {chipThuGon}
        <div
          className={
            kem.length > 0
              ? "grid items-start gap-4 md:grid-cols-[fit-content(35rem)_minmax(17.5rem,1fr)] md:gap-x-8"
              : ""
          }
        >
          <div className="space-y-3">{oChon.map((o) => oBoc(o))}</div>
          {kem.length > 0 ? (
            <div className="flex min-w-0 flex-col gap-2">{kem.map((o) => oBoc(o))}</div>
          ) : null}
        </div>
        {bang.map((d) => (
          <BangO key={d.bang.ma} d={d} gia={gia} onDoi={onDoi} chiDoc={chiDoc} />
        ))}
      </div>
    ) : (
      <div className="space-y-3">
        {chipThuGon}
        {donVi.length > 0 ? (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-[repeat(3,minmax(0,16.25rem))] lg:gap-x-6">
            {donVi.map((d) =>
              d.loai === "o" ? (
                oBoc(d.o, d.o.kieu === "doan_van" ? "col-span-full" : "min-w-0")
              ) : (
                <div key={d.bang.ma} className="col-span-full">
                  <BangO d={d} gia={gia} onDoi={onDoi} chiDoc={chiDoc} />
                </div>
              ),
            )}
          </div>
        ) : null}
      </div>
    );

  // Chỉ đọc mà cả nhóm không còn ô nào hiện (ô thu gọn chưa ai điền) → bỏ nhóm.
  if (donVi.length === 0 && !chipThuGon) return null;

  const soDien = nhom.gap ? soODaDien(oCuaNhom(nhom), gia) : 0;
  return (
    <div ref={vung} className="border-t border-hairline pt-3 first:border-t-0 first:pt-0">
      {nhom.tieu_de ? (
        <h4 className="mb-2 text-emph font-semibold text-ink">{nhom.tieu_de}</h4>
      ) : null}
      {nhom.gap ? (
        <NganGap
          tieuDe={TIEU_DE_GAP}
          chip={soDien > 0 ? <Chip tone="neutral">{soDien} ô đã điền</Chip> : null}
          moSan={soDien > 0}
        >
          {than}
        </NganGap>
      ) : (
        than
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

  const oNhap = (
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
