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

import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import Button, { buttonClass } from "@/components/ui/Button";
import type { ClinicalCompletionGate } from "@/lib/clinical-completion";
import { SU_KIEN_BANG } from "@/lib/nhip-lam-moi";
import {
  donTuDong,
  dongTuDon,
  phanThayDoi,
  type ChiDinhVaKetQua,
  type DauPhieu,
  type DinhNghiaPhieu,
  type DongDonMayChu,
  type DongThuoc,
  type MauKetQuaNgan,
  type NhomCls,
  type ONhap,
} from "@/lib/phieu-kham";
import { guiThaoTac } from "../api";
import DanhMucChiDinh from "./DanhMucChiDinh";
import HanhTrinhLuot from "./HanhTrinhLuot";
import LichSuSuaPhieu from "./LichSuSuaPhieu";
import PhieuKham, { type KetQuaLuu, type ThamChieu } from "./PhieuKham";

interface PhieuLuot extends DinhNghiaPhieu {
  du_lieu: Record<string, ONhap>;
  revision: number;
}

interface ThamChieuDu extends ThamChieu {
  chi_dinh_cls: NhomCls[];
}

const CHO_LUU_DON_MS = 1500;
/** Bảng mà đổi thì danh sách chỉ định + kết quả có thể đổi. */
const BANG_KET_QUA = new Set(["service_order", "form_instance", "tep_ket_qua"]);

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
  chanRay,
}: {
  visitId: string;
  clinicPatientId: string;
  /** Người đang mở được ghi (bác sĩ / thư ký của lượt) — máy chủ vẫn kiểm lại. */
  choGhi: boolean;
  datChiDinh: (
    codes: string[],
    /** Mã dịch vụ bác sĩ tick "Bắt buộc" (25/09/2026). */
    batBuoc: string[],
  ) => Promise<{ ok: true } | { ok: false; loi: string }>;
  onDaDat: () => void;
  /** Báo cho nút Hoàn tất: còn đang lưu dở / lỗi lưu thì nói ra. */
  onTrangThai?: (g: ClinicalCompletionGate) => void;
  /** Chỉ vẽ các mục này của phiếu (bàn tư vấn: `["B"]`). */
  chiMuc?: string[];
  /** Nút Hoàn tất của bàn khám — vẽ ở chân cột phải (Tuyền 27/09/2026). */
  chanRay?: ReactNode;
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
  /** Bản đã lưu gần nhất — tự lưu chỉ gửi phần khác bản này (lát 2). */
  const daLuu = useRef<Record<string, ONhap>>({});
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
      daLuu.current = d.du_lieu ?? {};
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

  // KẾT QUẢ TỰ HIỆN (lát 4, 26/09/2026). Màn này tự fetch nên `router.refresh`
  // không với tới — nghe chung dòng tin của RealtimeRefresher (không mở kết nối
  // riêng). CHỈ nạp lại danh sách chỉ định + kết quả (chỉ đọc); phiếu đang gõ
  // KHÔNG nạp lại để không đè chữ người đang nhập.
  useEffect(() => {
    let hen: ReturnType<typeof setTimeout> | undefined;
    const khiBangDoi = (ev: Event) => {
      const bang = (ev as CustomEvent<string | null>).detail;
      if (bang !== null && !BANG_KET_QUA.has(bang)) return;
      if (document.visibilityState === "hidden") return;
      clearTimeout(hen);
      hen = setTimeout(() => void napKetQua(), 250);
    };
    window.addEventListener(SU_KIEN_BANG, khiBangDoi);
    return () => {
      clearTimeout(hen);
      window.removeEventListener(SU_KIEN_BANG, khiBangDoi);
    };
  }, [napKetQua]);

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
      const thayDoi = phanThayDoi(goi, daLuu.current);
      if (Object.keys(thayDoi).length === 0) return { ok: true };
      const kq = await ghi({
        thao_tac: "luu-phieu",
        visit_id: visitId,
        form_id: phieu.form_id,
        thay_doi: thayDoi,
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
      daLuu.current = { ...daLuu.current, ...thayDoi };
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
  // "Trên phiếu giấy: SÂ 2D TC-BT" — nhãn phiếu chỉ định giấy của từng mã (27/09).
  const nhanGiay = useMemo(() => {
    const ra: Record<string, string> = {};
    for (const n of tc?.chi_dinh_cls ?? []) {
      for (const m of n.muc) if (m.service_code && !ra[m.service_code]) ra[m.service_code] = m.nhan;
    }
    return ra;
  }, [tc]);
  // Mã thủ thuật — kết quả của chúng hiện ở khối 3, không lẫn vào khối 2.
  const maThuThuat = useMemo(
    () => new Set((tc?.thu_thuat ?? []).flatMap((t) => (t.service_code ? [t.service_code] : []))),
    [tc],
  );
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

  const dat = async (codes: string[], batBuoc: string[]) => {
    const kq = await datChiDinh(codes, batBuoc);
    if (kq.ok) {
      onDaDat();
      void napKetQua();
    }
    return kq;
  };

  // Bật / tắt "Bắt buộc" của chỉ định đã đặt (chưa thu tiền) — 25/09/2026.
  const doiBatBuoc = async (orderId: string, batBuoc: boolean) => {
    const kq = await guiThaoTac("bat-buoc", orderId, { bat_buoc: batBuoc });
    if (kq.ok) void napKetQua();
    return kq.ok ? ({ ok: true } as const) : ({ ok: false, loi: kq.loi } as const);
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
      {/* Bàn tư vấn chỉ vẽ mục B — dải hành trình là của phiếu bác sĩ chính. */}
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
        // Bàn tư vấn chỉ vẽ mục B — dải hành trình là của phiếu bác sĩ chính.
        dauTrang={chiMuc ? undefined : <HanhTrinhLuot visitId={visitId} />}
        chanRay={chanRay}
        nutIn={
          <>
          {/* In phiếu khám (Tuyền 24/09/2026: "chỗ cho in phiếu khám của bệnh nhân
              đâu?"). Mở tab riêng, ngoài thanh bên → in sạch khổ A4. Bản mẫu:
              nút ở CHÂN CỘT PHẢI, trên Hoàn tất (27/09). */}
          <a
            href={`/print/phieu-kham/${visitId}`}
            target="_blank"
            rel="noopener"
            className={`${buttonClass("secondary", "md")} lg:w-full`}
          >
            In phiếu khám
          </a>
          <LichSuSuaPhieu visitId={visitId} dinhNghia={phieu} />
          </>
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
            onDoiBatBuoc={choGhi ? doiBatBuoc : undefined}
            chiDoc={!choGhi}
          />
        }
        oThuThuat={
          <DanhMucChiDinh
            nhom={nhomThuThuat}
            daDat={daDat}
            daChiDinh={ketQua}
            onDat={dat}
            onDoiBatBuoc={choGhi ? doiBatBuoc : undefined}
            chiDoc={!choGhi}
          />
        }
        maThuThuat={maThuThuat}
        ketQua={{
          mauDuPhong,
          goiYMau,
          nhanGiay,
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
