"use client";

import { useActionState } from "react";
import { chooseClinic } from "./actions";

export interface ClinicChoice {
  clinicId: string;
  name: string;
  roleLabel: string;
}

export default function ClinicPicker({
  choices,
}: {
  choices: readonly ClinicChoice[];
}) {
  const [state, formAction, pending] = useActionState(chooseClinic, null);

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-muted px-4">
      <form
        action={formAction}
        className="w-full max-w-sm space-y-4 rounded-lg bg-white p-6 shadow-[0_1px_3px_rgba(0,0,0,0.08)]"
      >
        <div className="space-y-1">
          <h1 className="flex items-center gap-2 text-xl font-semibold text-ink">
            <span className="h-2 w-2 rounded-full bg-brand-600" />
            Chọn phòng khám
          </h1>
          <p className="text-sm text-ink-muted">
            Bạn đang làm việc ở nhiều nơi. Chọn nơi làm việc cho ca này.
          </p>
        </div>

        <div className="space-y-2">
          {choices.map((choice) => (
            <button
              key={choice.clinicId}
              type="submit"
              name="clinic_id"
              value={choice.clinicId}
              disabled={pending}
              className="min-h-11 w-full rounded-md border border-line px-3 py-2.5 text-left transition-colors duration-150 hover:border-brand-600 hover:bg-brand-600/5 disabled:opacity-50"
            >
              <span className="block text-sm font-medium text-ink">
                {choice.name}
              </span>
              <span className="block text-xs text-ink-muted">
                {choice.roleLabel}
              </span>
            </button>
          ))}
        </div>

        {state?.error && (
          <p className="rounded bg-danger-bg px-3 py-2 text-sm text-danger">
            {state.error}
          </p>
        )}

        <p className="text-xs text-ink-muted">
          Lựa chọn này áp dụng cho ca làm việc hiện tại. Đổi lại bất cứ lúc nào
          bằng nút “Đổi phòng khám” ở cuối thanh điều hướng.
        </p>
      </form>
    </div>
  );
}
