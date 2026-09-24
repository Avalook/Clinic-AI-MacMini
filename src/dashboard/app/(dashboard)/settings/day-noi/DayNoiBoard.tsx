"use client";

// Khối chỉnh dây — CHỈ VẼ + gửi lệnh. Máy chủ giữ luật (giới hạn số, loại không
// vừa qua tư vấn vừa đi thẳng phòng, vai hợp lệ) và quyền `config.wiring.manage`.

import { useCallback, useEffect, useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";

interface Day {
  ma: string;
  nhan: string;
  kieu: "bat_tat" | "so";
  gia_tri: boolean | number;
  mac_dinh: boolean | number;
  nho_nhat: number;
  lon_nhat: number;
  don_vi: string;
}
interface LoaiKham {
  id: string;
  code: string;
  name: string;
  qua_tu_van: boolean;
  di_thang_phong: boolean;
}
interface Chuong {
  su_kien: string;
  nhan: string;
  vai: string[];
  bac_si_chinh: boolean;
  bat: boolean;
}
interface ViTri {
  id: string;
  code: string;
  ten: string;
  ten_ngan: string | null;
  tang: string | null;
  nhom_nghe: string;
  room_id: string | null;
  is_active: boolean;
}
interface DuLieu {
  day: Day[];
  loai_kham: LoaiKham[];
  chuong: Chuong[];
  vai_nhan: string[];
  vi_tri: ViTri[];
  phong: { id: string; name: string }[];
  nhom_nghe: string[];
}

const TEN_VAI: Record<string, string> = {
  CSKH: "CSKH",
  RECEPTION: "Lễ tân",
  TKYK: "Thư ký y khoa",
  DOCTOR: "Bác sĩ",
  ULTRASOUND_DOCTOR: "BS siêu âm",
  NURSE_ULTRASOUND: "Điều dưỡng",
  TRUONG_CA: "Trưởng ca",
  MANAGEMENT: "Quản lý",
  CASHIER: "Thu ngân",
  PHARMACIST: "Dược sĩ",
};
const TEN_NHOM: Record<string, string> = {
  BAC_SI: "Bác sĩ",
  DIEU_DUONG: "Điều dưỡng / hỗ trợ",
  DOI_TAC: "Đối tác",
  CHUNG: "Chung",
};

const O_NHAP =
  "min-h-10 rounded-control border border-line bg-surface px-3 text-body text-ink";

export default function DayNoiBoard() {
  const [dl, setDl] = useState<DuLieu | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [xong, setXong] = useState<string | null>(null);
  const [dang, setDang] = useState(false);

  const doc = useCallback(async () => {
    const r = await fetch("/api/day-noi", { cache: "no-store" });
    const d = (await r.json().catch(() => null)) as (DuLieu & { message?: string }) | null;
    if (!r.ok || !d) return { loi: d?.message ?? "Không đọc được dây nối." };
    return { dl: d };
  }, []);

  const tai = useCallback(async () => {
    const kq = await doc();
    if (kq.dl) {
      setDl(kq.dl);
      setLoi(null);
    } else setLoi(kq.loi ?? null);
  }, [doc]);

  useEffect(() => {
    let huy = false;
    void doc().then((kq) => {
      if (huy) return;
      if (kq.dl) setDl(kq.dl);
      else setLoi(kq.loi ?? null);
    });
    return () => {
      huy = true;
    };
  }, [doc]);

  const gui = async (thao_tac: string, du_lieu: unknown, cau: string, id?: string) => {
    setDang(true);
    setLoi(null);
    setXong(null);
    try {
      const r = await fetch("/api/day-noi", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ thao_tac, id, du_lieu }),
      });
      const d = (await r.json().catch(() => null)) as { message?: string; error?: string } | null;
      if (!r.ok) setLoi(d?.message ?? d?.error ?? "Không lưu được.");
      else setXong(cau);
      await tai();
    } catch {
      setLoi("Mất kết nối — CHƯA lưu.");
    } finally {
      setDang(false);
    }
  };

  if (loi && !dl) {
    return (
      <p role="alert" className="text-body text-danger">
        {loi}
      </p>
    );
  }
  if (!dl) return <p className="text-body text-ink-muted">Đang tải…</p>;

  return (
    <div className="space-y-4">
      {loi ? (
        <p role="alert" className="rounded-control border border-danger bg-danger-bg px-3 py-2 text-meta text-danger">
          {loi}
        </p>
      ) : null}
      {xong ? (
        <p className="rounded-control border border-success bg-success-bg px-3 py-2 text-meta text-success">
          {xong}
        </p>
      ) : null}

      <Khung tieuDe="Dây hành trình khách" ghiChu="Bật/tắt và thời hạn — áp dụng ngay cho khách tiếp theo.">
        <ul className="space-y-3">
          {dl.day.map((d) => (
            <DongDay key={d.ma} d={d} dang={dang} gui={gui} />
          ))}
        </ul>
      </Khung>

      <Khung
        tieuDe="Loại khám / loại lịch"
        ghiChu="Qua tư vấn: đo sinh hiệu → bác sĩ tư vấn → bác sĩ chính. Đi thẳng phòng: làm chỉ định hẹn từ lượt trước, không qua bác sĩ."
      >
        <ul className="divide-y divide-line">
          {dl.loai_kham.map((l) => (
            <li key={l.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <span className="text-body text-ink">{l.name}</span>
              <span className="flex flex-wrap gap-3">
                <label className="flex min-h-10 items-center gap-2 text-meta text-ink">
                  <input
                    type="checkbox"
                    className="size-4 accent-brand-600"
                    checked={l.qua_tu_van}
                    disabled={dang}
                    onChange={(e) =>
                      void gui(
                        "loai-kham",
                        { qua_tu_van: e.target.checked, ...(e.target.checked ? { di_thang_phong: false } : {}) },
                        `Đã đổi "${l.name}".`,
                        l.id,
                      )
                    }
                  />
                  Qua tư vấn
                </label>
                <label className="flex min-h-10 items-center gap-2 text-meta text-ink">
                  <input
                    type="checkbox"
                    className="size-4 accent-brand-600"
                    checked={l.di_thang_phong}
                    disabled={dang}
                    onChange={(e) =>
                      void gui(
                        "loai-kham",
                        { di_thang_phong: e.target.checked, ...(e.target.checked ? { qua_tu_van: false } : {}) },
                        `Đã đổi "${l.name}".`,
                        l.id,
                      )
                    }
                  />
                  Đi thẳng phòng
                </label>
              </span>
            </li>
          ))}
        </ul>
      </Khung>

      <Khung tieuDe="Ai nhận chuông" ghiChu="Vai nhận thấy chuông khi đứng vai ấy; bác sĩ chính nhận đích danh.">
        <ul className="space-y-3">
          {dl.chuong.map((c) => (
            <DongChuong key={c.su_kien} c={c} vaiNhan={dl.vai_nhan} dang={dang} gui={gui} />
          ))}
        </ul>
      </Khung>

      <Khung tieuDe="Vị trí trực" ghiChu="Vị trí dùng để xếp lịch trực và mở màn theo vị trí. Tắt thì không xếp lịch mới vào được.">
        <ViTriMoi dl={dl} dang={dang} gui={gui} />
        <ul className="mt-3 divide-y divide-line">
          {dl.vi_tri.map((v) => (
            <DongViTri key={v.id} v={v} phong={dl.phong} dang={dang} gui={gui} />
          ))}
        </ul>
      </Khung>
    </div>
  );
}

