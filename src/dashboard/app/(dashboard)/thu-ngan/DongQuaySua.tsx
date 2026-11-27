// Cách dùng + lưu ý của dòng QUẦY THÊM trong `ChinhDonQuay` — lưu khi rời ô.
// (Dòng bác sĩ kê chỉ xem: cách dùng là quyết định chuyên môn.)

import { useState } from "react";

import { INPUT } from "../form-ui";

interface DongCoCachDung {
  ten: string;
  cach_dung: string | null;
  luu_y: string | null;
  mua: boolean;
  da_chot: boolean;
}

export default function DongQuaySua<D extends DongCoCachDung>({
  d,
  dang,
  onLuu,
}: {
  d: D;
  dang: boolean;
  onLuu: (d: D, cachDung: string, luuY: string) => Promise<void>;
}) {
  const [cachDung, setCachDung] = useState(d.cach_dung ?? "");
  const [luuY, setLuuY] = useState(d.luu_y ?? "");
  return (
    <div className="grid gap-2 pl-6 sm:grid-cols-2">
      <input
        value={cachDung}
        disabled={dang || !d.mua || d.da_chot}
        onChange={(e) => setCachDung(e.target.value)}
        onBlur={() => void onLuu(d, cachDung, luuY)}
        placeholder="Cách dùng"
        aria-label={`Cách dùng ${d.ten}`}
        className={INPUT}
      />
      <input
        value={luuY}
        disabled={dang || !d.mua || d.da_chot}
        onChange={(e) => setLuuY(e.target.value)}
        onBlur={() => void onLuu(d, cachDung, luuY)}
        placeholder="Lưu ý"
        aria-label={`Lưu ý ${d.ten}`}
        className={INPUT}
      />
    </div>
  );
}
