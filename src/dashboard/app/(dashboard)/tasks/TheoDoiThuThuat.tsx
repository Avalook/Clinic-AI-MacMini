"use client";

// THEO DÕI SAU THỦ THUẬT — BÁC SĨ QUYẾT (Tuyền chốt 16/09/2026).
//
// Màn CSKH có hai ô khoá "Đã làm thủ thuật" và "Không cần follow-up sau thủ
// thuật". Chúng đọc đúng thứ bác sĩ chọn ở đây; CSKH không tích được. Chỉ hiện
// khi lượt khám có chỉ định thủ thuật — backend trả `co_thu_thuat`.
//
// Luật (ai được chọn, hạn gọi tính từ lúc làm xong thủ thuật) nằm ở
// `theo_doi_thu_thuat_service.py`; màn này chỉ hiển thị và gửi lựa chọn.

import { useEffect, useState } from "react";
import { nhanLoi } from "@/lib/loi-api";

interface TheoDoi {
  co_thu_thuat: boolean;
  thu_thuat_xong_luc: string | null;
  theo_doi: "CAN" | "KHONG_CAN" | null;
  sau_ngay: number | null;
  han_goi: string | null;
  quyet_boi: string | null;
}

function ngay(iso: string): string {
  return new Date(iso).toLocaleDateString("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    timeZone: "Asia/Ho_Chi_Minh",
  });
}

export default function TheoDoiThuThuat({
  visitId,
  readOnly,
}: {
  visitId: string;
  readOnly: boolean;
}) {
  const [tt, setTt] = useState<TheoDoi | null>(null);
  const [sauNgay, setSauNgay] = useState("1");
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);

  useEffect(() => {
    let huy = false;
    void fetch(`/api/visits/${visitId}/theo-doi-thu-thuat`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d: TheoDoi | null) => {
        if (huy || !d) return;
        setTt(d);
        if (d.sau_ngay) setSauNgay(String(d.sau_ngay));
      })
      .catch(() => null);
    return () => {
      huy = true;
    };
  }, [visitId]);

  if (!tt?.co_thu_thuat) return null;

  async function luu(theoDoi: "CAN" | "KHONG_CAN") {
    setDang(true);
    setLoi(null);
    const res = await fetch(`/api/visits/${visitId}/theo-doi-thu-thuat`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        theo_doi: theoDoi,
        sau_ngay: theoDoi === "CAN" ? Number(sauNgay) || null : null,
      }),
    });
    setDang(false);
    const d = (await res.json().catch(() => null)) as
      | (TheoDoi & { message?: string; error?: string })
      | null;
    if (!res.ok || !d) {
      setLoi(nhanLoi(d, `Không lưu được (lỗi ${res.status}).`));
      return;
    }
    setTt(d);
  }

  return (
    <div className="space-y-2 rounded-card border border-hairline p-3">
      <p className="text-sm font-semibold text-ink">Theo dõi sau thủ thuật</p>
      <p className="text-label text-ink-muted">
        {tt.thu_thuat_xong_luc
          ? `Thủ thuật làm xong ngày ${ngay(tt.thu_thuat_xong_luc)}.`
          : "Có chỉ định thủ thuật — chưa làm xong."}{" "}
        CSKH gọi hỏi thăm theo lựa chọn này.
      </p>
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          disabled={readOnly || dang}
          onClick={() => void luu("KHONG_CAN")}
          aria-pressed={tt.theo_doi === "KHONG_CAN"}
          className={`h-8 rounded-control px-3 text-body font-medium disabled:opacity-50 ${
            tt.theo_doi === "KHONG_CAN"
              ? "bg-brand-600 text-white"
              : "bg-surface text-ink ring-1 ring-inset ring-line-strong hover:bg-surface-muted"
          }`}
        >
          Không cần theo dõi
        </button>
        <span className="text-label text-ink-muted">hoặc theo dõi sau</span>
        <input
          type="number"
          min={1}
          max={365}
          value={sauNgay}
          disabled={readOnly || dang}
          onChange={(e) => setSauNgay(e.target.value)}
          className="h-8 w-16 rounded-control px-2 text-body ring-1 ring-inset ring-line-strong"
          aria-label="Số ngày theo dõi sau thủ thuật"
        />
        <span className="text-label text-ink-muted">ngày</span>
        <button
          type="button"
          disabled={readOnly || dang}
          onClick={() => void luu("CAN")}
          aria-pressed={tt.theo_doi === "CAN"}
          className={`h-8 rounded-control px-3 text-body font-medium disabled:opacity-50 ${
            tt.theo_doi === "CAN"
              ? "bg-brand-600 text-white"
              : "bg-surface text-ink ring-1 ring-inset ring-line-strong hover:bg-surface-muted"
          }`}
        >
          Cần theo dõi
        </button>
      </div>
      {tt.theo_doi && (
        <p className="text-label text-ink-soft">
          {tt.theo_doi === "KHONG_CAN"
            ? "Đã chọn: không cần theo dõi."
            : `Đã chọn: theo dõi sau ${tt.sau_ngay} ngày${
                tt.han_goi ? ` — CSKH gọi trước ${ngay(tt.han_goi)}` : ""
              }.`}
          {tt.quyet_boi ? ` (${tt.quyet_boi})` : ""}
        </p>
      )}
      {loi && <p className="text-label text-danger">{loi}</p>}
    </div>
  );
}
