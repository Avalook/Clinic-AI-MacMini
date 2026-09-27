"use client";

import {
  CheckCircle2,
  Clock3,
  IdCard,
  MapPin,
  Monitor,
  Phone,
  Search,
  ShieldCheck,
  UsersRound,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState, useTransition } from "react";

import PriorityChip from "@/components/ui/PriorityChip";
import StatusChip, { type StatusTone } from "@/components/ui/StatusChip";
import ThanhTab from "@/components/ui/ThanhTab";

import NutXemLuot from "../../_lam-viec/NutXemLuot";
import KhungKhach from "../../_lam-viec/KhungKhach";
import { STATUS_PRESENTATION, resolveStatus } from "@/lib/work-item-status";
import {
  patientLine,
  waitedMinutes,
  type WorklistItem,
} from "@/lib/worklist";
import NutCheckIn from "@/components/ui/NutCheckIn";
import { useThuTuKham } from "./dung-thu-tu-kham";
import { choTruoc } from "./thu-tu-chen";
import type { MaXacMinh } from "@/lib/xac-minh";
import type { WeekApptRow } from "../../home/WeeklyAppointmentsTable";

/** Nút "Vào khám" (mở rồi đóng bước tiếp nhận của kernel cũ) — OFF 24/09/2026.
 *  Tuyền: "bấm check-in là tính luôn rồi" — sau check-in khối Hành trình tự
 *  xếp khách (dây H1/H2), bước tiếp nhận cũ không đẩy ai đi đâu nữa (buổi khám
 *  giả lập 585 thao tác chưa từng bấm nó). Giữ code, tắt bằng cờ này. */
const NUT_VAO_KHAM = false;

type TabDanhSach = "cho" | "da";

/** Khung cuộn của danh sách — hai tab dùng CHUNG một chiều cao. */
const KHUNG_CUON = "max-h-[610px] overflow-y-auto px-1";

type KernelCommand = "start" | "complete";


/** SỐ QUẦY = số tiếp đón chung trong ngày (Tuyền 17/09/2026: "số chung, vào
 *  quầy bác sĩ nào thì lại số riêng sau"). Lịch check-in trước khi có cột này
 *  mới rơi về số riêng của bác sĩ. */
function soQuay(item: WorklistItem): string {
  if (item.so_tiep_don != null) return String(item.so_tiep_don);
  return item.queue_number ?? "—";
}

/** SỐ BOOKING cấp lúc đặt (23/09/2026) — đứng cạnh số quầy. */
function soDat(item: WorklistItem): string {
  return item.so_booking != null ? `#${item.so_booking}` : "—";
}

function time(value: string | null): string {
  return value
    ? new Date(value).toLocaleTimeString("vi-VN", {
        hour: "2-digit",
        minute: "2-digit",
      })
    : "—";
}

function initials(name: string | null): string {
  if (!name) return "BN";
  const words = name.trim().split(/\s+/);
  return words
    .slice(-2)
    .map((word) => word[0]?.toLocaleUpperCase("vi-VN") ?? "")
    .join("");
}


