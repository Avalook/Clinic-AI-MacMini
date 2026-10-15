"use client";

// "Khách mua thuốc" — khách CHỈ ĐẾN MUA THUỐC, không khám (V8, Tuyền 30/09/2026).
//
// Tìm hoặc tạo khách → máy chủ mở (hoặc lấy lại) lượt BÁN LẺ: không tiền khám,
// không hàng chờ bác sĩ / điều phối / hành trình. Mọi luật ở FastAPI
// (`ban_le_service`): ai được mở, chống trùng SĐT, mỗi khách một lượt đang mở.
// Màn chỉ gửi và vẽ lại câu máy chủ trả.
//
// Chọn khách cũ (bấm tên) → hiện ngay LỊCH SỬ ĐƠN THUỐC, chưa mở lượt; "Bán theo
// đơn này" ở từng đơn mở lượt + nối đơn + thêm dòng một lần (09/10/2026). "Mở
// lượt mua thuốc" vẫn là mua lẻ không theo đơn.
//
// Ở /pharmacy: mở xong chọn luôn lượt vừa mở. Ở /pharmacy/inventory: chuyển
// sang /pharmacy?luot=<id> để kê và thu.

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import Button from "@/components/ui/Button";

import { INPUT } from "../form-ui";
import LichSuDonThuoc from "./LichSuDonThuoc";
import { CHAM } from "./DongThuoc";

interface KhachTim {
  clinic_patient_id: string;
  full_name: string;
  patient_code: string | null;
  phone_primary: string | null;
  birth_year: number | null;
}

interface KetQuaMo {
  visit_id?: string;
  trung?: boolean;
  matches?: { clinic_patient_id: string; full_name: string; patient_code: string }[];
  message?: string;
  error?: string;
  detail?: string;
}

async function moLuot(than: Record<string, unknown>): Promise<KetQuaMo> {
  try {
    const r = await fetch("/api/pharmacy/ban-le", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(than),
    });
    const d = (await r.json().catch(() => null)) as KetQuaMo | null;
    if (!r.ok) {
      return { error: d?.message ?? d?.error ?? `Không mở được lượt (HTTP ${r.status}).` };
    }
    return d ?? { error: "Máy chủ không trả lời." };
  } catch {
    return { error: "Mất kết nối — CHƯA mở lượt." };
  }
}

