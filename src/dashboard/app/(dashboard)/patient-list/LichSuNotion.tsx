"use client";

// LỊCH SỬ KHÁM CŨ TỪ NOTION (Tuyền 05/10/2026) — chỉ đọc, trong hồ sơ khách.
//
// Phòng khám dùng Notion 04/2025 → 10/2026; lịch sử ấy được nhập vào schema
// `lich_su_notion` (không trộn vào lượt khám đang chạy luồng việc). Khối này đọc
// `GET /api/lich-su-notion?khach=` (danh sách lượt) và mở từng lượt bằng
// `?luot=` khi bấm. Ai thấy NỘI DUNG khám do máy chủ quyết (`co_noi_dung`).
//
// Chỉ có NGÀY khám — Notion không có giờ vào/ra. "Lần N" tính trên dữ liệu
// Notion; cùng ngày nhiều lượt thì in "cùng ngày, không rõ thứ tự".

import { useEffect, useState } from "react";
import { ChevronRight, ExternalLink, FileText, History } from "lucide-react";

import Chip from "@/components/ui/Chip";
import { fmtDate } from "../../../lib/datetime";

type Luot = {
  id: string;
  ma: string | null;
  ngay_kham: string;
  lan_thu: number | null;
  thu_tu_khong_chac: boolean;
  loai_kham_goc: string | null;
  loai_kham: string | null;
  bac_si_goc: string | null;
  bac_si: string | null;
  chan_doan: string | null;
  so_dich_vu: number;
  so_xet_nghiem: number;
  so_thuoc: number;
  so_bat_thuong: number;
};

type LichSu = {
  co_lich_su: boolean;
  co_noi_dung?: boolean;
  ghi_chu_co_dinh?: string;
  nguoi?: {
    ho_so_notion: string[];
    ghi_chu_lan_dau: string | null;
    link_drive: string | null;
    ghep_vao_ho_so_co_san: boolean;
  };
  luot?: Luot[];
  lich_hen?: {
    ma: string | null;
    ngay_hen: string | null;
    gio_hen: string | null;
    loai_kham_goc: string | null;
    bac_si_goc: string | null;
    tinh_trang_den: string | null;
    tinh_trang_cskh: string | null;
  }[];
};

type KetQua = {
  ma: string | null;
  tieu_de: string | null;
  mo_ta: string | null;
  ket_luan: string | null;
  bac_si_ky: string[] | null;
  da_co_noi_dung: boolean;
  link_drive_cu: string | null;
};

type ChiTiet = {
  ma: string | null;
  nguon_ngay: string;
  co_so_goc: string | null;
  kham_tu_van: string | null;
  chan_doan: string | null;
  ghi_chu_vinh_vien: string | null;
  notion_url: string | null;
  dich_vu: {
    id: string;
    ten_goc: string[] | null;
    ten_bang_gia: string | null;
    nguoi_lam: string[] | null;
    ket_qua: KetQua[];
  }[];
  ket_qua_khong_gan_dich_vu: KetQua[];
  xet_nghiem: {
    id: string;
    noi_lam: string[] | null;
    ket_qua: string | null;
    ket_qua_ai: string | null;
    tro_ly_ghi_chu: string | null;
    tep: { i: number; ten: string | null; co_tep: boolean }[];
  }[];
  thuoc: {
    ma: string | null;
    ten_thuoc: string[] | null;
    huong_dan: string | null;
    so_luong: string | null;
    luu_y: string | null;
  }[];
  bat_thuong: { loai: string; chi_tiet: string | null }[];
};

function nhanLan(l: Luot): string {
  if (l.lan_thu == null) return "Lần —";
  return l.thu_tu_khong_chac ? `Lần ${l.lan_thu} · cùng ngày, không rõ thứ tự` : `Lần ${l.lan_thu}`;
}

function KhoiChu({ nhan, chu }: { nhan: string; chu: string | null }) {
  if (!chu || !chu.trim()) return null;
  return (
    <div>
      <p className="text-label font-semibold uppercase tracking-wide text-ink-muted">{nhan}</p>
      <p className="mt-1 whitespace-pre-wrap break-words text-body text-ink">{chu}</p>
    </div>
  );
}