type Gui = (thao_tac: string, du_lieu: unknown, cau: string, id?: string) => Promise<void>;

function Khung({
  tieuDe,
  ghiChu,
  children,
}: {
  tieuDe: string;
  ghiChu: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-card border border-line bg-surface p-4 shadow-card">
      <h2 className="text-emph font-semibold text-ink">{tieuDe}</h2>
      <p className="mb-3 text-meta text-ink-muted">{ghiChu}</p>
      {children}
    </section>
  );
}

function DongDay({ d, dang, gui }: { d: Day; dang: boolean; gui: Gui }) {
  const [so, setSo] = useState(String(d.gia_tri));
  if (d.kieu === "bat_tat") {
    return (
      <li className="flex flex-wrap items-center justify-between gap-2">
        <span className="min-w-0 flex-1 text-body text-ink">{d.nhan}</span>
        <Button
          size="lg"
          variant={d.gia_tri ? "primary" : "secondary"}
          disabled={dang}
          onClick={() => void gui("day", { ma: d.ma, gia_tri: !d.gia_tri }, "Đã đổi dây.")}
        >
          {d.gia_tri ? "Đang bật" : "Đang tắt"}
        </Button>
      </li>
    );
  }
  return (
    <li className="flex flex-wrap items-center justify-between gap-2">
      <span className="min-w-0 flex-1 text-body text-ink">{d.nhan}</span>
      <span className="flex items-center gap-2">
        <input
          type="number"
          min={d.nho_nhat}
          max={d.lon_nhat}
          value={so}
          aria-label={d.nhan}
          onChange={(e) => setSo(e.target.value)}
          className={`${O_NHAP} w-24`}
        />
        <span className="text-meta text-ink-muted">{d.don_vi}</span>
        <Button
          size="lg"
          disabled={dang || so === String(d.gia_tri) || so.trim() === ""}
          onClick={() => void gui("day", { ma: d.ma, gia_tri: Number(so) }, "Đã đổi dây.")}
        >
          Lưu
        </Button>
      </span>
    </li>
  );
}

