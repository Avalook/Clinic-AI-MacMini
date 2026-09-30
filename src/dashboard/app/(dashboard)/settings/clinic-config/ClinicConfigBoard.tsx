"use client";

// Quản lý tự khai cấu trúc phòng khám của mình.
//
// MỘT TRANG, HAI PHẦN — không tách thành hai màn. Ba câu hỏi ở đây ("phòng nào
// ở tầng nào", "phòng nào làm siêu âm", "bác sĩ nào khám được gì") luôn được
// hỏi cùng lúc: người khai vừa đánh dấu SA1 là phòng siêu âm thì câu tiếp theo
// là ai đứng ở đó. Tách ra là bắt họ nhớ giữa hai lần tải trang.
//
// MỌI THAO TÁC GHI ĐỀU LẠC QUAN rồi hoàn tác khi hỏng. Đây là màn cấu hình, tần
// suất bấm cao và mạng ra Seoul mất ~200ms mỗi lượt; chờ máy chủ trả lời mới đổi
// giao diện thì mỗi ô tick giật một nhịp.

import { useState, useTransition } from "react";

import CoSoPhong from "./CoSoPhong";
import { Users, Check, AlertTriangle, ClipboardList } from "lucide-react";
import type {
  ConfigLocation,
  ConfigMissing,
  ConfigService,
  ConfigStaff,
  FormDef,
  NodeDef,
  ViecChonDuoc,
} from "./types";

