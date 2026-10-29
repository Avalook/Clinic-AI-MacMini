"use client";

// LƯỢT CHƯA HOÀN TẤT KHÁM — Tuyền duyệt phiếu 22/10/2026.
//
// Hoàn tất khám không phải một nút: máy tự khép lượt khi hết việc dở. Lượt
// check-in quá 2 giờ mà chưa khép là còn việc bị bỏ quên — đo prod 21/10: 26
// lượt, 22 vì vòng đọc kết quả chưa đóng. Mỗi khách MỘT dòng, nói đúng việc còn
// dở; bấm "Mở lượt" về đúng ngày + đúng khách trên Bàn khám.
//
// Máy chủ quyết hết (`services/nhac_chua_hoan_tat.py`): lượt nào, vì sao, chữ
// hiện, ai thấy (cùng luật khối "Chờ bác sĩ quyết"). Màn chỉ vẽ.

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import StatusChip, { type StatusTone } from "@/components/ui/StatusChip";
import { fmtDayTime } from "@/lib/datetime";

import { docBang } from "../_lam-viec/api";
import { useNgheBang } from "../dung-nghe-bang";

interface LuotChua {
  visit_id: string;
  ten: string | null;
  ma_bn: string | null;
  checked_in_at: string;
  ngay: string;
  tu_hom_truoc: boolean;
  ly_do: string;
  ly_do_chu: string;
  bac_si_ten: string | null;
}

interface GoiChua {
  items: LuotChua[];
  pham_vi: "cua_toi" | "bac_si_duoc_phan" | "co_so";
  nguong_phut: number;
}

// Việc thường ngày, không phải báo động (giảm đỏ/vàng 14/10/2026): chỉ phân
// "đến lượt bác sĩ làm" với "đang chờ chỗ khác".
const TONE: Record<string, StatusTone> = {
  cho_doc_ket_qua: "ready",
  dang_doc_do: "in_progress",
  kham_do: "in_progress",
  cho_kham: "assigned",
  cho_ket_qua: "blocked",
  con_chi_dinh: "blocked",
};

export default function LuotChuaHoanTat({ lanNap }: { lanNap: number }) {
  const [goi, setGoi] = useState<GoiChua | null>(null);

  const nap = useCallback(async () => {
    const kq = await docBang<GoiChua>("chua-hoan-tat");
    if (kq.ok) setGoi(kq.data);
  }, []);

  useEffect(() => {
    let huy = false;
    void docBang<GoiChua>("chua-hoan-tat").then((kq) => {
      if (!huy && kq.ok) setGoi(kq.data);
    });
    return () => {
      huy = true;
    };
  }, [lanNap]);
  // Vòng đọc đóng / phiên khám xong ở máy khác → dòng tự rời danh sách.
  useNgheBang(["review_round", "consultation", "visit"], () => void nap());

  if (!goi || goi.items.length === 0) return null;
  const gio = Math.round(goi.nguong_phut / 60);

  return (
    <section
      aria-label="Lượt chưa Hoàn tất khám"
      className="rounded-card bg-surface p-3.5 shadow-card"
    >
      <h2 className="text-sm font-semibold text-ink">
        Lượt chưa Hoàn tất khám · {goi.items.length}
      </h2>
      <p className="mt-1 text-xs text-ink-muted">
        Check-in quá {gio} giờ mà còn việc dở. Làm xong việc ghi ở từng dòng thì lượt
        tự Hoàn tất.
      </p>
      <ul className="mt-3 grid gap-2">
        {goi.items.map((l) => (
          <li
            key={l.visit_id}
            className="flex flex-wrap items-center gap-2 rounded-control bg-surface-muted px-3 py-2"
          >
            <span className="text-sm font-semibold text-ink">{l.ten ?? "—"}</span>
            {l.ma_bn ? <span className="text-xs text-ink-muted">{l.ma_bn}</span> : null}
            <StatusChip tone={TONE[l.ly_do] ?? "blocked"} label={l.ly_do_chu} size="sm" />
            <span className="text-xs text-ink-muted">
              Check-in {fmtDayTime(l.checked_in_at)}
              {goi.pham_vi !== "cua_toi" && l.bac_si_ten ? ` · BS ${l.bac_si_ten}` : ""}
            </span>
            <Link
              href={`/ban-kham?ngay=${encodeURIComponent(l.ngay)}&luot=${encodeURIComponent(l.visit_id)}`}
              className="ml-auto inline-flex min-h-9 items-center rounded-control px-2 text-sm font-semibold text-primary hover:underline"
            >
              Mở lượt
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
