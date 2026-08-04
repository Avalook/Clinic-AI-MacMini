import { useState } from 'react';
import { X, CheckCircle2, Circle, ArrowRight, AlertTriangle } from 'lucide-react';
import { ROUTE_TEMPLATES, type RouteTemplate } from '../../data/mock-data';

interface RouteSelectModalProps {
  patientName: string;
  completedSteps?: string[];
  onClose: () => void;
  onConfirm: () => void;
}

export default function RouteSelectModal({
  patientName,
  completedSteps = ['Tiếp nhận', 'Sinh hiệu', 'Khám bác sĩ'],
  onClose,
  onConfirm,
}: RouteSelectModalProps) {
  const [selectedRoute, setSelectedRoute] = useState<string>(ROUTE_TEMPLATES[0].id);
  const [isException, setIsException] = useState(false);
  const [exceptionReason, setExceptionReason] = useState('');
  const [confirmed, setConfirmed] = useState(false);

  const currentRoute = ROUTE_TEMPLATES.find(r => r.id === selectedRoute)!;

  function handleConfirm() {
    setConfirmed(true);
    setTimeout(() => {
      onConfirm();
    }, 1500);
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 600 }}>
        {/* Header */}
        <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--line)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h2 style={{ fontSize: 16, fontWeight: 700, color: 'var(--ink)', margin: 0 }}>
              Chọn quy trình điều phối
            </h2>
            <p style={{ fontSize: 12, color: 'var(--ink-muted)', margin: '4px 0 0' }}>
              Bệnh nhân: <strong>{patientName}</strong> · Sau khi bác sĩ khám xong
            </p>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--ink-muted)', padding: 4 }}>
            <X size={20} />
          </button>
        </div>

        <div style={{ padding: '20px 24px' }}>
          {/* Completed steps */}
          <div style={{ marginBottom: 20 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--ink)', marginBottom: 8 }}>
              Bước đã hoàn tất (không thay đổi)
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              {completedSteps.map(step => (
                <div
                  key={step}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 4,
                    padding: '6px 10px',
                    background: 'var(--success-bg)',
                    borderRadius: 'var(--radius-chip)',
                    fontSize: 11,
                    fontWeight: 600,
                    color: 'var(--success)',
                  }}
                >
                  <CheckCircle2 size={13} /> {step}
                </div>
              ))}
            </div>
          </div>

          {/* Route selection */}
          <div style={{ marginBottom: 20 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--ink)', marginBottom: 10 }}>
              Chọn tuyến điều phối tiếp theo
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {ROUTE_TEMPLATES.map(route => (
                <RouteOption
                  key={route.id}
                  route={route}
                  selected={selectedRoute === route.id}
                  onSelect={() => setSelectedRoute(route.id)}
                />
              ))}
            </div>
          </div>

          {/* Preview */}
          <div style={{ marginBottom: 20 }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--ink)', marginBottom: 8 }}>
              Xem trước hành trình
            </div>
            <div
              style={{
                padding: '14px 16px',
                background: 'var(--surface-muted)',
                borderRadius: 'var(--radius-card)',
                border: '1px solid var(--line)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 6 }}>
                {/* Completed */}
                {['Tiếp nhận', 'Sinh hiệu', 'Khám BS'].map((step, i) => (
                  <span key={i}>
                    <span style={{ fontSize: 12, color: 'var(--success)', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 3 }}>
                      <CheckCircle2 size={13} /> {step}
                    </span>
                    <ArrowRight size={12} style={{ color: 'var(--line-strong)', margin: '0 2px' }} />
                  </span>
                ))}
                {/* New steps */}
                {currentRoute.steps.map((step, i) => (
                  <span key={i}>
                    <span style={{ fontSize: 12, color: 'var(--brand-600)', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 3, background: 'var(--brand-50)', padding: '2px 6px', borderRadius: 4 }}>
                      <Circle size={11} /> {step.stationName}
                    </span>
                    {i < currentRoute.steps.length - 1 && <ArrowRight size={12} style={{ color: 'var(--line-strong)', margin: '0 2px' }} />}
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* Exception toggle */}
          <div style={{ marginBottom: 16 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={isException}
                onChange={() => setIsException(!isException)}
              />
              <AlertTriangle size={14} color="var(--warning)" />
              <span style={{ fontWeight: 500, color: 'var(--ink)' }}>Đổi tuyến giữa chừng (ngoại lệ)</span>
            </label>
          </div>

          {isException && (
            <div style={{ marginBottom: 16, padding: '12px 16px', background: 'var(--warning-bg)', borderRadius: 'var(--radius-chip)', border: '1px solid var(--warning)' }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--warning)', marginBottom: 6 }}>
                ⚠ Bắt buộc ghi lý do khi đổi tuyến giữa chừng
              </div>
              <textarea
                value={exceptionReason}
                onChange={(e) => setExceptionReason(e.target.value)}
                placeholder="Lý do đổi tuyến: VD: SA1 quá tải, BN có thai cần ưu tiên XN trước..."
                rows={2}
                style={{ width: '100%', fontSize: 12, resize: 'none', background: 'white' }}
              />
              <div style={{ fontSize: 10, color: 'var(--ink-muted)', marginTop: 4 }}>
                Hệ thống sẽ lưu tuyến trước/sau vào lịch sử điều phối
              </div>
            </div>
          )}

          {/* Prerequisite check */}
          <div style={{ padding: '10px 14px', background: 'var(--surface-sunken)', borderRadius: 'var(--radius-chip)', fontSize: 11, color: 'var(--ink-muted)' }}>
            <strong style={{ color: 'var(--ink)' }}>Kiểm tra điều kiện:</strong>
            <ul style={{ margin: '4px 0 0 16px', lineHeight: 1.8 }}>
              <li>✅ Chỉ định siêu âm đã có</li>
              <li>✅ Chỉ định xét nghiệm đã có</li>
              <li>✅ Khám bác sĩ hoàn tất</li>
            </ul>
          </div>
        </div>

        {/* Footer */}
        <div style={{ padding: '16px 24px', borderTop: '1px solid var(--line)', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button className="btn btn-secondary" onClick={onClose}>Hủy</button>
          <button
            className="btn btn-primary"
            onClick={handleConfirm}
            disabled={isException && !exceptionReason}
            style={{ opacity: (isException && !exceptionReason) ? 0.5 : 1 }}
          >
            {confirmed ? '✓ Đã xác nhận!' : 'Xác nhận tuyến điều phối'}
          </button>
        </div>
      </div>
    </div>
  );
}

function RouteOption({ route, selected, onSelect }: { route: RouteTemplate; selected: boolean; onSelect: () => void }) {
  return (
    <button
      onClick={onSelect}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '12px 16px',
        borderRadius: 'var(--radius-control)',
        border: selected ? '2px solid var(--brand-600)' : '1px solid var(--line)',
        background: selected ? 'var(--brand-50)' : 'var(--surface)',
        cursor: 'pointer',
        textAlign: 'left',
        width: '100%',
        fontFamily: 'inherit',
        transition: 'all 0.15s ease',
      }}
    >
      {/* Radio */}
      <div
        style={{
          width: 18,
          height: 18,
          borderRadius: '50%',
          border: `2px solid ${selected ? 'var(--brand-600)' : 'var(--line-strong)'}`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
        }}
      >
        {selected && (
          <div style={{ width: 10, height: 10, borderRadius: '50%', background: 'var(--brand-600)' }} />
        )}
      </div>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: selected ? 'var(--brand-700)' : 'var(--ink)' }}>
          {route.name}
        </div>
        <div style={{ display: 'flex', gap: 4, marginTop: 4 }}>
          {route.steps.map((step, i) => (
            <span key={i} style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <span
                style={{
                  fontSize: 10,
                  fontWeight: 500,
                  color: 'var(--ink-muted)',
                  background: 'var(--surface-sunken)',
                  padding: '1px 6px',
                  borderRadius: 3,
                }}
              >
                {step.stationName}
              </span>
              {i < route.steps.length - 1 && <ArrowRight size={10} style={{ color: 'var(--line-strong)' }} />}
            </span>
          ))}
        </div>
      </div>
    </button>
  );
}