export default function ClinicConfigBoard({
  initialLocations,
  initialStaff,
  initialServices,
  nodes,
  viecChonDuoc,
  forms,
  ok,
  configMissing,
}: {
  initialLocations: ConfigLocation[];
  initialStaff: ConfigStaff[];
  initialServices: ConfigService[];
  nodes: NodeDef[];
  viecChonDuoc: ViecChonDuoc[];
  configMissing: ConfigMissing[];
  forms: FormDef[];
  ok: boolean;
}) {
  const [locations, setLocations] = useState(initialLocations);
  const [staff, setStaff] = useState(initialStaff);
  const [services, setServices] = useState(initialServices);
  const [err, setErr] = useState<string | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  async function send(what: string, payload: Record<string, unknown>) {
    const res = await fetch("/api/clinic-config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ what, ...payload }),
    });
    if (!res.ok) {
      const body = (await res.json().catch(() => ({}))) as {
        error?: string;
        detail?: string;
      };
      // Backend nói bằng câu người vận hành đọc được ("Phòng SA1 lấy
      // DICHVU-SIEUAM làm bước chính…"). Hiện nguyên câu đó, đừng thay bằng
      // "Lưu thất bại" — câu chung chung không cho biết phải sửa gì.
      throw new Error(body.detail ?? body.error ?? "Không lưu được.");
    }
  }

  // ── Phòng là TÀI NGUYÊN (CORE-C, 23/09/2026) ──────────────────────────────
  // Định danh là room_id; tên đổi tự do. Sau mỗi lệnh thêm/đổi/bật-tắt thì đọc
  // lại sơ đồ từ máy chủ — không tự đoán trạng thái sau khi tạo phòng mới.
  const [thieu, setThieu] = useState(configMissing);
  const [viec, setViec] = useState(viecChonDuoc);

  async function docLai() {
    const r = await fetch("/api/clinic-config?what=overview", { cache: "no-store" });
    const d = (await r.json().catch(() => null)) as {
      locations?: ConfigLocation[];
      config_missing?: ConfigMissing[];
      viec_chon_duoc?: ViecChonDuoc[];
    } | null;
    if (d?.locations) setLocations(d.locations);
    if (d?.config_missing) setThieu(d.config_missing);
    if (d?.viec_chon_duoc) setViec(d.viec_chon_duoc);
  }







  function saveServiceForm(
    id: string,
    field: "form_code" | "form_code_nam",
    value: string,
  ) {
    const truoc = services;
    const sv = services.find((x) => x.service_type_id === id);
    if (!sv) return;
    const next = { ...sv, [field]: value || null };
    setServices(services.map((x) => (x.service_type_id === id ? next : x)));
    setErr(null);
    startTransition(async () => {
      try {
        await send("service-form", {
          service_type_id: id,
          form_code: next.form_code,
          form_code_nam: next.form_code_nam,
        });
        setSaved(id);
      } catch (e) {
        setServices(truoc);
        setErr(e instanceof Error ? e.message : String(e));
      }
    });
  }

  function saveDefaultPrice(id: string, raw: string) {
    const parsed = Number(raw);
    if (!Number.isFinite(parsed) || parsed < 0) {
      setErr("Giá mặc định phải là số không âm.");
      return;
    }
    const gia = Math.round(parsed);
    const truoc = services;
    setServices(
      services.map((s) =>
        s.service_type_id === id ? { ...s, gia_mac_dinh: gia } : s,
      ),
    );
    setErr(null);
    startTransition(async () => {
      try {
        await send("service-type", { service_type_id: id, gia_mac_dinh: gia });
        setSaved(id);
      } catch (e) {
        setServices(truoc);
        setErr(e instanceof Error ? e.message : String(e));
      }
    });
  }

  function toggleStaffNode(staffId: string, code: string) {
    const truoc = staff;
    const person = staff.find((s) => s.staff_id === staffId);
    if (!person) return;
    const next = person.nodes.includes(code)
      ? person.nodes.filter((c) => c !== code)
      : [...person.nodes, code].sort();
    setStaff(
      staff.map((s) => (s.staff_id === staffId ? { ...s, nodes: next } : s)),
    );
    setErr(null);
    startTransition(async () => {
      try {
        await send("staff-nodes", { staff_id: staffId, node_codes: next });
        setSaved(staffId);
      } catch (e) {
        setStaff(truoc);
        setErr(e instanceof Error ? e.message : String(e));
      }
    });
  }

  function toggleThuKyBacSi(thuKyId: string, bacSiId: string) {
    const truoc = staff;
    const tk = staff.find((s) => s.staff_id === thuKyId);
    if (!tk) return;
    const hienTai = tk.bac_si ?? [];
    const next = hienTai.includes(bacSiId)
      ? hienTai.filter((x) => x !== bacSiId)
      : [...hienTai, bacSiId];
    setStaff(
      staff.map((s) => (s.staff_id === thuKyId ? { ...s, bac_si: next } : s)),
    );
    setErr(null);
    startTransition(async () => {
      try {
        await send("thu-ky-bac-si", {
          thu_ky_staff_id: thuKyId,
          bac_si_staff_ids: next,
        });
        setSaved(thuKyId);
      } catch (e) {
        setStaff(truoc);
        setErr(e instanceof Error ? e.message : String(e));
      }
    });
  }

  const thuKy = staff.filter((s) => s.role === "TKYK");
  const bacSi = staff.filter(
    (s) => s.role === "DOCTOR" || s.role === "ULTRASOUND_DOCTOR",
  );

  if (!ok) {
    return (
      <div className="rounded-card border border-danger bg-danger-bg px-4 py-3 text-sm text-danger">
        Không đọc được cấu hình phòng khám từ máy chủ. Chưa sửa được gì lúc này
        — thử tải lại trang.
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {err && (
        <div
          role="alert"
          className="flex items-start gap-2 rounded-card border border-danger bg-danger-bg px-4 py-3 text-sm text-danger"
        >
          <AlertTriangle size={16} className="mt-0.5 shrink-0" />
          <span>{err}</span>
        </div>
      )}

      {thieu.length > 0 && (
        <div
          role="status"
          className="flex items-start gap-2 rounded-card border border-warning bg-warning-bg px-4 py-3 text-sm text-warning"
        >
          <AlertTriangle size={16} className="mt-0.5 shrink-0" />
          <span>
            <b>Chưa có phòng nào làm:</b> {thieu.map((t) => t.name).join(" · ")}. Chỉ
            định các dịch vụ này sẽ không xếp được phòng — gắn dịch vụ (hoặc cả
            nhóm) vào một phòng đang bật ở mục &quot;Phòng làm việc gì&quot;.
          </span>
        </div>
      )}

      {/* ── Cơ sở → phòng: gọn, bấm mới mở (27/09/2026) — xem CoSoPhong.tsx. */}
      <CoSoPhong
        locations={locations}
        nodes={nodes}
        viec={viec}
        staff={staff}
        onDocLai={docLai}
        onLoi={setErr}
      />

      {/* ── Dịch vụ nào dùng phiếu khám nào ─────────────────────────────── */}
      <section className="rounded-card border border-line bg-surface shadow-card">
        <header className="flex items-center gap-2 border-b border-line px-4 py-3">
          <ClipboardList size={18} className="shrink-0 text-brand-600" />
          <h2 className="text-base font-semibold text-ink">
            Dịch vụ khám: phiếu và giá mặc định
          </h2>
          <span className="ml-auto text-xs text-ink-muted">
            {services.filter((s) => s.form_code).length}/{services.length} đã gán
          </span>
        </header>
        <p className="border-b border-line px-4 py-2 text-xs text-ink-muted">
          Giá mặc định được tính khi chưa chọn dịch vụ khám con. Bác sĩ mở lượt
          khám sẽ thấy đúng phiếu khai ở đây. Để trống nghĩa là
          dịch vụ này không có phiếu chuyên khoa (thủ thuật, tư vấn) — màn bác
          sĩ sẽ nói rõ điều đó thay vì để trống. Cột{" "}
          <span className="font-medium text-ink">nam</span> chỉ khai khi nội
          dung khám khác nhau theo giới, ví dụ khám tiền hôn nhân: nữ khám phụ
          khoa, nam khám nam khoa.
        </p>
        <ul className="divide-y divide-brand-100">
          {services.map((s) => (
            <li
              key={s.service_type_id}
              className="flex flex-wrap items-center gap-2 px-4 py-2.5"
            >
              <span className="min-w-0 flex-1 truncate text-ink">
                {s.name}
                {!s.is_active && (
                  <span className="ml-2 text-label text-ink-muted">(ngưng)</span>
                )}
              </span>
              {saved === s.service_type_id && !isPending && (
                <Check size={14} className="shrink-0 text-success" />
              )}
              <label className="flex items-center gap-1.5 text-xs text-ink-muted">
                Giá mặc định
                <input
                  key={`${s.service_type_id}-${s.gia_mac_dinh}`}
                  type="number"
                  min={0}
                  step={1000}
                  defaultValue={s.gia_mac_dinh}
                  disabled={isPending}
                  onBlur={(e) => saveDefaultPrice(s.service_type_id, e.target.value)}
                  className="w-32 rounded-control border border-line bg-surface px-2 py-1 text-right text-sm tabular-nums text-ink disabled:opacity-60"
                />
                đ
              </label>
              <label className="flex items-center gap-1.5 text-xs text-ink-muted">
                Phiếu
                <select
                  value={s.form_code ?? ""}
                  disabled={isPending}
                  onChange={(e) =>
                    saveServiceForm(s.service_type_id, "form_code", e.target.value)
                  }
                  className="rounded-control border border-line bg-surface px-2 py-1 text-sm text-ink disabled:opacity-60"
                >
                  <option value="">— không có —</option>
                  {forms.map((f) => (
                    <option key={f.form_code} value={f.form_code}>
                      {f.title}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex items-center gap-1.5 text-xs text-ink-muted">
                nếu là nam
                <select
                  value={s.form_code_nam ?? ""}
                  disabled={isPending || !s.form_code}
                  onChange={(e) =>
                    saveServiceForm(
                      s.service_type_id,
                      "form_code_nam",
                      e.target.value,
                    )
                  }
                  className="rounded-control border border-line bg-surface px-2 py-1 text-sm text-ink disabled:opacity-60"
                >
                  <option value="">— như trên —</option>
                  {forms.map((f) => (
                    <option key={f.form_code} value={f.form_code}>
                      {f.title}
                    </option>
                  ))}
                </select>
              </label>
            </li>
          ))}
          {services.length === 0 && (
            <li className="px-4 py-6 text-center text-sm text-ink-muted">
              Chưa khai dịch vụ nào.
            </li>
          )}
        </ul>
      </section>

      {/* ── Ai làm được bước nào ────────────────────────────────────────── */}
      <section className="rounded-card border border-line bg-surface shadow-card">
        <header className="flex items-center gap-2 border-b border-line px-4 py-3">
          <Users size={18} className="shrink-0 text-brand-600" />
          <h2 className="text-base font-semibold text-ink">
            Ai làm được bước nào
          </h2>
          <span className="ml-auto text-xs text-ink-muted">
            {staff.length} người
          </span>
        </header>
        <p className="border-b border-line px-4 py-2 text-xs text-ink-muted">
          Bác sĩ khám cả 5 chuyên khoa, hay chỉ 2–3, hay chỉ siêu âm — đánh dấu
          ở đây. Không đánh dấu gì là hợp lệ: lễ tân và thu ngân không đảm nhiệm
          bước khám nào.
        </p>
        <ul className="divide-y divide-brand-100">
          {staff.map((s) => (
            <li key={s.staff_id} className="px-4 py-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium text-ink">{s.full_name}</span>
                <span className="text-xs text-ink-muted">{s.role}</span>
                {s.location_name && (
                  <span className="text-xs text-ink-muted">
                    · {s.location_name}
                  </span>
                )}
                {saved === s.staff_id && !isPending && (
                  <Check size={14} className="text-success" />
                )}
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {nodes.map((n) => {
                  const on = s.nodes.includes(n.code);
                  return (
                    <button
                      key={n.code}
                      type="button"
                      disabled={isPending}
                      onClick={() => toggleStaffNode(s.staff_id, n.code)}
                      title={n.code}
                      className={`rounded-full border px-2.5 py-1 text-xs transition-colors duration-150 disabled:opacity-60 ${
                        on
                          ? "border-brand-400 bg-brand-100 text-brand-800"
                          : "border-line bg-surface text-ink-muted hover:bg-brand-50"
                      }`}
                    >
                      {n.name}
                    </button>
                  );
                })}
              </div>
            </li>
          ))}
          {staff.length === 0 && (
            <li className="px-4 py-6 text-center text-sm text-ink-muted">
              Chưa có nhân sự đang hoạt động.
            </li>
          )}
        </ul>
      </section>

      {/* ── Thư ký đi cùng bác sĩ nào (Tuyền chốt 15/09/2026) ──────────── */}
      <section className="rounded-card border border-line bg-surface shadow-card">
        <header className="flex items-center gap-2 border-b border-line px-4 py-3">
          <Users size={18} className="shrink-0 text-brand-600" />
          <h2 className="text-base font-semibold text-ink">
            Thư ký đi cùng bác sĩ
          </h2>
          <span className="ml-auto text-xs text-ink-muted">
            {thuKy.length} thư ký
          </span>
        </header>
        <p className="border-b border-line px-4 py-2 text-xs text-ink-muted">
          Thư ký chỉ thấy và làm việc cho khách của bác sĩ được đánh dấu. Chưa
          đánh dấu ai thì thư ký không thấy khách nào.
        </p>
        <ul className="divide-y divide-brand-100">
          {thuKy.map((s) => (
            <li key={s.staff_id} className="px-4 py-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium text-ink">{s.full_name}</span>
                {saved === s.staff_id && !isPending && (
                  <Check size={14} className="text-success" />
                )}
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {bacSi.map((b) => {
                  const on = (s.bac_si ?? []).includes(b.staff_id);
                  return (
                    <button
                      key={b.staff_id}
                      type="button"
                      disabled={isPending}
                      onClick={() => toggleThuKyBacSi(s.staff_id, b.staff_id)}
                      className={`rounded-full border px-2.5 py-1 text-xs transition-colors duration-150 disabled:opacity-60 ${
                        on
                          ? "border-brand-400 bg-brand-100 text-brand-800"
                          : "border-line bg-surface text-ink-muted hover:bg-brand-50"
                      }`}
                    >
                      {b.full_name}
                    </button>
                  );
                })}
              </div>
            </li>
          ))}
          {thuKy.length === 0 && (
            <li className="px-4 py-6 text-center text-sm text-ink-muted">
              Chưa có thư ký y khoa đang hoạt động.
            </li>
          )}
        </ul>
      </section>
    </div>
  );
}
