"use client";

// Màn lượt khám — lát 1. MỘT màn cho sáu vai.
//
// Màn này KHÔNG quyết định gì. Nó vẽ đúng cái backend trả về và gửi đúng thao
// tác người bấm. Mấy tập vai dưới đây chỉ để GIẤU nút không phải việc của mình
// cho gọn mắt; bấm được hay không vẫn do backend (require_role + service) nói,
// và câu từ chối của backend được hiện nguyên văn.

import { useCallback, useEffect, useState } from "react";
import Button from "../../../components/ui/Button";
import { loiDocDuoc } from "../../../lib/loi-doc-duoc";
import { SU_KIEN_BANG } from "../../../lib/nhip-lam-moi";
import { ROLE_LABEL } from "../../../lib/roles";
import NutCheckIn from "@/components/ui/NutCheckIn";

// ── Hình dạng dữ liệu của GET /api/v1/luot-kham/bang ─────────────────────────

export interface SinhHieu {
  tam_thu: number;
  tam_truong: number;
  mach: number | null;
  nhiet_do: number | null;
  can_nang: number | null;
  chieu_cao: number | null;
  luc: string | null;
  nguoi_do: string | null;
}
export interface GhiChu {
  noi_dung: string;
  nguoi_ghi: string | null;
  luc: string | null;
}
export interface Phien {
  id: string;
  vong: number;
  loai: "PRIMARY" | "REVIEW";
  trang_thai: string;
  ket_qua: string | null;
  bac_si_id: string | null;
  nguoi_bat_dau_id: string | null;
  ghi_chu: GhiChu[];
}
export interface ChiDinh {
  id: string;
  phien_id: string;
  ma_dich_vu: string;
  ten_dich_vu: string;
  node: string;
  trang_thai: string;
  phong_id: string | null;
  phong: string | null;
  giu_toi_vong: number | null;
  version: number;
  nguoi_ghi: string | null;
  nguoi_duyet: string | null;
  nguoi_lam: string | null;
  ket_qua: string | null;
  ly_do_khong_lam: string | null;
}
export interface ChoHang {
  id: string;
  hang: "DOCTOR" | "ROOM";
  ly_do: "PRIMARY" | "SERVICE" | "REVIEW";
  ref_id: string;
  trang_thai: string;
  du_dieu_kien_luc: string | null;
  phong_id: string | null;
  bac_si_id: string | null;
}
export interface Vong {
  id: string;
  vong: number;
  trang_thai: string;
  yeu_cau: { chi_dinh_id: string; can: string; trang_thai: string }[];
}
export interface Luot {
  visit_id: string;
  ma_bn: string;
  ten: string;
  bac_si_id: string | null;
  bac_si: string | null;
  check_in_luc: string | null;
  sinh_hieu_trang_thai: string;
  dich: string | null;
  ket_thuc_luc: string | null;
  sinh_hieu: SinhHieu | null;
  phien: Phien[];
  chi_dinh: ChiDinh[];
  hang_cho: ChoHang[];
  vong: Vong[];
}
export interface Bang {
  vai: string;
  toi: string;
  luot: Luot[];
  phong: { id: string; ma: string; ten: string; nodes: string[] }[];
  dich_vu: { ma: string; ten: string; node: string; vai_lam: string[] }[];
  lich_cho_check_in: {
    id: string;
    gio: string | null;
    ten: string;
    ma_bn: string;
    bac_si: string | null;
  }[];
}

type Gui = (thaoTac: string, id: string, duLieu?: unknown) => Promise<boolean>;

// ── Chữ cho người đọc ────────────────────────────────────────────────────────

