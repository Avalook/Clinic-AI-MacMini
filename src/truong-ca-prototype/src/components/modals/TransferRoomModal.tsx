import { useState } from 'react';
import { X, ArrowRight, BarChart3 } from 'lucide-react';
import { PATIENTS, STATIONS } from '../../data/mock-data';

interface TransferRoomModalProps {
  onClose: () => void;
  onConfirm: () => void;
}

export default function TransferRoomModal({ onClose, onConfirm }: TransferRoomModalProps) {
  const [selectedPatient, setSelectedPatient] = useState('');
  const [targetRoom, setTargetRoom] = useState<'sa1' | 'sa2' | 'sa3'>('sa2');
  const [reason, setReason] = useState('');

  const saPatients = PATIENTS.filter(p => ['sa1', 'sa2', 'sa3'].includes(p.currentStation));
  const sa1 = STATIONS.find(s => s.id === 'sa1')!;
  const sa2 = STATIONS.find(s => s.id === 'sa2')!;
  const sa3 = STATIONS.find(s => s.id === 'sa3')!;

  const rooms = [
    { id: 'sa1' as const, station: sa1, load: sa1.waiting + sa1.currentServing },
    { id: 'sa2' as const, station: sa2, load: sa2.waiting + sa2.currentServing },
    { id: 'sa3' as const, station: sa3, load: sa3.waiting + sa3.currentServing },
  ];
  const maxLoad = Math.max(...rooms.map(r => r.load));

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 520 }}>
        {/* Header */}
        <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--line)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h2 style={{ fontSize: 16, fontWeight: 700, color: 'var(--ink)', margin: 0 }}>
              Điều chuyển phòng siêu âm
            </h2>
            <p style={{ fontSize: 12, color: 'var(--ink-muted)', margin: '4px 0 0' }}>
              Chuyển BN giữa SA1, SA2 và SA3
            </p>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--ink-muted)', padding: 4 }}>
            <X size={20} />
          </button>
        </div>

        <div style={{ padding: '20px 24px' }}>
          {/* Patient select */}
          <div style={{ marginBottom: 20 }}>
            <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--ink)', display: 'block', marginBottom: 6 }}>
              Chọn bệnh nhân đang chờ
            </label>
            <select
              value={selectedPatient}
              onChange={(e) => setSelectedPatient(e.target.value)}
              style={{ width: '100%', fontSize: 13 }}
            >
              <option value="">-- Chọn BN --</option>
              {saPatients.map(p => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.code}) — đang ở {p.currentStationName} · chờ {p.waitMinutes}p
                </option>
              ))}
            </select>
          </div>

          {/* Room load comparison */}
          <div style={{ marginBottom: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}>
              <BarChart3 size={14} color="var(--ink-muted)" />
              <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--ink)' }}>Tải phòng siêu âm hiện tại</span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {rooms.map(room => (
                <div key={room.id} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <div style={{ width: 40, fontSize: 12, fontWeight: 700, color: room.station.color }}>
                    {room.station.shortName}
                  </div>
                  <div style={{ flex: 1 }}>
                    <div
                      style={{
                        height: 24,
                        background: 'var(--surface-sunken)',
                        borderRadius: 6,
                        overflow: 'hidden',
                        position: 'relative',
                      }}
                    >
                      <div
                        style={{
                          height: '100%',
                          width: `${(room.load / maxLoad) * 100}%`,
                          background: room.load > 10 ? 'var(--danger)' : room.load > 6 ? 'var(--warning)' : room.station.color,
                          borderRadius: 6,
                          transition: 'width 0.5s ease',
                          display: 'flex',
                          alignItems: 'center',
                          paddingLeft: 8,
                        }}
                      >
                        <span style={{ fontSize: 11, fontWeight: 700, color: 'white' }}>
                          {room.load} BN
                        </span>
                      </div>
                    </div>
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--ink-muted)', width: 60, textAlign: 'right' }}>
                    TB: {room.station.avgWaitMinutes}p
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Target room */}
          <div style={{ marginBottom: 20 }}>
            <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--ink)', display: 'block', marginBottom: 6 }}>
              Chọn phòng đích
            </label>
            <div style={{ display: 'flex', gap: 8 }}>
              {rooms.map(room => (
                <button
                  key={room.id}
                  className={targetRoom === room.id ? 'btn btn-primary' : 'btn btn-secondary'}
                  onClick={() => setTargetRoom(room.id)}
                  style={{
                    flex: 1,
                    flexDirection: 'column',
                    padding: '12px',
                    gap: 4,
                  }}
                >
                  <div style={{ fontSize: 14, fontWeight: 700 }}>{room.station.shortName}</div>
                  <div style={{ fontSize: 10, opacity: 0.8 }}>{room.load} BN · TB {room.station.avgWaitMinutes}p</div>
                </button>
              ))}
            </div>
          </div>

          {/* Reason */}
          <div style={{ marginBottom: 20 }}>
            <label style={{ fontSize: 12, fontWeight: 600, color: 'var(--ink)', display: 'block', marginBottom: 6 }}>
              Lý do điều chuyển *
            </label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Vd: Cân bằng tải SA1 quá đông, SA2 đang rảnh..."
              rows={3}
              style={{ width: '100%', fontSize: 12, resize: 'none' }}
            />
          </div>

          {/* Preview */}
          {selectedPatient && (
            <div style={{ padding: '12px 16px', background: 'var(--surface-muted)', borderRadius: 'var(--radius-chip)', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={{ fontSize: 12, color: 'var(--ink-muted)' }}>
                {saPatients.find(p => p.id === selectedPatient)?.currentStationName}
              </span>
              <ArrowRight size={16} color="var(--brand-600)" />
              <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--brand-600)' }}>
                {rooms.find(r => r.id === targetRoom)?.station.name}
              </span>
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{ padding: '16px 24px', borderTop: '1px solid var(--line)', display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
          <button className="btn btn-secondary" onClick={onClose}>Hủy</button>
          <button
            className="btn btn-primary"
            onClick={onConfirm}
            disabled={!selectedPatient || !reason}
            style={{ opacity: (!selectedPatient || !reason) ? 0.5 : 1 }}
          >
            Xác nhận chuyển phòng
          </button>
        </div>
      </div>
    </div>
  );
}
