import { STATIONS, type Station } from '../../data/mock-data';

function SlaIndicator({ status }: { status: Station['slaStatus'] }) {
  const colors = {
    ok: { bg: 'var(--success-bg)', color: 'var(--success)', label: 'Trong mức' },
    warning: { bg: 'var(--warning-bg)', color: 'var(--warning)', label: 'Báo tri (SA2)' },
    critical: { bg: 'var(--danger-bg)', color: 'var(--danger)', label: 'Quá SLA' },
  };
  const c = colors[status];
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        padding: '2px 8px',
        borderRadius: 999,
        fontSize: 10,
        fontWeight: 600,
        background: c.bg,
        color: c.color,
      }}
    >
      <span style={{ width: 6, height: 6, borderRadius: '50%', background: c.color, ...(status !== 'ok' ? { animation: 'pulse-dot 1.5s ease-in-out infinite' } : {}) }} />
      {c.label}
    </span>
  );
}

export default function StationCards() {
  // Skip 'checkout' from the overview grid since it's not in the reference image's main grid
  const visibleStations = STATIONS.filter(s => !['checkout'].includes(s.id));

  return (
    <div
      className="fade-in"
      style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${Math.min(visibleStations.length, 5)}, 1fr)`,
        gap: 12,
      }}
    >
      {visibleStations.map((station) => (
        <div
          key={station.id}
          className="card"
          style={{
            padding: 0,
            overflow: 'hidden',
            transition: 'transform 0.15s ease, box-shadow 0.15s ease',
            cursor: 'default',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = 'translateY(-2px)';
            e.currentTarget.style.boxShadow = 'var(--shadow-panel)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = 'translateY(0)';
            e.currentTarget.style.boxShadow = 'var(--shadow-card)';
          }}
        >
          {/* Station header */}
          <div
            style={{
              padding: '10px 14px',
              background: station.bgColor,
              borderBottom: `2px solid ${station.color}`,
              display: 'flex',
              alignItems: 'center',
              gap: 8,
            }}
          >
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: 8,
                background: station.color,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'white',
                fontSize: 12,
                fontWeight: 700,
              }}
            >
              {station.shortName.charAt(0)}
            </div>
            <span style={{ fontSize: 12, fontWeight: 700, color: station.color }}>
              {station.name}
            </span>
          </div>

          {/* Stats */}
          <div style={{ padding: '12px 14px' }}>
            {/* Counts */}
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
              <div>
                <div style={{ fontSize: 10, color: 'var(--ink-muted)', textTransform: 'uppercase' }}>Chờ</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--ink)' }}>{station.waiting}</div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: 10, color: 'var(--ink-muted)', textTransform: 'uppercase' }}>Đang phục vụ</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: station.color }}>{station.currentServing}</div>
              </div>
            </div>

            {/* Wait time */}
            <div style={{ marginBottom: 8 }}>
              <div style={{ fontSize: 10, color: 'var(--ink-muted)' }}>Thời gian chờ TB</div>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--ink)' }}>
                {String(Math.floor(station.avgWaitMinutes / 60)).padStart(2, '0')}:{String(station.avgWaitMinutes % 60).padStart(2, '0')}
              </div>
            </div>

            {/* SLA */}
            <div style={{ marginBottom: 8 }}>
              <div style={{ fontSize: 10, color: 'var(--ink-muted)', marginBottom: 4 }}>SLA</div>
              <SlaIndicator status={station.slaStatus} />
            </div>

            {/* Staff */}
            <div style={{ marginBottom: 4 }}>
              <div style={{ fontSize: 10, color: 'var(--ink-muted)' }}>Phụ trách</div>
              <div style={{ fontSize: 11, fontWeight: 500, color: 'var(--ink-soft)' }}>{station.staff}</div>
            </div>

            {/* Capacity */}
            <div>
              <div style={{ fontSize: 10, color: 'var(--ink-muted)' }}>Năng lực</div>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--ink)' }}>
                {station.capacity.current} / {station.capacity.total}
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
