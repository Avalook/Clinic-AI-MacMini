"use client";

// BÀN KHÁM — màn của bác sĩ và thư ký đi kèm (Tuyền chốt 16/09/2026).
//
// BỐ CỤC GIỮ ĐÚNG màn Tuyền đã chọn ("đây là view tôi muốn làm", Bàn khám bác sĩ
// cũ): hàng chờ hẹp bên trái, bệnh án rộng ở giữa, chỉ định bên phải.
//
// NGUỒN DỮ LIỆU ĐỔI SANG MỘT ĐƯỜNG: hàng chờ phòng (`queue_entry`), phiên khám
// (`consultation`), chỉ định (`service_order`). Màn cũ đọc thẻ việc và chỉ định
// ghi vào `payload` của thẻ — một đường thứ ba song song mà trên final cloud có
// 0 chỉ định thật.
//
// CHECK-IN / CHECK-OUT CỦA PHÒNG = hai nút: "Bắt đầu khám" và "Đã khám xong"
// (Tuyền: *"bác sĩ chọn rồi ấn bắt đầu khám cho người đó rồi điền thông tin bên
// trong, khám xong thì ghi đã khám xong là được"*). Khám xong mà còn chỉ định
// chưa làm thì khách tự sang hàng chờ phòng làm chỉ định — máy chủ quyết.

import { ClipboardPlus, FlaskConical, HeartPulse, Search, Stethoscope } from "lucide-react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import PriorityChip from "@/components/ui/PriorityChip";
import StatCard, { StatRow } from "@/components/ui/StatCard";
import StatusChip, { type StatusTone } from "@/components/ui/StatusChip";

import LuotKhamTruoc, { type LuotTruoc } from "../doctor/board/LuotKhamTruoc";
import ServiceFormEngine from "../tasks/ServiceFormEngine";
import ClinicalRecordForm from "../tasks/ClinicalRecordForm";
import type { DoctorApptRow } from "../tasks/DoctorWorkBoard";
import {
  docBang,
  guiThaoTac,
  soPhutTu,
  gioVn,
  type DongHangCho,
  type Phong,
  type PhongHomNay,
} from "../_lam-viec/api";
import KhungTep from "../_lam-viec/KhungTep";

// ── Dữ liệu của bảng lượt khám (chỉ những trường màn này dùng) ─────────────
interface SinhHieu {
  tam_thu: number | null;
  tam_truong: number | null;
  mach: number | null;
  nhiet_do: number | null;
  nhip_tho: number | null;
  spo2: number | null;
  can_nang: number | null;
  chieu_cao: number | null;
  bmi: number | null;
  muc_do_dau: number | null;
  luc: string | null;
  nguoi_do: string | null;
}
interface ChiDinh {
  id: string;
  phien_id: string;
  ma_dich_vu: string;
  ten_dich_vu: string;
  node: string;
  trang_thai: string;
  phong: string | null;
  version: number;
  nguoi_ghi: string | null;
  ket_qua: string | null;
  ly_do_khong_lam: string | null;
  /** Việc gửi đối tác làm — không có phòng nào của phòng khám để xếp. */
  doi_tac?: boolean;
  trang_thai_doi_tac?: "CHO_LAY_MAU" | "DA_LAY_MAU" | "CHO_TAI_LIEU" | "DA_GUI_KET_QUA" | null;
}
interface Luot {
  visit_id: string;
  sinh_hieu: SinhHieu | null;
  chi_dinh: ChiDinh[];
}
interface DichVu {
  ma: string;
  ten: string;
  node: string;
}
interface Bang {
  luot: Luot[];
  dich_vu: DichVu[];
}

const LA_PHONG_KHAM = (p: Phong) => p.nodes.some((n) => n.startsWith("KHAM-"));

