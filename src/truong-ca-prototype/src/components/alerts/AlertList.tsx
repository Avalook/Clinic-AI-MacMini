import { useState } from 'react';
import { AlertTriangle, AlertOctagon, Clock, Unlink, ArrowRightLeft, CheckCircle, Eye, EyeOff } from 'lucide-react';
import { ALERTS, type Alert } from '../../data/mock-data';

interface AlertListProps {
  onDispatch: () => void;
}

const typeConfig = {
  wait_too_long: { icon: Clock, label: 'Chờ quá lâu', color: 'var(--warning)' },
  missing_next_step: { icon: AlertOctagon, label: 'Thiếu bước tiếp', color: 'var(--danger)' },
  unassigned_order: { icon: ArrowRightLeft, label: 'Chỉ định chưa nhận', color: 'var(--warning)' },
  dual_queue: { icon: Unlink, label: 'Hai hàng đợi bất thường', color: 'var(--danger)' },
};

export default function AlertList({ onDispatch }: AlertListProps) {
  const [alerts, setAlerts] = useState(ALERTS);
  const [filterType, setFilterType] = useState<string>('all');
  const [showAcknowledged, setShowAcknowledged] = useState(false);

  let filtered = alerts;
  if (filterType !== 'all') {
    filtered = filtered.filter(a => a.type === filterType);
  }
  if (!showAcknowledged) {
    filtered = filtered.filter(a => !a.acknowledged);
  }

  function acknowledge(id: string) {
    setAlerts(prev => prev.map(a => a.id === id ? { ...a, acknowledged: true } : a));
  }

  return (
    <div className="fade-in">
      <div style={{ marginBottom: 16 }}>
        <h2 style={{ fontSize: 16, fontWeight: 700, color: 'var(--ink)', margin: 0 }}>
          Cảnh báo & SLA
        </h2>
        <p style={{ fontSize: 12, color: 'var(--ink-muted)', margin: '4px 0 0' }}>
          {alerts.filter(a => !a.acknowledged).length} cảnh báo chưa xử lý
        </p>
      </div>

      {/* Summary cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12, marginBottom: 20 }}>
        {Object.entries(typeConfig).map(([type, config]) => {
          const Icon = config.icon;
          const count = alerts.filter(a => a.type === type && !a.acknowledged).length;
          return (
            <div
              key={type}
              className="card"
              onClick={() => setFilterType(filterType === type ? 'all' : type)}
              style={{
                padding: '14px 16px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                border: filterType === type ? `2px solid ${config.color}` : undefined,
                transition: 'all 0.15s ease',
              }}
            >
              <div
                style={{
                  width: 38,
                  height: 38,
                  borderRadius: '50%',
                  background: type.includes('critical') || type === 'missing_next_step' || type === 'dual_queue' ? 'var(--danger-bg)' : 'var(--warning-bg)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Icon size={18} color={config.color} />
              </div>
              <div>
                <div style={{ fontSize: 11, color: 'var(--ink-muted)' }}>{config.label}</div>
                <div style={{ fontSize: 22, fontWeight: 800, color: count > 0 ? config.color : 'var(--ink)' }}>{count}</div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Toggle acknowledged */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div style={{ display: 'flex', gap: 4 }}>
          {['all', ...Object.keys(typeConfig)].map(t => (
            <button
              key={t}
              className={filterType === t ? 'btn btn-primary' : 'btn btn-secondary'}
              onClick={() => setFilterType(t)}
              style={{ padding: '4px 10px', fontSize: 11 }}
            >
              {t === 'all' ? 'Tất cả' : typeConfig[t as keyof typeof typeConfig]?.label}
            </button>
          ))}
        </div>
        <button
          className="btn btn-ghost"
          onClick={() => setShowAcknowledged(!showAcknowledged)}
          style={{ fontSize: 11 }}
        >
          {showAcknowledged ? <EyeOff size={13} /> : <Eye size={13} />}
          {showAcknowledged ? 'Ẩn đã xử lý' : 'Hiện đã xử lý'}
        </button>
      </div>

      {/* Alert items */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {filtered.length === 0 ? (
          <div className="card" style={{ padding: '40px 20px', textAlign: 'center' }}>
            <CheckCircle size={40} color="var(--success)" style={{ marginBottom: 12 }} />
            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--ink)' }}>Không có cảnh báo</div>
            <div style={{ fontSize: 12, color: 'var(--ink-muted)', marginTop: 4 }}>Tất cả trạm đang hoạt động bình thường</div>
          </div>
        ) : (
          filtered.map(alert => <AlertItem key={alert.id} alert={alert} onAcknowledge={acknowledge} onDispatch={onDispatch} />)
        )}
      </div>

      {/* Threshold config */}
      <ThresholdConfig />
    </div>
  );
}

function AlertItem({
  alert,
  onAcknowledge,
  onDispatch,
}: {
  alert: Alert;
  onAcknowledge: (id: string) => void;
  onDispatch: () => void;
}) {
  const config = typeConfig[alert.type];
  const Icon = config.icon;

  return (
    <div
      className="card"
      style={{
        padding: '14px 18px',
        display: 'flex',
        alignItems: 'flex-start',
        gap: 14,
        opacity: alert.acknowledged ? 0.5 : 1,
        borderLeft: `4px solid ${alert.severity === 'critical' ? 'var(--danger)' : 'var(--warning)'}`,
      }}
    >
      <div
        style={{
          width: 34,
          height: 34,
          borderRadius: '50%',
          background: alert.severity === 'critical' ? 'var(--danger-bg)' : 'var(--warning-bg)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
        }}
      >
        <Icon size={16} color={alert.severity === 'critical' ? 'var(--danger)' : 'var(--warning)'} />
      </div>
      <div style={{ flex: 1 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--ink)' }}>{alert.message}</div>
          <span className={`badge ${alert.severity === 'critical' ? 'badge-danger' : 'badge-warning'}`}>
            {alert.severity === 'critical' ? 'Nghiêm trọng' : 'Cảnh báo'}
          </span>
        </div>
        <div style={{ fontSize: 12, color: 'var(--ink-muted)', marginBottom: 8 }}>
          <strong>{alert.patientName}</strong> ({alert.patientCode}) · Phòng: {alert.station} · {alert.time}
        </div>
        {!alert.acknowledged && (
          <div style={{ display: 'flex', gap: 6 }}>
            <button className="btn btn-primary" onClick={onDispatch} style={{ padding: '5px 12px', fontSize: 11 }}>
              <AlertTriangle size={12} /> Điều phối ngay
            </button>
            <button className="btn btn-secondary" onClick={() => onAcknowledge(alert.id)} style={{ padding: '5px 12px', fontSize: 11 }}>
              <CheckCircle size={12} /> Ghi chú & bỏ qua
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function ThresholdConfig() {
  const [thresholds, setThresholds] = useState({
    doctor: 20,
    sa1: 15,
    sa2: 15,
    lab: 20,
    pharmacy: 10,
    maxPerRoom: 8,
  });

  return (
    <div className="card" style={{ marginTop: 24, padding: '20px' }}>
      <h3 style={{ fontSize: 14, fontWeight: 700, color: 'var(--ink)', marginBottom: 16 }}>
        ⚙ Cấu hình ngưỡng cảnh báo
      </h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
        {[
          { key: 'doctor', label: 'Khám BS (phút)' },
          { key: 'sa1', label: 'Siêu âm (phút)' },
          { key: 'lab', label: 'Xét nghiệm (phút)' },
          { key: 'pharmacy', label: 'Nhà thuốc (phút)' },
          { key: 'maxPerRoom', label: 'BN tối đa/phòng' },
        ].map(({ key, label }) => (
          <div key={key}>
            <label style={{ fontSize: 11, color: 'var(--ink-muted)', display: 'block', marginBottom: 4 }}>{label}</label>
            <input
              type="text"
              value={thresholds[key as keyof typeof thresholds]}
              onChange={(e) => setThresholds(prev => ({ ...prev, [key]: Number(e.target.value) || 0 }))}
              style={{ width: '100%' }}
            />
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 8, marginTop: 16 }}>
        <button className="btn btn-primary">Lưu ngưỡng</button>
        <button className="btn btn-secondary">Reset mặc định</button>
      </div>
    </div>
  );
}
