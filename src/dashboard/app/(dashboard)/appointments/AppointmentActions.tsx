"use client";

// Per-row Confirm / Reject controls for a doctor's own SCHEDULED appointment.
// Calls PATCH /api/appointments then refreshes the (server-rendered) list.

import { useState } from "react";
import { useRouter } from "next/navigation";

export default function AppointmentActions({
  appointmentId,
}: {
  appointmentId: string;
}) {
  const router = useRouter();
  const [busy, setBusy] = useState<null | "confirm" | "decline">(null);
  const [error, setError] = useState<string | null>(null);

  async function act(action: "confirm" | "decline") {
    setBusy(action);
    setError(null);
    const res = await fetch("/api/appointments", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: appointmentId, action }),
    });
    const json = await res.json();
    if (!res.ok) {
      setBusy(null);
      setError(json.error ?? "Có lỗi xảy ra.");
      return;
    }
    router.refresh();
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <button
        onClick={() => act("confirm")}
        disabled={busy !== null}
        className="min-h-9 flex-1 rounded-md bg-[#16a34a] px-2.5 py-1.5 text-xs font-medium text-white transition-colors duration-150 hover:bg-[#15803d] active:bg-[#15803d] disabled:opacity-50 sm:min-h-0 sm:flex-none sm:py-1"
      >
        {busy === "confirm" ? "..." : "Xác nhận"}
      </button>
      <button
        onClick={() => act("decline")}
        disabled={busy !== null}
        className="min-h-9 flex-1 rounded-md border border-[#dc2626] px-2.5 py-1.5 text-xs font-medium text-[#dc2626] transition-colors duration-150 hover:bg-[#fee2e2] active:bg-[#fee2e2] disabled:opacity-50 sm:min-h-0 sm:flex-none sm:py-1"
      >
        {busy === "decline" ? "..." : "Từ chối"}
      </button>
      {error && <span className="w-full text-xs text-[#dc2626]">{error}</span>}
    </div>
  );
}
