"use client";

// Báo cáo mức dùng theo phòng: kỳ và dữ liệu được chia sẻ với bảng tồn; máy chủ
// tính mức dùng từ số đếm thật, thiếu mốc thì nói "chưa đủ dữ liệu".

import Chip from "@/components/ui/Chip";
import ChipLoc from "@/components/ui/ChipLoc";
import type { GoiTieuHao } from "./bao-cao-vat-tu";
import { soVatTu, tienVatTu } from "./gui-vat-tu";

const gio = (iso: string | null) =>
  iso
    ? new Date(iso).toLocaleString("vi-VN", {
        timeZone: "Asia/Ho_Chi_Minh",
        day: "2-digit",
        month: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "—";

export default function TieuHaoVatTu({
  baoCao: goi,
  loi,
  dang,
  chiDu,
  setChiDu,
}: {
  baoCao: GoiTieuHao | null;
  loi: string | null;
  dang: boolean;
  chiDu: boolean;
  setChiDu: (chiDu: boolean) => void;
}) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <ChipLoc
          nhan="Lọc dòng"
          chon={chiDu ? "du" : "tat_ca"}
          onChon={(v) => setChiDu(v === "du")}
          muc={[
            { ma: "tat_ca", nhan: "Tất cả dòng" },
            { ma: "du", nhan: "Chỉ dòng đủ dữ liệu" },
          ]}
        />
      </div>
      {loi ? (
        <p role="alert" className="text-body text-danger">
          {loi}
        </p>
      ) : null}
      {dang && !goi ? (
        <p role="status" className="text-body text-ink-muted">
          Đang cập nhật số liệu…
        </p>
      ) : null}
      {goi && goi.theo_phong.length === 0 ? (
        <p className="rounded-card border border-line bg-surface px-4 py-6 text-center text-body text-ink-muted">
          Chưa có số liệu phòng. Ghi thao tác “Cấp cho phòng”, sau đó kiểm kê đầu và cuối kỳ để xem mức dùng.
        </p>
      ) : null}
      {goi?.theo_phong.map((p) => {
        const dong = goi.items.filter((d) => d.room_id === p.room_id && (!chiDu || d.du_du_lieu));
        if (dong.length === 0) return null;
        return (
          <section key={p.room_id} aria-label={p.phong} className="space-y-1">
            <h3 className="flex flex-wrap items-baseline gap-x-3 text-title text-ink">
              {p.phong}
              <span className="text-body font-normal tabular-nums text-ink-muted">
                {tienVatTu(p.gia_tri_da_dung)}
                {p.chua_du > 0 ? ` · ${p.chua_du} dòng chưa đủ dữ liệu` : ""}
              </span>
            </h3>
            <ul className="overflow-hidden rounded-card border border-line bg-surface shadow-card">
              {dong.map((d) => (
                <li
                  key={`${d.room_id}-${d.vat_tu_id}`}
                  className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-hairline px-3 py-2 last:border-b-0"
                >
                  <div className="min-w-0 flex-1 basis-56">
                    <p className="text-emph font-medium text-ink">
                      {d.ten}
                      {d.canh_bao ? (
                        <Chip tone="neutral" className="ml-2">
                          {d.canh_bao.charAt(0).toUpperCase() + d.canh_bao.slice(1)}
                        </Chip>
                      ) : null}
                    </p>
                    <p className="text-meta text-ink-muted">
                      {d.du_du_lieu
                        ? `Đầu ${soVatTu(d.dau)} · Nhận ${soVatTu(d.nhan)} · Trả ${soVatTu(d.tra)}${d.tra_nha_san_xuat ? ` (trả nhà sản xuất ${soVatTu(d.tra_nha_san_xuat)})` : ""} · Cuối ${soVatTu(d.cuoi)} (đếm ${gio(d.dem_dau_luc)} → ${gio(d.dem_cuoi_luc)}${d.dau_trong_ky ? "; chưa có lần đếm trước kỳ nên lấy lần đếm đầu tiên trong kỳ" : ""})`
                        : d.ly_do_thieu}
                    </p>
                  </div>
                  {d.du_du_lieu ? (
                    <div className="text-right">
                      <p className="text-emph font-semibold tabular-nums text-ink">
                        Hao hụt theo số đếm {soVatTu(d.tieu_hao)} {d.don_vi ?? ""}
                      </p>
                      <p className="text-meta tabular-nums text-ink-muted">
                        Đã bán cho khách {soVatTu(d.da_ban)} · Đã dùng (không bán) {soVatTu(d.dung_khong_ban)}
                        {d.trong_do_huy ? ` · Huỷ ${soVatTu(d.trong_do_huy)}` : ""}
                      </p>
                      <p className="text-meta tabular-nums text-ink-muted">{tienVatTu(d.gia_tri_da_dung)}</p>
                    </div>
                  ) : (
                    <Chip tone="neutral">Chưa đủ dữ liệu</Chip>
                  )}
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
