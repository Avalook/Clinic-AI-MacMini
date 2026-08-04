import { STATIONS, PATIENTS, type Station } from '../../data/mock-data';
import { ArrowRightLeft } from 'lucide-react';

interface QueueGridProps {
  onTransfer: () => void;
}

const queueStations = ['doctor', 'sa1', 'sa2', 'sa3', 'lab', 'pharmacy'];

export default function QueueGrid({ onTransfer }: QueueGridProps) {
  const visible = STATIONS.filter(s => queueStations.includes(s.id));

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, color: 'var(--ink)', margin: 0 }}>
          Hàng đợi theo trạm
        </h2>
        <p style={{ fontSize: 12, color: 'var(--ink-muted)', margin: '4px 0 0' }}>
          Khám bác sĩ · SA1 · SA2 · SA3 · Xét nghiệm · Thuốc & Thanh toán
        </p>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: 16,
        }}
      >
        {visible.map(station => {
          const stationPatients = PATIENTS.filter(p => p.currentStation === station.id);
          const serving = stationPatients.slice(0, station.currentServing);
          const waiting = stationPatients.slice(station.currentServing);
          const maxWait = waiting.length > 0 ? Math.max(...waiting.map(p => p.waitMinutes)) : 0;

          return (
            <QueuePanel
              key={station.id}
              station={station}
              serving={serving}
              waiting={waiting}
              maxWait={maxWait}
              onTransfer={onTransfer}
            />
          );
        })}
      </div>
    </div>
  );
}

function QueuePanel({
  station,
  serving,
  waiting,
  maxWait,
  onTransfer,
}: {
  station: Station;
  serving: typeof PATIENTS;
  waiting: typeof PATIENTS;
  maxWait: number;
  onTransfer: () => void;
}) {
  return (
    <div className="card" style={{ overflow: 'hidden' }}>
      {/* Header */}
      <div
        style={{
          padding: '12px 16px',
          background: station.bgColor,
          borderBottom: `2px solid ${station.color}`,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              background: station.color,
              color: 'white',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 800,
              fontSize: 13,
            }}
          >
            {station.shortName.charAt(0)}
          </div>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, color: station.color }}>{station.name}</div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 12, fontSize: 12 }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 20, fontWeight: 800, color: station.color }}>{station.currentServing}</div>
            <div style={{ fontSize: 10, color: 'var(--ink-muted)' }}>Đang PV</div>
          </div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: 20, fontWeight: 800, color: 'var(--ink)' }}>{station.waiting}</div>
            <div style={{ fontSize: 10, color: 'var(--ink-muted)' }}>Đang chờ</div>
          </div>
        </div>
      </div>

      {/* Serving */}
      {serving.length > 0 && (
        <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--surface-sunken)' }}>
          <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--ink-muted)', textTransform: 'uppercase', marginBottom: 6 }}>
            Đang phục vụ
          </div>
          {serving.map(p => (
            <div
              key={p.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '8px 12px',
                background: 'var(--surface-selected)',
                borderRadius: 'var(--radius-chip)',
                marginBottom: 4,
                border: `1px solid ${station.color}20`,
              }}
            >
              <div>
                <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--ink)' }}>{p.name}</div>
                <div style={{ fontSize: 11, color: 'var(--ink-muted)' }}>{p.code} · {p.queueCode}</div>
              </div>
              <div style={{ fontSize: 11, color: station.color, fontWeight: 600 }}>
                {p.waitMinutes}p
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Waiting list */}
      <div style={{ padding: '12px 16px' }}>
        <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--ink-muted)', textTransform: 'uppercase', marginBottom: 6 }}>
          Tiếp theo ({waiting.length})
        </div>
        {waiting.length === 0 ? (
          <div style={{ fontSize: 12, color: 'var(--ink-faint)', padding: '8px 0' }}>Không có ai đang chờ</div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 200, overflowY: 'auto' }}>
            {waiting.map((p, i) => (
              <div
                key={p.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '6px 10px',
                  borderRadius: 'var(--radius-chip)',
                  background: i === 0 ? 'var(--surface-sunken)' : 'transparent',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--ink-muted)', width: 20 }}>{i + 1}</span>
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--ink)' }}>{p.name}</div>
                    <div style={{ fontSize: 10, color: 'var(--ink-muted)' }}>{p.queueCode}</div>
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span
                    style={{
                      fontSize: 11,
                      fontWeight: 600,
                      color: p.waitMinutes > 15 ? 'var(--danger)' : 'var(--ink-muted)',
                    }}
                  >
                    {p.waitMinutes}p
                  </span>
                  {p.priority !== 'normal' && (
                    <span className={`badge ${p.priority === 'urgent' ? 'badge-danger' : 'badge-warning'}`} style={{ fontSize: 9 }}>
                      {p.priorityLabel}
                    </span>
                  )}
                  {(station.id === 'sa1' || station.id === 'sa2' || station.id === 'sa3') && (
                    <button
                      className="btn btn-ghost"
                      onClick={onTransfer}
                      style={{ padding: 2, borderRadius: 4 }}
                      title="Chuyển phòng"
                    >
                      <ArrowRightLeft size={12} />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Footer stats */}
      <div
        style={{
          padding: '10px 16px',
          borderTop: '1px solid var(--surface-sunken)',
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: 11,
        }}
      >
        <span style={{ color: 'var(--ink-muted)' }}>
          TB: <strong style={{ color: 'var(--ink)' }}>{station.avgWaitMinutes}p</strong>
        </span>
        <span style={{ color: maxWait > 20 ? 'var(--danger)' : 'var(--ink-muted)' }}>
          Lâu nhất: <strong>{maxWait}p</strong>
        </span>
      </div>
    </div>
  );
}