function Row({
  item,
  selected,
  onSelect,
  keoDuoc,
  dangKeo,
  onKeoBatDau,
  onKeoXong,
  onTha,
}: {
  item: WorklistItem;
  selected: boolean;
  onSelect: () => void;
  /** Có tay cầm kéo hay không (chỉ khách đã check-in mới có thứ tự để đổi). */
  keoDuoc: boolean;
  dangKeo: boolean;
  onKeoBatDau: () => void;
  onKeoXong: () => void;
  onTha: () => void;
}) {
  const waited = waitedMinutes(item);

  return (
    // KÉO THẢ NGAY TRONG DANH SÁCH (Tuyền 16/09/2026) — bảng "Thứ tự khám hôm
    // nay" riêng ở trên đã bỏ. Một chỗ hiện hàng đợi, và cũng chính chỗ ấy đổi
    // thứ tự; hai bảng cạnh nhau kể cùng một hàng là hai bảng sẽ lệch nhau.
    <div
      draggable={keoDuoc}
      onDragStart={onKeoBatDau}
      onDragEnd={onKeoXong}
      onDragOver={(e) => {
        if (keoDuoc) e.preventDefault();
      }}
      onDrop={(e) => {
        e.preventDefault();
        onTha();
      }}
      className={`flex w-full items-start gap-1 border-b border-line px-1 py-1 transition-colors last:border-b-0 ${
        dangKeo ? "opacity-50" : ""
      } ${selected ? "rounded-control border border-brand-500 bg-surface-selected shadow-card" : "hover:bg-surface-sunken"}`}
    >
      {/* TAY CẦM — hai gạch ngang nhỏ, đúng quy ước "chỗ này kéo được". Nó
          KHÔNG bọc trong nút chọn: bấm để xem hồ sơ và kéo để đổi thứ tự là
          hai việc khác nhau, gộp một chỗ thì mỗi cú kéo hụt lại đổi người đang
          xem. */}
      <span
        aria-hidden
        title={keoDuoc ? "Kéo để đổi thứ tự khám" : undefined}
        className={`mt-3 flex shrink-0 flex-col gap-[3px] px-1.5 py-2 ${
          keoDuoc ? "cursor-grab text-ink-faint hover:text-ink-muted" : "invisible"
        }`}
      >
        <span className="block h-px w-3 bg-current" />
        <span className="block h-px w-3 bg-current" />
        <span className="block h-px w-3 bg-current" />
      </span>
    <button
      type="button"
      onClick={onSelect}
      aria-current={selected ? "true" : undefined}
      className="min-w-0 flex-1 px-1 py-2 text-left"
    >
      <span className="flex items-start gap-2">
        {/* SỐ THỨ TỰ: bỏ ô viền (Tuyền 16/09/2026) — nó chiếm ba phía chỉ để
            đóng khung hai chữ số. Màu thương hiệu đọc nhanh hơn viền.
            SỐ BOOKING NGAY CẠNH số check-in (Tuyền 24/09/2026). Độ rộng cột
            lấy từ thang (w-9 / w-10 / w-11), không [..px] tự chế. */}
        <span className="w-9 shrink-0 pt-0.5 text-center text-sm font-bold tabular-nums text-brand-700">
          {soQuay(item)}
        </span>
        <span className="w-10 shrink-0 pt-0.5 text-center text-xs font-semibold tabular-nums text-ink-soft">
          {soDat(item)}
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex min-w-0 items-center gap-1.5">
            <span className="truncate text-sm font-semibold text-ink">
              {item.patient.full_name ?? "Chưa rõ tên"}
            </span>
            {item.khach_uu_tien ? (
              <span title={item.uu_tien_ly_do ?? undefined}>
                <PriorityChip priority="P0" />
              </span>
            ) : null}
          </span>
          <span className="block truncate text-xs text-ink-muted">
            {patientLine(item.patient) || item.patient.patient_code || "Chưa đủ thông tin"}
          </span>
          <span className="mt-1 flex items-center justify-between gap-2 text-label">
            <span className="truncate text-ink-muted">
              Check-in {time(item.checked_in_at)}
            </span>
            <span className="truncate text-ink-muted">
              {item.booking_channel === "WALK_IN" ? "Đến trực tiếp" : "Đặt hẹn"}
            </span>
          </span>
        </span>
        {/* CHỜ = phút từ lúc check-in. Không tô "quá SLA" nữa: hạn ấy là của
            bước tiếp nhận cũ (nút "Vào khám" đã tắt), không còn ai đóng nó. */}
        <span className="w-11 shrink-0 pt-1 text-right text-xs font-semibold tabular-nums text-warning">
          {`${waited}′`}
        </span>
      </span>
    </button>
    </div>
  );
}

/** Một dòng "Chờ check-in": lịch hẹn hôm nay, khách chưa tới — bấm là check-in.
 *  Cùng đường với bảng Lịch hẹn hôm nay (`PATCH /api/appointments`
 *  action=checkin): hai đường check-in là hai luật cấp số lệch nhau. */