function initials(name: string | null): string {
  if (!name) return "BN";
  return name
    .trim()
    .split(/\s+/)
    .slice(-2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("");
}

function tone(d: DongHangCho): { tone: StatusTone; nhan: string } {
  switch (d.trang_thai) {
    case "serving":
      return { tone: "in_progress", nhan: "Đang khám" };
    case "called":
      return { tone: "called", nhan: "Đã gọi vào" };
    case "waiting":
      return { tone: "ready", nhan: "Chờ khám" };
    case "blocked":
      return { tone: "blocked", nhan: "Đang ở bước khác" };
    default:
      return { tone: "completed", nhan: "Đã khám xong" };
  }
}

const TEN_TRANG_THAI_CHI_DINH: Record<string, string> = {
  draft: "Nháp — chờ bác sĩ duyệt",
  authorized: "Đã duyệt — chờ xếp phòng",
  assigned: "Chờ ở phòng",
  in_progress: "Đang làm",
  performed: "Đã làm",
  not_performed: "Không làm được",
};

/** Việc đối tác: nói trạng thái bên đối tác, không nói "chờ xếp phòng". */
const TEN_TRANG_THAI_DOI_TAC: Record<string, string> = {
  CHO_LAY_MAU: "Đã gửi đối tác",
  DA_LAY_MAU: "Đối tác đã lấy mẫu",
  CHO_TAI_LIEU: "Đối tác đang làm",
  DA_GUI_KET_QUA: "Đối tác đã gửi kết quả",
};

export default function BanKham({
  phongMa,
  vai,
  staffId = null,
}: {
  /** Mã phòng trên đường dẫn (/ban-kham/KN-NOITIET). Rỗng = khách của tôi. */
  phongMa: string | null;
  vai: string | null;
  staffId?: string | null;
}) {
  const laBacSi = vai === "DOCTOR";
  const laThuKy = vai === "TKYK";

  const router = useRouter();
  const [phongs, setPhongs] = useState<PhongHomNay | null>(null);
  const [hang, setHang] = useState<DongHangCho[] | null>(null);
  const [bang, setBang] = useState<Bang | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [chonId, setChonId] = useState<string | null>(null);
  const [lanNap, setLanNap] = useState(0);

  // Phòng khám của người này hôm nay (theo lịch), để biết hàng chờ nào là của họ.
  useEffect(() => {
    let huy = false;
    void docBang<PhongHomNay>("phong-hom-nay").then((kq) => {
      if (huy) return;
      if (kq.ok) setPhongs(kq.data);
      else setLoi(kq.loi);
    });
    return () => {
      huy = true;
    };
  }, []);

  const phongKham = useMemo(
    () => (phongs?.tat_ca_phong ?? []).filter(LA_PHONG_KHAM),
    [phongs],
  );
  const maPhong = phongMa;
  const phong = phongKham.find((p) => p.code === maPhong) ?? null;

  useEffect(() => {
    if (phongs === null) return;
    let huy = false;
    const nap = async () => {
      const [h, b] = await Promise.all([
        docBang<{ hang_cho: DongHangCho[] }>(
          "hang-cho",
          phong ? { phong: phong.id } : {},
        ),
        docBang<Bang>(null),
      ]);
      if (huy) return;
      if (!h.ok) setLoi(h.loi);
      else {
        setLoi(null);
        setHang(h.data.hang_cho.filter((d) => d.loai === "KHAM"));
      }
      if (b.ok) setBang(b.data);
    };
    void nap();
    // Làm mới đều: người khác (điều dưỡng đo xong, thư ký bấm) đổi hàng chờ.
    const t = setInterval(() => void nap(), 15000);
    return () => {
      huy = true;
      clearInterval(t);
    };
  }, [phongs, phong, lanNap]);

  const napLai = useCallback(() => setLanNap((n) => n + 1), []);

  const hienRa = useMemo(() => {
    const kim = query.trim().toLocaleLowerCase("vi");
    const ds = hang ?? [];
    if (!kim) return ds;
    return ds.filter((d) =>
      [d.ten, d.ma_bn, String(d.so_thu_tu)].some((v) =>
        v?.toLocaleLowerCase("vi").includes(kim),
      ),
    );
  }, [hang, query]);

  const dangKham = hienRa.filter((d) => d.trang_thai === "serving");
  const choKham = hienRa.filter(
    (d) => d.trang_thai === "waiting" || d.trang_thai === "called",
  );
  const buocKhac = hienRa.filter((d) => d.trang_thai === "blocked");
  const daXong = hienRa.filter((d) => d.trang_thai === "done");
  const macDinh = dangKham[0] ?? choKham[0] ?? buocKhac[0] ?? null;
  const chon = hienRa.find((d) => d.id === chonId) ?? macDinh;
  const luot = bang?.luot.find((l) => l.visit_id === chon?.visit_id) ?? null;

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <label className="text-sm font-semibold text-ink" htmlFor="chon-phong">
          Phòng
        </label>
        <select
          id="chon-phong"
          value={maPhong ?? ""}
          onChange={(e) => {
            setChonId(null);
            router.push(
              e.target.value
                ? `/ban-kham/${encodeURIComponent(e.target.value)}`
                : "/ban-kham",
            );
          }}
          className="min-h-10 rounded-control border border-line bg-surface px-3 text-sm text-ink"
        >
          <option value="">Khách của tôi (mọi phòng)</option>
          {phongKham.map((p) => (
            <option key={p.id} value={p.code}>
              {p.ten}
              {p.tang ? ` · ${p.tang}` : ""}
              {phongs?.phong_cua_toi.some((m) => m.id === p.id) ? " · hôm nay" : ""}
            </option>
          ))}
        </select>
        {loi ? (
          <p role="alert" className="text-sm text-danger">
            {loi}
          </p>
        ) : null}
      </div>

      <StatRow>
        <StatCard label="Chờ khám" value={choKham.length} tone="brand" />
        <StatCard label="Đang khám" value={dangKham.length} tone="neutral" />
        <StatCard label="Đang ở bước khác" value={buocKhac.length} tone="warning" />
        <StatCard label="Đã khám xong" value={daXong.length} tone="neutral" />
      </StatRow>

      <div className="grid items-start gap-4 xl:grid-cols-[minmax(220px,0.55fr)_minmax(480px,1.9fr)_minmax(320px,1fr)]">
        <aside
          aria-label="Hàng chờ khám"
          className="min-w-0 overflow-hidden rounded-card bg-surface shadow-card"
        >
          <div className="px-3 py-3">
            <label className="flex items-center gap-2 rounded-control bg-surface-muted px-3 py-2 text-ink-muted">
              <Search className="size-4 shrink-0" aria-hidden="true" />
              <span className="sr-only">Tìm khách</span>
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Tìm tên, mã hoặc số thứ tự"
                className="min-w-0 flex-1 bg-transparent text-xs text-ink outline-none placeholder:text-ink-faint"
              />
            </label>
          </div>
          {hang === null ? (
            <p className="px-3 pb-3 text-xs text-ink-muted">Đang tải hàng chờ…</p>
          ) : (
            <div className="max-h-[720px] overflow-y-auto">
              <Nhom ten="Đang khám" ds={dangKham} chon={chon?.id ?? null} onChon={setChonId} trong="Chưa có ai đang khám." />
              <Nhom ten="Chờ khám" ds={choKham} chon={chon?.id ?? null} onChon={setChonId} trong="Không có khách đang chờ." />
              <Nhom ten="Đang ở bước khác" ds={buocKhac} chon={chon?.id ?? null} onChon={setChonId} />
              <Nhom ten="Đã khám xong hôm nay" ds={daXong} chon={chon?.id ?? null} onChon={setChonId} />
            </div>
          )}
        </aside>

        <HoSo
          dong={chon}
          luot={luot}
          choBam={laBacSi || laThuKy}
          laBacSi={laBacSi}
          staffId={staffId}
          onDaBam={napLai}
        />

        <ChiDinhPanel
          dong={chon}
          luot={luot}
          dichVu={bang?.dich_vu ?? []}
          laBacSi={laBacSi}
          laThuKy={laThuKy}
          onDaGui={napLai}
        />
      </div>
    </div>
  );
}