export default function KhachMuaThuoc({
  onMo,
  sangNhaThuoc = false,
}: {
  /** Lượt vừa mở — màn Nhà thuốc chọn luôn lượt này. */
  onMo?: (visitId: string) => void;
  /** Ở Kho thuốc: mở xong chuyển sang /pharmacy để kê và thu. */
  sangNhaThuoc?: boolean;
}) {
  const router = useRouter();
  const [mo, setMo] = useState(false);
  const [tim, setTim] = useState("");
  const [ketQua, setKetQua] = useState<KhachTim[]>([]);
  const [ten, setTen] = useState("");
  const [sdt, setSdt] = useState("");
  const [namSinh, setNamSinh] = useState("");
  const [trung, setTrung] = useState<KetQuaMo["matches"] | null>(null);
  const [dang, setDang] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  // Khách cũ đang chọn — khung lịch sử đơn thuốc của họ hiện bên dưới.
  const [chon, setChon] = useState<string | null>(null);

  const chonKhach = (id: string | null) => setChon(id);

  // Tìm khách: gõ ≥ 2 ký tự, chờ 300ms sau lần gõ cuối.
  useEffect(() => {
    const q = tim.trim();
    if (!mo || q.length < 2) return;
    let bo = false;
    const hen = setTimeout(() => {
      fetch(`/api/pharmacy/tim-khach?${new URLSearchParams({ q })}`, { cache: "no-store" })
        .then((r) => (r.ok ? r.json() : null))
        .then((d: { items?: KhachTim[] } | null) => {
          if (!bo) setKetQua(d?.items ?? []);
        })
        .catch(() => {
          if (!bo) setKetQua([]);
        });
    }, 300);
    return () => {
      bo = true;
      clearTimeout(hen);
    };
  }, [tim, mo]);

  const xong = (visitId: string) => {
    setMo(false);
    setTim("");
    setKetQua([]);
    setTen("");
    setSdt("");
    setNamSinh("");
    setTrung(null);
    chonKhach(null);
    if (sangNhaThuoc) {
      router.push(`/pharmacy?${new URLSearchParams({ luot: visitId })}`);
      return;
    }
    onMo?.(visitId);
    router.refresh();
  };

  const gui = async (than: Record<string, unknown>) => {
    setDang(true);
    setLoi(null);
    const kq = await moLuot(than);
    setDang(false);
    if (kq.error) {
      setLoi(kq.error);
      return;
    }
    if (kq.trung) {
      setTrung(kq.matches ?? []);
      return;
    }
    if (kq.visit_id) xong(kq.visit_id);
  };

  const khachMoi = (force: boolean) =>
    void gui({
      khach_moi: { ho_ten: ten, sdt: sdt || null, nam_sinh: namSinh || null, force },
    });

  if (!mo) {
    return (
      <Button className={CHAM} size="md" variant="primary" onClick={() => setMo(true)}>
        Khách mua thuốc
      </Button>
    );
  }

  return (
    <section
      aria-label="Khách mua thuốc"
      className="w-full space-y-3 rounded-card border border-line bg-surface p-3 shadow-card"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-emph font-semibold text-ink">Khách mua thuốc (không khám)</h2>
        <Button className={CHAM} size="sm" variant="ghost" onClick={() => setMo(false)}>
          Đóng
        </Button>
      </div>
      <p className="text-meta text-ink-muted">
        Mở lượt bán lẻ: không tiền khám, không vào hàng chờ bác sĩ. Kê thuốc và thu tiền ngay
        tại quầy; thu xong lượt tự đóng. Khách cũ: bấm tên để xem lịch sử đơn thuốc và bán
        theo đơn.
      </p>
      {loi ? (
        <p role="alert" className="rounded-control bg-danger-bg px-3 py-2 text-meta text-danger">
          {loi}
        </p>
      ) : null}

      <div className="space-y-2">
        <input
          value={tim}
          onChange={(e) => {
            setTim(e.target.value);
            chonKhach(null);
          }}
          placeholder="Tìm khách: SĐT / mã khách / tên…"
          aria-label="Tìm khách có sẵn"
          className={INPUT}
        />
        {tim.trim().length >= 2 ? (
          ketQua.length === 0 ? (
            <p className="text-meta text-ink-muted">Không thấy khách — nhập khách mới bên dưới.</p>
          ) : (
            <ul className="divide-y divide-line rounded-control border border-line">
              {ketQua.map((k) => (
                <li
                  key={k.clinic_patient_id}
                  className={`flex flex-wrap items-center gap-2 px-3 py-2 ${
                    chon === k.clinic_patient_id ? "bg-brand-50" : ""
                  }`}
                >
                  <button
                    type="button"
                    aria-pressed={chon === k.clinic_patient_id}
                    title="Xem đơn gần nhất"
                    className="min-w-0 flex-1 text-left"
                    onClick={() => chonKhach(k.clinic_patient_id)}
                  >
                    <span className="block truncate text-body font-medium text-ink">
                      {k.full_name}
                    </span>
                    <span className="block truncate text-meta text-ink-muted">
                      {[k.patient_code, k.phone_primary, k.birth_year].filter(Boolean).join(" · ")}
                    </span>
                  </button>
                  <Button
                    className={CHAM}
                    size="sm"
                    variant="soft"
                    disabled={dang}
                    onClick={() => void gui({ clinic_patient_id: k.clinic_patient_id })}
                  >
                    Mở lượt mua thuốc
                  </Button>
                </li>
              ))}
            </ul>
          )
        ) : null}
        {chon ? (
          <div className="overflow-hidden rounded-control border border-line">
            <LichSuDonThuoc
              key={chon}
              clinicPatientId={chon}
              choSua
              onDoi={(_cau, loiMoi) => setLoi(loiMoi)}
              onMo={xong}
            />
          </div>
        ) : null}
      </div>

      <div className="space-y-2 border-t border-line pt-3">
        <p className="text-meta font-semibold uppercase tracking-wide text-ink-muted">
          Khách mới
        </p>
        <div className="grid gap-2 sm:grid-cols-3">
          <input
            value={ten}
            onChange={(e) => setTen(e.target.value)}
            placeholder="Họ tên"
            aria-label="Họ tên khách mới"
            className={INPUT}
          />
          <input
            value={sdt}
            onChange={(e) => setSdt(e.target.value)}
            inputMode="tel"
            placeholder="Số điện thoại"
            aria-label="Số điện thoại khách mới"
            className={INPUT}
          />
          <input
            value={namSinh}
            onChange={(e) => setNamSinh(e.target.value)}
            inputMode="numeric"
            placeholder="Năm sinh"
            aria-label="Năm sinh khách mới"
            className={INPUT}
          />
        </div>
        {trung ? (
          <div className="space-y-2 rounded-control bg-warning-bg px-3 py-2">
            <p className="text-meta text-warning">
              Số điện thoại này đã có hồ sơ — chọn đúng người, hoặc vẫn tạo khách mới (người nhà
              dùng chung số).
            </p>
            {trung.map((m) => (
              <div key={m.clinic_patient_id} className="flex flex-wrap items-center gap-2">
                <span className="min-w-0 flex-1 text-body text-ink">
                  {m.full_name} · {m.patient_code}
                </span>
                <Button
                  className={CHAM}
                  size="sm"
                  variant="soft"
                  disabled={dang}
                  onClick={() => void gui({ clinic_patient_id: m.clinic_patient_id })}
                >
                  Dùng hồ sơ này
                </Button>
              </div>
            ))}
            <Button
              className={CHAM}
              size="sm"
              variant="secondary"
              disabled={dang}
              onClick={() => khachMoi(true)}
            >
              Vẫn tạo khách mới
            </Button>
          </div>
        ) : null}
        <Button
          className={CHAM}
          size="md"
          variant="primary"
          disabled={dang || !ten.trim()}
          onClick={() => khachMoi(false)}
        >
          {dang ? "Đang mở…" : "Tạo khách & mở lượt mua thuốc"}
        </Button>
      </div>
    </section>
  );
}
