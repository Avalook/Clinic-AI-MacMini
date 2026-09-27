"use client";

// Bàn của đối tác: DANH SÁCH KHÁCH, mỗi khách một thẻ, dưới là việc của họ.
//
// Bản đầu liệt kê chỉ định phẳng — mỗi việc một dòng. Tuyền bác đúng: bàn đón
// NGƯỜI, không đón việc. Một khách tới lấy máu có thể mang hai ba chỉ định, và
// danh sách phẳng làm cùng một người hiện ba dòng cách xa nhau, đúng lúc người
// ngồi bàn đang cầm ống nghiệm và cần biết "người này còn gì nữa không".
//
// MỖI VIỆC VẪN MỘT NÚT GỬI RIÊNG, và vẫn KHÔNG có ô "chọn bệnh nhân". Đối tác
// không khai người nhận; họ chỉ nói "đây là kết quả của việc này", còn việc ấy
// thuộc về ai là do máy chủ tra ra. Thiếu ràng buộc đó thì một tài khoản ngoài
// phòng khám gửi được tệp cho bất kỳ ai — chỉ cần đoán đúng một mã.
//
// 17/09/2026 (Tuyền): thêm bước "Chờ tài liệu" giữa lấy mẫu và gửi kết quả, để
// CSKH thấy đối tác đã nhận việc; giao diện dùng chung khung với các vai khác
// (thanh chỉ số, thẻ, trạng thái dạng bậc thang).

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  CheckCircle2,
  Clock3,
  FileUp,
  FlaskConical,
  Hourglass,
  Inbox,
} from "lucide-react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";
import { doCoTep, guiTepCoTienDo } from "../../lib/gui-tep-co-tien-do";
import {
  EmptyWorkspace,
  Monogram,
  WorkspaceMetric,
  WorkspaceMetricRow,
} from "../(dashboard)/tasks/WorkspacePrimitives";

type TrangThai = "CHO_LAY_MAU" | "DA_LAY_MAU" | "CHO_TAI_LIEU" | "DA_GUI_KET_QUA";

interface Viec {
  chi_dinh_id: string;
  ten_dich_vu: string;
  chi_dinh_luc: string | null;
  trang_thai: TrangThai;
  lay_mau_luc: string | null;
  cho_tai_lieu_luc: string | null;
  ket_qua_luc: string | null;
  /** Ghi chú đối tác đã ghi (24/09/2026). */
  ghi_chu_lay_mau?: string | null;
  ghi_chu_tai_lieu?: string | null;
  /** Khách trả TRỰC TIẾP cho đối tác (Tuyền chốt 27/09/2026). */
  doi_tac_thu?: boolean;
  /** Giá tham khảo trong bảng giá phòng khám. */
  gia_tham_khao?: number | null;
  /** Ghi nhận "đã thu tiền khách" còn hiệu lực — null = chưa thu. */
  da_thu?: DaThu | null;
}

interface DaThu {
  id: string;
  so_tien: number;
  hinh_thuc: "CASH" | "TRANSFER";
  ghi_chu: string | null;
  luc: string | null;
}

const TEN_HINH_THUC: Record<DaThu["hinh_thuc"], string> = {
  CASH: "Tiền mặt",
  TRANSFER: "Chuyển khoản",
};

function tienVnd(n: number): string {
  return `${n.toLocaleString("vi-VN")}đ`;
}

interface Khach {
  clinic_patient_id: string;
  ten_khach: string;
  ma_khach: string;
  cho_tu: string | null;
  viec: Viec[];
}

type KetQua = { khach: Khach[]; so_viec: number } | { loi: string };

const BUOC: { ma: TrangThai; nhan: string }[] = [
  { ma: "CHO_LAY_MAU", nhan: "Lấy mẫu" },
  { ma: "DA_LAY_MAU", nhan: "Nhận mẫu" },
  { ma: "CHO_TAI_LIEU", nhan: "Chờ tài liệu" },
  { ma: "DA_GUI_KET_QUA", nhan: "Đã gửi tệp" },
];

