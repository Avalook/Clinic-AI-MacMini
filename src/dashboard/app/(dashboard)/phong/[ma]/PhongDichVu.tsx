"use client";

// MỘT PHÒNG DỊCH VỤ: siêu âm, thủ thuật, lấy mẫu (Tuyền chốt 16/09/2026).
//
// Trái: hàng chờ của phòng. Phải: khách đang chọn —
//   Bắt đầu  → khách vào phòng (giờ vào)
//   ghi kết quả + gửi ảnh/video/PDF vào ô (xem ngay tại chỗ)
//   Xong     → khách ra phòng (giờ ra), sang bước tiếp theo
//
// Ai bấm được là do MÁY CHỦ quyết theo bước của chỉ định: siêu âm — bác sĩ hoặc
// điều dưỡng siêu âm; thủ thuật — CHỈ bác sĩ (điều dưỡng, thư ký hỗ trợ); lấy
// mẫu — điều dưỡng. Màn này không tự đoán, chỉ hiện câu từ chối của máy chủ.

import { useCallback, useEffect, useRef, useState } from "react";

import {
  docBang,
  guiThaoTac,
  gioVn,
  soPhutTu,
  type DongHangCho,
  type Phong,
  type PhongHomNay,
} from "../../_lam-viec/api";
import HangChoCot from "../../_lam-viec/HangChoCot";
import KhungTep from "../../_lam-viec/KhungTep";
import XemLuot from "../../_lam-viec/XemLuot";
import Button from "@/components/ui/Button";

type LoaiPhong = "SIEU_AM" | "THU_THUAT" | "LAY_MAU" | "KHAC";

function loaiCua(node: string | null): LoaiPhong {
  if (!node) return "KHAC";
  if (node === "DICHVU-SIEUAM") return "SIEU_AM";
  if (node.startsWith("DICHVU-LAYMAU")) return "LAY_MAU";
  if (node === "DICHVU-THUTHUAT" || node === "DICHVU-SANGLOC-COTUCUNG") {
    return "THU_THUAT";
  }
  return "KHAC";
}

const NHAN_KET_QUA: Record<LoaiPhong, string> = {
  SIEU_AM: "Kết quả siêu âm (mô tả, kết luận)",
  THU_THUAT: "Ghi thực hiện thủ thuật",
  LAY_MAU: "Ghi chú lấy mẫu (nếu có)",
  KHAC: "Ghi kết quả",
};

const NUT_XONG: Record<LoaiPhong, string> = {
  SIEU_AM: "Siêu âm xong",
  THU_THUAT: "Làm thủ thuật xong",
  LAY_MAU: "Đã lấy mẫu",
  KHAC: "Làm xong",
};

