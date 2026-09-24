"use client";

// NHÓM QUYỀN MẪU — quản lý tự thêm, sửa, xoá (Tuyền 23/09/2026:
// *"quản lý quyền cao nhất, thay đổi các nút và vai trò, mặc định các nút ở đó
// có thể thêm sửa xoá được"*).
//
// Trước hôm nay, "preset của vai" là một hằng số trong mã Python: phòng khám
// muốn thêm nhóm "Điều dưỡng ca tối" thì phải chờ lập trình viên. Giờ nó là dữ
// liệu, và màn này là chỗ sửa.
//
// MỘT CÂU PHẢI NÓI RÕ TRÊN MÀN, vì hiểu nhầm nó là đổi quyền của cả chục người
// mà không ai bấm nút nào: **sửa nhóm KHÔNG đổi quyền của người đã được cấp**.
// Nhóm chỉ là "bấm một cái cấp cả loạt". Quyền thật nằm ở từng người.

import { useCallback, useEffect, useState } from "react";

import Button from "@/components/ui/Button";

export interface Khoi {
  ma: string;
  ten: string;
}

interface Nhom {
  ma: string;
  ten: string;
  khoi: string[];
  mo_ta: string | null;
  he_thong: boolean;
  active: boolean;
}

const NHOM_MOI: Nhom = {
  ma: "",
  ten: "",
  khoi: [],
  mo_ta: null,
  he_thong: false,
  active: true,
};