function ChuaDenRow({ a }: { a: WeekApptRow }) {
  const router = useRouter();
  const [dang, startTransition] = useTransition();
  const [loi, setLoi] = useState<string | null>(null);

  async function checkIn() {
    setLoi(null);
    const res = await fetch("/api/appointments", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: a.id, action: "checkin" }),
    });
    if (!res.ok) {
      const b = (await res.json().catch(() => null)) as { error?: string } | null;
      setLoi(b?.error ?? `Không check-in được (HTTP ${res.status})`);
      return;
    }
    startTransition(() => router.refresh());
  }

  return (
    <div className="border-b border-line px-2 py-2 last:border-b-0">
      <div className="flex items-center gap-2">
        <span className="w-10 shrink-0 text-center text-sm font-bold tabular-nums text-ink-soft">
          {a.so_booking != null ? `#${a.so_booking}` : "—"}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-semibold text-ink">
            {a.patient?.full_name ?? "Chưa rõ tên"}
          </span>
          <span className="block truncate text-xs text-ink-muted">
            Hẹn {time(a.slot_start)}
            {a.booking_channel === "WALK_IN" ? " · đến trực tiếp" : ""}
          </span>
        </span>
        {/* NÚT CHECK-IN Ở MỌI DÒNG (Tuyền 24/09/2026). Ai được check-in do máy
            chủ quyết theo khối quyền — không ẩn theo tên vai ở đây. */}
        <NutCheckIn size="sm" disabled={dang} onChon={() => checkIn()}>
          {dang ? "…" : "Check-in"}
        </NutCheckIn>
      </div>
      {loi ? (
        <p className="mt-1 rounded-control bg-danger-bg px-2 py-1 text-label text-danger">
          {loi}
        </p>
      ) : null}
    </div>
  );
}

