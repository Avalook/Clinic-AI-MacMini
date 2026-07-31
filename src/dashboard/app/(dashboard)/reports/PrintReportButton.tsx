"use client";

// Nút tạo báo cáo PDF — dùng window.print() (trình duyệt hỏi lưu PDF).
// Tách thành client component để không ảnh hưởng Server Component ReportsPage.

import { useState } from "react";

export default function PrintReportButton() {
  const [printing, setPrinting] = useState(false);

  function handlePrint() {
    setPrinting(true);
    // Đợi state render xong rồi mới in tránh nút bị capture trong PDF
    setTimeout(() => {
      window.print();
      setPrinting(false);
    }, 120);
  }

  return (
    <button
      id="print-report-btn"
      onClick={handlePrint}
      disabled={printing}
      className={
        "inline-flex shrink-0 items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium shadow-sm transition-colors " +
        "border-brand-800 bg-brand-800 text-white hover:bg-[#831e53] disabled:opacity-60 " +
        "print:hidden"
      }
    >
      {/* file-text icon (SVG inline để không cần thêm dep) */}
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="16" y1="13" x2="8" y2="13" />
        <line x1="16" y1="17" x2="8" y2="17" />
        <polyline points="10 9 9 9 8 9" />
      </svg>
      {printing ? "Đang chuẩn bị…" : "Tạo file báo cáo"}
    </button>
  );
}