function DongKetQua({ k }: { k: KetQua }) {
  return (
    <div className="mt-2 rounded-control bg-surface px-3 py-2">
      <p className="text-meta font-medium text-ink">{k.tieu_de ?? k.ma ?? "Kết quả"}</p>
      {k.ket_luan ? (
        <p className="mt-1 whitespace-pre-wrap text-body text-ink">
          <span className="font-semibold">Kết luận: </span>
          {k.ket_luan}
        </p>
      ) : null}
      {k.mo_ta ? (
        <details className="mt-1">
          <summary className="cursor-pointer text-meta text-ink-muted">Mô tả</summary>
          <p className="mt-1 whitespace-pre-wrap text-body text-ink-soft">{k.mo_ta}</p>
        </details>
      ) : null}
      {k.bac_si_ky && k.bac_si_ky.length > 0 ? (
        <p className="mt-1 text-meta text-ink-muted">Ký: {k.bac_si_ky.join(" · ")}</p>
      ) : null}
      {!k.da_co_noi_dung ? (
        <p className="mt-1 text-meta text-ink-muted">Nội dung tờ kết quả đang được bổ sung.</p>
      ) : null}
      {k.link_drive_cu ? (
        <a
          href={k.link_drive_cu}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-1 inline-flex items-center gap-1 text-meta text-brand-700 hover:underline"
        >
          Ảnh/video trên Drive <ExternalLink size={12} />
        </a>
      ) : null}
    </div>
  );
}

