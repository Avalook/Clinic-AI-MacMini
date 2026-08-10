"use client";

// Phản hồi / khiếu nại của khách (DoD CSKH mục 3): *"Có chỗ ghi lại phản hồi
// khách hàng sau khám, các vấn đề khách hàng claim, tình trạng xử lý…"*
//
// Ba vế đủ cả ba: NỘI DUNG (khách nói gì), LOẠI (khen / góp ý / khiếu nại),
// và VÒNG ĐỜI (mới → đang xử lý → đã xử lý, kèm đã xử lý THẾ NÀO).
//
// Đóng một khiếu nại bắt buộc ghi hướng xử lý — "đã xử lý" mà không nói xử lý
// ra sao thì ba tuần sau khách gọi lại và không ai biết lần trước đã hứa gì.
// Backend từ chối; nút ở đây khoá sẵn để người dùng không phải ăn lỗi mới biết.

import { useState } from "react";
import { nhanLoi } from "@/lib/loi-api";
import { useRouter } from "next/navigation";
import { MessageSquareText } from "lucide-react";

export interface DongPhanHoi {
  id: string;
  loai: string;
  noi_dung: string;
  trang_thai: string;
  huong_xu_ly: string | null;
  created_at: string;
  nguoi_tiep_nhan: string | null;
}

const NHAN_LOAI: Record<string, string> = {
  KHEN: "Khen",
  GOP_Y: "Góp ý",
  KHIEU_NAI: "Khiếu nại",
};
const MAU_LOAI: Record<string, string> = {
  KHEN: "bg-success-bg text-success",
  GOP_Y: "bg-surface-sunken text-ink-soft",
  KHIEU_NAI: "bg-danger-bg text-danger",
};
const NHAN_TRANG_THAI: Record<string, string> = {
  MOI: "Mới",
  DANG_XU_LY: "Đang xử lý",
  DA_XU_LY: "Đã xử lý",
};

function gio(iso: string): string {
  return new Date(iso).toLocaleString("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Ho_Chi_Minh",
  });
}