export default function QueueBoard({
  items,
  chuaDen = [],
}: {
  items: WorklistItem[];
  /** Lịch hẹn hôm nay chưa check-in (Tuyền 24/09/2026: check-in ngay ở đây). */
  chuaDen?: WeekApptRow[];
}) {
  const [tab, setTab] = useState<TabDanhSach>(chuaDen.length > 0 ? "cho" : "da");
  const [selectedId, setSelectedId] = useState<string | null>(items[0]?.id ?? null);
  const [query, setQuery] = useState("");
  const [dangKeo, setDangKeo] = useState<string | null>(null);
  const { thuTu, dangGhi, loi: loiThuTu, keo } = useThuTuKham();

  // HÀNG ĐỢI = NGƯỜI ĐÃ CHECK-IN (Tuyền chốt 16/09/2026).
  //
  // Trước đó danh sách này gồm CẢ người chưa tới — họ có việc tiếp nhận đang
  // mở nhưng chưa đứng ở quầy, nên "chờ 240 phút" đếm từ lúc đặt lịch chứ
  // không phải lúc đến. Ai chưa tới thì ở bảng Lịch hẹn khám ngoài trang chủ.
  //
  // XẾP THEO THỨ TỰ THẬT, không theo chờ lâu / mã số: `call_order` do backend
  // tính (cùng nguồn với bảng gọi số), và chính nó là thứ lễ tân kéo. Ai chưa
  // có trong bảng thứ tự thì xuống cuối, giữ theo giờ check-in.
  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("vi-VN");
    const matching = items.filter((item) => {
      if (!item.checked_in_at) return false;
      const haystack = [
        item.patient.full_name,
        item.patient.patient_code,
        item.queue_number,
        item.so_tiep_don != null ? String(item.so_tiep_don) : null,
        item.so_booking != null ? `#${item.so_booking}` : null,
      ]
        .filter(Boolean)
        .join(" ")
        .toLocaleLowerCase("vi-VN");
      return !needle || haystack.includes(needle);
    });
    const hang = (x: WorklistItem): number =>
      (x.appointment_id ? thuTu.get(x.appointment_id) : undefined) ??
      Number.MAX_SAFE_INTEGER;
    return [...matching].sort(
      (a, b) => hang(a) - hang(b) || waitedMinutes(b) - waitedMinutes(a),
    );
  }, [items, query, thuTu]);

  /** Thả người đang kéo vào ngay TRƯỚC `dich` (null = xuống cuối hàng). */
  function thaVao(dich: string | null) {
    const nguon = filtered.find((x) => x.id === dangKeo);
    setDangKeo(null);
    if (!nguon?.appointment_id) return;
    const ids = filtered
      .map((x) => x.appointment_id)
      .filter((x): x is string => Boolean(x));
    const dichAppt = dich
      ? (filtered.find((x) => x.id === dich)?.appointment_id ?? null)
      : null;
    if (dich && !dichAppt) return;
    const cho = choTruoc(ids, nguon.appointment_id, dichAppt);
    if (cho) void keo(nguon.appointment_id, cho.sau, cho.truoc);
  }

  const selected =
    filtered.find((item) => item.id === selectedId) ??
    filtered[0] ??
    null;

  const soDaCheckIn = items.filter((x) => x.checked_in_at).length;
  const kim = query.trim().toLocaleLowerCase("vi-VN");
  const chuaDenXep = chuaDen
    .filter(
      (a) =>
        !kim ||
        [
          a.patient?.full_name,
          a.patient?.patient_code,
          a.so_booking != null ? `#${a.so_booking}` : null,
        ]
          .filter(Boolean)
          .join(" ")
          .toLocaleLowerCase("vi-VN")
          .includes(kim),
    )
    .sort((a, b) => new Date(a.slot_start).getTime() - new Date(b.slot_start).getTime());

  if (items.length === 0 && chuaDen.length === 0) {
    return (
      <div className="rounded-card border border-line bg-surface p-10 text-center">
        <p className="font-medium text-ink">Hàng đợi trống</p>
        <p className="mt-1 text-sm text-ink-muted">
          Chưa có người bệnh nào chờ tiếp nhận hôm nay.
        </p>
      </div>
    );
  }

  return (
    <div
      className={`grid items-start gap-3 ${
        tab === "da"
          ? "xl:grid-cols-[minmax(280px,0.9fr)_minmax(380px,1.25fr)_minmax(240px,0.8fr)]"
          : "xl:max-w-3xl"
      }`}
    >
      <section
        aria-label="Danh sách hàng đợi"
        className="overflow-hidden rounded-card border border-line bg-surface shadow-card"
      >
        <header className="border-b border-line p-3">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="text-sm font-semibold text-ink">Danh sách hàng đợi</h2>
            <p className="text-label text-ink-muted">
              {tab === "cho"
                ? "Theo giờ hẹn · bấm Check-in khi khách đến"
                : "Theo giờ check-in · kéo tay cầm để đổi thứ tự"}
            </p>
          </div>
          {/* HAI DANH SÁCH (Tuyền 24/09/2026): check-in ngay ở đây; ai check-in
              rồi sang danh sách "Đã check-in". */}
          <ThanhTab
            className="mt-3"
            nhan="Danh sách tiếp đón"
            muc={[
              { ma: "cho", nhan: `Chờ check-in (${chuaDen.length})` },
              { ma: "da", nhan: `Đã check-in (${soDaCheckIn})` },
            ]}
            chon={tab}
            onChon={setTab}
          />
          {/* BA Ô LỌC ĐÃ BỎ (Tuyền 16/09/2026): tab "Khách ưu tiên" — dấu sao
              trên từng dòng đã nói rồi; tab "Cần xác minh" — nó dò một mã bước
              viết cứng trong giao diện; và hai ô "Bộ lọc" / "Sắp xếp" — hàng
              đợi chỉ có MỘT thứ tự đúng, là thứ tự gọi khám, nên cho đổi cách
              xếp chỉ tạo ra một cái nhìn không khớp với thứ tự thật. */}
          <label className="mt-3 flex items-center gap-2 rounded-control border border-line bg-surface px-3 py-2 text-ink-muted focus-within:border-brand-500">
            <Search size={15} aria-hidden />
            <span className="sr-only">Tìm tên, mã BN hoặc số thứ tự</span>
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Tìm tên, mã BN hoặc số thứ tự"
              className="min-w-0 flex-1 bg-transparent text-xs text-ink outline-none placeholder:text-ink-faint"
            />
          </label>
          {loiThuTu && (
            <p className="mt-2 rounded-control bg-danger-bg px-2 py-1 text-label text-danger">
              {loiThuTu}
            </p>
          )}
        </header>

        {tab === "cho" ? (
          <>
            <div className="flex gap-2 border-b border-line bg-surface-muted px-3 py-2 text-label font-medium uppercase tracking-wide text-ink-faint">
              <span className="w-10 shrink-0">Đặt</span>
              <span className="min-w-0 flex-1">Người bệnh</span>
            </div>
            <div className={KHUNG_CUON}>
              {chuaDenXep.length > 0 ? (
                chuaDenXep.map((a) => (
                  <ChuaDenRow key={a.id} a={a} />
                ))
              ) : (
                <p className="px-4 py-10 text-center text-sm text-ink-muted">
                  {kim
                    ? "Không có khách nào khớp từ khoá."
                    : "Khách hẹn hôm nay đã check-in hết."}
                </p>
              )}
            </div>
          </>
        ) : (
          <>
        <div className="flex gap-2 border-b border-line bg-surface-muted px-3 py-2 text-label font-medium uppercase tracking-wide text-ink-faint">
          <span className="w-7 shrink-0" />
          <span className="w-9 shrink-0 text-center">STT</span>
          <span className="w-10 shrink-0 text-center">Đặt</span>
          <span className="min-w-0 flex-1">Người bệnh</span>
          <span className="w-11 shrink-0 text-right">Chờ</span>
        </div>
        <div className={KHUNG_CUON}>
          {filtered.length > 0 ? (
            filtered.map((item) => (
              <Row
                key={item.id}
                item={item}
                selected={item.id === selected?.id}
                onSelect={() => setSelectedId(item.id)}
                // CHỈ KÉO ĐƯỢC NGƯỜI CÓ TRONG BẢNG THỨ TỰ.
                //
                // `GET /queue` xếp hàng theo LỊCH HẸN TRONG NGÀY, nên một lượt
                // check-in hôm qua chưa đóng vẫn đứng trong danh sách này mà
                // KHÔNG có thứ tự gọi. Kéo họ thì backend trả "Khách này không
                // còn trong hàng chờ đã check-in" — một câu đúng luật nhưng đọc
                // như lỗi hệ thống. Tắt tay cầm là nói thật: ở đây không có
                // thứ tự để đổi.
                keoDuoc={
                  Boolean(item.appointment_id) &&
                  thuTu.has(item.appointment_id ?? "") &&
                  !dangGhi
                }
                dangKeo={dangKeo === item.id}
                onKeoBatDau={() => setDangKeo(item.id)}
                onKeoXong={() => setDangKeo(null)}
                onTha={() => thaVao(item.id)}
              />
            ))
          ) : (
            <p className="px-4 py-10 text-center text-sm text-ink-muted">
              {query.trim()
                ? "Không có người bệnh nào khớp từ khoá."
                : "Chưa có khách nào check-in."}
            </p>
          )}
        </div>
        {/* Vùng thả CUỐI HÀNG: kéo xuống dưới người cuối cùng là đẩy xuống
            chót. Không có nó thì chỉ chèn được vào TRƯỚC một ai đó. */}
        <div
          onDragOver={(e) => {
            if (dangKeo) e.preventDefault();
          }}
          onDrop={(e) => {
            e.preventDefault();
            thaVao(null);
          }}
          className="h-4"
          aria-hidden
        />
        <footer className="flex items-center justify-between border-t border-line px-3 py-3 text-xs text-ink-muted">
          <span>
            {filtered.length} người đang chờ
            {query.trim() ? " (đang lọc)" : ""}
          </span>
          {query.trim() && (
            <button
              type="button"
              onClick={() => setQuery("")}
              className="text-brand-700 hover:underline"
            >
              Xem tất cả
            </button>
          )}
        </footer>
          </>
        )}
      </section>

      {tab === "da" && selected ? <PatientDetail item={selected} /> : null}
      {tab === "da" && selected ? (
        <CounterPanel item={selected} />
      ) : null}
    </div>
  );
}

