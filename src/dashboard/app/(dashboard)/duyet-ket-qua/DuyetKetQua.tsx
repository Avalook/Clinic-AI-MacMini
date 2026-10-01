"use client";

// DUYỆT KẾT QUẢ — bác sĩ (Notion "Kế hoạch v1.0.0", vai Bác sĩ):
// *"Dưới kết quả xét nghiệm sẽ có nút Phê duyệt cho gửi và chỗ ghi Đánh giá của
// bác sĩ. Khi bác sĩ phê duyệt … tự động cập nhật trạng thái sang 'Đã có kết
// quả xét nghiệm' cho CSKH"*.
//
// Mỗi thẻ là MỘT CHỈ ĐỊNH đã có kết quả (đối tác gửi tệp, bác sĩ siêu âm ghi
// kết luận…). Tệp xem ngay trong thẻ, không tải về.

import { useCallback, useEffect, useState } from "react";

import ThongBaoHoanTac, { type ThongBao } from "@/components/ui/ThongBaoHoanTac";

import { docBang, guiThaoTac, gioVn } from "../_lam-viec/api";
import { lenhHoanTac } from "../_lam-viec/hoan-tac";
import KhungTep from "../_lam-viec/KhungTep";

interface KetQua {
  id: string;
  dich_vu: string;
  noi_dung: string | null;
  ket_qua_luc: string | null;
  clinic_patient_id: string;
  ten: string;
  ma_bn: string;
  bac_si: string | null;
  cua_toi: boolean;
  nguoi_lam: string | null;
  tep: { id: string; ten: string; da_cho_gui: boolean }[];
  duyet_lan_truoc: string | null;
}

export default function DuyetKetQua() {
  const [ds, setDs] = useState<KetQua[] | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [chiCuaToi, setChiCuaToi] = useState(true);
  const [lanNap, setLanNap] = useState(0);
  // Duyệt nhầm (01/10/2026): "Đã duyệt … · Hoàn tác" — thu hồi về chờ duyệt.
  const [thongBao, setThongBao] = useState<ThongBao | null>(null);

  useEffect(() => {
    let huy = false;
    void docBang<{ ket_qua: KetQua[] }>("ket-qua-cho-duyet").then((kq) => {
      if (huy) return;
      if (kq.ok) {
        setLoi(null);
        setDs(kq.data.ket_qua);
      } else setLoi(kq.loi);
    });
    return () => {
      huy = true;
    };
  }, [lanNap]);

  const napLai = useCallback(() => setLanNap((n) => n + 1), []);
  const daDuyet = useCallback(
    (k: KetQua) => {
      setThongBao({
        cau: `Đã duyệt ${k.dich_vu} — ${k.ten}`,
        goi: lenhHoanTac("thu-hoi-ket-qua", k.id),
      });
      napLai();
    },
    [napLai],
  );
  const dongThongBao = useCallback(() => setThongBao(null), []);
  const hien = (ds ?? []).filter((k) => !chiCuaToi || k.cua_toi);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <p className="text-sm text-ink-muted">
          {ds === null ? "Đang tải…" : `${hien.length} kết quả chờ duyệt`}
        </p>
        <label className="inline-flex items-center gap-2 text-sm text-ink">
          <input
            type="checkbox"
            checked={chiCuaToi}
            onChange={(e) => setChiCuaToi(e.target.checked)}
          />
          Chỉ khách của tôi
        </label>
        {loi ? (
          <p role="alert" className="text-sm text-danger">
            {loi}
          </p>
        ) : null}
      </div>
      {ds !== null && hien.length === 0 ? (
        <p className="rounded-card border border-line bg-surface p-6 text-center text-sm text-ink-muted">
          Không có kết quả nào đang chờ duyệt.
        </p>
      ) : null}
      {hien.map((k) => (
        <TheKetQua key={k.id} k={k} onXong={() => daDuyet(k)} />
      ))}
      <ThongBaoHoanTac thongBao={thongBao} onDong={dongThongBao} onHoanTacXong={napLai} />
    </div>
  );
}

function TheKetQua({ k, onXong }: { k: KetQua; onXong: () => void }) {
  const [danhGia, setDanhGia] = useState("");
  const [dangGui, setDangGui] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);

  const duyet = async () => {
    setDangGui(true);
    setLoi(null);
    const kq = await guiThaoTac("duyet-ket-qua", k.id, { danh_gia: danhGia });
    setDangGui(false);
    if (!kq.ok) setLoi(kq.loi);
    else onXong();
  };

  return (
    <article className="space-y-3 rounded-card bg-surface p-4 shadow-card">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <div className="min-w-0">
          <h2 className="text-base font-semibold text-ink">{k.dich_vu}</h2>
          <p className="text-sm text-ink-muted">
            {k.ten} · {k.ma_bn}
            {k.bac_si ? ` · BS ${k.bac_si}` : ""}
          </p>
        </div>
        <p className="text-label text-ink-muted">
          Có kết quả lúc {gioVn(k.ket_qua_luc)}
          {k.nguoi_lam ? ` · ${k.nguoi_lam}` : ""}
        </p>
      </header>
      {k.duyet_lan_truoc ? (
        <p role="status" className="rounded-control bg-warning-bg px-3 py-2 text-sm text-ink">
          Đã duyệt lúc {gioVn(k.duyet_lan_truoc)}, nay có tệp mới chưa được cho gửi:{" "}
          <span className="font-medium">
            {k.tep
              .filter((t) => !t.da_cho_gui)
              .map((t) => t.ten)
              .join(", ")}
          </span>
          . Bản mới không thừa hưởng lần duyệt cũ — xem rồi duyệt lại.
        </p>
      ) : null}
      {k.noi_dung ? (
        <p className="whitespace-pre-line rounded-control bg-surface-muted px-3 py-2 text-sm text-ink">
          {k.noi_dung}
        </p>
      ) : null}
      {k.tep.length > 0 ? (
        <KhungTep
          clinicPatientId={k.clinic_patient_id}
          serviceOrderId={k.id}
          choTaiLen={false}
          tieuDe="Tệp kết quả"
        />
      ) : null}
      <label className="block">
        <span className="text-sm font-semibold text-ink">Đánh giá của bác sĩ</span>
        <textarea
          value={danhGia}
          onChange={(e) => setDanhGia(e.target.value)}
          rows={3}
          className="mt-1 w-full rounded-control border border-line bg-surface px-3 py-2 text-sm text-ink"
          placeholder="Nhận định, hướng xử trí, lời dặn gửi kèm kết quả…"
        />
      </label>
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          disabled={dangGui}
          onClick={() => void duyet()}
          className="inline-flex min-h-11 items-center rounded-control bg-brand-600 px-5 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
        >
          {dangGui ? "Đang ghi…" : "Phê duyệt cho gửi"}
        </button>
        {loi ? (
          <p role="alert" className="text-sm text-danger">
            {loi}
          </p>
        ) : null}
      </div>
    </article>
  );
}