export default function PhongDichVu({
  ma,
  vaiTro,
}: {
  ma: string;
  vaiTro?: string | null;
}) {
  const [phong, setPhong] = useState<Phong | null>(null);
  const [khongCo, setKhongCo] = useState(false);
  const [hang, setHang] = useState<DongHangCho[] | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [chonId, setChonId] = useState<string | null>(null);
  const [lanNap, setLanNap] = useState(0);

  useEffect(() => {
    let huy = false;
    void docBang<PhongHomNay>("phong-hom-nay").then((kq) => {
      if (huy) return;
      if (!kq.ok) {
        setLoi(kq.loi);
        return;
      }
      const p = kq.data.tat_ca_phong.find((x) => x.code === ma) ?? null;
      setPhong(p);
      setKhongCo(p === null);
    });
    return () => {
      huy = true;
    };
  }, [ma]);

  useEffect(() => {
    if (!phong) return;
    let huy = false;
    const nap = async () => {
      const kq = await docBang<{ hang_cho: DongHangCho[] }>("hang-cho", {
        phong: phong.id,
      });
      if (huy) return;
      if (kq.ok) {
        setLoi(null);
        setHang(kq.data.hang_cho.filter((d) => d.loai === "DICH_VU"));
      } else setLoi(kq.loi);
    };
    void nap();
    const t = setInterval(() => void nap(), 15000);
    return () => {
      huy = true;
      clearInterval(t);
    };
  }, [phong, lanNap]);

  const napLai = useCallback(() => setLanNap((n) => n + 1), []);

  if (khongCo) {
    return (
      <p className="rounded-card border border-danger bg-danger-bg p-4 text-sm text-danger">
        Không có phòng “{ma}”, hoặc phòng đã tắt.
      </p>
    );
  }

  const ds = hang ?? [];
  const macDinh =
    ds.find((d) => d.trang_thai === "serving") ??
    ds.find((d) => d.trang_thai === "waiting" || d.trang_thai === "called") ??
    null;
  const chon = ds.find((d) => d.id === chonId) ?? macDinh;

  return (
    <div className="grid gap-4">
      <header className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h1 className="text-xl font-semibold text-ink">{phong?.ten ?? "Đang tải…"}</h1>
        {phong?.tang ? <p className="text-sm text-ink-muted">{phong.tang}</p> : null}
        {hang ? (
          <p className="text-sm text-ink-muted">
            {ds.filter((d) => d.trang_thai === "waiting" || d.trang_thai === "called").length}{" "}
            đang chờ · {ds.filter((d) => d.trang_thai === "serving").length} đang làm ·{" "}
            {ds.filter((d) => d.trang_thai === "done").length} đã xong
          </p>
        ) : null}
        {loi ? (
          <p role="alert" className="text-sm text-danger">
            {loi}
          </p>
        ) : null}
      </header>

      <div className="grid items-start gap-4 lg:grid-cols-[minmax(240px,0.6fr)_minmax(0,1.8fr)]">
        <aside aria-label="Hàng chờ phòng">
          {hang === null ? (
            <p className="text-sm text-ink-muted">Đang tải hàng chờ…</p>
          ) : (
            <HangChoCot
              dong={ds}
              chon={chon?.id ?? null}
              onChon={(id) => {
                setChonId(id);
                // Màn hẹp: khung khách nằm DƯỚI danh sách — tự cuộn tới (smoke
                // 18/09, 375).
                if (window.innerWidth < 1024) {
                  requestAnimationFrame(() =>
                    document
                      .getElementById("khung-khach-trong-phong")
                      ?.scrollIntoView({ block: "start" }),
                  );
                }
              }}
              trong="Chưa có khách nào được chỉ định vào phòng này."
            />
          )}
        </aside>
        {chon ? (
          <KhachTrongPhong
            key={chon.id}
            dong={chon}
            vaiTro={vaiTro}
            onDaBam={napLai}
          />
        ) : (
          <section className="grid min-h-72 place-items-center rounded-card bg-surface p-8 text-center text-sm text-ink-muted shadow-card">
            Chọn một khách trong hàng chờ.
          </section>
        )}
      </div>
    </div>
  );
}

