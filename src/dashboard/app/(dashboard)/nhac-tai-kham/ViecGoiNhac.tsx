"use client";

// Hàng đợi gọi nhắc tái khám — HAI LƯỢT, và mỗi cuộc gọi ghi được kết quả.
//
// Thay cho bảng cũ đọc `GET /api/v1/cskh/recalls`. Đường kia trả về một PHÉP
// CHIẾU tính lại mỗi lần mở trang: không dòng nào trong database, không hạn,
// không người phụ trách, không phân biệt lượt gọi, và nút "Đã gọi" của nó ghi
// ra một dòng giống hệt nhau dù bắt máy được hay không.
//
// Ở đây mỗi thẻ là một VIỆC CÓ THẬT (`nhac_tai_kham`). Gọi xong thì việc rời
// hàng đợi; chưa gọi thì nó nằm đó sang hôm sau và đếm quá hạn.

import { useState } from "react";
import { useRouter } from "next/navigation";
import { PhoneCall, PhoneOff, Stethoscope, XCircle } from "lucide-react";

export interface ViecGoi {
  id: string;
  luot_goi: number;
  ngay_hen: string;
  han_goi: string;
  full_name: string | null;
  phone_primary: string | null;
  patient_code: string | null;
  qua_han: boolean;
  slot_start: string | null;
}

export interface DuLieu {
  ngay: string;
  cua_so_ngay: number;
  luot1: ViecGoi[];
  luot2: ViecGoi[];
}

const KET_QUA = [
  { ma: "DA_LIEN_HE", nhan: "Đã liên hệ", Icon: PhoneCall },
  { ma: "CHUA_NGHE_MAY", nhan: "Chưa nghe máy", Icon: PhoneOff },
  { ma: "CAN_BAC_SI", nhan: "Cần bác sĩ", Icon: Stethoscope },
  { ma: "TU_CHOI", nhan: "Khách từ chối", Icon: XCircle },
] as const;

function ngayVn(iso: string | null): string {
  if (!iso) return "—";
  const t = Date.parse(iso.length === 10 ? `${iso}T00:00:00` : iso);
  return Number.isFinite(t) ? new Date(t).toLocaleDateString("vi-VN") : "—";
}

