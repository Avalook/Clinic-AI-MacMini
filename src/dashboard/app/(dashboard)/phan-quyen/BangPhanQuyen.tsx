"use client";

// Danh sách người bên trái, KỸ NĂNG bên phải (Tuyền chốt 28/09/2026, bản "D"):
// phòng khám giao việc theo kỹ năng (file nhân sự: Phụ SA, Bio, TKYK…) nên màn
// cấp quyền nói đúng ngôn ngữ ấy. 21 lego (25/09) lùi vào "Ngoại lệ (nâng cao)"
// cho trường hợp một người cần thêm / bớt riêng một màn.

import { useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import { ROLE_LABEL, isClinicRole } from "@/lib/roles";
import KyNangCuaNguoi, { type KyNang } from "./KyNangCuaNguoi";
import LegoCuaNguoi from "./LegoCuaNguoi";
import NhomQuyenMau from "./NhomQuyenMau";
import QuyenTheoMan from "./QuyenTheoMan";

interface Nguoi {
  id: string;
  ten: string;
  vai: string;
}

interface QuyenCon {
  ma: string;
  ten: string;
  rui_ro: string;
  chung_chi_lam_sang: boolean;
}

interface Khoi {
  ma: string;
  ten: string;
  mo_ta: string;
  quyen: QuyenCon[];
}

interface DanhMuc {
  khoi: Khoi[];
  preset: Record<string, string[]>;
}

export default function BangPhanQuyen({
  nhanSu,
  chonTruoc,
}: {
  nhanSu: Nguoi[];
  chonTruoc?: string;
}) {
  const [danhMuc, setDanhMuc] = useState<DanhMuc | null>(null);
  const [chon, setChon] = useState<Nguoi | null>(
    nhanSu.find((n) => n.id === chonTruoc) ?? nhanSu[0] ?? null,
  );
  const [dangLam, setDangLam] = useState<string | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [tim, setTim] = useState("");
  // Hai việc khác nhau trên cùng một màn: cấp quyền CHO MỘT NGƯỜI, và sửa các
  // NHÓM MẪU dùng để cấp cho nhanh. Gộp vào một danh sách là mời người dùng
  // tưởng sửa nhóm thì quyền của người cũng đổi theo.
  const [tab, setTab] = useState<Tab>("nguoi");

  useEffect(() => {
    let huy = false;
    void fetch("/api/phan-quyen", { cache: "no-store" })
      .then((r) => (r.ok ? (r.json() as Promise<DanhMuc>) : null))
      .then((kq) => {
        if (huy) return;
        if (kq) setDanhMuc(kq);
        else setLoi("Không đọc được danh mục quyền.");
      });
    return () => {
      huy = true;
    };
  }, []);

  // Đổi key để khung lego đọc lại sau khi thêm gói mẫu.
  const [lanDoc, setLanDoc] = useState(0);

  // Kỹ năng của phòng khám + ai có kỹ năng nào (cột trái ghi dưới tên).
  const [kyNang, setKyNang] = useState<{ ds: KyNang[]; thanhVien: Record<string, string[]> } | null>(null);
  useEffect(() => {
    let huy = false;
    void fetch("/api/phan-quyen?ky-nang=1", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then((d: { ky_nang?: KyNang[]; thanh_vien?: Record<string, string[]> } | null) => {
        if (huy) return;
        if (d?.ky_nang) setKyNang({ ds: d.ky_nang, thanhVien: d.thanh_vien ?? {} });
      });
    return () => {
      huy = true;
    };
  }, [lanDoc]);
  const tenKyNang = (id: string) =>
    (kyNang?.thanhVien[id] ?? [])
      .map((ma) => kyNang?.ds.find((k) => k.ma === ma)?.ten)
      .filter(Boolean)
      .join(" · ");

  const themPreset = async (vai: string) => {
    if (!chon) return;
    setDangLam("preset");
    const r = await fetch("/api/phan-quyen", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        thao_tac: "them-preset",
        staff_id: chon.id,
        du_lieu: { vai },
      }),
    });
    setDangLam(null);
    if (!r.ok) {
      setLoi("Không thêm được gói mẫu.");
      return;
    }
    setLanDoc((n) => n + 1);
  };

  const tenVai = (vai: string) => (isClinicRole(vai) ? ROLE_LABEL[vai] : vai);

  const hienRa = nhanSu.filter((n) =>
    n.ten.toLocaleLowerCase("vi").includes(tim.trim().toLocaleLowerCase("vi")),
  );

  if (tab === "man") {
    return (
      <div className="grid grid-cols-[minmax(0,1fr)] gap-4">
        <ThanhChon tab={tab} onDoi={setTab} />
        <QuyenTheoMan />
      </div>
    );
  }

  if (tab === "nhom") {
    return (
      <div className="grid grid-cols-[minmax(0,1fr)] gap-4">
        <ThanhChon tab={tab} onDoi={setTab} />
        <NhomQuyenMau
          khoiCo={(danhMuc?.khoi ?? []).map((k) => ({ ma: k.ma, ten: k.ten }))}
        />
      </div>
    );
  }

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-4 lg:grid-cols-[minmax(0,20rem)_minmax(0,1fr)]">
      <div className="lg:col-span-2">
        <ThanhChon tab={tab} onDoi={setTab} />
      </div>
      <section
        aria-label="Nhân sự"
        className="rounded-card bg-surface-muted p-3 shadow-card"
      >
        <input
          value={tim}
          onChange={(e) => setTim(e.target.value)}
          placeholder="Tìm tên…"
          className="min-h-10 w-full rounded-control border border-line bg-surface px-3 text-sm text-ink"
        />
        <ul className="mt-2 flex max-h-[32rem] flex-col gap-1 overflow-y-auto">
          {hienRa.map((n) => (
            <li key={n.id}>
              <button
                type="button"
                onClick={() => setChon(n)}
                aria-current={chon?.id === n.id}
                className={`w-full rounded-control px-3 py-2 text-left text-sm ${
                  chon?.id === n.id
                    ? "bg-brand-50 font-semibold text-brand-700"
                    : "text-ink hover:bg-surface"
                }`}
              >
                {n.ten}
                <span className="block text-label font-normal text-ink-muted">
                  {tenKyNang(n.id) || tenVai(n.vai)}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section aria-label="Lego" className="rounded-card bg-surface-muted p-3.5 shadow-card">
        {loi ? (
          <p role="alert" className="mb-2 text-sm text-danger">
            {loi}
          </p>
        ) : null}

        {chon === null ? (
          <p className="text-sm text-ink-muted">Chọn một người để xem quyền.</p>
        ) : (
          <>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 className="text-sm font-semibold text-ink">{chon.ten}</h2>
                <p className="text-label text-ink-muted">
                  Tick kỹ năng người này làm — tick là mở đúng các màn, phòng ghi bên cạnh.
                </p>
              </div>
            </div>
            <KyNangCuaNguoi
              key={chon.id}
              staffId={chon.id}
              danhMuc={kyNang?.ds ?? []}
              nhanSu={nhanSu.map((n) => ({ id: n.id, ten: n.ten }))}
              onDoi={() => setLanDoc((n) => n + 1)}
              onLoi={setLoi}
            />
            {/* NGOẠI LỆ (nâng cao): 21 lego như trước — thêm / bớt riêng một màn
                cho một người khi kỹ năng không đủ (vd cho xem Báo cáo). */}
            <details className="mt-4 rounded-card border border-line bg-surface px-3 py-2">
              <summary className="cursor-pointer text-body font-medium text-ink-soft">
                Ngoại lệ (nâng cao) — bật / tắt từng màn riêng cho người này
              </summary>
              <div className="mt-2 flex justify-end">
                <Button
                  type="button"
                  variant="secondary"
                  disabled={dangLam !== null}
                  onClick={() => void themPreset(chon.vai)}
                >
                  {dangLam === "preset" ? "Đang thêm…" : `+ Thêm gói mẫu ${tenVai(chon.vai)}`}
                </Button>
              </div>
              <LegoCuaNguoi key={`${chon.id}-${lanDoc}`} staffId={chon.id} onLoi={setLoi} />
            </details>
          </>
        )}
      </section>
    </div>
  );
}

/** Đổi giữa "cấp cho một người" và "sửa nhóm mẫu". */
type Tab = "nguoi" | "nhom" | "man";

function ThanhChon({ tab, onDoi }: { tab: Tab; onDoi: (t: Tab) => void }) {
  const nut = (ma: Tab, chu: string) => (
    <button
      type="button"
      onClick={() => onDoi(ma)}
      aria-current={tab === ma}
      className={`min-h-10 rounded-control px-4 text-sm ${
        tab === ma
          ? "bg-brand-600 font-semibold text-white"
          : "border border-line bg-surface text-ink-soft hover:bg-surface-muted"
      }`}
    >
      {chu}
    </button>
  );
  return (
    <div className="flex flex-wrap gap-2">
      {nut("nguoi", "Quyền của từng người")}
      {nut("man", "Theo màn")}
      {nut("nhom", "Nhóm quyền mẫu")}
    </div>
  );
}
