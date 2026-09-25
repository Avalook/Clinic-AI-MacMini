"use client";

// PHIẾU KHÁM CỦA MỘT LƯỢT — clinical shell nối gói bảy phiếu v5 vào Bàn khám
// (Tuyền 23/09/2026 tối: "form sửa theo như này đi… làm luôn").
//
//   · Phiếu: đọc/ghi `phieu_kham_luot` qua `/api/phieu-kham`. TỰ LƯU theo nhịp
//     gõ — KHÔNG có nút "Lưu hồ sơ" ("tôi bảo không cần nút lưu hồ sơ đó mà").
//     Hai người cùng gõ → máy chủ trả 409, màn nói ra và tải lại, không đè.
//   · Mục C / F: danh mục có giá → chỉ định thật (lệnh của Bàn khám truyền vào).
//   · Kết quả: hiện ngay dưới mục C; bác sĩ [Điền kết quả] tại chỗ.
//   · Mục E: đơn thuốc tự lưu qua đường đơn bệnh án sẵn có → tới nhà thuốc.
//   · KHÔNG KHOÁ: chế độ luôn "editable"; Hoàn tất ở Bàn khám chỉ là mốc giờ.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import Button, { buttonClass } from "@/components/ui/Button";
import type { ClinicalCompletionGate } from "@/lib/clinical-completion";
import {
  donTuDong,
  dongTuDon,
  type ChiDinhVaKetQua,
  type DauPhieu,
  type DinhNghiaPhieu,
  type DongDonMayChu,
  type DongThuoc,
  type MauKetQuaNgan,
  type NhomCls,
  type ONhap,
} from "@/lib/phieu-kham";
import DanhMucChiDinh from "./DanhMucChiDinh";
import PhieuKham, { type KetQuaLuu, type ThamChieu } from "./PhieuKham";

interface PhieuLuot extends DinhNghiaPhieu {
  du_lieu: Record<string, ONhap>;
  revision: number;
}

interface ThamChieuDu extends ThamChieu {
  chi_dinh_cls: NhomCls[];
}

const CHO_LUU_DON_MS = 1500;

async function doc<T>(url: string): Promise<T | null> {
  const r = await fetch(url, { cache: "no-store" }).catch(() => null);
  if (!r || !r.ok) return null;
  return (await r.json().catch(() => null)) as T | null;
}

async function ghi(than: unknown): Promise<{ ok: boolean; status: number; d: Record<string, unknown> | null }> {
  try {
    const r = await fetch("/api/phieu-kham", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(than),
    });
    const d = (await r.json().catch(() => null)) as Record<string, unknown> | null;
    return { ok: r.ok, status: r.status, d };
  } catch {
    return { ok: false, status: 0, d: null };
  }
}

function cauLoi(d: Record<string, unknown> | null, macDinh: string): string {
  const m = d?.message ?? d?.detail ?? d?.error;
  return typeof m === "string" && m ? m : macDinh;
}