function Nhom({
  ten,
  ds,
  chon,
  onChon,
  trong,
}: {
  ten: string;
  ds: DongHangCho[];
  chon: string | null;
  onChon: (id: string) => void;
  trong?: string;
}) {
  if (ds.length === 0 && !trong) return null;
  return (
    <section>
      <h3 className="border-y border-line bg-surface-muted px-3 py-2 text-xs font-semibold text-ink-soft">
        {ten} ({ds.length})
      </h3>
      {ds.length === 0 ? (
        <p className="px-3 py-3 text-xs text-ink-faint">{trong}</p>
      ) : (
        ds.map((d) => {
          const t = tone(d);
          const dangChon = d.id === chon;
          return (
            <button
              key={d.id}
              type="button"
              onClick={() => onChon(d.id)}
              aria-current={dangChon ? "true" : undefined}
              className={`w-full border-l-3 px-2.5 py-3 text-left transition-colors ${
                dangChon
                  ? "border-brand-500 bg-surface-selected"
                  : "border-transparent bg-surface hover:bg-surface-sunken"
              }`}
            >
              <span className="flex items-start gap-2.5">
                <span className="grid size-9 shrink-0 place-items-center rounded-full border border-line bg-surface-sunken text-xs font-semibold text-ink-soft">
                  {d.so_thu_tu}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-1.5">
                    <span className="truncate text-sm font-semibold text-ink" title={d.ten}>
                      {d.ten}
                    </span>
                    {d.uu_tien ? (
                      <span title={d.uu_tien_ly_do ?? undefined}>
                        <PriorityChip priority="P0" />
                      </span>
                    ) : null}
                  </span>
                  <span className="mt-0.5 block truncate text-xs text-ink-muted">
                    {d.ma_bn} · {d.dich_vu_kham ?? "Chưa gán dịch vụ"}
                  </span>
                  <span className="mt-1 block truncate text-xs text-ink-faint">
                    {d.bac_si ?? "Chưa có bác sĩ"}
                    {d.trang_thai === "done"
                      ? ` · xong ${gioVn(d.xong_luc)}`
                      : d.trang_thai === "serving"
                        ? ` · đã khám ${soPhutTu(d.bat_dau_luc)}`
                        : ` · chờ ${soPhutTu(d.vao_hang_luc)}`}
                    {d.checkin_luc ? ` · tổng ${soPhutTu(d.checkin_luc)}` : ""}
                    {d.vong === "REVIEW" ? " · quay lại đọc KQ" : ""}
                  </span>
                </span>
                <StatusChip tone={t.tone} label={t.nhan} />
              </span>
            </button>
          );
        })
      )}
    </section>
  );
}