function KhachTrongPhong({
  dong,
  vaiTro,
  onDaBam,
}: {
  dong: DongHangCho;
  vaiTro?: string | null;
  onDaBam: () => void;
}) {
  const loai = loaiCua(dong.node_code);
  const isProcedure = loai === "THU_THUAT";
  const chiXem = isProcedure && (vaiTro === "DOCTOR" || vaiTro === "BAC_SI");

  const [ketQua, setKetQua] = useState(dong.ket_qua_ghi ?? "");
  const [phienBan, setPhienBan] = useState(dong.phien_ban ?? 0);
  const [dangLuuNhap, setDangLuuNhap] = useState(false);
  const [daLuuNhap, setDaLuuNhap] = useState(false);
  const daKhoiTao = useRef(false);

  const [lyDo, setLyDo] = useState("");
  const [moKhongLam, setMoKhongLam] = useState(false);
  const [dangGui, setDangGui] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);
  const [xemLuot, setXemLuot] = useState(false);

  const dangLam = dong.trang_thai === "serving";
  const dangCho = dong.trang_thai === "waiting" || dong.trang_thai === "called";
  const daXong = dong.trang_thai === "done";

  // Tự động lưu nháp kết quả khi đang làm việc (Autosave với OCC versioning)
  useEffect(() => {
    if (!dangLam || chiXem) return;
    if (!daKhoiTao.current) {
      daKhoiTao.current = true;
      return;
    }
    const timer = setTimeout(async () => {
      setDangLuuNhap(true);
      setDaLuuNhap(false);
      try {
        const res = await fetch("/api/luot-kham", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            thao_tac: "luu-nhap-dich-vu",
            id: dong.ref_id,
            du_lieu: {
              result_note: ketQua,
              expected_version: phienBan,
            },
          }),
        });
        const data = (await res.json().catch(() => null)) as {
          version?: number;
          message?: string;
        } | null;
        if (res.ok && data?.version) {
          setPhienBan(data.version);
          setDaLuuNhap(true);
          setLoi(null);
        } else {
          setLoi(data?.message ?? "Không thể tự động lưu nháp.");
        }
      } catch {
        setLoi("Mất kết nối — chưa lưu nháp được.");
      } finally {
        setDangLuuNhap(false);
      }
    }, 1500);

    return () => clearTimeout(timer);
  }, [ketQua, dangLam, chiXem, dong.ref_id, phienBan]);

  const bam = async (thaoTac: string, duLieu: Record<string, unknown> = {}) => {
    setDangGui(true);
    setLoi(null);
    const kq = await guiThaoTac(thaoTac, dong.ref_id, duLieu);
    setDangGui(false);
    if (!kq.ok) setLoi(kq.loi);
    else onDaBam();
  };

  return (
    <section
      id="khung-khach-trong-phong"
      aria-label={`Khách ${dong.ten}`}
      className="min-w-0 space-y-4 rounded-card bg-surface p-4 shadow-card"
    >
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-label font-semibold uppercase tracking-wide text-ink-muted">
            Số {dong.so_thu_tu}
          </p>
          <h2 className="text-lg font-semibold text-ink">{dong.ten}</h2>
          <p className="text-sm text-ink-muted">
            {dong.ma_bn} · {dong.viec ?? "—"}
            {dong.bac_si ? ` · BS chỉ định: ${dong.bac_si}` : ""}
          </p>
          <p className="mt-1 text-label text-ink-muted">
            {daXong
              ? `Xong lúc ${gioVn(dong.xong_luc)}`
              : dangLam
                ? `Bắt đầu ${gioVn(dong.bat_dau_luc)} · đã làm ${soPhutTu(dong.bat_dau_luc)}`
                : dong.trang_thai === "blocked"
                  ? "Khách đang ở một bước khác — chưa gọi vào được."
                  : `Vào hàng ${gioVn(dong.vao_hang_luc)} · chờ ${soPhutTu(dong.vao_hang_luc)}`}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {dangCho && !chiXem ? (
            <button
              type="button"
              disabled={dangGui}
              onClick={() => void bam("bat-dau-dich-vu")}
              className="inline-flex min-h-11 items-center rounded-control bg-brand-600 px-5 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
            >
              {dangGui ? "Đang ghi…" : "Bắt đầu"}
            </button>
          ) : null}
          {chiXem ? (
            <span className="inline-flex items-center rounded-control bg-surface-muted px-3 py-1.5 text-xs font-medium text-ink-muted">
              Bác sĩ chỉ xem (Điều dưỡng vận hành)
            </span>
          ) : null}
        </div>
      </header>

      {loi ? (
        <p role="alert" className="rounded-control border border-danger bg-danger-bg px-3 py-2 text-sm text-danger">
          {loi}
        </p>
      ) : null}

      {/* ĐÃ XONG: xem lại đúng cái đã ghi */}
      {daXong ? (
        <div className="rounded-control bg-surface-muted px-3 py-2 text-sm">
          <p className="text-ink">
            {dong.exec_status === "not_performed" ? "Không làm được" : "Đã làm"}
            {dong.nguoi_lam ? ` · ${dong.nguoi_lam}` : ""} · {gioVn(dong.xong_luc)}
          </p>
          {dong.ly_do_khong_lam ? (
            <p className="text-xs text-warning">Lý do: {dong.ly_do_khong_lam}</p>
          ) : null}
          {dong.ket_qua_ghi ? (
            <p className="mt-1 whitespace-pre-line text-xs text-ink-soft">Kết quả đã ghi: {dong.ket_qua_ghi}</p>
          ) : null}
          <Button size="sm" variant="ghost" className="mt-1 -ml-3" onClick={() => setXemLuot(true)}>
            Xem lại cả lượt
          </Button>
          {xemLuot ? <XemLuot visitId={dong.visit_id} onDong={() => setXemLuot(false)} /> : null}
        </div>
      ) : null}

      {/* Ô TỆP: có ngay từ lúc khách đang làm, để gửi ảnh/video ngay khi chụp. */}
      {(dangLam || daXong) && loai !== "LAY_MAU" ? (
        <KhungTep
          clinicPatientId={dong.clinic_patient_id}
          serviceOrderId={dong.ref_id}
          choTaiLen={!chiXem}
          tieuDe={loai === "SIEU_AM" ? "Ảnh & video siêu âm" : "Ảnh · video · phiếu"}
        />
      ) : null}

      {dangLam ? (
        chiXem ? (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-ink">{NHAN_KET_QUA[loai]}</span>
              <span className="text-xs text-ink-muted">Bác sĩ chỉ xem</span>
            </div>
            <textarea
              value={ketQua}
              readOnly
              rows={6}
              className="mt-1 w-full rounded-control border border-line bg-surface-muted px-3 py-2 text-sm text-ink-soft"
              placeholder="(Chưa có nội dung ghi nhận)"
            />
          </div>
        ) : (
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-ink">{NHAN_KET_QUA[loai]}</span>
              <span className="text-xs text-ink-muted">
                {dangLuuNhap ? "Đang lưu nháp…" : daLuuNhap ? "Đã tự động lưu" : ""}
              </span>
            </div>
            <textarea
              value={ketQua}
              onChange={(e) => setKetQua(e.target.value)}
              rows={loai === "LAY_MAU" ? 2 : 6}
              className="mt-1 w-full rounded-control border border-line bg-surface px-3 py-2 text-sm text-ink"
              placeholder={
                loai === "SIEU_AM"
                  ? "Tử cung, nội mạc, buồng trứng P/T, kết luận…"
                  : loai === "THU_THUAT"
                    ? "Thủ thuật đã làm, diễn biến, dặn dò…"
                    : ""
              }
            />
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                disabled={dangGui}
                onClick={() =>
                  void bam("xong-dich-vu", { performed: true, result_note: ketQua })
                }
                className="inline-flex min-h-11 items-center rounded-control bg-success px-5 text-sm font-semibold text-white disabled:opacity-50"
              >
                {dangGui ? "Đang ghi…" : NUT_XONG[loai]}
              </button>
              <button
                type="button"
                onClick={() => setMoKhongLam((v) => !v)}
                className="inline-flex min-h-11 items-center rounded-control border border-line px-4 text-sm text-ink-soft hover:bg-surface-muted"
              >
                Không làm được…
              </button>
            </div>
            {moKhongLam ? (
              <div className="flex flex-wrap items-end gap-2">
                <label className="min-w-60 flex-1">
                  <span className="text-xs font-semibold text-ink">Lý do không làm được</span>
                  <input
                    value={lyDo}
                    onChange={(e) => setLyDo(e.target.value)}
                    className="mt-1 min-h-10 w-full rounded-control border border-line bg-surface px-3 text-sm text-ink"
                  />
                </label>
                <button
                  type="button"
                  disabled={dangGui || !lyDo.trim()}
                  onClick={() =>
                    void bam("xong-dich-vu", {
                      performed: false,
                      reason: lyDo,
                      result_note: ketQua,
                    })
                  }
                  className="inline-flex min-h-10 items-center rounded-control border border-danger px-4 text-sm font-semibold text-danger disabled:opacity-50"
                >
                  Ghi không làm được
                </button>
              </div>
            ) : null}
          </div>
        )
      ) : null}
    </section>
  );
}
