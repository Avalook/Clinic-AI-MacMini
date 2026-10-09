"use client";

// Tab ca của BÁO CÁO CA CỦA TÔI (/bao-cao-ca, 09/10/2026). Danh sách ca do MÁY CHỦ
// trả (`ca_duoc_xem` — suy từ lịch trực hôm nay); màn chỉ vẽ và gửi ca được chọn.
// Dùng chung cho tab Cuối ca (`CuoiNgay.tsx`) và Hàng hoá (`BaoCaoHangHoa.tsx`).

export interface CaDuocXem {
  ca: string;
  ten: string;
  co_so: string;
  ten_co_so: string;
}

export interface CaDangXem {
  ca: string;
  coSo: string;
}

export default function TabCaCuaToi({
  ds,
  dangXem,
  onChon,
}: {
  ds: CaDuocXem[];
  dangXem: CaDangXem | null;
  onChon: (c: CaDangXem) => void;
}) {
  // Tên cơ sở chỉ cần khi người ấy trực ở hơn một cơ sở hôm nay.
  const nhieuCoSo = new Set(ds.map((x) => x.co_so)).size > 1;
  return (
    <div role="tablist" aria-label="Ca của tôi" className="flex flex-wrap gap-1">
      {ds.map((x) => {
        const chon = dangXem?.ca === x.ca && dangXem?.coSo === x.co_so;
        return (
          <button
            key={`${x.ca}-${x.co_so}`}
            type="button"
            role="tab"
            aria-selected={chon}
            onClick={() => onChon({ ca: x.ca, coSo: x.co_so })}
            className={`min-h-10 whitespace-nowrap rounded-control px-3 text-sm font-medium ${
              chon ? "bg-brand-600 text-white" : "bg-surface-muted text-ink-soft hover:bg-surface-sunken"
            }`}
          >
            Ca {x.ten.toLowerCase()}
            {nhieuCoSo && x.ten_co_so ? ` · ${x.ten_co_so}` : ""}
          </button>
        );
      })}
    </div>
  );
}