const NHAN_TRANG_THAI: Record<TrangThai, { chu: string; mau: string }> = {
  CHO_LAY_MAU: { chu: "Chờ lấy mẫu", mau: "bg-warning-bg text-warning" },
  DA_LAY_MAU: { chu: "Đã có mẫu · chờ nhận", mau: "bg-brand-50 text-brand-700" },
  CHO_TAI_LIEU: { chu: "Đang chờ tài liệu", mau: "bg-brand-50 text-brand-700" },
  DA_GUI_KET_QUA: { chu: "Đã gửi tệp · chờ xác nhận", mau: "bg-success-bg text-success" },
};

function gioVn(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("vi-VN", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "—";
  }
}

function choBaoLau(iso: string | null): string {
  if (!iso) return "";
  const phut = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (!Number.isFinite(phut) || phut < 0) return "";
  if (phut < 60) return `chờ ${phut} phút`;
  const gio = Math.floor(phut / 60);
  if (gio < 24) return `chờ ${gio} giờ`;
  return `chờ ${Math.floor(gio / 24)} ngày`;
}

// Đọc danh sách — KHÔNG đụng state. Tách ra để chỗ gọi tự quyết định có nhận kết
// quả hay không: lần tải đầu chạy trong effect và phải bỏ kết quả nếu người dùng
// đã rời màn, còn lần tải lại sau khi gửi thì luôn nhận.
async function docDanhSach(): Promise<KetQua> {
  try {
    const r = await fetch("/api/doi-tac", { cache: "no-store" });
    const d = (await r.json().catch(() => null)) as
      | { khach?: Khach[]; so_viec?: number; error?: string; message?: string }
      | null;
    if (!r.ok) return { loi: d?.message ?? d?.error ?? "Không đọc được danh sách khách." };
    return { khach: d?.khach ?? [], so_viec: d?.so_viec ?? 0 };
  } catch {
    return { loi: "Mất kết nối tới máy chủ." };
  }
}

async function bamViec(
  duong: string,
  id: string,
  ghiChu: string,
  them: Record<string, unknown> = {},
): Promise<string | null> {
  try {
    const r = await fetch(duong, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ chi_dinh_id: id, ghi_chu: ghiChu.trim() || undefined, ...them }),
    });
    if (r.ok) return null;
    const d = (await r.json().catch(() => null)) as { error?: string; message?: string } | null;
    return d?.message ?? d?.error ?? "Không ghi được.";
  } catch {
    return "Mất kết nối — CHƯA ghi được.";
  }
}

type Loc = "can-lam" | "da-gui";