function HoSo({
  dong,
  luot,
  choBam,
  laBacSi,
  staffId,
  onDaBam,
}: {
  dong: DongHangCho | null;
  luot: Luot | null;
  choBam: boolean;
  laBacSi: boolean;
  staffId: string | null;
  onDaBam: () => void;
}) {
  const [xemLai, setXemLai] = useState<{ id: string; luot: LuotTruoc } | null>(null);
  const dangXem = xemLai && xemLai.id === dong?.id ? xemLai.luot : null;
  const [dangGui, setDangGui] = useState(false);
  const [loi, setLoi] = useState<{ id: string; cau: string } | null>(null);

  if (!dong) {
    return (
      <section
        aria-label="Hồ sơ khám bệnh"
        className="grid min-h-96 place-items-center rounded-card bg-surface p-8 text-center shadow-card"
      >
        <div>
          <Stethoscope className="mx-auto size-8 text-brand-500" aria-hidden="true" />
          <p className="mt-3 font-medium text-ink">Chọn một khách trong hàng chờ</p>
          <p className="mt-1 text-sm text-ink-muted">
            Khách vào hàng chờ khám sau khi điều dưỡng đo sinh hiệu xong.
          </p>
        </div>
      </section>
    );
  }

  const bam = async (thaoTac: "nhan-kham" | "kham-xong" | "goi-khach") => {
    if (
      thaoTac === "kham-xong" &&
      !window.confirm(
        `Đã khám xong cho ${dong.ten}? Khách còn chỉ định chưa làm sẽ tự sang hàng chờ phòng làm chỉ định.`,
      )
    ) {
      return;
    }
    setDangGui(true);
    setLoi(null);
    // Gọi khách: theo CHỖ CHỜ; bắt đầu/khám xong: theo PHIÊN KHÁM.
    const kq = await guiThaoTac(
      thaoTac,
      thaoTac === "goi-khach" ? dong.id : dong.ref_id,
    );
    setDangGui(false);
    if (!kq.ok) setLoi({ id: dong.id, cau: kq.loi });
    else onDaBam();
  };
  const t = tone(dong);
  const sh = luot?.sinh_hieu ?? null;
  const loiHienTai = loi?.id === dong.id ? loi.cau : null;

  return (
    <section
      aria-label="Hồ sơ khám bệnh"
      className="min-w-0 overflow-hidden rounded-card bg-surface shadow-card"
    >
      <header className="px-4 py-3">
        <div className="flex flex-wrap items-center gap-3">
          <span className="grid size-11 place-items-center rounded-full border border-line bg-surface-sunken text-sm font-semibold text-ink-soft">
            {initials(dong.ten)}
          </span>
          <div className="min-w-44 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-base font-semibold text-ink">{dong.ten}</h2>
              <StatusChip tone={t.tone} label={t.nhan} size="md" />
              {dong.vong === "REVIEW" ? (
                <StatusChip tone="blocked" label="Quay lại đọc kết quả" size="md" />
              ) : null}
            </div>
            <p className="text-xs text-ink-muted">
              {dong.ma_bn} · {dong.bac_si ?? "Chưa có bác sĩ"}
            </p>
          </div>
          <dl className="grid grid-cols-4 divide-x divide-line text-xs">
            <Truong nhan="Số thứ tự" gia={String(dong.so_thu_tu)} />
            <Truong
              nhan={dong.trang_thai === "serving" ? "Đã khám" : "Đã chờ"}
              gia={
                dong.trang_thai === "serving"
                  ? soPhutTu(dong.bat_dau_luc) || "—"
                  : soPhutTu(dong.vao_hang_luc) || "—"
              }
            />
            <Truong
              nhan="Từ lúc check-in"
              gia={soPhutTu(dong.checkin_luc) || "—"}
            />
            <Truong nhan="Loại khám" gia={dong.dich_vu_kham ?? "Chưa gán dịch vụ"} />
          </dl>
        </div>

        {/* CHECK-IN / CHECK-OUT PHÒNG. */}
        {choBam ? (
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {dong.trang_thai === "waiting" || dong.trang_thai === "called" ? (
              <button
                type="button"
                disabled={dangGui}
                onClick={() => void bam("goi-khach")}
                className="inline-flex min-h-11 items-center gap-2 rounded-control border border-brand-600 px-5 text-sm font-semibold text-brand-700 hover:bg-brand-50 disabled:opacity-50"
              >
                {dong.trang_thai === "called"
                  ? `Gọi lại (đã gọi ${gioVn(dong.goi_luc)})`
                  : "Gọi vào khám"}
              </button>
            ) : null}
            {dong.trang_thai === "waiting" || dong.trang_thai === "called" ? (
              <button
                type="button"
                disabled={dangGui}
                onClick={() => void bam("nhan-kham")}
                className="inline-flex min-h-11 items-center gap-2 rounded-control bg-brand-600 px-5 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
              >
                <Stethoscope className="size-4" aria-hidden="true" />
                {dangGui ? "Đang ghi…" : "Bắt đầu khám"}
              </button>
            ) : null}
            {dong.trang_thai === "serving" ? (
              <button
                type="button"
                disabled={dangGui}
                onClick={() => void bam("kham-xong")}
                className="inline-flex min-h-11 items-center gap-2 rounded-control bg-success px-5 text-sm font-semibold text-white disabled:opacity-50"
              >
                {dangGui
                  ? "Đang ghi…"
                  : laBacSi
                    ? "Xác nhận & ký · khám xong"
                    : "Đã khám xong"}
              </button>
            ) : null}
            {dong.trang_thai === "blocked" ? (
              <p className="text-xs text-warning">
                Khách đang ở một bước khác (đang làm dịch vụ) — chưa gọi vào được.
              </p>
            ) : null}
            {loiHienTai ? (
              <p role="alert" className="text-xs text-danger">
                {loiHienTai}
              </p>
            ) : null}
          </div>
        ) : null}

        <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-control border border-line bg-surface-muted px-3 py-2 text-xs text-ink-soft">
          <HeartPulse className="size-4 shrink-0 text-brand-600" aria-hidden="true" />
          {sh ? (
            <>
              <span>
                HA <b>{sh.tam_thu ?? "—"}/{sh.tam_truong ?? "—"}</b>
              </span>
              <span>Mạch <b>{sh.mach ?? "—"}</b></span>
              <span>Nhiệt <b>{sh.nhiet_do ?? "—"}</b></span>
              <span>Nhịp thở <b>{sh.nhip_tho ?? "—"}</b></span>
              <span>SpO₂ <b>{sh.spo2 ?? "—"}</b></span>
              <span>Cân <b>{sh.can_nang ?? "—"}</b></span>
              <span>Cao <b>{sh.chieu_cao ?? "—"}</b></span>
              <span>BMI <b>{sh.bmi ?? "—"}</b></span>
              {sh.muc_do_dau !== null ? <span>Đau <b>{sh.muc_do_dau}</b></span> : null}
              <span className="text-ink-muted">
                · {sh.nguoi_do ?? "?"} đo lúc {gioVn(sh.luc)}
              </span>
            </>
          ) : (
            <span>Chưa có sinh hiệu.</span>
          )}
        </div>
      </header>

      <div className="p-3 pt-0">
        <LuotKhamTruoc
          clinicPatientId={dong.clinic_patient_id}
          visitIdHienTai={dong.visit_id}
          dangXem={dangXem}
          onXem={(l) => setXemLai(l ? { id: dong.id, luot: l } : null)}
        />
        {dangXem ? (
          <div className="mt-2">
            <ServiceFormEngine
              key={dangXem.visit_id}
              visitId={dangXem.visit_id}
              serviceCode={dangXem.service_code}
              readOnly
            />
          </div>
        ) : !dong.form_code ? (
          <p className="rounded-control border border-dashed border-warning bg-warning-bg px-3 py-6 text-center text-xs text-warning">
            Dịch vụ “{dong.dich_vu_kham ?? "chưa gán"}” chưa gắn phiếu khám nào.
            Vào Cấu trúc phòng khám để gán, hoặc chọn đúng loại khám khi đặt lịch.
          </p>
        ) : (
          <ServiceFormEngine
            key={dong.visit_id}
            visitId={dong.visit_id}
            serviceCode={dong.form_code}
            readOnly={!choBam || dong.trang_thai === "done"}
          />
        )}
        {/* BỆNH ÁN · CHẨN ĐOÁN · ĐƠN THUỐC (demo 17/09/2026). Thư ký nhập, màn
            bác sĩ tự tải lại khi bên kia lưu (sự kiện realtime), bác sĩ duyệt
            đơn và ký. Khám xong vẫn bấm ở nút trên — trạng thái truyền vào là
            COMPLETED để form KHÔNG bày nút "Kết thúc khám" của đường cũ. */}
        {dong.loai === "KHAM" && dong.appointment_id && !dangXem ? (
          <details open className="mt-3 rounded-card border border-line">
            <summary className="cursor-pointer px-3 py-2 text-sm font-semibold text-ink">
              Bệnh án · Chẩn đoán · Đơn thuốc · Lời dặn
            </summary>
            <ClinicalRecordForm
              key={dong.appointment_id}
              appt={
                {
                  id: dong.appointment_id,
                  slot_start: dong.checkin_luc ?? dong.vao_hang_luc ?? "",
                  status: "COMPLETED",
                  queue_number: String(dong.so_thu_tu),
                  patient: {
                    clinic_patient_id: dong.clinic_patient_id,
                    patient_code: dong.ma_bn,
                    full_name: dong.ten,
                    date_of_birth: null,
                    phone_primary: null,
                    phone_secondary: null,
                    gender: null,
                    ethnicity: null,
                    nationality: null,
                    occupation: null,
                    patient_objection: null,
                    address: null,
                    guardian_name: null,
                  },
                  service: dong.dich_vu_kham
                    ? { name: dong.dich_vu_kham, form_code: dong.form_code }
                    : null,
                } as unknown as DoctorApptRow
              }
              staffId={staffId}
              onClose={() => {}}
              canSign={laBacSi}
              readOnly={!choBam || dong.trang_thai === "done"}
            />
          </details>
        ) : null}
      </div>
    </section>
  );
}

