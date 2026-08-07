"use client";

// Các lượt khám TRƯỚC của bệnh nhân đang mở.
//
// "Lần 1 ngày…, lần 2 ngày…" — rê chuột vào một ngày thì hiện tóm tắt ngay
// bên cạnh; bấm vào thì phiếu bên dưới quay về đúng hôm đó, kèm một nút để
// quay lại khám tiếp.
//
// RANH GIỚI QUAN TRỌNG NHẤT: phiếu cũ mở ở chế độ CHỈ XEM.
// Không có ranh giới đó thì bác sĩ gõ vào một phiếu tưởng là hôm nay và ghi
// đè lên bệnh án tháng trước — mà bệnh án đã ký thì luật cấm sửa. Nên khi
// đang xem lại, cả màn đổi màu và nút "Lưu phiếu" biến mất.
//
// Chưa khám lần nào thì component này không hiện gì.

import { useEffect, useState } from "react";
import { History, RotateCcw } from "lucide-react";

export interface LuotTruoc {
  visit_id: string;
  service_code: string;
  ten_dich_vu: string | null;
  bac_si: string | null;
  kham_luc: string | null;
  visit_status: string;
  form_data: Record<string, unknown>;
}

/** Vài dòng đầu của phiếu, đủ để nhớ ra hôm đó khám gì. */
function tomTat(form: Record<string, unknown>): string[] {
  const ra: string[] = [];
  for (const [, v] of Object.entries(form)) {
    if (ra.length >= 4) break;
    if (typeof v === "string" && v.trim().length > 2) ra.push(v.trim());
    else if (Array.isArray(v) && v.length) ra.push(v.join(", "));
  }
  return ra;
}

function ngay(iso: string | null): string {
  if (!iso) return "—";
  const t = Date.parse(iso);
  return Number.isFinite(t) ? new Date(t).toLocaleDateString("vi-VN") : "—";
}

export default function LuotKhamTruoc({
  clinicPatientId,
  visitIdHienTai,
  dangXem,
  onXem,
}: {
  clinicPatientId: string | null;
  visitIdHienTai: string | null;
  /** Lượt đang xem lại, hoặc null khi đang khám hôm nay. */
  dangXem: LuotTruoc | null;
  onXem: (luot: LuotTruoc | null) => void;
}) {
  const [items, setItems] = useState<LuotTruoc[]>([]);
  const [hien, setHien] = useState<string | null>(null);

  useEffect(() => {
    // `setItems([])` đồng bộ ngay trong thân effect bị React compiler chặn —
    // nó kéo theo một lượt render thừa. Dọn danh sách trong nhánh async bên
    // dưới, cùng chỗ với lúc nạp xong.
    let bo = false;
    if (!clinicPatientId) {
      const t = setTimeout(() => {
        if (!bo) setItems([]);
      }, 0);
      return () => {
        bo = true;
        clearTimeout(t);
      };
    }
    fetch(`/api/clinical-forms/history?clinic_patient_id=${clinicPatientId}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d: { items?: LuotTruoc[] } | null) => {
        if (bo || !d) return;
        // Lượt ĐANG khám không phải "lượt trước".
        setItems((d.items ?? []).filter((x) => x.visit_id !== visitIdHienTai));
      })
      .catch(() => {});
    return () => {
      bo = true;
    };
  }, [clinicPatientId, visitIdHienTai]);

  // Chưa khám lần nào thì thôi.
  if (items.length === 0 && !dangXem) return null;

  return (
    <div className="relative mt-2">
      {dangXem ? (
        <div className="flex flex-wrap items-center gap-2 rounded-control bg-warning-bg px-3 py-2 text-xs text-warning">
          <History className="size-3.5 shrink-0" aria-hidden="true" />
          <span>
            Đang xem lại lượt khám ngày{" "}
            <strong>{ngay(dangXem.kham_luc)}</strong>
            {dangXem.bac_si ? ` · ${dangXem.bac_si}` : ""} — chỉ xem, không sửa
            được.
          </span>
          <button
            type="button"
            onClick={() => onXem(null)}
            className="ml-auto inline-flex items-center gap-1.5 rounded-control bg-brand-600 px-2.5 py-1 text-xs font-medium text-surface hover:bg-brand-700"
          >
            <RotateCcw className="size-3.5" aria-hidden="true" />
            Quay lại khám tiếp
          </button>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          <span className="text-ink-muted">Lượt khám trước:</span>
          {items.map((l, i) => (
            <button
              key={l.visit_id}
              type="button"
              onMouseEnter={() => setHien(l.visit_id)}
              onMouseLeave={() => setHien(null)}
              onFocus={() => setHien(l.visit_id)}
              onBlur={() => setHien(null)}
              onClick={() => onXem(l)}
              className="rounded-control bg-surface-muted px-2 py-1 text-ink-soft transition-colors hover:bg-brand-50 hover:text-brand-700"
            >
              Lần {items.length - i} · {ngay(l.kham_luc)}
            </button>
          ))}
        </div>
      )}

      {/* Tóm tắt hiện BÊN CẠNH khi rê chuột — không phải một hộp thoại phải
          đóng lại, vì bác sĩ chỉ muốn liếc rồi đi tiếp. */}
      {hien && !dangXem
        ? (() => {
            const l = items.find((x) => x.visit_id === hien);
            if (!l) return null;
            const dong = tomTat(l.form_data);
            return (
              <div className="absolute left-0 top-full z-20 mt-1 w-72 rounded-card bg-surface p-3 text-xs shadow-panel">
                <p className="font-semibold text-ink">
                  {ngay(l.kham_luc)}
                  {l.ten_dich_vu ? ` · ${l.ten_dich_vu}` : ""}
                </p>
                {l.bac_si && (
                  <p className="mt-0.5 text-ink-muted">BS {l.bac_si}</p>
                )}
                {dong.length ? (
                  <ul className="mt-1.5 grid gap-1 text-ink-soft">
                    {dong.map((d, i) => (
                      <li key={i} className="line-clamp-2">
                        {d}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-1.5 text-ink-muted">
                    Phiếu hôm đó chưa ghi nội dung nào.
                  </p>
                )}
                <p className="mt-2 text-brand-600">Bấm để xem lại nguyên phiếu</p>
              </div>
            );
          })()
        : null}
    </div>
  );
}
