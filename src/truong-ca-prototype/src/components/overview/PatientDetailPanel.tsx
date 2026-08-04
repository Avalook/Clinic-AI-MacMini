import { X, Phone, ArrowRightLeft, RefreshCw, MessageSquare, CheckCircle2, Circle, Loader2 } from 'lucide-react';
import type { Patient } from '../../data/mock-data';

interface PatientDetailPanelProps {
  patient: Patient;
  onClose: () => void;
  onTransfer: () => void;
  onRouteSelect: () => void;
}

export default function PatientDetailPanel({ patient, onClose, onTransfer, onRouteSelect }: PatientDetailPanelProps) {
  return (
    <div
      className="slide-in-right"
      style={{
        width: 380,
        minWidth: 380,
        background: 'var(--surface)',
        borderLeft: '1px solid var(--line)',
        height: '100%',
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
      }}
    >
      {/* Header */}
      <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--line)', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <span style={{ fontSize: 16, fontWeight: 700, color: 'var(--ink)' }}>Chi tiết hành trình</span>
            <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--ink-muted)', padding: 4 }}>
              <X size={18} />
            </button>
          </div>
        </div>
        {/* SLA time */}
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 24, fontWeight: 800, color: patient.slaPercent > 85 ? 'var(--danger)' : 'var(--brand-600)' }}>
            {patient.waitMinutes} phút
          </div>
          <div style={{ fontSize: 10, color: 'var(--ink-muted)' }}>
            (Quá SLA {Math.max(0, patient.waitMinutes - 15)} phút)
          </div>
        </div>
      </div>

      {/* Patient info */}
      <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--line)' }}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <div
            style={{
              width: 44,
              height: 44,
              borderRadius: '50%',
              background: 'var(--brand-50)',
              color: 'var(--brand-700)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 16,
              fontWeight: 700,
            }}
          >
            {patient.name.split(' ').slice(-2).map(w => w[0]).join('')}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--ink)' }}>{patient.name}</div>
            <div style={{ fontSize: 12, color: 'var(--ink-muted)' }}>
              {patient.code} · {patient.age} tuổi · {patient.gender}
            </div>
            <div style={{ fontSize: 12, color: 'var(--ink-muted)', display: 'flex', alignItems: 'center', gap: 4, marginTop: 2 }}>
              <Phone size={11} /> {patient.phone}
            </div>
          </div>
        </div>
      </div>

      {/* Timeline */}
      <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--line)', flex: 1 }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)', marginBottom: 4 }}>
          Hành trình dịch vụ
        </div>
        <div style={{ display: 'flex', gap: 8, marginBottom: 12, fontSize: 10 }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 3, color: 'var(--success)' }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--success)' }} /> Đã hoàn tất
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 3, color: 'var(--brand-600)' }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--brand-600)' }} /> Đang thực hiện
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 3, color: 'var(--ink-faint)' }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--line-strong)', border: '1px solid var(--ink-faint)' }} /> Chờ tới
          </span>
        </div>

        {/* Vertical timeline */}
        <div style={{ position: 'relative', paddingLeft: 24 }}>
          {patient.route.map((step, i) => {
            const isLast = i === patient.route.length - 1;
            const statusIcon = step.status === 'completed'
              ? <CheckCircle2 size={16} color="var(--success)" fill="var(--success-bg)" />
              : step.status === 'in_progress'
                ? <Loader2 size={16} color="var(--brand-600)" style={{ animation: 'spin 1.5s linear infinite' }} />
                : <Circle size={16} color="var(--line-strong)" />;

            return (
              <div key={i} style={{ position: 'relative', paddingBottom: isLast ? 0 : 20 }}>
                {/* Line */}
                {!isLast && (
                  <div
                    style={{
                      position: 'absolute',
                      left: -16,
                      top: 18,
                      bottom: 0,
                      width: 2,
                      background: step.status === 'completed' ? 'var(--success)' : 'var(--line)',
                    }}
                  />
                )}
                {/* Icon */}
                <div style={{ position: 'absolute', left: -24, top: 0 }}>
                  {statusIcon}
                </div>
                {/* Content */}
                <div style={{ paddingLeft: 4 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: step.status === 'waiting' ? 'var(--ink-faint)' : 'var(--ink)' }}>
                        {step.stationName}
                      </div>
                      {step.staff && (
                        <div style={{ fontSize: 11, color: 'var(--ink-muted)' }}>{step.room} – {step.staff}</div>
                      )}
                    </div>
                    {step.startTime && (
                      <div style={{ fontSize: 11, color: 'var(--ink-muted)', textAlign: 'right' }}>
                        {step.startTime}
                        {step.endTime && <span> → {step.endTime}</span>}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Staff */}
      <div style={{ padding: '12px 20px', borderBottom: '1px solid var(--line)' }}>
        <div style={{ fontSize: 11, color: 'var(--ink-muted)', marginBottom: 4 }}>Phụ trách chính</div>
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--ink)' }}>
          {patient.assignedTo}
          <span style={{ fontSize: 11, color: 'var(--ink-muted)', marginLeft: 8 }}>0902 345 678</span>
        </div>
      </div>

      {/* Actions */}
      <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--line)' }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)', marginBottom: 10 }}>
          Hành động của trưởng ca <span style={{ fontSize: 10, color: 'var(--ink-muted)', fontWeight: 400 }}>(lựa chọn lý do)</span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <button className="btn btn-secondary" onClick={onRouteSelect} style={{ justifyContent: 'flex-start' }}>
            <RefreshCw size={14} /> Đổi mũi tên (route)
          </button>
          <button className="btn btn-secondary" onClick={onTransfer} style={{ justifyContent: 'flex-start' }}>
            <ArrowRightLeft size={14} /> Điều chuyển phòng
          </button>
          <div style={{ position: 'relative' }}>
            <label style={{ fontSize: 11, color: 'var(--ink-muted)', marginBottom: 4, display: 'block' }}>Lý do thao tác *</label>
            <input type="text" placeholder="Lý do thao tác *" style={{ width: '100%', fontSize: 12 }} />
          </div>
          <textarea
            placeholder="Ghi chú điều phối nhanh"
            rows={2}
            style={{ width: '100%', fontSize: 12, resize: 'none' }}
          />
          <button className="btn btn-primary" style={{ width: '100%' }}>
            <MessageSquare size={14} /> Ghi chận & điều phối tiếp
          </button>
        </div>
      </div>

      {/* Notes log */}
      <div style={{ padding: '16px 20px' }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--ink)', marginBottom: 10 }}>
          Nhật ký thao tác
        </div>
        {patient.notes.map((note, i) => (
          <div key={i} style={{ marginBottom: 10, paddingLeft: 12, borderLeft: '2px solid var(--line)' }}>
            <div style={{ fontSize: 11, color: 'var(--ink-muted)' }}>
              <strong>{note.time}</strong> — {note.actor}
            </div>
            <div style={{ fontSize: 12, color: 'var(--ink-soft)', fontWeight: 500 }}>{note.action}</div>
            <div style={{ fontSize: 11, color: 'var(--ink-muted)' }}>{note.detail}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