export default function PhanHoiKhach({
  clinicPatientId,
  items,
}: {
  clinicPatientId: string;
  /** Nạp server-side, truyền xuống làm prop — không nạp trong effect. */
  items: DongPhanHoi[];
}) {
  const router = useRouter();
  const [moForm, setMoForm] = useState(false);
  const [loai, setLoai] = useState("KHIEU_NAI");
  const [noiDung, setNoiDung] = useState("");
  const [dangLuu, setDangLuu] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  // Ô "đã xử lý thế nào" của từng dòng đang mở.
  const [dangDong, setDangDong] = useState<string | null>(null);
  const [huongXuLy, setHuongXuLy] = useState("");

  async function ghi() {
    setDangLuu(true);
    setLoi(null);
    const res = await fetch("/api/cskh/phan-hoi", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        clinic_patient_id: clinicPatientId,
        loai,
        noi_dung: noiDung.trim(),
      }),
    });
    setDangLuu(false);
    if (!res.ok) {
      const d = (await res.json().catch(() => null)) as
        | { error?: string; message?: string }
        | null;
      setLoi(nhanLoi(d, "Không ghi được."));
      return;
    }
    setMoForm(false);
    setNoiDung("");
    router.refresh();
  }

  async function capNhat(id: string, trangThai: string, huong?: string) {
    setDangLuu(true);
    setLoi(null);
    const res = await fetch("/api/cskh/phan-hoi", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id,
        trang_thai: trangThai,
        huong_xu_ly: huong ?? null,
      }),
    });
    setDangLuu(false);
    if (!res.ok) {
      const d = (await res.json().catch(() => null)) as
        | { error?: string; message?: string }
        | null;
      setLoi(nhanLoi(d, "Không cập nhật được."));
      return;
    }
    setDangDong(null);
    setHuongXuLy("");
    router.refresh();
  }

  return (
    <section className="min-w-0 overflow-hidden rounded-2xl border border-line bg-surface shadow-card">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-3">
        <h2 className="flex items-center gap-1.5 text-sm font-semibold text-ink">
          <MessageSquareText className="size-4 text-ink-muted" />
          Phản hồi của khách
        </h2>
        <button
          type="button"
          onClick={() => setMoForm((v) => !v)}
          className="rounded-full border border-brand-300 px-2.5 py-0.5 text-[11px] font-semibold text-brand-700 hover:bg-brand-50"
        >
          + Ghi phản hồi
        </button>
      </div>

      <div className="space-y-2 px-4 py-3">
        {moForm && (
          <div className="space-y-2 rounded-xl border border-line bg-surface-muted p-3">
            <select
              value={loai}
              onChange={(e) => setLoai(e.target.value)}
              className="w-full rounded-lg border border-line bg-surface px-2 py-1.5 text-xs text-ink"
            >
              <option value="KHIEU_NAI">Khiếu nại / claim</option>
              <option value="GOP_Y">Góp ý</option>
              <option value="KHEN">Khen</option>
            </select>
            <textarea
              value={noiDung}
              onChange={(e) => setNoiDung(e.target.value)}
              rows={2}
              placeholder="Khách nói gì?"
              className="w-full rounded-lg border border-line bg-surface px-2 py-1.5 text-xs text-ink"
            />
            <button
              type="button"
              onClick={() => void ghi()}
              disabled={dangLuu || !noiDung.trim()}
              className="w-full rounded-lg bg-brand-600 py-1.5 text-xs font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
            >
              {dangLuu ? "Đang ghi…" : "Ghi lại"}
            </button>
          </div>
        )}

        {loi && <p className="text-[11px] text-danger">{loi}</p>}

        {items.length === 0 ? (
          <p className="py-2 text-[11px] text-ink-faint">
            Chưa có phản hồi nào được ghi.
          </p>
        ) : (
          <ul className="space-y-2">
            {items.map((p) => (
              <li
                key={p.id}
                className="rounded-xl border border-line bg-surface p-2.5"
              >
                <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
                  <span
                    className={`rounded-full px-2 py-0.5 font-bold ${MAU_LOAI[p.loai] ?? ""}`}
                  >
                    {NHAN_LOAI[p.loai] ?? p.loai}
                  </span>
                  <span className="font-mono text-ink-muted">
                    {gio(p.created_at)}
                  </span>
                  {p.nguoi_tiep_nhan && (
                    <span className="text-ink-faint">· {p.nguoi_tiep_nhan}</span>
                  )}
                  <span
                    className={`ml-auto rounded-full px-2 py-0.5 font-semibold ${
                      p.trang_thai === "DA_XU_LY"
                        ? "bg-success-bg text-success"
                        : p.trang_thai === "DANG_XU_LY"
                          ? "bg-warning-bg text-warning"
                          : "bg-surface-sunken text-ink-soft"
                    }`}
                  >
                    {NHAN_TRANG_THAI[p.trang_thai] ?? p.trang_thai}
                  </span>
                </div>
                <p className="mt-1 text-xs text-ink">{p.noi_dung}</p>
                {p.huong_xu_ly && (
                  <p className="mt-1 text-[11px] text-ink-muted">
                    Xử lý: {p.huong_xu_ly}
                  </p>
                )}

                {p.trang_thai !== "DA_XU_LY" && (
                  <div className="mt-2 space-y-1.5">
                    {dangDong === p.id ? (
                      <>
                        <input
                          value={huongXuLy}
                          onChange={(e) => setHuongXuLy(e.target.value)}
                          placeholder="Đã xử lý thế nào?"
                          className="w-full rounded-lg border border-line bg-surface-muted px-2 py-1 text-[11px] text-ink"
                        />
                        <button
                          type="button"
                          onClick={() =>
                            void capNhat(p.id, "DA_XU_LY", huongXuLy.trim())
                          }
                          disabled={dangLuu || !huongXuLy.trim()}
                          className="rounded-full bg-success px-2.5 py-0.5 text-[11px] font-semibold text-white disabled:opacity-50"
                        >
                          Chốt đã xử lý
                        </button>
                      </>
                    ) : (
                      <div className="flex gap-1.5">
                        {p.trang_thai === "MOI" && (
                          <button
                            type="button"
                            onClick={() => void capNhat(p.id, "DANG_XU_LY")}
                            disabled={dangLuu}
                            className="rounded-full border border-line px-2.5 py-0.5 text-[11px] font-medium text-ink-soft hover:bg-surface-muted"
                          >
                            Bắt đầu xử lý
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => setDangDong(p.id)}
                          className="rounded-full border border-success px-2.5 py-0.5 text-[11px] font-medium text-success hover:bg-success-bg"
                        >
                          Đã xử lý…
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