const LOAI_PHIEN: Record<string, string> = {
  PRIMARY: "Khám ban đầu",
  REVIEW: "Đọc kết quả",
};
const TRANG_THAI_PHIEN: Record<string, string> = {
  queued: "Chờ khám",
  in_progress: "Đang khám",
  completed: "Đã xong",
  cancelled: "Đã huỷ",
};
const KET_QUA_PHIEN: Record<string, string> = {
  NO_SERVICES: "không cần dịch vụ",
  SERVICES: "làm dịch vụ rồi quay lại",
  DONE: "kết thúc khám",
  MORE_SERVICES: "cần thêm dịch vụ",
};
const TRANG_THAI_CHI_DINH: Record<string, string> = {
  draft: "Nháp — chờ bác sĩ duyệt",
  authorized: "Đã duyệt — chờ xếp phòng",
  assigned: "Đã xếp phòng",
  in_progress: "Đang làm",
  performed: "Đã làm",
  not_performed: "Không làm được",
  cancelled: "Đã huỷ",
};
const TRANG_THAI_VONG: Record<string, string> = {
  collecting: "đang chờ dịch vụ",
  ready: "đủ điều kiện, chờ bác sĩ",
  in_review: "đang đọc",
  closed: "đã đọc xong",
};

// Chỉ để giấu nút — backend vẫn là người quyết định.
const LE_TAN = new Set(["RECEPTION", "MANAGEMENT"]);
const DO_SINH_HIEU = new Set(["NURSE_ULTRASOUND", "RECEPTION", "DOCTOR"]);
const DIEU_PHOI = new Set(["TRUONG_CA", "MANAGEMENT"]);

const THE = "rounded-card bg-surface p-4 ring-1 ring-inset ring-hairline";
const O_NHAP =
  "h-8 w-full rounded-control bg-surface px-2 text-body text-ink " +
  "ring-1 ring-inset ring-line-strong";
const O_VIET =
  "min-h-20 w-full rounded-control bg-surface px-2 py-1.5 text-body " +
  "text-ink ring-1 ring-inset ring-line-strong";

const GIO = new Intl.DateTimeFormat("vi-VN", {
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "Asia/Ho_Chi_Minh",
});

function gio(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : GIO.format(d);
}

/** Khoá gửi lại cho MỘT lần bấm. Không dùng crypto.randomUUID: nó chỉ có trong
 *  secure context, còn staging/prod đang chạy HTTP thường. */
