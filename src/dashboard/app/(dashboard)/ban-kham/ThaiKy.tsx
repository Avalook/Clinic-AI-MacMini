"use client";

// THAI KỲ — batch pilot 18/09/2026, đặt cạnh phiếu Sản khoa ở Bàn khám.
//
// Trước đây bảng `pregnancy` không có lối ghi nào: không vai nào tạo được thai
// kỳ, và dự kiến sinh nằm rải ba chỗ. Màn này chỉ hiện và gửi; luật ở máy chủ:
//   · CHỈ BÁC SĨ tạo / sửa / ghi kết cục (thư ký, lễ tân chỉ xem);
//   · dự kiến sinh do bác sĩ nhập, BẮT BUỘC chọn nguồn — hệ thống không tự
//     tính dự kiến sinh (chưa có quy tắc Dr4Women);
//   · tuổi thai hiển thị là phép trừ từ dự kiến sinh đã xác nhận, ghi rõ vậy.

import { useCallback, useEffect, useState } from "react";

import Button from "@/components/ui/Button";

interface ThaiKyDong {
  id: string;
  ket_cuc: string;
  ngay_ket_cuc: string | null;
  kinh_cuoi: string | null;
  du_kien_sinh: string | null;
  nguon_du_kien_sinh: string | null;
  nguon_du_kien_sinh_nhan: string | null;
  tuoi_thai: { tuan: number; ngay: number } | null;
  nguy_co_cao: boolean;
  ly_do_nguy_co: string | null;
  bac_si_xac_nhan: string | null;
}
interface DuLieu {
  hien_tai: ThaiKyDong | null;
  truoc: ThaiKyDong[];
  duoc_ghi: boolean;
  nguon: { ma: string; nhan: string }[];
}

const KET_CUC: Record<string, string> = {
  DELIVERED: "Đã sinh",
  MISCARRIAGE: "Sảy thai",
  TERMINATED: "Đình chỉ thai",
  UNKNOWN: "Không rõ",
};
const INPUT =
  "min-h-10 rounded-control border border-line bg-surface px-3 text-sm text-ink";

