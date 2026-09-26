"use client";

// Tab "Gắn mẫu cho dịch vụ": dịch vụ nào (có phòng làm) điền kết quả vào mẫu nào.
//
// Một dịch vụ gắn được NHIỀU mẫu (siêu âm thai theo quý) — phòng dịch vụ cho bác
// sĩ chọn. Chưa gắn mẫu nào thì phòng mở mẫu gợi ý / mẫu CHUNG nhập tự do.
// Máy chỉ ĐỀ XUẤT theo tên (bấm [Gắn] mới gắn): "SÂ tuyến vú" với "SÂ tuyến
// giáp" chỉ khác một từ, tự gắn là gắn nhầm.

import { useEffect, useMemo, useState } from "react";

import Button from "@/components/ui/Button";
import Chip from "@/components/ui/Chip";

import { docJson, guiLenh, type BangGan, type DeXuat } from "./du-lieu";

const O_NHAP =
  "min-h-10 rounded-control border border-line bg-surface px-3 text-body text-ink";

function khongDau(s: string): string {
  return s
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/đ/g, "d");
}

export default function GanMau({ bang, onDoi }: { bang: BangGan; onDoi: () => void }) {
  const [tim, setTim] = useState("");
  const [chiChuaGan, setChiChuaGan] = useState(false);
  const [dang, setDang] = useState<string | null>(null);
  const [loi, setLoi] = useState<string | null>(null);
  const [bao, setBao] = useState<string | null>(null);
  const [deXuat, setDeXuat] = useState<DeXuat[] | null>(null);
  const choGan = bang.quyen.gan;

  useEffect(() => {
    if (!choGan) return;
    let huy = false;
    void docJson<{ de_xuat: DeXuat[] }>("/api/mau-ket-qua?xem=de-xuat").then((kq) => {
      if (!huy && kq.ok) setDeXuat(kq.d.de_xuat);
    });
    return () => {
      huy = true;
    };
  }, [choGan, bang]);

  const tenMau = useMemo(() => new Map(bang.mau.map((m) => [m.ma, m.ten])), [bang.mau]);

  const theoPhong = useMemo(() => {
    const q = khongDau(tim.trim());
    const ds = bang.dich_vu.filter(
      (d) =>
        (!chiChuaGan || d.mau.length === 0) &&
        (!q || khongDau(`${d.ten} ${d.ma_kiotviet ?? ""} ${d.phong ?? ""}`).includes(q)),
    );
    const nhom = new Map<string, typeof ds>();
    for (const d of ds) nhom.set(d.phong ?? "Khác", [...(nhom.get(d.phong ?? "Khác") ?? []), d]);
    return [...nhom.entries()];
  }, [bang.dich_vu, tim, chiChuaGan]);

  const soChuaGan = bang.dich_vu.filter((d) => d.mau.length === 0).length;

  const lenh = async (thaoTac: "gan" | "go", serviceCode: string, mau: string, cau: string) => {
    setDang(`${serviceCode}:${mau}`);
    setLoi(null);
    setBao(null);
    const kq = await guiLenh({ thao_tac: thaoTac, service_code: serviceCode, mau });
    setDang(null);
    if (!kq.ok) {
      setLoi(kq.loi);
      return;
    }
    setBao(cau);
    onDoi();
  };

  return (
    <div className="space-y-3">
      {!choGan ? (
        <p className="rounded-control bg-surface-muted px-3 py-2 text-meta text-ink-muted">
          Bạn đang xem — cần quyền “Gắn mẫu kết quả cho dịch vụ” để gắn / gỡ.
        </p>
      ) : null}

      {choGan && deXuat && deXuat.length > 0 ? (
        <details className="rounded-card border border-hairline bg-surface">
          <summary className="flex min-h-10 cursor-pointer items-center gap-2 px-3 text-body font-medium text-ink">
            Máy đề xuất theo tên
            <Chip tone="brand">{deXuat.length}</Chip>
            <span className="text-meta font-normal text-ink-muted">— kiểm rồi mới bấm Gắn</span>
          </summary>
          <ul className="divide-y divide-hairline border-t border-hairline">
            {deXuat.map((x) => (
              <li key={`${x.ma_dich_vu}:${x.mau}`} className="flex flex-wrap items-center gap-2 px-3 py-2">
                <span className="min-w-0 flex-1 text-body text-ink">
                  {x.ten_dich_vu} <span className="text-ink-muted">→ {x.ten_mau}</span>
                </span>
                <span className="text-meta text-ink-faint">{x.so_tu_trung} từ trùng</span>
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  disabled={dang !== null}
                  onClick={() =>
                    void lenh("gan", x.ma_dich_vu, x.mau, `Đã gắn “${x.ten_mau}” cho ${x.ten_dich_vu}.`)
                  }
                >
                  Gắn
                </Button>
              </li>
            ))}
          </ul>
        </details>
      ) : null}

      <div className="flex flex-wrap items-center gap-3">
        <input
          type="search"
          value={tim}
          onChange={(e) => setTim(e.target.value)}
          placeholder="Tìm dịch vụ theo tên, mã phòng khám, phòng làm"
          aria-label="Tìm dịch vụ"
          className={`${O_NHAP} w-full max-w-md`}
        />
        <label className="flex min-h-10 items-center gap-2 text-meta text-ink">
          <input
            type="checkbox"
            className="size-4 accent-brand-600"
            checked={chiChuaGan}
            onChange={(e) => setChiChuaGan(e.target.checked)}
          />
          Chỉ dịch vụ chưa gắn mẫu ({soChuaGan})
        </label>
      </div>

      {loi ? (
        <p role="alert" className="rounded-control border border-danger bg-danger-bg px-3 py-2 text-meta text-danger">
          {loi}
        </p>
      ) : null}
      {bao ? (
        <p className="rounded-control border border-success bg-success-bg px-3 py-2 text-meta text-success">{bao}</p>
      ) : null}

      {theoPhong.length === 0 ? <p className="text-body text-ink-muted">Không có dịch vụ nào khớp.</p> : null}
      {theoPhong.map(([phong, ds]) => (
        <section key={phong} className="rounded-card border border-hairline bg-surface">
          <h2 className="border-b border-hairline px-3 py-2 text-meta font-semibold uppercase tracking-wide text-ink-muted">
            {phong} · {ds.length}
          </h2>
          <ul className="divide-y divide-hairline">
            {ds.map((d) => {
              const conLai = bang.mau.filter((m) => !d.mau.includes(m.ma));
              return (
                <li key={d.service_code} className="flex flex-wrap items-center gap-x-3 gap-y-2 px-3 py-2">
                  <div className="min-w-0 flex-1 basis-60">
                    <p className="text-body text-ink">{d.ten}</p>
                    <p className="text-meta text-ink-faint">{d.ma_kiotviet ?? d.service_code}</p>
                  </div>
                  <div className="flex flex-wrap items-center gap-1.5">
                    {d.mau.length === 0 ? (
                      <Chip tone="warning">Chưa gắn — phòng dùng mẫu gợi ý</Chip>
                    ) : (
                      d.mau.map((m) => (
                        <span key={m} className="inline-flex items-center gap-1">
                          <Chip tone="brand">{tenMau.get(m) ?? m}</Chip>
                          {choGan ? (
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              aria-label={`Gỡ mẫu ${tenMau.get(m) ?? m} khỏi ${d.ten}`}
                              disabled={dang !== null}
                              onClick={() =>
                                void lenh("go", d.service_code, m, `Đã gỡ “${tenMau.get(m) ?? m}” khỏi ${d.ten}.`)
                              }
                            >
                              Gỡ
                            </Button>
                          ) : null}
                        </span>
                      ))
                    )}
                  </div>
                  {choGan && conLai.length > 0 ? (
                    <select
                      value=""
                      aria-label={`Gắn thêm mẫu cho ${d.ten}`}
                      disabled={dang !== null}
                      onChange={(e) => {
                        const m = e.target.value;
                        if (m) void lenh("gan", d.service_code, m, `Đã gắn “${tenMau.get(m) ?? m}” cho ${d.ten}.`);
                      }}
                      className={`${O_NHAP} max-w-full`}
                    >
                      <option value="">+ Gắn mẫu…</option>
                      {conLai.map((m) => (
                        <option key={m.ma} value={m.ma}>
                          {m.ten}
                        </option>
                      ))}
                    </select>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </div>
  );
}