function PatientDetail({ item }: { item: WorklistItem }) {
  const tone = resolveStatus(item);
  const waited = waitedMinutes(item);
  const targetMinutes = (() => {
    const from = item.checked_in_at ?? item.created_at;
    if (!from || !item.due_at) return null;
    return Math.max(
      0,
      Math.round((new Date(item.due_at).getTime() - new Date(from).getTime()) / 60000),
    );
  })();

  return (
    <section
      aria-label="Thông tin người bệnh"
      className="overflow-hidden rounded-card border border-line bg-surface shadow-card"
    >
      <header className="flex items-center justify-between border-b border-line px-4 py-3">
        <h2 className="text-sm font-semibold text-ink">Thông tin người bệnh</h2>
        <StatusChip
          tone={STATUS_PRESENTATION[tone].token as StatusTone}
          label={STATUS_PRESENTATION[tone].label}
        />
      </header>

      <div className="grid gap-4 border-b border-line p-4 md:grid-cols-[1.1fr_0.8fr_96px]">
        <div className="flex gap-3">
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full border border-line bg-surface-sunken text-base font-semibold text-ink-soft">
            {initials(item.patient.full_name)}
          </span>
          <div className="min-w-0">
            <h3 className="truncate text-lg font-semibold text-ink">
              {item.patient.full_name ?? "Chưa rõ tên"}
            </h3>
            <p className="text-xs text-ink-muted">{patientLine(item.patient) || "—"}</p>
            <p className="mt-2 flex items-center gap-1.5 text-xs text-ink-soft">
              <Phone size={13} aria-hidden /> {item.patient.phone_primary ?? "—"}
            </p>
            <p className="mt-1 flex items-center gap-1.5 text-xs text-ink-soft">
              <IdCard size={13} aria-hidden /> Mã BN: {item.patient.patient_code ?? "—"}
            </p>
            {/* Hành trình hành chính của lượt (batch pilot 18/09): check-in, đo,
                đang ở đâu, dịch vụ, thanh toán, lịch tiếp — không có chữ khám. */}
            {item.visit_id ? <NutXemLuot visitId={item.visit_id} /> : null}
          </div>
        </div>
        <dl className="border-l border-line pl-4 text-xs">
          <Field label="Số tiếp đón" value={soQuay(item)} />
          <Field label="Số booking" value={soDat(item)} />
          <Field label="Ngày sinh" value={item.patient.date_of_birth ? new Date(item.patient.date_of_birth).toLocaleDateString("vi-VN") : "—"} />
          <div className="mt-2 flex items-start gap-1.5 text-ink-muted">
            <MapPin size={13} className="mt-0.5 shrink-0" aria-hidden />
            <span>Địa chỉ: Chưa có trong dữ liệu hàng đợi</span>
          </div>
        </dl>
        <div className="rounded-control border border-line p-2 text-center">
          <p className="text-label text-ink-muted">SLA mục tiêu</p>
          <p className="mt-1 font-semibold text-ink">
            {targetMinutes === null ? "—" : `${targetMinutes} phút`}
          </p>
          <div className="my-2 h-1 overflow-hidden rounded-full bg-surface-sunken">
            <div
              className={`h-full ${waited > (targetMinutes ?? Number.POSITIVE_INFINITY) ? "bg-status-overdue" : "bg-warning"}`}
              style={{ width: `${Math.min(100, targetMinutes ? (waited / targetMinutes) * 100 : 0)}%` }}
            />
          </div>
          <p className="text-label text-ink-muted">Thời gian chờ</p>
          <p className="font-semibold text-warning">{waited} phút</p>
        </div>
      </div>

      <div className="grid gap-3 border-b border-line p-3 md:grid-cols-3">
        <InfoCard title="Lịch hẹn" icon={<Clock3 size={15} />}>
          <Field label="Ngày / giờ" value={item.slot_start ? new Date(item.slot_start).toLocaleString("vi-VN", { dateStyle: "short", timeStyle: "short" }) : "—"} />
          <Field label="Hình thức" value={item.booking_channel === "WALK_IN" ? "Đến trực tiếp" : "Đặt hẹn"} />
        </InfoCard>
        {/* MỘT MỐC, KHÔNG BA (Tuyền 16/09/2026): *"check-in đồng nghĩa là thời
            điểm vào hàng đợi rồi mà"*. Ba dòng "Thời điểm đến / Vào hàng đợi
            lúc / Bắt đầu xử lý" kể gần như cùng một chuyện, và mốc bắt đầu
            khám là thời gian CON nằm trong khoảng check-in → check-out. */}
        <InfoCard title="Thông tin hàng đợi" icon={<UsersRound size={15} />}>
          <Field label="Check-in" value={time(item.checked_in_at)} />
          <Field label="Số tiếp đón" value={soQuay(item)} />
          <Field label="Số riêng của bác sĩ" value={item.queue_number ?? "—"} />
        </InfoCard>
        <InfoCard title="Bảo hiểm y tế" icon={<ShieldCheck size={15} />}>
          <p className="rounded-control bg-surface-sunken px-2 py-2 text-xs text-ink-muted">
            Chưa có dữ liệu BHYT trong API hàng đợi.
          </p>
        </InfoCard>
      </div>

    </section>
  );
}