function DongChuong({
  c,
  vaiNhan,
  dang,
  gui,
}: {
  c: Chuong;
  vaiNhan: string[];
  dang: boolean;
  gui: Gui;
}) {
  const [vai, setVai] = useState<Set<string>>(() => new Set(c.vai));
  const [bs, setBs] = useState(c.bac_si_chinh);
  const [bat, setBat] = useState(c.bat);
  return (
    <li className="rounded-control border border-line p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-body font-semibold text-ink">{c.nhan}</span>
        <label className="flex min-h-10 items-center gap-2 text-meta text-ink">
          <input
            type="checkbox"
            className="size-4 accent-brand-600"
            checked={bat}
            onChange={(e) => setBat(e.target.checked)}
          />
          Bật chuông
        </label>
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
        <label className="flex min-h-10 items-center gap-2 text-meta text-ink">
          <input
            type="checkbox"
            className="size-4 accent-brand-600"
            checked={bs}
            onChange={(e) => setBs(e.target.checked)}
          />
          Bác sĩ chính (đích danh)
        </label>
        {vaiNhan.map((v) => (
          <label key={v} className="flex min-h-10 items-center gap-2 text-meta text-ink">
            <input
              type="checkbox"
              className="size-4 accent-brand-600"
              checked={vai.has(v)}
              onChange={(e) => {
                const moi = new Set(vai);
                if (e.target.checked) moi.add(v);
                else moi.delete(v);
                setVai(moi);
              }}
            />
            {TEN_VAI[v] ?? v}
          </label>
        ))}
      </div>
      <div className="mt-2">
        <Button
          size="lg"
          variant="primary"
          disabled={dang}
          onClick={() =>
            void gui(
              "chuong",
              { su_kien: c.su_kien, vai: [...vai], bac_si_chinh: bs, bat },
              `Đã lưu người nhận chuông "${c.nhan}".`,
            )
          }
        >
          Lưu người nhận
        </Button>
      </div>
    </li>
  );
}

function ViTriMoi({ dl, dang, gui }: { dl: DuLieu; dang: boolean; gui: Gui }) {
  const [ten, setTen] = useState("");
  const [nhom, setNhom] = useState(dl.nhom_nghe[0] ?? "CHUNG");
  const [phong, setPhong] = useState("");
  return (
    <div className="flex flex-wrap items-end gap-2">
      <input
        value={ten}
        onChange={(e) => setTen(e.target.value)}
        placeholder="Tên vị trí mới (vd: Siêu âm 3)"
        aria-label="Tên vị trí mới"
        className={`${O_NHAP} flex-1`}
      />
      <select
        value={nhom}
        onChange={(e) => setNhom(e.target.value)}
        aria-label="Nhóm nghề"
        className={O_NHAP}
      >
        {dl.nhom_nghe.map((n) => (
          <option key={n} value={n}>
            {TEN_NHOM[n] ?? n}
          </option>
        ))}
      </select>
      <select
        value={phong}
        onChange={(e) => setPhong(e.target.value)}
        aria-label="Gắn phòng"
        className={O_NHAP}
      >
        <option value="">(không gắn phòng)</option>
        {dl.phong.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name}
          </option>
        ))}
      </select>
      <Button
        size="lg"
        variant="primary"
        disabled={dang || ten.trim() === ""}
        onClick={() =>
          void gui(
            "vi-tri-moi",
            { ten: ten.trim(), nhom_nghe: nhom, room_id: phong || null },
            `Đã thêm vị trí "${ten.trim()}".`,
          ).then(() => setTen(""))
        }
      >
        + Thêm vị trí
      </Button>
    </div>
  );
}

function DongViTri({
  v,
  phong,
  dang,
  gui,
}: {
  v: ViTri;
  phong: { id: string; name: string }[];
  dang: boolean;
  gui: Gui;
}) {
  const [ten, setTen] = useState(v.ten);
  return (
    <li className="flex flex-wrap items-center gap-2 py-2">
      <input
        value={ten}
        onChange={(e) => setTen(e.target.value)}
        aria-label={`Tên vị trí ${v.ten}`}
        className={`${O_NHAP} min-w-0 flex-1`}
      />
      <Chip tone={v.is_active ? "success" : "neutral"}>{v.is_active ? "đang dùng" : "đã tắt"}</Chip>
      <select
        value={v.room_id ?? ""}
        disabled={dang}
        aria-label={`Phòng của ${v.ten}`}
        onChange={(e) =>
          void gui(
            "vi-tri",
            e.target.value ? { room_id: e.target.value } : { bo_phong: true },
            "Đã đổi phòng của vị trí.",
            v.id,
          )
        }
        className={O_NHAP}
      >
        <option value="">(không gắn phòng)</option>
        {phong.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name}
          </option>
        ))}
      </select>
      <Button
        size="lg"
        disabled={dang || ten.trim() === "" || ten === v.ten}
        onClick={() => void gui("vi-tri", { ten: ten.trim() }, "Đã đổi tên vị trí.", v.id)}
      >
        Lưu tên
      </Button>
      <Button
        size="lg"
        variant={v.is_active ? "danger" : "secondary"}
        disabled={dang}
        onClick={() =>
          void gui(
            "vi-tri",
            { is_active: !v.is_active },
            v.is_active ? "Đã tắt vị trí." : "Đã bật lại vị trí.",
            v.id,
          )
        }
      >
        {v.is_active ? "Tắt" : "Bật lại"}
      </Button>
    </li>
  );
}