export default function ViecGoiNhac({
  duLieu,
  khongDocDuoc,
}: {
  duLieu: DuLieu | null;
  khongDocDuoc: boolean;
}) {
  const router = useRouter();
  const [dangGui, setDangGui] = useState<string | null>(null);
  const [ghiChu, setGhiChu] = useState<Record<string, string>>({});
  const [loi, setLoi] = useState<string | null>(null);

  async function ghi(viecId: string, ketQua: string) {
    setDangGui(viecId);
    setLoi(null);
    try {
      const res = await fetch(`/api/recall-jobs/${viecId}/ket-qua`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ket_qua: ketQua, ghi_chu: ghiChu[viecId] ?? null }),
      });
      if (!res.ok) {
        const d = (await res.json().catch(() => null)) as {
          error?: string;
          message?: string;
        } | null;
        setLoi(d?.message ?? d?.error ?? "Không ghi được kết quả. Thử lại giúp em.");
        return;
      }
      router.refresh();
    } finally {
      setDangGui(null);
    }
  }

  if (khongDocDuoc) {
    // "Không đọc được" và "hôm nay không ai cần gọi" nhìn giống hệt nhau trên
    // màn hình mà hậu quả thì ngược nhau — nên nói thẳng ra.
    return (
      <div className="rounded-card border border-danger bg-danger-bg px-4 py-3 text-sm text-danger">
        Không đọc được hàng đợi gọi nhắc. Danh sách trống ở đây KHÔNG có nghĩa
        là hôm nay không ai cần gọi.
      </div>
    );
  }
  if (!duLieu) return null;

  const nhom = [
    {
      key: "luot1",
      tieuDe: "Lượt 1 — mời đặt lịch",
      moTa: `Bác sĩ đã dặn ngày tái khám, khách chưa đặt lịch. Gọi trước hẹn ${duLieu.cua_so_ngay} ngày.`,
      viec: duLieu.luot1,
    },
    {
      key: "luot2",
      tieuDe: "Lượt 2 — nhắc đi khám hôm nay",
      moTa: "Khách đã có lịch hôm nay. Gọi buổi sáng để nhắc.",
      viec: duLieu.luot2,
    },
  ];

  return (
    <div className="space-y-5">
      {loi && (
        <p className="rounded-card border border-danger bg-danger-bg px-4 py-2.5 text-sm text-danger">
          {loi}
        </p>
      )}

      {nhom.map((n) => (
        <section key={n.key} className="space-y-2">
          <div className="flex flex-wrap items-baseline gap-x-3">
            <h2 className="text-base font-semibold text-ink">{n.tieuDe}</h2>
            <span className="rounded-chip bg-brand-50 px-2 py-0.5 text-xs font-medium text-brand-700">
              {n.viec.length} việc
            </span>
            <p className="text-xs text-ink-muted">{n.moTa}</p>
          </div>

          {n.viec.length === 0 ? (
            <p className="rounded-card border border-line bg-surface px-4 py-6 text-center text-sm text-ink-muted shadow-card">
              Không còn ai phải gọi ở lượt này.
            </p>
          ) : (
            <ul className="space-y-2">
              {n.viec.map((v) => (
                <li
                  key={v.id}
                  className="rounded-card border border-line bg-surface p-3 shadow-card"
                >
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <div className="min-w-0">
                      <span className="font-medium text-ink">
                        {v.full_name ?? "(không rõ tên)"}
                      </span>
                      {v.patient_code && (
                        <span className="ml-2 font-mono text-xs text-ink-muted">
                          {v.patient_code}
                        </span>
                      )}
                      <div className="mt-0.5 text-xs text-ink-muted">
                        {v.phone_primary ?? "chưa có số điện thoại"}
                        <span className="mx-1.5 text-line-strong">·</span>
                        hẹn {ngayVn(v.ngay_hen)}
                        {v.luot_goi === 1 && <> · nên gọi {ngayVn(v.han_goi)}</>}
                      </div>
                    </div>
                    {v.qua_han && (
                      <span className="rounded-chip bg-danger-bg px-2 py-0.5 text-xs font-medium text-danger">
                        Quá hạn gọi
                      </span>
                    )}
                  </div>

                  <div className="mt-2.5 flex flex-wrap items-center gap-2">
                    <input
                      value={ghiChu[v.id] ?? ""}
                      onChange={(e) =>
                        setGhiChu((p) => ({ ...p, [v.id]: e.target.value }))
                      }
                      placeholder="Ghi chú cuộc gọi (không bắt buộc)"
                      className="min-w-[180px] flex-1 rounded-control border border-line bg-surface px-2.5 py-1.5 text-xs text-ink outline-none focus:border-brand-500"
                    />
                    {/* BỐN KẾT QUẢ, KHÔNG PHẢI MỘT NÚT "ĐÃ GỌI".
                        "Chuông đổ không ai bắt" cũng là một việc đã làm, và nó
                        phải khác "đã nói chuyện được" — nếu không thì hôm sau
                        người khác thấy 'đã gọi' rồi bỏ qua một người chưa ai
                        nói chuyện với. */}
                    {KET_QUA.map(({ ma, nhan, Icon }) => (
                      <button
                        key={ma}
                        type="button"
                        disabled={dangGui === v.id}
                        onClick={() => ghi(v.id, ma)}
                        className="inline-flex items-center gap-1.5 rounded-control border border-line px-2.5 py-1.5 text-xs font-medium text-ink-soft transition-colors hover:bg-surface-muted disabled:opacity-50"
                      >
                        <Icon size={13} />
                        {nhan}
                      </button>
                    ))}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      ))}
    </div>
  );
}