function CounterPanel({ item }: { item: WorklistItem }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  /** Check-in cho khách đặt lịch trước.
   *
   * Đi qua ĐÚNG đường mà nút "Đã đến" ở Trang chủ đi — `PATCH /api/appointments`
   * với `action: "checkin"`. Không có đường riêng cho màn này: hai đường
   * check-in là hai luật cấp số thứ tự chờ ngày lệch nhau.
   */
  async function checkIn(xacMinhCach?: MaXacMinh) {
    if (!item.appointment_id) return;
    setError(null);
    const res = await fetch("/api/appointments", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        id: item.appointment_id,
        action: "checkin",
        xac_minh_cach: xacMinhCach,
      }),
    });
    if (!res.ok) {
      const body = (await res.json().catch(() => null)) as { error?: string } | null;
      setError(body?.error ?? `Không check-in được (HTTP ${res.status})`);
      return;
    }
    startTransition(() => router.refresh());
  }

  async function issue(
    command: KernelCommand,
    expectedVersion: number,
  ): Promise<number | null> {
    setError(null);
    const response = await fetch(`/api/work-items/${item.id}/commands/${command}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ expected_version: expectedVersion }),
    });
    const body = (await response.json().catch(() => null)) as
      | { error?: string; version?: number }
      | null;
    if (!response.ok) {
      setError(body?.error ?? `Không thực hiện được (HTTP ${response.status})`);
      return null;
    }
    return typeof body?.version === "number" ? body.version : expectedVersion + 1;
  }

  /** "VÀO KHÁM" = MỞ RỒI ĐÓNG BƯỚC TIẾP NHẬN TRONG MỘT CÚ BẤM.
   *
   *  Tuyền 16/09/2026: bỏ nút "Xong tiếp nhận — mời vào khám", chỉ còn "Vào
   *  khám" — *"vào khám là bắt đầu tính cho khám mà"*. Ở quầy hai nút ấy luôn
   *  bấm liền nhau: không có việc gì xảy ra giữa "bắt đầu xử lý" và "xong tiếp
   *  nhận" ngoài chính cú bấm thứ hai.
   *
   *  Vẫn gửi ĐỦ HAI LỆNH xuống kernel chứ không bịa một lệnh mới: bước tiếp
   *  nhận phải đi qua IN_PROGRESS rồi mới COMPLETED thì mốc thời gian mới thật,
   *  và chính nó là thứ đẩy khách sang bàn bác sĩ. Bỏ lệnh thứ hai là khách
   *  kẹt ở quầy. `version` lấy từ câu trả lời của lệnh trước — kernel tăng
   *  version mỗi lệnh, gửi lại số cũ là bị từ chối 409. */
  async function vaoKham() {
    let v: number | null = item.version;
    if (item.status === "PENDING") v = await issue("start", v);
    if (v === null) return;
    v = await issue("complete", v);
    if (v === null) return;
    startTransition(() => router.refresh());
  }

  const canAct = item.actionable_by_me && !item.blocked;
  const finished = ["COMPLETED", "SKIPPED", "CANCELLED"].includes(item.status);

  return (
    <aside aria-label="Điều phối tại quầy" className="flex flex-col gap-3">
      <section className="rounded-card border border-line bg-surface p-3 shadow-card">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-ink">Điều phối tại quầy</h2>
          <span className="text-xs text-brand-700">Dữ liệu thật</span>
        </div>
        <div className="mt-3 rounded-control border border-line p-3">
          <h3 className="flex items-center gap-2 text-xs font-semibold text-ink">
            <Monitor size={15} className="text-brand-600" aria-hidden />
            Xem trước màn hình hiển thị
          </h3>
          {/* MỜI TÊN, KHÔNG MỜI SỐ.
              
              Ở quầy tiếp nhận, Lễ tân gọi tên người bệnh — số thứ tự chỉ để
              đối chiếu. Con số chiếm chỗ to nhất mà không phải thứ được đọc lên. */}
          <div className="mt-3 grid grid-cols-[1fr_62px] overflow-hidden rounded-control border border-brand-500 text-center">
            <div className="bg-surface px-2 py-3">
              <p className="text-label uppercase text-ink-muted">Mời</p>
              <p className="truncate text-2xl font-semibold text-ink">
                {item.patient.full_name ?? "—"}
              </p>
              {soQuay(item) !== "—" ? (
                <p className="text-label text-ink-muted">
                  số {soQuay(item)}
                </p>
              ) : null}
            </div>
            <div className="border-l border-line bg-surface px-2 py-3">
              <p className="text-label uppercase text-ink-muted">Chờ</p>
              <p className="text-xl font-semibold text-ink">{waitedMinutes(item)}′</p>
            </div>
          </div>
        </div>

      </section>

      {error ? <p className="rounded-control bg-danger-bg px-3 py-2 text-xs text-danger">{error}</p> : null}

      {/* CHECK-IN — dành cho khách ĐẶT LỊCH TRƯỚC.
          
          Khách đến trực tiếp đã được check-in sẵn lúc tạo lịch (walk-in trong
          ngày tự vào thẳng trạng thái đã đến), nên nút này chỉ hiện khi thật sự
          còn việc để làm. */}
      {item.checked_in_at ? (
        <p className="rounded-control bg-success-bg px-3 py-2 text-xs text-success">
          Đã check-in lúc {time(item.checked_in_at)}
        </p>
      ) : (
        <NutCheckIn
          size="lg"
          fullWidth
          disabled={!item.appointment_id || pending}
          onChon={() => checkIn()}
        >
          <CheckCircle2 size={17} className="mr-2" />
          {pending ? "Đang lưu…" : "Check-in — khách đã đến"}
        </NutCheckIn>
      )}

      {/* KHUNG KHÁCH (Tuyền 27/09/2026: "Lễ tân cũng nên có"): ghi chú chung ·
          tự nhắc tôi · mọi thứ của khách — CÙNG component với Quản lý khách hàng. */}
      {item.patient.clinic_patient_id ? (
        <KhungKhach
          key={item.patient.clinic_patient_id}
          clinicPatientId={item.patient.clinic_patient_id}
        />
      ) : null}

      {NUT_VAO_KHAM && (
      <button
        type="button"
        disabled={!canAct || finished || pending}
        onClick={() => void vaoKham()}
        className="flex w-full items-center justify-center gap-2 rounded-control bg-brand-600 px-4 py-3 text-sm font-semibold text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:bg-surface-sunken disabled:text-ink-faint"
      >
        <CheckCircle2 size={19} />
        {pending ? "Đang lưu…" : "Vào khám"}
      </button>
      )}
    </aside>
  );
}

function InfoCard({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="rounded-control border border-line p-3">
      <h3 className="mb-2 flex items-center gap-2 text-xs font-semibold text-ink">
        <span className="text-brand-600">{icon}</span>{title}
      </h3>
      <dl className="space-y-1.5 text-xs">{children}</dl>
    </section>
  );
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-2">
      <dt className="text-ink-muted">{label}</dt>
      <dd className="text-right text-ink">{value}</dd>
    </div>
  );
}
