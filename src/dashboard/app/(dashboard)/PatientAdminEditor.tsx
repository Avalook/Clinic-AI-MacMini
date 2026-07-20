"use client";

// Sửa THÔNG TIN HÀNH CHÍNH của bệnh nhân (mục I) — dùng CHUNG cho: popup hồ sơ
// ("Công việc của tôi" + "Danh sách bệnh nhân"), trang "Thông tin khách hàng",
// và trang chi tiết BN. Xem → bấm "Sửa" → form → "Lưu" gọi PATCH /api/patients.
// KHÔNG đụng CCCD (D-identity) và KHÔNG đổi cơ sở (location) ở đây — chỉ các
// trường hành chính. Quyền ghi do server gate (canEditPatient); chỉ render khi
// caller cho phép (canEdit).

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Pencil } from "lucide-react";
import { fmtDate } from "../../lib/datetime";
import { todayVn } from "../../lib/roster";
import { digitsOnly, phoneError } from "../../lib/validation";
import { INPUT, LABEL } from "./form-ui";
import DateField from "./DateField";
import { linhVucLabel } from "../../lib/linh-vuc";

export interface PatientAdmin {
  clinic_patient_id: string;
  full_name: string;
  date_of_birth: string | null;
  phone_primary: string | null;
  phone_secondary: string | null;
  gender: string | null;
  ethnicity: string | null;
  nationality: string | null;
  occupation: string | null;
  patient_objection: string | null;
  address: string | null;
  guardian_name: string | null;
  // CSKH (đặt lịch) — CHỈ HIỂN THỊ ở đây (đọc), KHÔNG sửa trong editor này nên
  // PATCH KHÔNG đụng (tránh ghi đè null). Optional: nguồn nào không select vẫn build được.
  van_de_di_kham?: string | null;
  linh_vuc?: string | null;
}

type Form = {
  full_name: string;
  date_of_birth: string;
  phone_primary: string;
  phone_secondary: string;
  gender: string;
  ethnicity: string;
  nationality: string;
  occupation: string;
  patient_objection: string;
  address: string;
  guardian_name: string;
};

function toForm(p: PatientAdmin): Form {
  return {
    full_name: p.full_name ?? "",
    date_of_birth: p.date_of_birth ?? "",
    phone_primary: p.phone_primary ?? "",
    phone_secondary: p.phone_secondary ?? "",
    gender: p.gender ?? "",
    ethnicity: p.ethnicity ?? "",
    nationality: p.nationality ?? "",
    occupation: p.occupation ?? "",
    patient_objection: p.patient_objection ?? "",
    address: p.address ?? "",
    guardian_name: p.guardian_name ?? "",
  };
}

function Row({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="flex gap-2 text-sm">
      <dt className="w-24 shrink-0 text-[#888888]">{label}</dt>
      <dd className="min-w-0 break-words font-medium text-[#171717]">
        {value || "—"}
      </dd>
    </div>
  );
}

