"use client";

// Các lượt khám TRƯỚC của bệnh nhân đang mở.
//
// "Lượt khám 3 · ngày…", "Buổi 2/10 · ngày…" — nhãn MÁY CHỦ đếm trên mọi lượt
// của khách (`nhan_luot`, 08/10/2026; trước đó "Lần n" theo số phiếu nạp về —
// thiếu phiếu là đánh số sai). Rê chuột vào một ngày thì hiện tóm tắt ngay
// bên cạnh; bấm vào thì phiếu bên dưới quay về đúng hôm đó, kèm một nút để
// quay lại khám tiếp.
//
// RANH GIỚI QUAN TRỌNG NHẤT: phiếu cũ mở ở chế độ CHỈ XEM.
// Không có ranh giới đó thì bác sĩ gõ vào một phiếu tưởng là hôm nay và ghi
// đè lên bệnh án tháng trước — mà bệnh án đã ký thì luật cấm sửa. Nên khi
// đang xem lại, cả màn đổi màu và nút "Lưu phiếu" biến mất.
//
// Chưa khám lần nào thì component này không hiện gì.
//
// PHẢN HỒI SAU DÙNG THUỐC (10/10/2026): CSKH ghi ở khung khách, gắn lượt có đơn
// → hiện NGAY dưới hàng lượt (không cần rê chuột), chỉ đọc; tự cập nhật khi sổ
// chăm sóc đổi (NOTIFY `tuong_tac_cskh`).

import { useEffect, useState } from "react";
import { History, RotateCcw } from "lucide-react";

import { doctorName } from "../../../../lib/doctor-name";
import { chuNhanLuot, type NhanLuot } from "../../../../lib/nhan-luot";
import { DongPhanHoiThuoc, type PhanHoiThuoc } from "../../_lam-viec/PhanHoiThuocKhach";
import { useNgheBang } from "../../dung-nghe-bang";

export interface LuotTruoc {
  visit_id: string;
  service_code: string;
  ten_dich_vu: string | null;
  bac_si: string | null;
  kham_luc: string | null;
  visit_status: string;
  form_data: Record<string, unknown>;
  /** Lượt ghi phiếu khám v5 (`phieu_kham_luot`, 29/09/2026): xem lại bằng
   *  phiếu v5 chỉ-xem; `form_data` là {khoá ô: chữ đọc được}, chẩn đoán đầu. */
  phieu_v5?: boolean;
  chan_doan?: string | null;
  /** Nhãn đếm lượt máy chủ tính ("Lượt khám 3", "Buổi 2/10"…). */
  nhan_luot?: NhanLuot | null;
  /** Phản hồi sau dùng thuốc CSKH ghi cho lượt này (máy chủ gắn). */
  phan_hoi_thuoc?: PhanHoiThuoc[];
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
  const [lan, setLan] = useState(0);
  useNgheBang(["tuong_tac_cskh"], () => setLan((n) => n + 1));

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
  }, [clinicPatientId, visitIdHienTai, lan]);

  // Chưa khám lần nào thì thôi.
  if (items.length === 0 && !dangXem) return null;

  // Đang xem lại một lượt → chỉ phản hồi của lượt ấy; còn lại → mọi lượt trước.
  const phanHoi = dangXem
    ? (items.find((x) => x.visit_id === dangXem.visit_id)?.phan_hoi_thuoc ??
      dangXem.phan_hoi_thuoc ??
      [])
    : items.flatMap((x) => x.phan_hoi_thuoc ?? []);

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
          {items.map((l) => (
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
              {chuNhanLuot(l.nhan_luot)} · {ngay(l.kham_luc)}
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
                  <p className="mt-0.5 text-ink-muted">{doctorName(l.bac_si)}</p>
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

      {phanHoi.length ? (
        <div className="mt-2 rounded-control bg-surface-muted px-3 py-2">
          <p className="text-meta font-semibold text-ink">
            Phản hồi sau dùng thuốc (CSKH ghi)
          </p>
          <ul className="mt-1 max-h-48 space-y-2 overflow-y-auto overscroll-contain">
            {phanHoi.map((p) => (
              <li key={p.id}>
                <DongPhanHoiThuoc p={p} />
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}