function khoaGuiLai(): string {
  return `lk-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}

function dangCho(q: ChoHang | null): boolean {
  return q !== null && (q.trang_thai === "waiting" || q.trang_thai === "called");
}

function buocHienTai(luot: Luot): string {
  if (luot.ket_thuc_luc) return "Đã kết thúc khám";
  const dangO = luot.hang_cho.find((q) => q.trang_thai === "serving");
  if (dangO) {
    if (dangO.hang === "DOCTOR") {
      return dangO.ly_do === "REVIEW"
        ? "Đang đọc kết quả với bác sĩ"
        : "Đang khám với bác sĩ";
    }
    const o = luot.chi_dinh.find((c) => c.id === dangO.ref_id);
    return `Đang làm: ${o?.ten_dich_vu ?? "dịch vụ"}`;
  }
  if (luot.sinh_hieu_trang_thai !== "recorded") return "Chờ đo sinh hiệu";
  const cho = luot.hang_cho.filter((q) => dangCho(q));
  if (cho.some((q) => q.ly_do === "REVIEW")) return "Chờ bác sĩ đọc kết quả";
  if (cho.some((q) => q.ly_do === "PRIMARY")) return "Chờ bác sĩ khám";
  if (cho.some((q) => q.ly_do === "SERVICE")) return "Chờ làm dịch vụ";
  if (luot.chi_dinh.some((c) => c.trang_thai === "authorized")) {
    return "Chờ trưởng ca xếp phòng";
  }
  return "Đang xử lý";
}

// ── Màn chính ────────────────────────────────────────────────────────────────

export default function LuotKhamBoard({ initial }: { initial: Bang | null }) {
  const [bang, setBang] = useState<Bang | null>(initial);
  const [loi, setLoi] = useState<string | null>(
    initial ? null : "Không đọc được dữ liệu từ máy chủ.",
  );
  const [thongBao, setThongBao] = useState<string | null>(null);
  const [dangGui, setDangGui] = useState(false);

  const taiLai = useCallback(async () => {
    try {
      const r = await fetch("/api/luot-kham", { cache: "no-store" });
      const d: unknown = await r.json().catch(() => null);
      if (!r.ok) {
        setLoi(loiDocDuoc(d, "Không đọc được dữ liệu từ máy chủ."));
        return;
      }
      setBang(d as Bang);
    } catch {
      setLoi("Mất kết nối tới máy chủ.");
    }
  }, []);

  // Shared clinic SSE; retain a sparse recovery poll for lost notifications.
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    const reload = () => {
      if (document.visibilityState !== "visible") return;
      clearTimeout(timer);
      timer = setTimeout(() => void taiLai(), 250);
    };
    const changed = (ev: Event) => {
      if (["encounter_flow", "vital_measurement", "consultation", "consultation_note",
        "service_order", "queue_entry", "review_round", "round_requirement"]
          .includes((ev as CustomEvent<string>).detail)) reload();
    };
    window.addEventListener(SU_KIEN_BANG, changed);
    window.addEventListener("focus", reload);
    document.addEventListener("visibilitychange", reload);
    const poll = setInterval(reload, 60_000);
    return () => {
      clearTimeout(timer); clearInterval(poll);
      window.removeEventListener(SU_KIEN_BANG, changed);
      window.removeEventListener("focus", reload);
      document.removeEventListener("visibilitychange", reload);
    };
  }, [taiLai]);

  const gui = useCallback<Gui>(
    async (thaoTac, id, duLieu) => {
      setDangGui(true);
      setThongBao(null);
      try {
        const r = await fetch("/api/luot-kham", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": khoaGuiLai(),
          },
          body: JSON.stringify({ thao_tac: thaoTac, id, du_lieu: duLieu ?? {} }),
        });
        const d: unknown = await r.json().catch(() => null);
        if (!r.ok) {
          setLoi(loiDocDuoc(d, "Không thực hiện được."));
          return false;
        }
        setLoi(null);
        setThongBao("Đã lưu.");
        await taiLai();
        return true;
      } catch {
        setLoi("Mất kết nối tới máy chủ — chưa lưu.");
        return false;
      } finally {
        setDangGui(false);
      }
    },
    [taiLai],
  );

  if (!bang) {
    return (
      <section className={THE}>
        <p role="alert" className="text-body text-danger">
          {loi}
        </p>
        <Button className="mt-3" size="sm" onClick={() => void taiLai()}>
          Tải lại
        </Button>
      </section>
    );
  }

  const tenVai = (ROLE_LABEL as Record<string, string>)[bang.vai] ?? bang.vai;

  return (
    <div className="space-y-4">
      <header className={`flex flex-wrap items-center justify-between gap-3 ${THE}`}>
        <div>
          <h1 className="text-title text-ink">
            Luồng khám mới{" "}
            <span className="text-meta text-ink-muted">· lát 1 · dữ liệu giả</span>
          </h1>
          <p className="text-meta text-ink-muted">
            Bạn đang dùng vai {tenVai}. Mỗi vai chỉ thấy nút phần việc của mình.
          </p>
        </div>
        <Button size="sm" disabled={dangGui} onClick={() => void taiLai()}>
          Tải lại
        </Button>
      </header>

      {loi && (
        <p
          role="alert"
          className="rounded-card bg-danger-bg px-4 py-2 text-body text-danger"
        >
          {loi}
        </p>
      )}
      {thongBao && !loi && (
        <p role="status" className="px-1 text-meta text-ink-muted">
          {thongBao}
        </p>
      )}

      {LE_TAN.has(bang.vai) && (
        <LichCheckIn bang={bang} gui={gui} dangGui={dangGui} />
      )}

      {bang.luot.length === 0 ? (
        <p className={`${THE} text-body text-ink-muted`}>
          Hôm nay chưa có khách nào đã check-in.
        </p>
      ) : (
        bang.luot.map((l) => (
          <TheLuot key={l.visit_id} luot={l} bang={bang} gui={gui} dangGui={dangGui} />
        ))
      )}
    </div>
  );
}

interface ChungProps {
  bang: Bang;
  gui: Gui;
  dangGui: boolean;
}

function LichCheckIn({ bang, gui, dangGui }: ChungProps) {
  const lich = bang.lich_cho_check_in;
  return (
    <section className={THE}>
      <h2 className="text-label uppercase text-ink-muted">
        Lịch hẹn hôm nay chờ check-in
      </h2>
      {lich.length === 0 ? (
        <p className="mt-2 text-body text-ink-muted">Không còn lịch hẹn nào chờ.</p>
      ) : (
        <ul className="mt-2 divide-y divide-hairline">
          {lich.map((a) => (
            <li
              key={a.id}
              className="flex flex-wrap items-center justify-between gap-2 py-2"
            >
              <span className="text-body text-ink">
                <span className="font-semibold">{gio(a.gio)}</span> · {a.ten}{" "}
                <span className="text-meta text-ink-muted">
                  {a.ma_bn} · BS {a.bac_si ?? "—"}
                </span>
              </span>
              <NutCheckIn
                size="sm"
                disabled={dangGui}
                onChon={() => gui("check-in", "", { appointment_id: a.id })}
              >
                Check-in
              </NutCheckIn>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function TheLuot({ luot, bang, gui, dangGui }: ChungProps & { luot: Luot }) {
  return (
    <article className={`space-y-3 ${THE}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <p className="text-emph font-semibold text-ink">{luot.ten}</p>
          <p className="text-meta text-ink-muted">
            {luot.ma_bn} · BS {luot.bac_si ?? "—"} · check-in {gio(luot.check_in_luc)}
          </p>
        </div>
        <span className="rounded-chip bg-surface-sunken px-2 py-0.5 text-meta font-semibold text-ink">
          {buocHienTai(luot)}
        </span>
      </div>

      <KhoiSinhHieu luot={luot} bang={bang} gui={gui} dangGui={dangGui} />

      {luot.phien.map((p) => (
        <KhoiPhien
          key={p.id}
          phien={p}
          luot={luot}
          bang={bang}
          gui={gui}
          dangGui={dangGui}
        />
      ))}

      {luot.chi_dinh.length > 0 && (
        <section className="space-y-2">
          <p className="text-label uppercase text-ink-muted">Chỉ định</p>
          <ul className="divide-y divide-hairline rounded-control ring-1 ring-inset ring-hairline">
            {luot.chi_dinh.map((c) => (
              <DongChiDinh
                key={c.id}
                c={c}
                luot={luot}
                bang={bang}
                gui={gui}
                dangGui={dangGui}
              />
            ))}
          </ul>
        </section>
      )}

      {luot.vong.map((v) => (
        <p key={v.id} className="text-meta text-ink-muted">
          Vòng đọc {v.vong}: {TRANG_THAI_VONG[v.trang_thai] ?? v.trang_thai} ·{" "}
          {v.yeu_cau.filter((y) => y.trang_thai !== "open").length}/{v.yeu_cau.length}{" "}
          dịch vụ bắt buộc đã xong
        </p>
      ))}
    </article>
  );
}

