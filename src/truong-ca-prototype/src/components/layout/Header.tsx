import { useState, useEffect } from 'react';
import { Clock, Calendar, RefreshCw, User } from 'lucide-react';

export default function Header() {
  const [time, setTime] = useState(new Date());
  const [autoRefresh, setAutoRefresh] = useState(true);

  useEffect(() => {
    const interval = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(interval);
  }, []);

  const days = ['Chủ nhật', 'Thứ hai', 'Thứ ba', 'Thứ tư', 'Thứ năm', 'Thứ sáu', 'Thứ bảy'];
  const dayOfWeek = days[time.getDay()];
  const dateStr = time.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' });
  const timeStr = time.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });

  return (
    <header
      style={{
        background: 'var(--surface)',
        borderBottom: '1px solid var(--line)',
        padding: '12px 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        position: 'sticky',
        top: 0,
        zIndex: 10,
      }}
    >
      <div>
        <h1 style={{ fontSize: 18, fontWeight: 700, color: 'var(--ink)', margin: 0 }}>
          Điều phối lượt khám — Trưởng ca
        </h1>
        <p style={{ fontSize: 12, color: 'var(--ink-muted)', margin: '2px 0 0' }}>
          Giám sát toàn bộ trạm dịch vụ, SLA, nguồn lực và điểm nghẽn trong thời gian thực.
        </p>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        {/* Date & Time */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            padding: '6px 14px',
            background: 'var(--surface-muted)',
            borderRadius: 'var(--radius-control)',
            border: '1px solid var(--line)',
          }}
        >
          <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--ink-soft)' }}>
            <Calendar size={14} />
            {dayOfWeek}, {dateStr}
          </span>
          <span style={{ width: 1, height: 16, background: 'var(--line)' }} />
          <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 16, fontWeight: 700, color: 'var(--ink)', fontVariantNumeric: 'tabular-nums' }}>
            <Clock size={15} />
            {timeStr}
          </span>
        </div>

        {/* Auto refresh */}
        <button
          onClick={() => setAutoRefresh(!autoRefresh)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '6px 12px',
            borderRadius: 'var(--radius-control)',
            border: '1px solid var(--line)',
            background: autoRefresh ? 'var(--brand-50)' : 'var(--surface)',
            color: autoRefresh ? 'var(--brand-700)' : 'var(--ink-muted)',
            fontSize: 12,
            fontWeight: 500,
            cursor: 'pointer',
            fontFamily: 'inherit',
          }}
        >
          <RefreshCw size={13} style={{ animation: autoRefresh ? 'spin 2s linear infinite' : 'none' }} />
          Tự động cập nhật
        </button>

        {/* User */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div
            style={{
              width: 34,
              height: 34,
              borderRadius: '50%',
              background: 'var(--brand-600)',
              color: 'white',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 12,
              fontWeight: 700,
            }}
          >
            NH
          </div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--ink)' }}>Nguyễn Hoàng Nam</div>
            <div style={{ fontSize: 11, color: 'var(--ink-muted)' }}>Trưởng ca</div>
          </div>
        </div>
      </div>
    </header>
  );
}
