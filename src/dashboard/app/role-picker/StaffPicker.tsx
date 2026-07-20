"use client";

// Danh sách tất cả nhân viên, nhóm theo chức danh, có ô tìm. Bấm tên mình →
// submit (server action chooseStaffIdentity) → vào không gian làm việc riêng.

import { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { ROLE_LABEL, departmentToRole } from "../../lib/roles";
import { unaccentVi } from "../../lib/validation";
import { chooseStaffIdentity } from "./actions";

export interface StaffPerson {
  id: string;
  full_name: string;
  short_name: string | null;
  primary_department: string;
}

const DEPT_ORDER = [
  "DOCTOR",
  "ULTRASOUND_DOCTOR",
  "NURSE_ULTRASOUND",
  "RECEPTION",
  "CASHIER",
  "CSKH",
  "MANAGEMENT",
];

export default function StaffPicker({ staff }: { staff: StaffPerson[] }) {
  const [q, setQ] = useState("");
  // Tìm nhân sự KHÔNG phân biệt dấu (D11): so khớp trên bản đã bỏ dấu.
  const term = unaccentVi(q.trim());

  const groups = useMemo(() => {
    const filtered = term
      ? staff.filter(
          (s) =>
            unaccentVi(s.full_name).includes(term) ||
            unaccentVi(s.short_name ?? "").includes(term),
        )
      : staff;
    const byDept = new Map<string, StaffPerson[]>();
    for (const s of filtered) {
      const arr = byDept.get(s.primary_department) ?? [];
      arr.push(s);
      byDept.set(s.primary_department, arr);
    }
    const order = [
      ...DEPT_ORDER.filter((d) => byDept.has(d)),
      ...[...byDept.keys()].filter((d) => !DEPT_ORDER.includes(d)),
    ];
    return order.map((dept) => ({ dept, people: byDept.get(dept)! }));
  }, [staff, term]);

  return (
    <div className="mx-auto flex min-h-screen max-w-3xl flex-col px-4 py-10">
      <div className="mb-6">
        <h1 className="flex items-center gap-2 text-2xl font-semibold text-[#171717]">
          <span className="h-2.5 w-2.5 rounded-full bg-[#ec4899]" />
          Chọn tên của bạn
        </h1>
        <p className="mt-1 text-sm text-[#71717a]">
          Mỗi người có không gian làm việc riêng. Bấm đúng tên của bạn để vào.
        </p>
      </div>

      <div className="relative mb-6">
        <Search
          size={18}
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#a1a1aa]"
        />
        <input
          autoFocus
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Tìm tên của bạn..."
          className="h-12 w-full rounded-xl border border-[#e4e4e7] bg-white pl-10 pr-3 text-base text-[#171717] shadow-[0_1px_3px_rgba(0,0,0,0.05)] outline-none focus:border-[#ec4899] focus:ring-2 focus:ring-[#ec4899]/15"
        />
      </div>

      <div className="space-y-6">
        {groups.length === 0 && (
          <p className="text-center text-sm text-[#888888]">
            Không tìm thấy nhân viên phù hợp.
          </p>
        )}
        {groups.map(({ dept, people }) => (
          <section key={dept}>
            <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[#a1a1aa]">
              {ROLE_LABEL[departmentToRole(dept)]} ({people.length})
            </h2>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {people.map((p) => (
                <form key={p.id} action={chooseStaffIdentity}>
                  <input type="hidden" name="staffId" value={p.id} />
                  <button
                    type="submit"
                    className="w-full rounded-xl border border-[#e4e4e7] bg-white px-3 py-3 text-left text-sm font-medium text-[#171717] shadow-[0_1px_2px_rgba(0,0,0,0.04)] transition-colors hover:border-[#ec4899] hover:bg-[#fdf2f8] active:bg-[#fce7f3]"
                  >
                    {p.full_name}
                  </button>
                </form>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