const SINH_HIEU_TRONG = {
  systolic: "",
  diastolic: "",
  pulse: "",
  temperature: "",
  weight_kg: "",
  height_cm: "",
};
const O_SINH_HIEU: [keyof typeof SINH_HIEU_TRONG, string][] = [
  ["systolic", "Tâm thu *"],
  ["diastolic", "Tâm trương *"],
  ["pulse", "Mạch"],
  ["temperature", "Nhiệt độ °C"],
  ["weight_kg", "Cân nặng kg"],
  ["height_cm", "Chiều cao cm"],
];

function KhoiSinhHieu({ luot, bang, gui, dangGui }: ChungProps & { luot: Luot }) {
  const [so, setSo] = useState(SINH_HIEU_TRONG);
  const s = luot.sinh_hieu;

  if (s) {
    const phan = [
      `HA ${s.tam_thu}/${s.tam_truong}`,
      s.mach != null ? `mạch ${s.mach}` : null,
      s.nhiet_do != null ? `${s.nhiet_do}°C` : null,
      s.can_nang != null ? `${s.can_nang} kg` : null,
      s.chieu_cao != null ? `${s.chieu_cao} cm` : null,
    ].filter(Boolean);
    return (
      <p className="text-body text-ink">
        Sinh hiệu: {phan.join(" · ")}{" "}
        <span className="text-meta text-ink-muted">
          — {s.nguoi_do ?? "—"} lúc {gio(s.luc)}
        </span>
      </p>
    );
  }
  if (!DO_SINH_HIEU.has(bang.vai) || luot.ket_thuc_luc) {
    return <p className="text-meta text-ink-muted">Chưa đo sinh hiệu.</p>;
  }

  return (
    <form
      className="space-y-2"
      onSubmit={async (e) => {
        e.preventDefault();
        const duLieu = Object.fromEntries(
          Object.entries(so).filter(([, v]) => v.trim() !== ""),
        );
        if (await gui("sinh-hieu", luot.visit_id, duLieu)) setSo(SINH_HIEU_TRONG);
      }}
    >
      <p className="text-label uppercase text-ink-muted">Đo sinh hiệu</p>
      <div className="grid grid-cols-2 gap-2 md:grid-cols-6">
        {O_SINH_HIEU.map(([truong, nhan]) => (
          <label key={truong} className="flex flex-col gap-1 text-meta text-ink-muted">
            {nhan}
            <input
              inputMode="decimal"
              className={O_NHAP}
              value={so[truong]}
              onChange={(e) => setSo({ ...so, [truong]: e.target.value })}
            />
          </label>
        ))}
      </div>
      <Button type="submit" variant="primary" size="sm" disabled={dangGui}>
        Lưu sinh hiệu
      </Button>
    </form>
  );
}