export default function ThaiKy({
  clinicPatientId,
  visitId,
}: {
  clinicPatientId: string;
  visitId: string;
}) {
  const [dl, setDl] = useState<DuLieu | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [mo, setMo] = useState<"tao" | "sua" | "ket_cuc" | null>(null);
  const [dks, setDks] = useState("");
  const [nguon, setNguon] = useState("");
  const [kinhCuoi, setKinhCuoi] = useState("");
  const [nguyCo, setNguyCo] = useState(false);
  const [lyDo, setLyDo] = useState("");
  const [ketCuc, setKetCuc] = useState("");
  const [ngayKc, setNgayKc] = useState("");
  const [dangGui, setDangGui] = useState(false);

  const nap = useCallback(async () => {
    const r = await fetch(`/api/thai-ky?clinic_patient_id=${clinicPatientId}`, {
      cache: "no-store",
    });
    const d = await r.json().catch(() => null);
    if (r.ok) setDl(d as DuLieu);
    else setLoi((d as { message?: string; error?: string } | null)?.message ?? "Không đọc được thai kỳ.");
  }, [clinicPatientId]);

  useEffect(() => {
    let huy = false;
    void fetch(`/api/thai-ky?clinic_patient_id=${clinicPatientId}`, { cache: "no-store" })
      .then(async (r) => ({ ok: r.ok, d: await r.json().catch(() => null) }))
      .then(({ ok, d }) => {
        if (huy) return;
        if (ok) setDl(d as DuLieu);
        else setLoi((d as { message?: string } | null)?.message ?? "Không đọc được thai kỳ.");
      });
    return () => {
      huy = true;
    };
  }, [clinicPatientId]);

  const moForm = (loai: "tao" | "sua" | "ket_cuc") => {
    const ht = dl?.hien_tai;
    setDks(ht?.du_kien_sinh ?? "");
    setNguon(ht?.nguon_du_kien_sinh ?? "");
    setKinhCuoi(ht?.kinh_cuoi ?? "");
    setNguyCo(ht?.nguy_co_cao ?? false);
    setLyDo(ht?.ly_do_nguy_co ?? "");
    setKetCuc("");
    setNgayKc("");
    setLoi(null);
    setMo(loai);
  };

  const gui = async () => {
    const ht = dl?.hien_tai;
    const duLieu =
      mo === "ket_cuc"
        ? { ket_cuc: ketCuc, ngay_ket_cuc: ngayKc }
        : {
            ...(mo === "tao" ? { clinic_patient_id: clinicPatientId, visit_id: visitId } : {}),
            du_kien_sinh: dks,
            nguon_du_kien_sinh: nguon,
            kinh_cuoi: kinhCuoi || null,
            nguy_co_cao: nguyCo,
            ly_do_nguy_co: lyDo || null,
          };
    setDangGui(true);
    const r = await fetch("/api/thai-ky", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(mo === "tao" ? { du_lieu: duLieu } : { id: ht?.id, du_lieu: duLieu }),
    });
    const d = await r.json().catch(() => null);
    setDangGui(false);
    if (!r.ok) {
      setLoi((d as { message?: string; error?: string } | null)?.message ?? (d as { error?: string } | null)?.error ?? "Không lưu được.");
      return;
    }
    setMo(null);
    await nap();
  };

  const ht = dl?.hien_tai ?? null;

  return (
    <section aria-label="Thai kỳ" className="mt-3 rounded-card border border-line p-3">
      <h3 className="text-sm font-semibold text-ink">Thai kỳ</h3>
      {dl === null ? (
        <p className="mt-1 text-xs text-ink-muted">{loi ?? "Đang tải…"}</p>
      ) : ht ? (
        <dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-xs sm:grid-cols-4">
          <div>
            <dt className="text-ink-faint">Dự kiến sinh</dt>
            <dd className="font-medium text-ink">{ht.du_kien_sinh ?? "—"}</dd>
          </div>
          <div>
            <dt className="text-ink-faint">Nguồn</dt>
            <dd className="font-medium text-ink">
              {ht.nguon_du_kien_sinh_nhan ?? "chưa ghi"}
              {ht.bac_si_xac_nhan ? ` · BS ${ht.bac_si_xac_nhan}` : ""}
            </dd>
          </div>
          <div>
            <dt className="text-ink-faint">Tuổi thai (tính từ dự kiến sinh)</dt>
            <dd className="font-medium text-ink">
              {ht.tuoi_thai ? `${ht.tuoi_thai.tuan} tuần ${ht.tuoi_thai.ngay} ngày` : "—"}
            </dd>
          </div>
          <div>
            <dt className="text-ink-faint">Nguy cơ cao</dt>
            <dd className="font-medium text-ink">
              {ht.nguy_co_cao ? `Có — ${ht.ly_do_nguy_co ?? ""}` : "Không"}
            </dd>
          </div>
        </dl>
      ) : (
        <p className="mt-1 text-xs text-ink-muted">
          Chưa có thai kỳ đang theo dõi.
          {dl.duoc_ghi ? "" : " Bác sĩ tạo thai kỳ khi xác nhận có thai."}
        </p>
      )}
      {dl && dl.truoc.length > 0 ? (
        <p className="mt-2 text-xs text-ink-muted">
          Thai kỳ trước:{" "}
          {dl.truoc
            .map((t) => `${KET_CUC[t.ket_cuc] ?? t.ket_cuc}${t.ngay_ket_cuc ? ` ${t.ngay_ket_cuc}` : ""}`)
            .join(" · ")}
        </p>
      ) : null}

      {dl?.duoc_ghi && mo === null ? (
        <div className="mt-2 flex flex-wrap gap-2">
          {ht ? (
            <>
              <Button size="sm" onClick={() => moForm("sua")}>
                Sửa dự kiến sinh / nguy cơ
              </Button>
              <Button size="sm" variant="ghost" onClick={() => moForm("ket_cuc")}>
                Ghi kết cục thai kỳ
              </Button>
            </>
          ) : (
            <Button size="sm" variant="primary" onClick={() => moForm("tao")}>
              Tạo thai kỳ
            </Button>
          )}
        </div>
      ) : null}

      {mo ? (
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {mo === "ket_cuc" ? (
            <>
              <label className="grid gap-1 text-xs font-semibold text-ink">
                Kết cục
                <select value={ketCuc} onChange={(e) => setKetCuc(e.target.value)} className={INPUT}>
                  <option value="">— chọn —</option>
                  {Object.entries(KET_CUC).map(([ma, nhan]) => (
                    <option key={ma} value={ma}>
                      {nhan}
                    </option>
                  ))}
                </select>
              </label>
              <label className="grid gap-1 text-xs font-semibold text-ink">
                Ngày
                <input type="date" value={ngayKc} onChange={(e) => setNgayKc(e.target.value)} className={INPUT} />
              </label>
            </>
          ) : (
            <>
              <label className="grid gap-1 text-xs font-semibold text-ink">
                Dự kiến sinh (bác sĩ xác nhận)
                <input type="date" value={dks} onChange={(e) => setDks(e.target.value)} className={INPUT} />
              </label>
              <label className="grid gap-1 text-xs font-semibold text-ink">
                Nguồn của dự kiến sinh
                <select value={nguon} onChange={(e) => setNguon(e.target.value)} className={INPUT}>
                  <option value="">— chọn —</option>
                  {dl?.nguon.map((n) => (
                    <option key={n.ma} value={n.ma}>
                      {n.nhan}
                    </option>
                  ))}
                </select>
              </label>
              <label className="grid gap-1 text-xs font-semibold text-ink">
                Ngày đầu kỳ kinh cuối (nếu có)
                <input type="date" value={kinhCuoi} onChange={(e) => setKinhCuoi(e.target.value)} className={INPUT} />
              </label>
              <label className="flex items-center gap-2 text-xs font-semibold text-ink">
                <input type="checkbox" checked={nguyCo} onChange={(e) => setNguyCo(e.target.checked)} />
                Thai nguy cơ cao
              </label>
              {nguyCo ? (
                <label className="grid gap-1 text-xs font-semibold text-ink sm:col-span-2">
                  Lý do nguy cơ cao
                  <input value={lyDo} onChange={(e) => setLyDo(e.target.value)} className={INPUT} />
                </label>
              ) : null}
            </>
          )}
          <div className="flex flex-wrap gap-2 sm:col-span-2">
            <Button size="sm" variant="primary" disabled={dangGui} onClick={() => void gui()}>
              {dangGui ? "Đang lưu…" : "Lưu"}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setMo(null)}>
              Thôi
            </Button>
          </div>
          {loi ? (
            <p role="alert" className="text-xs text-danger sm:col-span-2">
              {loi}
            </p>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