export default function NhomQuyenMau({ khoiCo }: { khoiCo: Khoi[] }) {
  const [nhom, setNhom] = useState<Nhom[] | null>(null);
  const [sua, setSua] = useState<Nhom | null>(null);
  const [dangLuu, setDangLuu] = useState(false);
  const [loi, setLoi] = useState<string | null>(null);

  const doc = useCallback(async (): Promise<Nhom[] | null> => {
    const r = await fetch("/api/phan-quyen?nhom=1", { cache: "no-store" });
    if (!r.ok) return null;
    const kq = (await r.json()) as { nhom: Nhom[] };
    return kq.nhom;
  }, []);

  useEffect(() => {
    let huy = false;
    void doc().then((kq) => {
      if (huy) return;
      if (kq) setNhom(kq);
      else setLoi("Không đọc được danh sách nhóm.");
    });
    return () => {
      huy = true;
    };
  }, [doc]);

  const napLai = async () => {
    const kq = await doc();
    if (kq) setNhom(kq);
  };

  const guiLenh = async (than: Record<string, unknown>): Promise<boolean> => {
    setDangLuu(true);
    setLoi(null);
    const r = await fetch("/api/phan-quyen", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(than),
    });
    setDangLuu(false);
    if (!r.ok) {
      const chi_tiet = (await r.json().catch(() => null)) as {
        message?: string;
        detail?: string;
      } | null;
      setLoi(chi_tiet?.message ?? chi_tiet?.detail ?? "Không lưu được nhóm.");
      return false;
    }
    await napLai();
    return true;
  };

  const luu = async () => {
    if (!sua) return;
    const xong = await guiLenh({
      thao_tac: "luu-nhom",
      du_lieu: {
        ma: sua.ma.trim().toUpperCase(),
        ten: sua.ten.trim(),
        khoi: sua.khoi,
        mo_ta: sua.mo_ta,
      },
    });
    if (xong) setSua(null);
  };

  return (
    <section
      aria-label="Nhóm quyền mẫu"
      className="rounded-card bg-surface-muted p-3.5 shadow-card"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-ink">Nhóm quyền mẫu</h2>
          <p className="text-label text-ink-muted">
            Bấm một cái cấp cả loạt khối. Sửa nhóm <strong>không</strong> đổi
            quyền của người đã được cấp trước đó.
          </p>
        </div>
        <Button
          type="button"
          variant="primary"
          disabled={dangLuu}
          onClick={() => setSua({ ...NHOM_MOI })}
        >
          + Nhóm mới
        </Button>
      </div>

      {loi ? (
        <p role="alert" className="mt-2 text-sm text-danger">
          {loi}
        </p>
      ) : null}

      {sua ? (
        <div className="mt-3 space-y-3 rounded-control border border-brand-600 bg-surface p-3">
          <div className="flex flex-wrap gap-3">
            <label className="min-w-40 flex-1">
              <span className="text-xs font-semibold text-ink">
                Mã nhóm (chữ hoa, không dấu)
              </span>
              <input
                value={sua.ma}
                disabled={nhom?.some((n) => n.ma === sua.ma) ?? false}
                onChange={(e) => setSua({ ...sua, ma: e.target.value })}
                placeholder="DD_CA_TOI"
                className="mt-1 min-h-10 w-full rounded-control border border-line bg-surface px-3 text-sm text-ink disabled:text-ink-faint"
              />
            </label>
            <label className="min-w-60 flex-1">
              <span className="text-xs font-semibold text-ink">Tên hiển thị</span>
              <input
                value={sua.ten}
                onChange={(e) => setSua({ ...sua, ten: e.target.value })}
                placeholder="Điều dưỡng ca tối"
                className="mt-1 min-h-10 w-full rounded-control border border-line bg-surface px-3 text-sm text-ink"
              />
            </label>
          </div>

          <fieldset>
            <legend className="text-xs font-semibold text-ink">
              Khối công việc trong nhóm
            </legend>
            <div className="mt-1 flex flex-wrap gap-2">
              {khoiCo.map((k) => {
                const co = sua.khoi.includes(k.ma);
                return (
                  <button
                    key={k.ma}
                    type="button"
                    onClick={() =>
                      setSua({
                        ...sua,
                        khoi: co
                          ? sua.khoi.filter((x) => x !== k.ma)
                          : [...sua.khoi, k.ma],
                      })
                    }
                    className={`min-h-10 rounded-chip px-3 text-sm ${
                      co
                        ? "bg-brand-600 font-semibold text-white"
                        : "border border-line bg-surface text-ink-soft hover:bg-surface-muted"
                    }`}
                  >
                    {k.ten}
                  </button>
                );
              })}
            </div>
          </fieldset>

          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="primary"
              disabled={dangLuu || !sua.ma.trim() || !sua.ten.trim()}
              onClick={() => void luu()}
            >
              {dangLuu ? "Đang lưu…" : "Lưu nhóm"}
            </Button>
            <Button type="button" variant="ghost" onClick={() => setSua(null)}>
              Thôi
            </Button>
          </div>
        </div>
      ) : null}

      {nhom === null ? (
        <p className="mt-3 text-sm text-ink-muted">Đang tải…</p>
      ) : (
        <ul className="mt-3 flex flex-col gap-2">
          {nhom.map((n) => (
            <li
              key={n.ma}
              className="rounded-control border border-line bg-surface px-3 py-2.5"
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-ink">
                    {n.ten}
                    <span className="ml-2 text-label text-ink-muted">{n.ma}</span>
                    {n.he_thong ? (
                      <span className="ml-2 text-label text-ink-muted">
                        · dựng sẵn
                      </span>
                    ) : null}
                    {!n.active ? (
                      <span className="ml-2 text-label text-warning">· đã tắt</span>
                    ) : null}
                  </p>
                  <p className="text-label text-ink-muted">
                    {n.khoi.length === 0
                      ? "Chưa có khối nào"
                      : n.khoi
                          .map(
                            (ma) => khoiCo.find((k) => k.ma === ma)?.ten ?? ma,
                          )
                          .join(" · ")}
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button
                    type="button"
                    variant="secondary"
                    disabled={dangLuu}
                    onClick={() => setSua({ ...n })}
                  >
                    Sửa
                  </Button>
                  <Button
                    type="button"
                    variant="danger"
                    disabled={dangLuu}
                    onClick={() =>
                      void guiLenh({ thao_tac: "xoa-nhom", ma: n.ma })
                    }
                  >
                    {n.he_thong ? "Tắt" : "Xoá"}
                  </Button>
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