function KhoiPhien({
  phien,
  luot,
  bang,
  gui,
  dangGui,
}: ChungProps & { phien: Phien; luot: Luot }) {
  const [ghiChu, setGhiChu] = useState("");
  const [maChon, setMaChon] = useState("");
  const [dichVu, setDichVu] = useState<string[]>([]);
  const [boNhap, setBoNhap] = useState<string[]>([]);
  const [boYeuCau, setBoYeuCau] = useState<string[]>([]);

  const vai = bang.vai;
  const cho = luot.hang_cho.find((q) => q.ref_id === phien.id) ?? null;
  const cuaToi = phien.nguoi_bat_dau_id === bang.toi;
  const dangKham = phien.trang_thai === "in_progress";
  const laBacSiKham = dangKham && vai === "DOCTOR" && cuaToi;
  const laThuKy = dangKham && vai === "TKYK";

  const nhap = luot.chi_dinh.filter(
    (c) => c.phien_id === phien.id && c.trang_thai === "draft",
  );
  const nhapDuyet = nhap.filter((c) => !boNhap.includes(c.id)).map((c) => c.id);
  // Dịch vụ có thể bắt buộc trước lần đọc kết quả: đã duyệt, chưa huỷ, không bị
  // dặn làm sau. Ở phiên đọc kết quả, thứ đã làm xong thì không bắt lại nữa.
  const ungVien = luot.chi_dinh.filter(
    (c) =>
      !["draft", "cancelled"].includes(c.trang_thai) &&
      c.giu_toi_vong == null &&
      !(
        phien.loai === "REVIEW" &&
        ["performed", "not_performed"].includes(c.trang_thai)
      ),
  );
  const yeuCau = ungVien
    .filter((c) => !boYeuCau.includes(c.id))
    .map((c) => ({ order_id: c.id, need: "PERFORMED" }));

  const bat = (ds: string[], id: string) =>
    ds.includes(id) ? ds.filter((x) => x !== id) : [...ds, id];

  return (
    <section className="space-y-2 rounded-control bg-surface-muted p-3">
      <p className="text-body text-ink">
        <span className="font-semibold">
          Vòng {phien.vong} · {LOAI_PHIEN[phien.loai]}
        </span>{" "}
        — {TRANG_THAI_PHIEN[phien.trang_thai] ?? phien.trang_thai}
        {phien.ket_qua ? ` · ${KET_QUA_PHIEN[phien.ket_qua] ?? phien.ket_qua}` : ""}
      </p>

      {phien.ghi_chu.map((g, i) => (
        <p key={i} className="whitespace-pre-wrap text-body text-ink">
          {g.noi_dung}{" "}
          <span className="text-meta text-ink-muted">
            — {g.nguoi_ghi ?? "—"} {gio(g.luc)}
          </span>
        </p>
      ))}

      {phien.trang_thai === "queued" &&
        vai === "DOCTOR" &&
        (dangCho(cho) ? (
          <Button
            variant="primary"
            size="sm"
            disabled={dangGui}
            onClick={() => void gui("nhan-kham", phien.id)}
          >
            {phien.loai === "REVIEW"
              ? "Gọi khách vào đọc kết quả"
              : "Nhận khách vào khám"}
          </Button>
        ) : (
          <p className="text-meta text-ink-muted">
            Khách đang ở bước khác — chưa gọi vào được.
          </p>
        ))}

      {dangKham && vai === "DOCTOR" && !cuaToi && (
        <p className="text-meta text-ink-muted">Bác sĩ khác đang khám phiên này.</p>
      )}

      {(laBacSiKham || laThuKy) && (
        <div className="space-y-3">
          <div className="space-y-2">
            <textarea
              className={O_VIET}
              placeholder="Ghi chú khám"
              value={ghiChu}
              onChange={(e) => setGhiChu(e.target.value)}
            />
            <Button
              size="sm"
              disabled={dangGui || !ghiChu.trim()}
              onClick={async () => {
                if (await gui("ghi-chu", phien.id, { body: ghiChu })) setGhiChu("");
              }}
            >
              Lưu ghi chú
            </Button>
          </div>

          <div className="space-y-2">
            <p className="text-label uppercase text-ink-muted">
              {laThuKy ? "Ghi nháp chỉ định" : "Chỉ định dịch vụ"}
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <select
                className={`${O_NHAP} md:w-auto`}
                value={maChon}
                onChange={(e) => setMaChon(e.target.value)}
              >
                <option value="">Chọn dịch vụ…</option>
                {bang.dich_vu.map((d) => (
                  <option key={d.ma} value={d.ma}>
                    {d.ten}
                  </option>
                ))}
              </select>
              <Button
                size="sm"
                disabled={!maChon || dichVu.includes(maChon)}
                onClick={() => {
                  setDichVu([...dichVu, maChon]);
                  setMaChon("");
                }}
              >
                Thêm
              </Button>
            </div>
            {dichVu.length > 0 && (
              <ul className="space-y-1">
                {dichVu.map((ma) => (
                  <li key={ma} className="flex items-center gap-2 text-body text-ink">
                    {bang.dich_vu.find((d) => d.ma === ma)?.ten ?? ma}
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setDichVu(dichVu.filter((x) => x !== ma))}
                    >
                      Bỏ
                    </Button>
                  </li>
                ))}
              </ul>
            )}

            {nhap.length > 0 && (
              <ul className="space-y-1">
                {nhap.map((c) => (
                  <li key={c.id} className="text-body text-ink">
                    {laBacSiKham ? (
                      <label className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={!boNhap.includes(c.id)}
                          onChange={() => setBoNhap(bat(boNhap, c.id))}
                        />
                        Duyệt nháp: {c.ten_dich_vu}
                        <span className="text-meta text-ink-muted">
                          (thư ký {c.nguoi_ghi ?? "—"})
                        </span>
                      </label>
                    ) : (
                      <>Nháp đã ghi: {c.ten_dich_vu}</>
                    )}
                  </li>
                ))}
              </ul>
            )}

            {laThuKy ? (
              <Button
                size="sm"
                variant="primary"
                disabled={dangGui || dichVu.length === 0}
                onClick={async () => {
                  if (
                    await gui("nhap-chi-dinh", phien.id, { service_codes: dichVu })
                  ) {
                    setDichVu([]);
                  }
                }}
              >
                Ghi nháp để bác sĩ duyệt
              </Button>
            ) : (
              <Button
                size="sm"
                variant="primary"
                disabled={dangGui || (dichVu.length === 0 && nhapDuyet.length === 0)}
                onClick={async () => {
                  const ok = await gui("duyet-chi-dinh", phien.id, {
                    service_codes: dichVu,
                    draft_order_ids: nhapDuyet,
                    expected_versions: Object.fromEntries(
                      nhap.filter((c) => nhapDuyet.includes(c.id))
                        .map((c) => [c.id, c.version]),
                    ),
                  });
                  if (ok) {
                    setDichVu([]);
                    setBoNhap([]);
                  }
                }}
              >
                Duyệt chỉ định
              </Button>
            )}
          </div>

          {laBacSiKham && (
            <div className="space-y-2">
              <p className="text-label uppercase text-ink-muted">Kết thúc phiên</p>
              {ungVien.length > 0 && (
                <ul className="space-y-1">
                  {ungVien.map((c) => (
                    <li key={c.id} className="text-body text-ink">
                      <label className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={!boYeuCau.includes(c.id)}
                          onChange={() => setBoYeuCau(bat(boYeuCau, c.id))}
                        />
                        Phải làm xong trước khi đọc: {c.ten_dich_vu}
                      </label>
                    </li>
                  ))}
                </ul>
              )}
              <div className="flex flex-wrap gap-2">
                {phien.loai === "PRIMARY" ? (
                  <>
                    <Button
                      size="sm"
                      disabled={dangGui}
                      onClick={() =>
                        void gui("ket-thuc-kham", phien.id, { outcome: "NO_SERVICES" })
                      }
                    >
                      Kết thúc — không cần dịch vụ
                    </Button>
                    <Button
                      size="sm"
                      variant="primary"
                      disabled={dangGui || yeuCau.length === 0}
                      onClick={() =>
                        void gui("ket-thuc-kham", phien.id, {
                          outcome: "SERVICES",
                          requirements: yeuCau,
                        })
                      }
                    >
                      Làm dịch vụ rồi quay lại đọc
                    </Button>
                  </>
                ) : (
                  <>
                    <Button
                      size="sm"
                      variant="primary"
                      disabled={dangGui}
                      onClick={() =>
                        void gui("ket-thuc-kham", phien.id, { outcome: "DONE" })
                      }
                    >
                      Kết thúc khám
                    </Button>
                    <Button
                      size="sm"
                      disabled={dangGui || yeuCau.length === 0}
                      onClick={() =>
                        void gui("ket-thuc-kham", phien.id, {
                          outcome: "MORE_SERVICES",
                          requirements: yeuCau,
                        })
                      }
                    >
                      Cần thêm dịch vụ rồi đọc lại
                    </Button>
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function DongChiDinh({
  c,
  luot,
  bang,
  gui,
  dangGui,
}: ChungProps & { c: ChiDinh; luot: Luot }) {
  const [phong, setPhong] = useState(c.phong_id ?? "");
  const [ketQua, setKetQua] = useState("");
  const [lyDo, setLyDo] = useState("");

  const vai = bang.vai;
  const vaiLam = bang.dich_vu.find((d) => d.node === c.node)?.vai_lam ?? [];
  const phongHopLe = bang.phong.filter((p) => p.nodes.includes(c.node));
  const cho = luot.hang_cho.find((q) => q.ref_id === c.id) ?? null;
  const dieuPhoi =
    DIEU_PHOI.has(vai) && (c.trang_thai === "authorized" || c.trang_thai === "assigned");
  const toiLam = vaiLam.includes(vai);

  return (
    <li className="space-y-2 p-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-body text-ink">
          <span className="font-semibold">{c.ten_dich_vu}</span>
          {c.phong ? ` · ${c.phong}` : ""}
        </p>
        <span className="text-meta text-ink-muted">
          {TRANG_THAI_CHI_DINH[c.trang_thai] ?? c.trang_thai}
        </span>
      </div>
      <p className="text-meta text-ink-muted">
        Ghi: {c.nguoi_ghi ?? "—"}
        {c.nguoi_duyet ? ` · duyệt: ${c.nguoi_duyet}` : ""}
        {c.nguoi_lam ? ` · làm: ${c.nguoi_lam}` : ""}
        {c.giu_toi_vong ? ` · làm sau vòng đọc ${c.giu_toi_vong}` : ""}
      </p>
      {c.ket_qua && (
        <p className="whitespace-pre-wrap text-body text-ink">Kết quả: {c.ket_qua}</p>
      )}
      {c.ly_do_khong_lam && (
        <p className="text-body text-ink">Không làm được: {c.ly_do_khong_lam}</p>
      )}

      {dieuPhoi && (
        <div className="flex flex-wrap items-center gap-2">
          <select
            className={`${O_NHAP} md:w-auto`}
            value={phong}
            onChange={(e) => setPhong(e.target.value)}
          >
            <option value="">Chọn phòng…</option>
            {phongHopLe.map((p) => (
              <option key={p.id} value={p.id}>
                {p.ten}
              </option>
            ))}
          </select>
          <Button
            size="sm"
            variant="primary"
            disabled={dangGui || !phong || phong === c.phong_id}
            onClick={() =>
              void gui("xep-phong", c.id, {
                room_id: phong,
                expected_version: c.version,
              })
            }
          >
            {c.trang_thai === "assigned" ? "Đổi phòng" : "Xếp phòng"}
          </Button>
          {phongHopLe.length === 0 && (
            <span className="text-meta text-danger">
              Chưa có phòng nào làm dịch vụ này.
            </span>
          )}
        </div>
      )}

      {toiLam &&
        c.trang_thai === "assigned" &&
        (dangCho(cho) ? (
          <Button
            size="sm"
            variant="primary"
            disabled={dangGui}
            onClick={() => void gui("bat-dau-dich-vu", c.id)}
          >
            Nhận khách làm dịch vụ
          </Button>
        ) : (
          <p className="text-meta text-ink-muted">
            Khách đang ở bước khác — chờ khách xong rồi gọi.
          </p>
        ))}

      {toiLam && c.trang_thai === "in_progress" && (
        <div className="space-y-2">
          <textarea
            className={O_VIET}
            placeholder="Ghi nhận khi làm (không bắt buộc)"
            value={ketQua}
            onChange={(e) => setKetQua(e.target.value)}
          />
          <div className="flex flex-wrap items-center gap-2">
            <Button
              size="sm"
              variant="primary"
              disabled={dangGui}
              onClick={() =>
                void gui("xong-dich-vu", c.id, {
                  performed: true,
                  result_note: ketQua.trim() || null,
                })
              }
            >
              Đã làm xong
            </Button>
            <input
              className={`${O_NHAP} md:w-64`}
              placeholder="Lý do không làm được"
              value={lyDo}
              onChange={(e) => setLyDo(e.target.value)}
            />
            <Button
              size="sm"
              variant="danger"
              disabled={dangGui || !lyDo.trim()}
              onClick={() =>
                void gui("xong-dich-vu", c.id, { performed: false, reason: lyDo })
              }
            >
              Không làm được
            </Button>
          </div>
        </div>
      )}
    </li>
  );
}
