"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

interface LabReviewActionsProps {
  labResultId: string;
  clinicPatientId: string;
  triageGroup: string;
  isFinalized: boolean;
  hasResult: boolean;
}

async function errorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { error?: string; message?: string };
    return body.error ?? body.message ?? "Không thể xử lý kết quả xét nghiệm.";
  } catch {
    return "Không thể xử lý kết quả xét nghiệm.";
  }
}

export default function LabReviewActions({
  labResultId,
  clinicPatientId,
  triageGroup,
  isFinalized,
  hasResult,
}: LabReviewActionsProps) {
  const router = useRouter();
  const [busy, setBusy] = useState<"triage" | "review" | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function classify() {
    setBusy("triage");
    setMessage(null);
    const response = await fetch(`/api/lab-result/${labResultId}/triage`, {
      method: "POST",
    });
    const messageText = response.ok
      ? "Đã phân loại và lưu kết quả. Vui lòng kiểm tra trước khi duyệt."
      : await errorMessage(response);
    setMessage(messageText);
    setBusy(null);
    router.refresh();
  }

  async function review() {
    const confirmed = window.confirm(
      "Xác nhận bạn đã đọc kết quả gốc và muốn duyệt, hoàn tất kết quả này?",
    );
    if (!confirmed) return;

    setBusy("review");
    setMessage(null);
    const response = await fetch(`/api/lab-result/${labResultId}/review`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ clinic_patient_id: clinicPatientId }),
    });
    setMessage(
      response.ok
        ? "Đã duyệt và hoàn tất. Quy tắc báo bệnh nhân vẫn được kiểm tra riêng."
        : await errorMessage(response),
    );
    setBusy(null);
    router.refresh();
  }

  if (isFinalized) {
    return (
      <span className="text-xs font-semibold text-success">
        Đã được bác sĩ duyệt
      </span>
    );
  }

  const pending = triageGroup === "PENDING";
  return (
    <div className="mt-2 flex flex-wrap items-center gap-2">
      {pending ? (
        <button
          type="button"
          onClick={classify}
          disabled={!hasResult || busy !== null}
          title={
            hasResult
              ? "Phân loại chỉ lưu mức an toàn, không sửa nội dung kết quả"
              : "Chưa có dữ liệu kết quả để phân loại"
          }
          className="rounded-md border border-brand-700 px-2.5 py-1 text-xs font-semibold text-brand-800 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {busy === "triage" ? "Đang phân loại…" : "Phân loại an toàn"}
        </button>
      ) : (
        <button
          type="button"
          onClick={review}
          disabled={!hasResult || busy !== null}
          className="rounded-md bg-brand-800 px-2.5 py-1 text-xs font-semibold text-white disabled:cursor-not-allowed disabled:opacity-40"
        >
          {busy === "review" ? "Đang hoàn tất…" : "Duyệt & hoàn tất"}
        </button>
      )}
      {message && (
        <span role="status" className="basis-full text-xs text-ink-soft">
          {message}
        </span>
      )}
    </div>
  );
}