export default function PatientAdminEditor({
  patient,
}: {
  patient: PatientAdmin;
}) {
  const router = useRouter();
  const [cur, setCur] = useState<PatientAdmin>(patient);
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<Form>(() => toForm(patient));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  const set = (k: keyof Form, v: string) => setForm((f) => ({ ...f, [k]: v }));

  function startEdit() {
    setForm(toForm(cur));
    setEditing(true);
    setError(null);
    setMsg(null);
  }

  async function save() {
    if (!form.full_name.trim()) return setError("Phải nhập họ tên.");
    const ve =
      phoneError(form.phone_primary) || phoneError(form.phone_secondary);
    if (ve) return setError(ve);
    setBusy(true);
    setError(null);
    const res = await fetch("/api/patients", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ clinic_patient_id: cur.clinic_patient_id, ...form }),
    });
    setBusy(false);
    if (!res.ok) return setError((await res.json()).error ?? "Lỗi lưu.");
    // Cập nhật hiển thị NGAY + đồng bộ phần còn lại của trang (server refetch).
    setCur({ ...cur, ...form });
    setEditing(false);
    setMsg("Đã lưu thông tin.");
    router.refresh();
  }

  if (!editing) {
    return (
      <div className="space-y-2">
        <dl className="grid gap-x-4 gap-y-1.5 sm:grid-cols-2">
          <Row label="Họ tên" value={cur.full_name} />
          <Row
            label="Ngày sinh"
            value={cur.date_of_birth ? fmtDate(cur.date_of_birth) : null}
          />
          <Row label="Giới tính" value={cur.gender} />
          <Row label="Dân tộc" value={cur.ethnicity} />
          <Row label="Quốc tịch" value={cur.nationality} />
          <Row label="Nghề nghiệp" value={cur.occupation} />
          <Row label="Đối tượng" value={cur.patient_objection} />
          <Row label="SĐT" value={cur.phone_primary} />
          <Row label="SĐT người nhà" value={cur.phone_secondary} />
          <Row label="Người giám hộ" value={cur.guardian_name} />
          <div className="sm:col-span-2">
            <Row label="Địa chỉ" value={cur.address} />
          </div>
          {cur.linh_vuc && (
            <Row label="Lĩnh vực" value={linhVucLabel(cur.linh_vuc)} />
          )}
          {cur.van_de_di_kham && (
            <div className="sm:col-span-2">
              <Row label="Vấn đề đi khám" value={cur.van_de_di_kham} />
            </div>
          )}
        </dl>
        <div className="flex items-center gap-2">
          <button
            onClick={startEdit}
            className="inline-flex min-h-8 items-center gap-1 rounded-md border border-[#f3cfe0] bg-white px-2.5 text-xs font-medium text-[#9d2463] hover:bg-[#fdf2f8]"
          >
            <Pencil size={12} /> Sửa thông tin
          </button>
          {msg && <span className="text-xs text-[#15803d]">{msg}</span>}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="grid gap-2 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <label className={LABEL}>Họ tên</label>
          <input
            className={INPUT}
            value={form.full_name}
            onChange={(e) => set("full_name", e.target.value)}
          />
        </div>
        <div>
          <label className={LABEL}>Ngày sinh</label>
          <DateField
            value={form.date_of_birth}
            onChange={(v) => set("date_of_birth", v)}
            max={todayVn()}
            ariaLabel="Ngày sinh"
          />
        </div>
        <div>
          <label className={LABEL}>Giới tính</label>
          <select
            className={INPUT}
            value={form.gender}
            onChange={(e) => set("gender", e.target.value)}
          >
            <option value="">— Chọn —</option>
            <option value="Nữ">Nữ</option>
            <option value="Nam">Nam</option>
            <option value="Khác">Khác</option>
          </select>
        </div>
        <div>
          <label className={LABEL}>SĐT chính</label>
          <input
            className={INPUT}
            inputMode="numeric"
            maxLength={10}
            placeholder="10 chữ số"
            value={form.phone_primary}
            onChange={(e) =>
              set("phone_primary", digitsOnly(e.target.value).slice(0, 10))
            }
          />
        </div>
        <div>
          <label className={LABEL}>SĐT người nhà</label>
          <input
            className={INPUT}
            inputMode="numeric"
            maxLength={10}
            placeholder="10 chữ số"
            value={form.phone_secondary}
            onChange={(e) =>
              set("phone_secondary", digitsOnly(e.target.value).slice(0, 10))
            }
          />
        </div>
        <div>
          <label className={LABEL}>Dân tộc</label>
          <input
            className={INPUT}
            value={form.ethnicity}
            onChange={(e) => set("ethnicity", e.target.value)}
          />
        </div>
        <div>
          <label className={LABEL}>Quốc tịch</label>
          <input
            className={INPUT}
            value={form.nationality}
            onChange={(e) => set("nationality", e.target.value)}
          />
        </div>
        <div>
          <label className={LABEL}>Nghề nghiệp</label>
          <input
            className={INPUT}
            value={form.occupation}
            onChange={(e) => set("occupation", e.target.value)}
          />
        </div>
        <div>
          <label className={LABEL}>Đối tượng</label>
          <input
            className={INPUT}
            value={form.patient_objection}
            onChange={(e) => set("patient_objection", e.target.value)}
            placeholder="DV / BHYT / ..."
          />
        </div>
        <div>
          <label className={LABEL}>Người giám hộ</label>
          <input
            className={INPUT}
            value={form.guardian_name}
            onChange={(e) => set("guardian_name", e.target.value)}
          />
        </div>
        <div className="sm:col-span-2">
          <label className={LABEL}>Địa chỉ</label>
          <input
            className={INPUT}
            value={form.address}
            onChange={(e) => set("address", e.target.value)}
            placeholder="Số nhà, đường, phường/xã, tỉnh/thành"
          />
        </div>
      </div>
      {error && <p className="text-xs text-[#dc2626]">{error}</p>}
      <div className="flex gap-2 pt-1">
        <button
          onClick={save}
          disabled={busy}
          className="min-h-10 rounded-lg bg-[#ec4899] px-4 text-sm font-semibold text-white hover:bg-[#db2777] disabled:opacity-50"
        >
          {busy ? "Đang lưu..." : "Lưu thông tin"}
        </button>
        <button
          onClick={() => {
            setEditing(false);
            setError(null);
          }}
          disabled={busy}
          className="min-h-10 rounded-lg border border-[#e4e4e7] bg-white px-4 text-sm text-[#52525b] hover:bg-[#f4f4f5]"
        >
          Huỷ
        </button>
      </div>
    </div>
  );
}