function NoiDungLuot({ ct }: { ct: ChiTiet }) {
  return (
    <div className="space-y-3 px-3.5 pb-3.5 pt-1">
      <KhoiChu nhan="Chẩn đoán" chu={ct.chan_doan} />
      <KhoiChu nhan="Khám – Tư vấn" chu={ct.kham_tu_van} />
      <KhoiChu nhan="Ghi chú vĩnh viễn" chu={ct.ghi_chu_vinh_vien} />
      {ct.dich_vu.length > 0 ? (
        <div>
          <p className="text-label font-semibold uppercase tracking-wide text-ink-muted">Dịch vụ</p>
          <ul className="mt-1 space-y-2">
            {ct.dich_vu.map((d) => (
              <li key={d.id} className="rounded-control bg-surface-muted px-3 py-2">
                <p className="text-body font-medium text-ink">
                  {(d.ten_goc ?? []).join(", ") || "—"}
                </p>
                <p className="text-meta text-ink-muted">
                  {d.ten_bang_gia ? `Bảng giá: ${d.ten_bang_gia}` : "Chưa ghép bảng giá"}
                  {d.nguoi_lam && d.nguoi_lam.length > 0 ? ` · ${d.nguoi_lam.join(", ")}` : ""}
                </p>
                {d.ket_qua.map((k, i) => (
                  <DongKetQua key={`${d.id}-${i}`} k={k} />
                ))}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {ct.ket_qua_khong_gan_dich_vu.length > 0 ? (
        <div>
          <p className="text-label font-semibold uppercase tracking-wide text-ink-muted">
            Kết quả (không gắn dịch vụ)
          </p>
          {ct.ket_qua_khong_gan_dich_vu.map((k, i) => (
            <DongKetQua key={i} k={k} />
          ))}
        </div>
      ) : null}
      {ct.xet_nghiem.length > 0 ? (
        <div>
          <p className="text-label font-semibold uppercase tracking-wide text-ink-muted">Xét nghiệm</p>
          <ul className="mt-1 space-y-2">
            {ct.xet_nghiem.map((x) => (
              <li key={x.id} className="rounded-control bg-surface-muted px-3 py-2">
                <p className="text-body font-medium text-ink">{(x.noi_lam ?? []).join(", ") || "—"}</p>
                {x.ket_qua ? <p className="mt-1 whitespace-pre-wrap text-body text-ink">{x.ket_qua}</p> : null}
                {x.ket_qua_ai ? (
                  <p className="mt-1 whitespace-pre-wrap text-meta text-ink-soft">Tóm tắt: {x.ket_qua_ai}</p>
                ) : null}
                {x.tro_ly_ghi_chu ? (
                  <p className="mt-1 whitespace-pre-wrap text-meta text-ink-muted">Ghi chú: {x.tro_ly_ghi_chu}</p>
                ) : null}
                {x.tep.length > 0 ? (
                  <div className="mt-1 flex flex-wrap gap-2">
                    {x.tep.map((t) =>
                      t.co_tep ? (
                        <a
                          key={t.i}
                          href={`/api/lich-su-notion/tep?xn=${x.id}&i=${t.i}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-meta text-brand-700 hover:underline"
                        >
                          <FileText size={12} /> {t.ten ?? "Tệp kết quả"}
                        </a>
                      ) : (
                        <span key={t.i} className="text-meta text-ink-faint">
                          {t.ten ?? "Tệp"} (chưa có trên hệ thống)
                        </span>
                      ),
                    )}
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      {ct.thuoc.length > 0 ? (
        <div>
          <p className="text-label font-semibold uppercase tracking-wide text-ink-muted">Thuốc</p>
          <ul className="mt-1 divide-y divide-hairline">
            {ct.thuoc.map((t, i) => (
              <li key={t.ma ?? i} className="py-1.5 text-body">
                <span className="font-medium text-ink">{(t.ten_thuoc ?? []).join(", ") || "—"}</span>
                {t.so_luong ? <span className="text-ink-muted"> · SL {t.so_luong}</span> : null}
                {t.huong_dan ? <p className="text-meta text-ink-soft">{t.huong_dan}</p> : null}
                {t.luu_y ? <p className="text-meta text-ink-muted">Lưu ý: {t.luu_y}</p> : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <p className="text-meta text-ink-muted">
        Phiếu cũ số {ct.ma ?? "—"} · Ngày khám lấy theo: {ct.nguon_ngay}
        {ct.co_so_goc ? ` · Cơ sở ghi trong hồ sơ: ${ct.co_so_goc}` : ""}
      </p>
    </div>
  );
}

export default function LichSuNotion({ clinicPatientId }: { clinicPatientId: string }) {
  const [ls, setLs] = useState<LichSu | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [mo, setMo] = useState<Record<string, boolean>>({});
  const [chiTiet, setChiTiet] = useState<Record<string, ChiTiet | "dang" | "loi">>({});

  useEffect(() => {
    // Đổi khách = component mới (cha đặt `key` theo khách) → state tự sạch.
    let huy = false;
    fetch(`/api/lich-su-notion?khach=${encodeURIComponent(clinicPatientId)}`, { cache: "no-store" })
      .then(async (r) => {
        const j = await r.json().catch(() => null);
        if (huy) return;
        // Không có quyền xem danh sách bệnh nhân (vd CSKH) → khối tự ẩn, không báo lỗi.
        if (r.status === 403) setLs({ co_lich_su: false });
        else if (!r.ok) setLoi((j && (j.message || j.detail)) || "Không đọc được hồ sơ khám trước.");
        else setLs(j as LichSu);
      })
      .catch(() => !huy && setLoi("Không đọc được hồ sơ khám trước."));
    return () => {
      huy = true;
    };
  }, [clinicPatientId]);

  async function bam(id: string) {
    const moi = !mo[id];
    setMo((m) => ({ ...m, [id]: moi }));
    if (!moi || chiTiet[id]) return;
    setChiTiet((c) => ({ ...c, [id]: "dang" }));
    const r = await fetch(`/api/lich-su-notion?luot=${encodeURIComponent(id)}`, { cache: "no-store" }).catch(
      () => null,
    );
    const j = r ? await r.json().catch(() => null) : null;
    setChiTiet((c) => ({ ...c, [id]: r && r.ok && j ? (j as ChiTiet) : "loi" }));
  }

  if (loi) {
    return (
      <section className="border-t border-line px-5 py-4">
        <p className="text-meta text-danger">{loi}</p>
      </section>
    );
  }
  if (!ls || !ls.co_lich_su) return null;
  const luot = ls.luot ?? [];
  const hen = ls.lich_hen ?? [];

  return (
    // `w-0 min-w-full`: lấp đúng bề rộng khung chứa nhưng KHÔNG góp bề rộng tối
    // thiểu — bảng lịch hẹn / dòng chẩn đoán dài không kéo khung khách (lưới
    // không min-w-0 ở /customers) rộng quá màn 375.
    <section
      className="w-0 min-w-full border-t border-line px-5 py-4"
      aria-label="Hồ sơ khám trước 10/2026"
    >
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="flex items-center gap-1.5 text-sm font-semibold text-ink">
          <History size={15} className="text-brand-600" /> Hồ sơ khám trước 10/2026 ({luot.length})
        </h3>
        <Chip tone="info">Hồ sơ cũ</Chip>
        {(ls.nguoi?.ho_so_notion ?? []).map((m) => (
          <Chip key={m}>{m}</Chip>
        ))}
      </div>
      <p className="mt-1 text-meta text-ink-muted">{ls.ghi_chu_co_dinh}</p>
      {ls.nguoi?.ghi_chu_lan_dau ? (
        <p className="mt-1 rounded-control bg-warning-bg px-3 py-2 text-meta text-warning">
          {ls.nguoi.ghi_chu_lan_dau}
        </p>
      ) : null}
      {ls.nguoi?.link_drive ? (
        <a
          href={ls.nguoi.link_drive}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-1 inline-flex items-center gap-1 text-meta text-brand-700 hover:underline"
        >
          Thư mục ảnh/video trên Drive <ExternalLink size={12} />
        </a>
      ) : null}

      {luot.length > 0 ? (
        <ul className="mt-3 space-y-2">
          {luot.map((l) => {
            const dangMo = !!mo[l.id];
            const ct = chiTiet[l.id];
            return (
              <li key={l.id} className="rounded-control border border-line">
                <button
                  type="button"
                  aria-expanded={dangMo}
                  disabled={!ls.co_noi_dung}
                  onClick={() => bam(l.id)}
                  className="flex min-h-10 w-full min-w-0 flex-wrap items-center gap-x-2 gap-y-1 px-3.5 py-2 text-left disabled:cursor-default"
                >
                  {ls.co_noi_dung ? (
                    <ChevronRight
                      size={14}
                      className={`shrink-0 text-ink-muted transition-transform ${dangMo ? "rotate-90" : ""}`}
                    />
                  ) : null}
                  <span className="tabular-nums text-body font-semibold text-ink">{fmtDate(l.ngay_kham)}</span>
                  <Chip tone={l.thu_tu_khong_chac ? "warning" : "neutral"}>{nhanLan(l)}</Chip>
                  <Chip tone="brand">{l.loai_kham ?? l.loai_kham_goc ?? "Không ghi loại khám"}</Chip>
                  <span className="text-meta text-ink-soft">{l.bac_si ?? l.bac_si_goc ?? "—"}</span>
                  <span className="text-meta text-ink-muted">
                    {l.so_dich_vu} dịch vụ · {l.so_xet_nghiem} XN · {l.so_thuoc} thuốc
                  </span>
                  {l.chan_doan ? (
                    <span className="basis-full truncate text-meta text-ink-soft">{l.chan_doan}</span>
                  ) : null}
                </button>
                {dangMo ? (
                  ct === "dang" || ct === undefined ? (
                    <p className="px-3.5 pb-3 text-meta text-ink-muted">Đang tải…</p>
                  ) : ct === "loi" ? (
                    <p className="px-3.5 pb-3 text-meta text-danger">Không đọc được lượt này.</p>
                  ) : (
                    <NoiDungLuot ct={ct} />
                  )
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : null}
      {!ls.co_noi_dung && luot.length > 0 ? (
        <p className="mt-2 text-meta text-ink-muted">Bạn chỉ xem được danh sách lượt — nội dung khám cần quyền xem phiếu khám.</p>
      ) : null}

      {hen.length > 0 ? (
        <details className="mt-3">
          <summary className="cursor-pointer text-meta text-ink-muted">Lịch hẹn trước 10/2026 ({hen.length})</summary>
          <div className="mt-2 overflow-x-auto">
            <table className="w-full border-collapse text-body">
              <thead>
                <tr className="text-left text-label font-semibold uppercase tracking-wide text-ink-muted">
                  <th className="border-b border-hairline py-1.5 pr-2">Ngày hẹn</th>
                  <th className="border-b border-hairline py-1.5 pr-2">Loại khám</th>
                  <th className="border-b border-hairline py-1.5 pr-2">Bác sĩ</th>
                  <th className="border-b border-hairline py-1.5 pr-2">Đến</th>
                  <th className="border-b border-hairline py-1.5">CSKH</th>
                </tr>
              </thead>
              <tbody>
                {hen.map((h, i) => (
                  <tr key={h.ma ?? i}>
                    <td className="border-b border-hairline py-1.5 pr-2 tabular-nums">
                      {h.ngay_hen ? fmtDate(h.ngay_hen) : "—"}
                      {h.gio_hen ? ` ${h.gio_hen}` : ""}
                    </td>
                    <td className="border-b border-hairline py-1.5 pr-2">{h.loai_kham_goc ?? "—"}</td>
                    <td className="border-b border-hairline py-1.5 pr-2">{h.bac_si_goc ?? "—"}</td>
                    <td className="border-b border-hairline py-1.5 pr-2">{h.tinh_trang_den ?? "—"}</td>
                    <td className="border-b border-hairline py-1.5">{(h.tinh_trang_cskh ?? "—").replace(/\n/g, " · ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      ) : null}
    </section>
  );
}