export default function BangDoiTac() {
  const [ds, setDs] = useState<Khach[] | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [dangLam, setDangLam] = useState<string | null>(null);
  const [tienDo, setTienDo] = useState<{ id: string; pt: number; ten: string } | null>(null);
  const [xong, setXong] = useState<string | null>(null);
  const [loc, setLoc] = useState<Loc>("can-lam");

  const nhan = useCallback((kq: KetQua) => {
    if ("loi" in kq) {
      setLoi(kq.loi);
      return;
    }
    setLoi(null);
    setDs(kq.khach);
  }, []);

  const tai = useCallback(async () => {
    nhan(await docDanhSach());
  }, [nhan]);

  useEffect(() => {
    let huy = false;
    const doc = () =>
      void docDanhSach().then((kq) => {
        if (!huy) nhan(kq);
      });
    doc();
    // Phòng khám chỉ định liên tục — không bắt đối tác tải lại trang.
    const t = setInterval(doc, 20000);
    return () => {
      huy = true;
      clearInterval(t);
    };
  }, [nhan]);

  const dem = useMemo(() => {
    const c: Record<TrangThai, number> = {
      CHO_LAY_MAU: 0,
      DA_LAY_MAU: 0,
      CHO_TAI_LIEU: 0,
      DA_GUI_KET_QUA: 0,
    };
    for (const k of ds ?? []) for (const v of k.viec) c[v.trang_thai] += 1;
    return c;
  }, [ds]);

  const hienThi = useMemo(
    () =>
      (ds ?? [])
        .map((k) => ({
          ...k,
          viec: k.viec.filter((v) =>
            loc === "da-gui"
              ? v.trang_thai === "DA_GUI_KET_QUA"
              : v.trang_thai !== "DA_GUI_KET_QUA",
          ),
        }))
        .filter((k) => k.viec.length > 0),
    [ds, loc],
  );

  const lamViec = useCallback(
    async (
      duong: string,
      v: Viec,
      k: Khach,
      bao: string,
      ghiChu = "",
      them: Record<string, unknown> = {},
    ): Promise<boolean> => {
      setDangLam(v.chi_dinh_id);
      setLoi(null);
      setXong(null);
      const l = await bamViec(duong, v.chi_dinh_id, ghiChu, them);
      if (l) setLoi(l);
      else setXong(`${bao} — ${v.ten_dich_vu} của ${k.ten_khach}.`);
      await tai();
      setDangLam(null);
      return l === null;
    },
    [tai],
  );

  const gui = useCallback(
    async (v: Viec, k: Khach, tep: File) => {
      setDangLam(v.chi_dinh_id);
      setLoi(null);
      setXong(null);
      setTienDo({ id: v.chi_dinh_id, pt: 0, ten: `${tep.name} · ${doCoTep(tep.size)}` });
      try {
        const fd = new FormData();
        fd.append("chi_dinh_id", v.chi_dinh_id);
        fd.append("file", tep);
        const r = await guiTepCoTienDo("/api/doi-tac", fd, (pt) =>
          setTienDo((t) => (t ? { ...t, pt } : t)),
        );
        if (!r.ok) {
          const d = r.data as { error?: string; message?: string } | null;
          setLoi(d?.message ?? d?.error ?? "Gửi không được.");
          return;
        }
        setXong(`Đã gửi tài liệu ${v.ten_dich_vu} của ${k.ten_khach}.`);
        await tai();
      } catch {
        setLoi("Mất kết nối — tệp CHƯA được gửi.");
      } finally {
        setTienDo(null);
        setDangLam(null);
      }
    },
    [tai],
  );

  if (loi && ds === null) {
    return (
      <p role="alert" className="rounded-card border border-danger bg-danger-bg px-4 py-3 text-body text-danger">
        {loi}
      </p>
    );
  }
  if (ds === null) {
    return <p className="text-body text-ink-muted">Đang tải…</p>;
  }

  return (
    <div className="space-y-4">
      <WorkspaceMetricRow>
        <WorkspaceMetric
          label="Chờ lấy mẫu"
          value={dem.CHO_LAY_MAU}
          icon={<FlaskConical className="size-5" />}
          tone={dem.CHO_LAY_MAU ? "warning" : "neutral"}
        />
        <WorkspaceMetric
          label="Có mẫu · chờ nhận"
          value={dem.DA_LAY_MAU}
          icon={<Inbox className="size-5" />}
          tone={dem.DA_LAY_MAU ? "brand" : "neutral"}
        />
        <WorkspaceMetric
          label="Đang chờ tài liệu"
          value={dem.CHO_TAI_LIEU}
          icon={<Hourglass className="size-5" />}
          tone={dem.CHO_TAI_LIEU ? "brand" : "neutral"}
        />
        <WorkspaceMetric
          label="Đã gửi hôm nay"
          value={dem.DA_GUI_KET_QUA}
          icon={<CheckCircle2 className="size-5" />}
          tone={dem.DA_GUI_KET_QUA ? "success" : "neutral"}
        />
      </WorkspaceMetricRow>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div
          role="tablist"
          aria-label="Lọc việc"
          className="inline-flex rounded-card border border-line bg-surface p-1 shadow-card"
        >
          {(
            [
              ["can-lam", `Cần làm (${dem.CHO_LAY_MAU + dem.DA_LAY_MAU + dem.CHO_TAI_LIEU})`],
              ["da-gui", `Đã gửi hôm nay (${dem.DA_GUI_KET_QUA})`],
            ] as [Loc, string][]
          ).map(([ma, nhanTab]) => (
            <button
              key={ma}
              type="button"
              role="tab"
              aria-selected={loc === ma}
              onClick={() => setLoc(ma)}
              className={`min-h-9 rounded-control px-3 text-sm font-medium ${
                loc === ma ? "bg-brand-600 text-white" : "text-ink-muted hover:text-ink"
              }`}
            >
              {nhanTab}
            </button>
          ))}
        </div>
        <p className="text-meta text-ink-muted">Tự cập nhật mỗi 20 giây</p>
      </div>

      {loi ? (
        <p role="alert" className="rounded-control border border-danger bg-danger-bg px-3 py-2 text-meta text-danger">
          {loi}
        </p>
      ) : null}
      {xong ? (
        <p role="status" className="rounded-control border border-success bg-success-bg px-3 py-2 text-meta text-success">
          {xong}
        </p>
      ) : null}

      {hienThi.length === 0 ? (
        <section className="rounded-card border border-line bg-surface p-4 shadow-card">
          <EmptyWorkspace
            title={loc === "da-gui" ? "Hôm nay chưa gửi kết quả nào" : "Không có việc nào đang chờ"}
            detail={
              loc === "da-gui"
                ? "Tài liệu gửi xong sẽ hiện ở đây để kiểm lại hoặc gửi thêm."
                : "Phòng khám chỉ định xét nghiệm / chụp chiếu gửi sang thì khách hiện ở đây."
            }
            icon={<Inbox className="size-7" />}
          />
        </section>
      ) : (
        <div className="grid gap-3 xl:grid-cols-2">
          {hienThi.map((k) => (
            <article
              key={k.clinic_patient_id}
              className="overflow-hidden rounded-card border border-line bg-surface shadow-card"
            >
              <header className="flex items-center gap-3 border-b border-line bg-surface-muted px-4 py-3">
                <Monogram value={k.ten_khach} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-body font-semibold text-ink">{k.ten_khach}</p>
                  <p className="text-meta text-ink-muted">Mã {k.ma_khach}</p>
                </div>
                <p className="flex shrink-0 items-center gap-1 text-meta text-ink-muted">
                  <Clock3 className="size-3.5" aria-hidden="true" />
                  {choBaoLau(k.cho_tu) || gioVn(k.cho_tu)}
                </p>
              </header>
              <ul className="divide-y divide-line">
                {k.viec.map((v) => (
                  <MotViec
                    key={v.chi_dinh_id}
                    viec={v}
                    dangLam={dangLam === v.chi_dinh_id}
                    tienDo={tienDo?.id === v.chi_dinh_id ? tienDo : null}
                    onLayMau={(g) =>
                      void lamViec("/api/doi-tac/da-lay-mau", v, k, "Đã ghi lấy mẫu", g)
                    }
                    onChoTaiLieu={(g) =>
                      void lamViec(
                        "/api/doi-tac/cho-tai-lieu",
                        v,
                        k,
                        "Đã nhận mẫu, chuyển sang chờ tài liệu",
                        g,
                      )
                    }
                    onGui={(tep) => void gui(v, k, tep)}
                    onDaThu={(soTien, hinhThuc, g) =>
                      lamViec("/api/doi-tac/da-thu-tien", v, k, "Đã ghi nhận thu tiền khách", g, {
                        so_tien: soTien,
                        hinh_thuc: hinhThuc,
                      })
                    }
                    onHuyThu={(lyDo) =>
                      lamViec("/api/doi-tac/huy-da-thu", v, k, "Đã huỷ ghi nhận thu tiền", "", {
                        ly_do: lyDo,
                      })
                    }
                  />
                ))}
              </ul>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

function MotViec({
  viec,
  dangLam,
  tienDo,
  onLayMau,
  onChoTaiLieu,
  onGui,
  onDaThu,
  onHuyThu,
}: {
  viec: Viec;
  dangLam: boolean;
  tienDo: { pt: number; ten: string } | null;
  onLayMau: (ghiChu: string) => void;
  onChoTaiLieu: (ghiChu: string) => void;
  onGui: (tep: File) => void;
  onDaThu: (soTien: string, hinhThuc: DaThu["hinh_thuc"], ghiChu: string) => Promise<boolean>;
  onHuyThu: (lyDo: string) => Promise<boolean>;
}) {
  const oTep = useRef<HTMLInputElement>(null);
  // Ghi chú đi kèm "Đã lấy mẫu" / "Nhận mẫu · chờ tài liệu" (24/09/2026).
  const [ghiChu, setGhiChu] = useState("");
  const tt = viec.trang_thai;
  const viTri = BUOC.findIndex((b) => b.ma === tt);
  const nhanTt = NHAN_TRANG_THAI[tt];
  const mocGanNhat =
    tt === "DA_GUI_KET_QUA"
      ? `Gửi lúc ${gioVn(viec.ket_qua_luc)}`
      : tt === "CHO_TAI_LIEU"
        ? `Nhận lúc ${gioVn(viec.cho_tai_lieu_luc)}`
        : tt === "DA_LAY_MAU"
          ? `Có mẫu lúc ${gioVn(viec.lay_mau_luc)}`
          : `Phòng khám gửi lúc ${gioVn(viec.chi_dinh_luc)}`;

  return (
    <li className="space-y-2.5 px-4 py-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-body font-medium text-ink">{viec.ten_dich_vu}</p>
          <p className="text-meta text-ink-muted">{mocGanNhat}</p>
        </div>
        <span className={`shrink-0 rounded-chip px-2 py-0.5 text-label font-semibold ${nhanTt.mau}`}>
          {nhanTt.chu}
        </span>
      </div>

      <ol className="grid grid-cols-4 gap-1" aria-label="Tiến độ việc">
        {BUOC.map((b, i) => (
          <li key={b.ma} className="min-w-0">
            <span
              className={`block h-1.5 rounded-full ${
                i < viTri || tt === "DA_GUI_KET_QUA"
                  ? "bg-success"
                  : i === viTri
                    ? "bg-brand-500"
                    : "bg-line"
              }`}
            />
            <span
              className={`mt-1 block truncate text-label ${
                i === viTri ? "font-semibold text-ink" : "text-ink-faint"
              }`}
            >
              {b.nhan}
            </span>
          </li>
        ))}
      </ol>

      {tienDo ? (
        <div className="space-y-1" role="status">
          <div className="h-1.5 overflow-hidden rounded-full bg-line">
            <div className="h-full bg-brand-500 transition-all" style={{ width: `${tienDo.pt}%` }} />
          </div>
          <p className="truncate text-label text-ink-muted">
            {tienDo.pt >= 100 ? "Đang cất tài liệu…" : `Đang gửi ${tienDo.pt}%`} · {tienDo.ten}
          </p>
        </div>
      ) : null}

      {viec.ghi_chu_lay_mau || viec.ghi_chu_tai_lieu ? (
        <div className="space-y-0.5 text-meta text-ink-soft">
          {viec.ghi_chu_lay_mau ? (
            <p className="whitespace-pre-wrap">Ghi chú lấy mẫu: {viec.ghi_chu_lay_mau}</p>
          ) : null}
          {viec.ghi_chu_tai_lieu ? (
            <p className="whitespace-pre-wrap">Ghi chú nhận mẫu: {viec.ghi_chu_tai_lieu}</p>
          ) : null}
        </div>
      ) : null}

      {viec.doi_tac_thu ? (
        <ThuTienKhach viec={viec} dangLam={dangLam} onDaThu={onDaThu} onHuyThu={onHuyThu} />
      ) : null}

      {tt === "CHO_LAY_MAU" || tt === "DA_LAY_MAU" ? (
        <label className="block">
          <span className="text-label font-semibold text-ink-muted">
            Ghi chú (tuỳ chọn)
          </span>
          <textarea
            value={ghiChu}
            onChange={(e) => setGhiChu(e.target.value)}
            rows={2}
            maxLength={2000}
            placeholder="VD: lấy mẫu lúc 10h, mẫu đủ; hẹn trả kết quả sau 3 ngày…"
            className="mt-1 w-full rounded-control border border-line bg-surface px-3 py-2 text-body text-ink"
          />
        </label>
      ) : null}

      <div className="flex flex-wrap justify-end gap-2">
        {tt === "CHO_LAY_MAU" ? (
          <button
            type="button"
            disabled={dangLam}
            onClick={() => onLayMau(ghiChu)}
            className="inline-flex min-h-10 items-center gap-1.5 rounded-control bg-brand-600 px-4 text-sm font-semibold text-white disabled:opacity-50"
          >
            <FlaskConical className="size-4" aria-hidden="true" />
            {dangLam ? "Đang ghi…" : "Đã lấy mẫu"}
          </button>
        ) : null}
        {tt === "DA_LAY_MAU" ? (
          <button
            type="button"
            disabled={dangLam}
            onClick={() => onChoTaiLieu(ghiChu)}
            className="inline-flex min-h-10 items-center gap-1.5 rounded-control bg-brand-600 px-4 text-sm font-semibold text-white disabled:opacity-50"
          >
            <Hourglass className="size-4" aria-hidden="true" />
            {dangLam ? "Đang ghi…" : "Nhận mẫu · chờ tài liệu"}
          </button>
        ) : null}
        <input
          ref={oTep}
          type="file"
          accept="image/*,video/mp4,video/quicktime,video/webm,application/pdf,.docx,.xlsx"
          className="hidden"
          onChange={(e) => {
            const t = e.target.files?.[0];
            // Xoá giá trị NGAY: chọn lại đúng tệp vừa gửi hỏng phải bắn được
            // sự kiện change lần nữa, không thì nút im lặng không làm gì.
            e.target.value = "";
            if (t) onGui(t);
          }}
        />
        {tt !== "CHO_LAY_MAU" ? (
          <button
            type="button"
            disabled={dangLam}
            onClick={() => oTep.current?.click()}
            className={`inline-flex min-h-10 items-center gap-1.5 rounded-control px-4 text-sm font-semibold disabled:opacity-50 ${
              tt === "CHO_TAI_LIEU"
                ? "bg-brand-600 text-white"
                : "border border-brand-500 text-brand-700 hover:bg-brand-50"
            }`}
          >
            <FileUp className="size-4" aria-hidden="true" />
            {dangLam && tienDo ? "Đang gửi…" : tt === "DA_GUI_KET_QUA" ? "Gửi thêm tài liệu" : "Tải tài liệu lên"}
          </button>
        ) : null}
      </div>
    </li>
  );
}

/** Khách trả TRỰC TIẾP cho đối tác (Tuyền chốt 27/09/2026, Q1): đối tác ghi
 *  nhận đã thu (số tiền mặc định = giá tham khảo, hình thức, ghi chú) và huỷ có
 *  lý do. Máy chủ kiểm số tiền / hình thức / lý do; màn chỉ gửi. */
function ThuTienKhach({
  viec,
  dangLam,
  onDaThu,
  onHuyThu,
}: {
  viec: Viec;
  dangLam: boolean;
  onDaThu: (soTien: string, hinhThuc: DaThu["hinh_thuc"], ghiChu: string) => Promise<boolean>;
  onHuyThu: (lyDo: string) => Promise<boolean>;
}) {
  const [mo, setMo] = useState<"thu" | "huy" | null>(null);
  const [soTien, setSoTien] = useState(
    viec.gia_tham_khao != null ? String(viec.gia_tham_khao) : "",
  );
  const [hinhThuc, setHinhThuc] = useState<DaThu["hinh_thuc"]>("CASH");
  const [ghiChu, setGhiChu] = useState("");
  const [lyDo, setLyDo] = useState("");
  const da = viec.da_thu;

  return (
    <div className="space-y-2 rounded-control bg-surface-muted px-3 py-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-meta text-ink-muted">
          Khách trả trực tiếp đối tác
          {viec.gia_tham_khao != null ? ` · tham khảo ${tienVnd(viec.gia_tham_khao)}` : ""}
        </p>
        {da ? (
          <Chip tone="success">
            Đã thu {tienVnd(da.so_tien)} · {TEN_HINH_THUC[da.hinh_thuc]}
          </Chip>
        ) : (
          <Chip tone="warning">Chưa thu</Chip>
        )}
      </div>
      {da?.ghi_chu ? <p className="whitespace-pre-wrap text-meta text-ink-soft">Ghi chú: {da.ghi_chu}</p> : null}
      {da?.luc ? <p className="text-label text-ink-faint">Ghi lúc {gioVn(da.luc)}</p> : null}

      {mo === "thu" && !da ? (
        <div className="grid gap-2 sm:grid-cols-2">
          <label className="block">
            <span className="text-label font-semibold text-ink-muted">Số tiền (đồng)</span>
            <input
              value={soTien}
              onChange={(e) => setSoTien(e.target.value)}
              inputMode="numeric"
              className="mt-1 h-10 w-full rounded-control border border-line bg-surface px-3 text-body tabular-nums text-ink"
            />
          </label>
          <label className="block">
            <span className="text-label font-semibold text-ink-muted">Hình thức</span>
            <select
              value={hinhThuc}
              onChange={(e) => setHinhThuc(e.target.value as DaThu["hinh_thuc"])}
              className="mt-1 h-10 w-full rounded-control border border-line bg-surface px-3 text-body text-ink"
            >
              <option value="CASH">Tiền mặt</option>
              <option value="TRANSFER">Chuyển khoản</option>
            </select>
          </label>
          <label className="block sm:col-span-2">
            <span className="text-label font-semibold text-ink-muted">Ghi chú (tuỳ chọn)</span>
            <input
              value={ghiChu}
              onChange={(e) => setGhiChu(e.target.value)}
              maxLength={2000}
              className="mt-1 h-10 w-full rounded-control border border-line bg-surface px-3 text-body text-ink"
            />
          </label>
        </div>
      ) : null}

      {mo === "huy" && da ? (
        <label className="block">
          <span className="text-label font-semibold text-ink-muted">Lý do huỷ ghi nhận</span>
          <input
            value={lyDo}
            onChange={(e) => setLyDo(e.target.value)}
            maxLength={2000}
            placeholder="VD: ghi nhầm số tiền"
            className="mt-1 h-10 w-full rounded-control border border-line bg-surface px-3 text-body text-ink"
          />
        </label>
      ) : null}

      <div className="flex flex-wrap justify-end gap-2">
        {mo === null && !da ? (
          <Button variant="soft" size="lg" disabled={dangLam} onClick={() => setMo("thu")}>
            Đã thu tiền khách
          </Button>
        ) : null}
        {mo === null && da ? (
          <Button variant="ghost" size="lg" disabled={dangLam} onClick={() => setMo("huy")}>
            Huỷ ghi nhận
          </Button>
        ) : null}
        {mo === "thu" && !da ? (
          <>
            <Button variant="ghost" size="lg" disabled={dangLam} onClick={() => setMo(null)}>
              Thôi
            </Button>
            <Button
              variant="primary"
              size="lg"
              disabled={dangLam || !soTien.trim()}
              onClick={() =>
                void onDaThu(soTien, hinhThuc, ghiChu).then((ok) => {
                  if (ok) setMo(null);
                })
              }
            >
              {dangLam ? "Đang ghi…" : "Ghi nhận đã thu"}
            </Button>
          </>
        ) : null}
        {mo === "huy" && da ? (
          <>
            <Button variant="ghost" size="lg" disabled={dangLam} onClick={() => setMo(null)}>
              Thôi
            </Button>
            <Button
              variant="danger"
              size="lg"
              disabled={dangLam || lyDo.trim().length < 3}
              onClick={() =>
                void onHuyThu(lyDo).then((ok) => {
                  if (ok) {
                    setMo(null);
                    setLyDo("");
                  }
                })
              }
            >
              {dangLam ? "Đang ghi…" : "Huỷ ghi nhận"}
            </Button>
          </>
        ) : null}
      </div>
    </div>
  );
}