export default function PhieuKhamLuot({
  visitId,
  clinicPatientId,
  choGhi,
  datChiDinh,
  onDaDat,
  onTrangThai,
  chiMuc,
}: {
  visitId: string;
  clinicPatientId: string;
  /** Người đang mở được ghi (bác sĩ / thư ký của lượt) — máy chủ vẫn kiểm lại. */
  choGhi: boolean;
  datChiDinh: (codes: string[]) => Promise<{ ok: true } | { ok: false; loi: string }>;
  onDaDat: () => void;
  /** Báo cho nút Hoàn tất: còn đang lưu dở / lỗi lưu thì nói ra. */
  onTrangThai?: (g: ClinicalCompletionGate) => void;
  /** Chỉ vẽ các mục này của phiếu (bàn tư vấn: `["B"]`). */
  chiMuc?: string[];
}) {
  const [chonPhieu, setChonPhieu] = useState<string | null>(null);
  const [phieu, setPhieu] = useState<PhieuLuot | null>(null);
  const [chonDuoc, setChonDuoc] = useState<{ form_id: string; ten: string }[] | null>(null);
  const [dau, setDau] = useState<DauPhieu | null>(null);
  const [ketQua, setKetQua] = useState<ChiDinhVaKetQua[]>([]);
  const [mauDuPhong, setMauDuPhong] = useState<MauKetQuaNgan[]>([]);
  const [tc, setTc] = useState<ThamChieuDu | null>(null);
  const [don, setDon] = useState<DongThuoc[]>([]);
  const [loi, setLoi] = useState<string | null>(null);
  const [loiDon, setLoiDon] = useState<string | null>(null);
  const [canLyDo, setCanLyDo] = useState(false);
  const [lyDo, setLyDo] = useState("");
  const revision = useRef(0);
  const henDon = useRef<ReturnType<typeof setTimeout> | null>(null);
  const soLanSuaDon = useRef(0);

  const napPhieu = useCallback(
    async (formId: string | null) => {
      const d = await doc<PhieuLuot & { form_id: string | null; chon_duoc?: { form_id: string; ten: string }[] }>(
        `/api/phieu-kham?visit_id=${visitId}&xem=phieu${formId ? `&chon=${formId}` : ""}`,
      );
      if (!d) {
        setLoi("Không đọc được phiếu khám của lượt này.");
        return;
      }
      if (!d.form_id) {
        setChonDuoc(d.chon_duoc ?? []);
        setPhieu(null);
        return;
      }
      revision.current = d.revision;
      setChonDuoc(null);
      setPhieu(d);
    },
    [visitId],
  );

  const napKetQua = useCallback(async () => {
    const d = await doc<{ chi_dinh: ChiDinhVaKetQua[]; mau_du_phong: MauKetQuaNgan[] }>(
      `/api/phieu-kham?visit_id=${visitId}`,
    );
    if (d) {
      setKetQua(d.chi_dinh);
      setMauDuPhong(d.mau_du_phong);
    }
  }, [visitId]);

  const napDon = useCallback(async () => {
    const d = await doc<{ dong: DongDonMayChu[] }>(
      `/api/phieu-kham?visit_id=${visitId}&xem=don-thuoc`,
    );
    return d ? d.dong.map(dongTuDon) : null;
  }, [visitId]);

  useEffect(() => {
    let huy = false;
    void (async () => {
      const [dp, t, dn] = await Promise.all([
        doc<DauPhieu>(`/api/phieu-kham?visit_id=${visitId}&xem=dau-phieu`),
        doc<ThamChieuDu>("/api/phieu-kham?xem=tham-chieu"),
        napDon(),
        napPhieu(null),
        napKetQua(),
      ]);
      if (huy) return;
      setDau(dp);
      setTc(t);
      if (dn) setDon(dn);
    })();
    return () => {
      huy = true;
      if (henDon.current) clearTimeout(henDon.current);
    };
  }, [visitId, napPhieu, napKetQua, napDon]);

  useEffect(() => {
    onTrangThai?.(
      loi || loiDon
        ? { ok: false, code: null, message: loi ?? loiDon }
        : { ok: true, code: null, message: null },
    );
  }, [loi, loiDon, onTrangThai]);

  const onLuu = useCallback(
    async (goi: Record<string, ONhap>): Promise<KetQuaLuu> => {
      if (!phieu) return { ok: false, loi: "Chưa mở phiếu." };
      const kq = await ghi({
        thao_tac: "luu-phieu",
        visit_id: visitId,
        form_id: phieu.form_id,
        du_lieu: goi,
        expected_revision: revision.current,
      });
      if (!kq.ok) {
        const cau =
          kq.status === 0
            ? "Mất kết nối — nội dung CHƯA được lưu."
            : cauLoi(kq.d, "Không lưu được phiếu.");
        setLoi(cau);
        if (kq.status === 409) void napPhieu(phieu.form_id);
        return { ok: false, loi: cau };
      }
      setLoi(null);
      revision.current = Number(kq.d?.revision ?? revision.current + 1);
      const canhBao = (kq.d?.canh_bao ?? []) as { ma: string; ten: string; loi: string }[];
      return { ok: true, canh_bao: canhBao };
    },
    [phieu, visitId, napPhieu],
  );

  const luuDon = useCallback(
    async (dong: DongThuoc[], lyDoGui: string | null) => {
      const lan = soLanSuaDon.current;
      const kq = await ghi({
        thao_tac: "luu-don",
        visit_id: visitId,
        dong: dong.filter((d) => d.ten_thuoc.trim()).map(donTuDong),
        ly_do: lyDoGui,
      });
      if (!kq.ok) {
        if (kq.d?.error === "PRESCRIPTION_CORRECTION_REASON_REQUIRED") setCanLyDo(true);
        setLoiDon(
          kq.status === 0
            ? "Mất kết nối — đơn thuốc CHƯA được lưu."
            : cauLoi(kq.d, "Không lưu được đơn thuốc."),
        );
        return;
      }
      setLoiDon(null);
      setCanLyDo(false);
      setLyDo("");
      // Nạp lại để dòng mới có MÃ — lần lưu sau không tạo trùng. Chưa gõ thêm
      // thì lấy nguyên bản máy chủ; đã gõ thêm thì chỉ gắn mã theo thứ tự dòng
      // có tên (máy chủ trả theo thứ tự tạo), không đè chữ vừa gõ.
      const moi = await napDon();
      if (!moi) return;
      if (soLanSuaDon.current === lan) {
        setDon(moi);
        return;
      }
      setDon((cu) => {
        let k = 0;
        return cu.map((d) => {
          if (!d.ten_thuoc.trim()) return d;
          const may = moi[k++];
          return d.id || !may ? d : { ...d, id: may.id };
        });
      });
    },
    [visitId, napDon],
  );

  const doiDon = (dong: DongThuoc[]) => {
    soLanSuaDon.current += 1;
    setDon(dong);
    if (henDon.current) clearTimeout(henDon.current);
    henDon.current = setTimeout(() => void luuDon(dong, null), CHO_LUU_DON_MS);
  };

  const daDat = useMemo(() => new Set(ketQua.map((k) => k.service_code)), [ketQua]);
  const goiYMau = useMemo(() => {
    const ra: Record<string, string> = {};
    for (const n of tc?.chi_dinh_cls ?? []) {
      for (const m of n.muc) {
        if (m.service_code && m.form_id_ket_qua) {
          ra[m.service_code] = m.form_id_ket_qua.replace(/^KQ_/, "");
        }
      }
    }
    for (const t of tc?.thu_thuat ?? []) {
      if (t.service_code && t.form_id_ket_qua) {
        ra[t.service_code] = t.form_id_ket_qua.replace(/^KQ_/, "");
      }
    }
    return ra;
  }, [tc]);

  const dat = async (codes: string[]) => {
    const kq = await datChiDinh(codes);
    if (kq.ok) {
      onDaDat();
      void napKetQua();
    }
    return kq;
  };

  if (chonDuoc) {
    return (
      <section className="space-y-3 rounded-card border border-hairline bg-surface p-4">
        <h2 className="text-title text-ink">Chọn phiếu khám cho lượt này</h2>
        <p className="text-body text-ink-muted">
          Loại khám của lượt chưa gắn phiếu nào. Chọn một phiếu để bắt đầu ghi.
        </p>
        <div className="flex flex-wrap gap-2">
          {chonDuoc.map((p) => (
            <Button
              key={p.form_id}
              type="button"
              variant={chonPhieu === p.form_id ? "primary" : "secondary"}
              disabled={!choGhi}
              onClick={() => {
                setChonPhieu(p.form_id);
                void napPhieu(p.form_id);
              }}
            >
              {p.ten}
            </Button>
          ))}
        </div>
      </section>
    );
  }

  if (!phieu) {
    return loi ? (
      <p role="alert" className="text-body text-danger">
        {loi}
      </p>
    ) : (
      <p className="text-body text-ink-muted">Đang mở phiếu khám…</p>
    );
  }

  const nhomThuThuat: NhomCls[] = [
    {
      nhom: "Thủ thuật / kỹ thuật điều trị",
      muc: (tc?.thu_thuat ?? []).map((t) => ({
        nhan: t.nhan,
        cach_tra_ket_qua: t.form_id_ket_qua ? "Có biểu mẫu" : "",
        form_id_ket_qua: t.form_id_ket_qua,
        service_code: t.service_code,
        gia: t.gia ?? null,
      })),
    },
  ];

  return (
    <div className="space-y-2">
      {loiDon ? (
        <div role="alert" className="space-y-2 rounded-control bg-danger-bg p-3 text-body text-danger">
          <p>Đơn thuốc: {loiDon}</p>
          {canLyDo ? (
            <div className="flex flex-wrap items-center gap-2">
              <input
                value={lyDo}
                onChange={(e) => setLyDo(e.target.value)}
                placeholder="Lý do đính chính đơn (đơn đã thu tiền / đã cấp)"
                aria-label="Lý do đính chính đơn thuốc"
                className="min-h-10 min-w-0 flex-1 rounded-control border border-line bg-surface px-3 text-body text-ink"
              />
              <Button
                type="button"
                variant="primary"
                disabled={!lyDo.trim()}
                onClick={() => void luuDon(don, lyDo.trim())}
              >
                Lưu đơn kèm lý do
              </Button>
            </div>
          ) : null}
        </div>
      ) : null}
      <PhieuKham
        key={`${phieu.form_id}-${phieu.version}`}
        dinhNghia={phieu}
        duLieu={phieu.du_lieu}
        cheDo={choGhi ? "editable" : "finalized_locked"}
        chiMuc={chiMuc}
        dauPhieu={dau}
        nutIn={
          // In phiếu khám (Tuyền 24/09/2026: "chỗ cho in phiếu khám của bệnh nhân
          // đâu?"). Mở tab riêng, ngoài thanh bên → in sạch khổ A4.
          <a
            href={`/print/phieu-kham/${visitId}`}
            target="_blank"
            rel="noopener"
            className={buttonClass("ghost", "sm")}
          >
            In phiếu khám
          </a>
        }
        ketQuaChiDinh={ketQua}
        onLuu={onLuu}
        thamChieuNgoai={tc}
        donThuoc={{ dong: don, onDoi: choGhi ? doiDon : undefined }}
        oChiDinhCls={
          <DanhMucChiDinh
            nhom={tc?.chi_dinh_cls ?? []}
            daDat={daDat}
            daChiDinh={ketQua}
            onDat={dat}
            chiDoc={!choGhi}
          />
        }
        oThuThuat={
          <DanhMucChiDinh
            nhom={nhomThuThuat}
            daDat={daDat}
            daChiDinh={ketQua}
            onDat={dat}
            chiDoc={!choGhi}
          />
        }
        ketQua={{
          mauDuPhong,
          goiYMau,
          choDien: choGhi,
          clinicPatientId,
          onDoi: () => {
            void napKetQua();
            onDaDat();
          },
        }}
      />
    </div>
  );
}
