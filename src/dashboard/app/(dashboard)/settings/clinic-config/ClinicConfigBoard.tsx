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
import { Layers, DoorOpen, Users, Check, AlertTriangle, ClipboardList } from "lucide-react";
import Button from "@/components/ui/Button";
import type {
  ConfigLocation,
  ConfigMissing,
  ConfigService,
  ConfigStaff,
  FormDef,
  NodeDef,
} from "./types";

const CHUA_KHAI = "— chưa khai tầng —";

export default function ClinicConfigBoard({
  initialLocations,
  initialStaff,
  initialServices,
  nodes,
  forms,
  ok,
  configMissing,
}: {
  initialLocations: ConfigLocation[];
  initialStaff: ConfigStaff[];
  initialServices: ConfigService[];
  nodes: NodeDef[];
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
  const [moi, setMoi] = useState<Record<string, { ten: string; buoc: string; tang: string }>>({});

  async function docLai() {
    const r = await fetch("/api/clinic-config?what=overview", { cache: "no-store" });
    const d = (await r.json().catch(() => null)) as {
      locations?: ConfigLocation[];
      config_missing?: ConfigMissing[];
    } | null;
    if (d?.locations) setLocations(d.locations);
    if (d?.config_missing) setThieu(d.config_missing);
  }

  function lamRoiDocLai(viec: () => Promise<void>, khoa: string) {
    setErr(null);
    startTransition(async () => {
      try {
        await viec();
        await docLai();
        setSaved(khoa);
      } catch (e) {
        setErr(e instanceof Error ? e.message : String(e));
      }
    });
  }

  function doiTenPhong(roomId: string, ten: string) {
    lamRoiDocLai(() => send("room-name", { room_id: roomId, name: ten }), roomId);
  }

  function batTatPhong(roomId: string, bat: boolean) {
    lamRoiDocLai(() => send("room-active", { room_id: roomId, is_active: bat }), roomId);
  }

  function themPhong(locationId: string) {
    const f = moi[locationId];
    if (!f?.ten.trim() || !f.buoc) {
      setErr("Nhập tên phòng và chọn phòng làm việc gì.");
      return;
    }
    lamRoiDocLai(async () => {
      const res = await fetch("/api/clinic-config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          what: "room-create",
          location_id: locationId,
          name: f.ten.trim(),
          node_code: f.buoc,
          floor: f.tang.trim() || null,
        }),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { detail?: string; error?: string };
        throw new Error(body.detail ?? body.error ?? "Không thêm được phòng.");
      }
      setMoi((m) => ({ ...m, [locationId]: { ten: "", buoc: "", tang: "" } }));
    }, locationId);
  }

  function saveRoomFloor(roomId: string, floor: string) {
    const truoc = locations;
    setLocations(moveRoomToFloor(locations, roomId, floor.trim() || null));
    setErr(null);
    startTransition(async () => {
      try {
        await send("room-floor", { room_id: roomId, floor });
        setSaved(roomId);
      } catch (e) {
        setLocations(truoc);
        setErr(e instanceof Error ? e.message : String(e));
      }
    });
  }

  function toggleRoomNode(roomId: string, code: string) {
    const truoc = locations;
    const room = findRoom(locations, roomId);
    if (!room) return;
    const next = room.serves.includes(code)
      ? room.serves.filter((c) => c !== code)
      : [...room.serves, code].sort();
    setLocations(setRoomServes(locations, roomId, next));
    setErr(null);
    startTransition(async () => {
      try {
        await send("room-nodes", { room_id: roomId, node_codes: next });
        setSaved(roomId);
      } catch (e) {
        setLocations(truoc);
        setErr(e instanceof Error ? e.message : String(e));
      }
    });
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
            định vào các bước này sẽ không xếp được phòng — thêm phòng hoặc gắn
            bước vào một phòng có sẵn.
          </span>
        </div>
      )}

      {/* ── Sơ đồ: cơ sở → tầng → phòng ─────────────────────────────────── */}
      {locations.map((loc) => (
        <section
          key={loc.location_id}
          className="rounded-card border border-line bg-surface shadow-card"
        >
          <header className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-3">
            <DoorOpen size={18} className="shrink-0 text-brand-600" />
            <h2 className="text-base font-semibold text-ink">{loc.name}</h2>
            <span className="text-xs text-ink-muted">{loc.code}</span>
            {!loc.is_active && (
              <span className="rounded-full bg-brand-100 px-2 py-0.5 text-label text-ink-muted">
                ngừng hoạt động
              </span>
            )}
            <span className="ml-auto text-xs text-ink-muted">
              {loc.floors.length} tầng ·{" "}
              {loc.floors.reduce((n, f) => n + f.rooms.length, 0)} phòng
            </span>
          </header>

          <div className="divide-y divide-brand-100">
            {loc.floors.map((f) => (
              <div key={f.floor ?? "__chua_khai__"} className="px-4 py-3">
                <div className="mb-2 flex items-center gap-1.5">
                  <Layers size={14} className="shrink-0 text-ink-muted" />
                  <span
                    className={
                      f.floor === null
                        ? "text-sm font-medium text-warning"
                        : "text-sm font-medium text-ink"
                    }
                  >
                    {f.floor === null ? CHUA_KHAI : `Tầng ${f.floor}`}
                  </span>
                </div>

                <ul className="space-y-2">
                  {f.rooms.map((r) => (
                    <li
                      key={r.room_id}
                      className="rounded-lg border border-line bg-brand-50/40 p-3"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        {/* TÊN là dữ liệu hiển thị — đổi tự do, room_id giữ
                            nguyên. Mã nội bộ (r.code) không hiện: nó không mang
                            nghĩa nghiệp vụ nào (CORE-C, 23/09/2026). */}
                        <input
                          type="text"
                          aria-label="Tên phòng"
                          defaultValue={r.name ?? ""}
                          maxLength={80}
                          disabled={isPending}
                          onBlur={(e) => {
                            const ten = e.target.value.trim();
                            if (ten && ten !== (r.name ?? "")) doiTenPhong(r.room_id, ten);
                          }}
                          className="min-w-0 flex-1 rounded-control border border-line bg-surface px-2 py-1 font-medium text-ink disabled:opacity-60"
                        />
                        {!r.is_active && (
                          <span className="text-label text-ink-muted">
                            (đang tắt)
                          </span>
                        )}
                        <Button
                          type="button"
                          size="sm"
                          variant={r.is_active ? "ghost" : "secondary"}
                          disabled={isPending}
                          onClick={() => batTatPhong(r.room_id, !r.is_active)}
                        >
                          {r.is_active ? "Tắt phòng" : "Bật phòng"}
                        </Button>
                        {saved === r.room_id && !isPending && (
                          <Check size={14} className="text-success" />
                        )}
                        <label className="ml-auto flex items-center gap-1.5 text-xs text-ink-muted">
                          Tầng
                          <input
                            type="text"
                            defaultValue={f.floor ?? ""}
                            placeholder="1 · Trệt · B1"
                            maxLength={40}
                            disabled={isPending}
                            onBlur={(e) => {
                              if ((e.target.value.trim() || null) !== f.floor)
                                saveRoomFloor(r.room_id, e.target.value);
                            }}
                            className="w-28 rounded-control border border-line bg-surface px-2 py-1 text-sm text-ink disabled:opacity-60"
                          />
                        </label>
                      </div>

                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {nodes.map((n) => {
                          const on = r.serves.includes(n.code);
                          const isPrimary = r.primary_node === n.code;
                          return (
                            <button
                              key={n.code}
                              type="button"
                              disabled={isPending}
                              onClick={() => toggleRoomNode(r.room_id, n.code)}
                              title={
                                isPrimary
                                  ? "Bước chính của phòng — đổi bước chính trước khi bỏ"
                                  : n.code
                              }
                              className={`rounded-full border px-2.5 py-1 text-xs transition-colors duration-150 disabled:opacity-60 ${
                                on
                                  ? "border-brand-400 bg-brand-100 text-brand-800"
                                  : "border-line bg-surface text-ink-muted hover:bg-brand-50"
                              }`}
                            >
                              {isPrimary && "★ "}
                              {n.name}
                            </button>
                          );
                        })}
                      </div>
                    </li>
                  ))}
                  {f.rooms.length === 0 && (
                    <li className="text-sm text-ink-muted">Chưa có phòng.</li>
                  )}
                </ul>
              </div>
            ))}
            {loc.floors.length === 0 && (
              <p className="px-4 py-6 text-center text-sm text-ink-muted">
                Cơ sở này chưa khai phòng nào.
              </p>
            )}
            {/* THÊM PHÒNG: tên tự do + phòng làm việc gì (bước chính, bắt buộc)
                + tầng. Thêm bước khác sau bằng các nút bước của phòng. */}
            <div className="flex flex-wrap items-end gap-2 px-4 py-3">
              <label className="flex min-w-0 flex-1 flex-col gap-1 text-xs text-ink-muted">
                Tên phòng mới
                <input
                  type="text"
                  maxLength={80}
                  placeholder="VD: Phòng 201 · Siêu âm 1 · Phòng Hoa"
                  value={moi[loc.location_id]?.ten ?? ""}
                  onChange={(e) =>
                    setMoi((m) => ({
                      ...m,
                      [loc.location_id]: {
                        ...(m[loc.location_id] ?? { ten: "", buoc: "", tang: "" }),
                        ten: e.target.value,
                      },
                    }))
                  }
                  className="rounded-control border border-line bg-surface px-2 py-1 text-sm text-ink"
                />
              </label>
              <label className="flex flex-col gap-1 text-xs text-ink-muted">
                Làm việc gì
                <select
                  value={moi[loc.location_id]?.buoc ?? ""}
                  onChange={(e) =>
                    setMoi((m) => ({
                      ...m,
                      [loc.location_id]: {
                        ...(m[loc.location_id] ?? { ten: "", buoc: "", tang: "" }),
                        buoc: e.target.value,
                      },
                    }))
                  }
                  className="rounded-control border border-line bg-surface px-2 py-1 text-sm text-ink"
                >
                  <option value="">— chọn —</option>
                  {nodes.map((n) => (
                    <option key={n.code} value={n.code}>
                      {n.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex flex-col gap-1 text-xs text-ink-muted">
                Tầng
                <input
                  type="text"
                  maxLength={40}
                  placeholder="1 · Trệt"
                  value={moi[loc.location_id]?.tang ?? ""}
                  onChange={(e) =>
                    setMoi((m) => ({
                      ...m,
                      [loc.location_id]: {
                        ...(m[loc.location_id] ?? { ten: "", buoc: "", tang: "" }),
                        tang: e.target.value,
                      },
                    }))
                  }
                  className="w-24 rounded-control border border-line bg-surface px-2 py-1 text-sm text-ink"
                />
              </label>
              <Button
                type="button"
                size="sm"
                variant="primary"
                disabled={isPending}
                onClick={() => themPhong(loc.location_id)}
              >
                + Thêm phòng
              </Button>
            </div>
          </div>
        </section>
      ))}

      {/* ── Dịch vụ nào dùng phiếu khám nào ─────────────────────────────── */}
      <section className="rounded-card border border-line bg-surface shadow-card">
        <header className="flex items-center gap-2 border-b border-line px-4 py-3">
          <ClipboardList size={18} className="shrink-0 text-brand-600" />
          <h2 className="text-base font-semibold text-ink">
            Dịch vụ nào dùng phiếu khám nào
          </h2>
          <span className="ml-auto text-xs text-ink-muted">
            {services.filter((s) => s.form_code).length}/{services.length} đã gán
          </span>
        </header>
        <p className="border-b border-line px-4 py-2 text-xs text-ink-muted">
          Bác sĩ mở lượt khám sẽ thấy đúng phiếu khai ở đây. Để trống nghĩa là
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

// ── Sửa cây cơ sở → tầng → phòng tại chỗ ───────────────────────────────────
//
// Đổi tầng là DI CHUYỂN phòng sang nhóm khác, không phải đổi một chữ. Viết
// riêng để phần giao diện ở trên không phải lồng ba vòng lặp.

function findRoom(locs: ConfigLocation[], roomId: string) {
  for (const l of locs)
    for (const f of l.floors) {
      const r = f.rooms.find((x) => x.room_id === roomId);
      if (r) return r;
    }
  return null;
}

function setRoomServes(
  locs: ConfigLocation[],
  roomId: string,
  serves: string[],
): ConfigLocation[] {
  return locs.map((l) => ({
    ...l,
    floors: l.floors.map((f) => ({
      ...f,
      rooms: f.rooms.map((r) => (r.room_id === roomId ? { ...r, serves } : r)),
    })),
  }));
}

function moveRoomToFloor(
  locs: ConfigLocation[],
  roomId: string,
  floor: string | null,
): ConfigLocation[] {
  return locs.map((l) => {
    const room = l.floors.flatMap((f) => f.rooms).find((r) => r.room_id === roomId);
    if (!room) return l;

    const goc = l.floors
      .map((f) => ({ ...f, rooms: f.rooms.filter((r) => r.room_id !== roomId) }))
      // Tầng rỗng sau khi chuyển đi thì BỎ — trừ "chưa khai", vì ô đó là lời
      // nhắc còn việc phải làm và biến mất sẽ đọc thành "đã khai xong".
      .filter((f) => f.rooms.length > 0 || f.floor === null);

    const dich = goc.find((f) => f.floor === floor);
    if (dich) {
      return {
        ...l,
        floors: goc.map((f) =>
          f === dich ? { ...f, rooms: [...f.rooms, room] } : f,
        ),
      };
    }
    return { ...l, floors: [...goc, { floor, rooms: [room] }] };
  });
}