function Truong({ nhan, gia }: { nhan: string; gia: string }) {
  return (
    <div className="max-w-36 px-3 first:pl-0">
      <dt className="text-ink-faint">{nhan}</dt>
      <dd className="mt-0.5 truncate font-medium text-ink" title={gia}>
        {gia}
      </dd>
    </div>
  );
}

function ChiDinhPanel({
  dong,
  luot,
  dichVu,
  laBacSi,
  laThuKy,
  onDaGui,
}: {
  dong: DongHangCho | null;
  luot: Luot | null;
  dichVu: DichVu[];
  laBacSi: boolean;
  laThuKy: boolean;
  onDaGui: () => void;
}) {
  const [go, setGo] = useState("");
  const [chon, setChon] = useState<{ id: string; ma: string[] }>({ id: "", ma: [] });
  const [dangGui, setDangGui] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [moKetQua, setMoKetQua] = useState<string | null>(null);

  const dsChon = chon.id === dong?.id ? chon.ma : [];
  const dangKham = dong?.trang_thai === "serving";
  const chiDinh = (luot?.chi_dinh ?? []).filter((c) => c.trang_thai !== "cancelled");
  const nhap = chiDinh.filter((c) => c.trang_thai === "draft");

  if (!dong) {
    return (
      <section className="rounded-card bg-surface-muted p-3.5 text-xs text-ink-muted shadow-card">
        Chọn khách để xem và ghi chỉ định.
      </section>
    );
  }

  const them = (ma: string) => {
    if (!ma || dsChon.includes(ma)) return;
    setChon({ id: dong.id, ma: [...dsChon, ma] });
    setGo("");
  };

  const gui = async () => {
    if (dsChon.length === 0 && !(laBacSi && nhap.length > 0)) return;
    setDangGui(true);
    setLoi(null);
    const kq = laBacSi
      ? await guiThaoTac("duyet-chi-dinh", dong.ref_id, {
          service_codes: dsChon,
          draft_order_ids: nhap.map((c) => c.id),
          expected_versions: Object.fromEntries(nhap.map((c) => [c.id, c.version])),
        })
      : await guiThaoTac("nhap-chi-dinh", dong.ref_id, { service_codes: dsChon });
    setDangGui(false);
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    setChon({ id: dong.id, ma: [] });
    onDaGui();
  };

  return (
    <section
      aria-label="Chỉ định và kết quả"
      className="min-w-0 rounded-card bg-surface-muted p-3.5 shadow-card"
    >
      <div className="flex items-center gap-2">
        <FlaskConical className="size-4 text-specialty-service" aria-hidden="true" />
        <h3 className="text-sm font-semibold text-ink">Chỉ định & kết quả</h3>
      </div>

      {chiDinh.length === 0 ? (
        <p className="mt-3 text-xs text-ink-muted">Lượt khám này chưa có chỉ định.</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {chiDinh.map((c) => (
            <li key={c.id} className="rounded-control border border-line bg-surface px-3 py-2">
              <div className="flex items-start justify-between gap-2">
                <p className="min-w-0 text-sm font-medium text-ink">{c.ten_dich_vu}</p>
                <span
                  className={`shrink-0 rounded-chip px-2 py-0.5 text-label font-semibold ${
                    c.trang_thai === "draft"
                      ? "bg-warning-bg text-warning"
                      : c.trang_thai === "performed"
                        ? "bg-success-bg text-success"
                        : "bg-brand-50 text-brand-700"
                  }`}
                >
                  {c.doi_tac && c.trang_thai !== "draft" && c.trang_thai_doi_tac
                    ? TEN_TRANG_THAI_DOI_TAC[c.trang_thai_doi_tac]
                    : TEN_TRANG_THAI_CHI_DINH[c.trang_thai] ?? c.trang_thai}
                </span>
              </div>
              <p className="mt-0.5 text-label text-ink-muted">
                {c.phong ? `${c.phong}` : ""}
                {c.ly_do_khong_lam ? ` · ${c.ly_do_khong_lam}` : ""}
              </p>
              {c.ket_qua ? (
                <p className="mt-1 whitespace-pre-line text-xs text-ink">{c.ket_qua}</p>
              ) : null}
              {c.trang_thai === "performed" || c.trang_thai === "in_progress" ? (
                <button
                  type="button"
                  onClick={() => setMoKetQua(moKetQua === c.id ? null : c.id)}
                  className="mt-1 text-label font-semibold text-brand-700 hover:underline"
                >
                  {moKetQua === c.id ? "Ẩn tệp kết quả" : "Xem tệp kết quả"}
                </button>
              ) : null}
              {moKetQua === c.id ? (
                <div className="mt-2">
                  <KhungTep
                    clinicPatientId={dong.clinic_patient_id}
                    serviceOrderId={c.id}
                    choTaiLen={false}
                    tieuDe="Tệp kết quả"
                  />
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      )}

      {(laBacSi || laThuKy) && dong.trang_thai !== "done" ? (
        <div className="mt-4 border-t border-line pt-3">
          {!dangKham ? (
            <p className="text-xs text-ink-muted">
              Bấm “Bắt đầu khám” trước khi ghi chỉ định.
            </p>
          ) : (
            <>
              <label className="text-xs font-semibold text-ink" htmlFor="go-dich-vu">
                {laBacSi ? "Chỉ định thêm" : "Ghi nháp chỉ định (bác sĩ duyệt)"}
              </label>
              <input
                id="go-dich-vu"
                list="danh-muc-chi-dinh"
                value={go}
                onChange={(e) => {
                  const v = e.target.value;
                  const dv = dichVu.find((d) => d.ten === v || d.ma === v);
                  if (dv) them(dv.ma);
                  else setGo(v);
                }}
                placeholder="Gõ tên siêu âm, xét nghiệm, thủ thuật…"
                className="mt-1 min-h-10 w-full rounded-control border border-line bg-surface px-3 text-sm text-ink"
              />
              <datalist id="danh-muc-chi-dinh">
                {dichVu.map((d) => (
                  <option key={d.ma} value={d.ten} />
                ))}
              </datalist>
              {dsChon.length > 0 ? (
                <ul className="mt-2 flex flex-wrap gap-1.5">
                  {dsChon.map((ma) => (
                    <li key={ma}>
                      <button
                        type="button"
                        onClick={() =>
                          setChon({ id: dong.id, ma: dsChon.filter((x) => x !== ma) })
                        }
                        className="rounded-chip bg-brand-50 px-2 py-1 text-label font-semibold text-brand-700"
                        title="Bấm để bỏ"
                      >
                        {dichVu.find((d) => d.ma === ma)?.ten ?? ma} ✕
                      </button>
                    </li>
                  ))}
                </ul>
              ) : null}
              <button
                type="button"
                disabled={dangGui || (dsChon.length === 0 && !(laBacSi && nhap.length > 0))}
                onClick={() => void gui()}
                className="mt-3 inline-flex w-full items-center justify-center gap-2 rounded-control border border-brand-600 px-3 py-2.5 text-sm font-medium text-brand-700 hover:bg-brand-50 disabled:opacity-50"
              >
                <ClipboardPlus className="size-4" aria-hidden="true" />
                {dangGui
                  ? "Đang ghi…"
                  : laBacSi
                    ? nhap.length > 0 && dsChon.length === 0
                      ? `Duyệt ${nhap.length} chỉ định nháp`
                      : "Duyệt chỉ định"
                    : "Ghi nháp chỉ định"}
              </button>
              {laBacSi ? (
                <p className="mt-1 text-label text-ink-muted">
                  Duyệt xong khách tự vào hàng chờ phòng làm dịch vụ.
                </p>
              ) : null}
              {loi ? (
                <p role="alert" className="mt-2 text-xs text-danger">
                  {loi}
                </p>
              ) : null}
            </>
          )}
        </div>
      ) : null}
    </section>
  );
}
