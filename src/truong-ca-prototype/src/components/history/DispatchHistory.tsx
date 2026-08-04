import { useState } from 'react';
import { Download, Filter } from 'lucide-react';
import { HISTORY } from '../../data/mock-data';

export default function DispatchHistory() {
  const [filterAction, setFilterAction] = useState<string>('all');

  const actions = [...new Set(HISTORY.map(h => h.action))];
  const filtered = filterAction === 'all' ? HISTORY : HISTORY.filter(h => h.action === filterAction);

  return (
    <div className="fade-in">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
        <div>
          <h2 style={{ fontSize: 16, fontWeight: 700, color: 'var(--ink)', margin: 0 }}>
            Lịch sử điều phối
          </h2>
          <p style={{ fontSize: 12, color: 'var(--ink-muted)', margin: '4px 0 0' }}>
            Ca sáng 14/05/2026 · {HISTORY.length} thao tác
          </p>
        </div>
        <button className="btn btn-secondary" style={{ fontSize: 12 }}>
          <Download size={14} /> Xuất báo cáo
        </button>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 16, flexWrap: 'wrap', alignItems: 'center' }}>
        <Filter size={13} style={{ color: 'var(--ink-muted)' }} />
        {['all', ...actions].map(a => (
          <button
            key={a}
            className={filterAction === a ? 'btn btn-primary' : 'btn btn-secondary'}
            onClick={() => setFilterAction(a)}
            style={{ padding: '4px 10px', fontSize: 11 }}
          >
            {a === 'all' ? 'Tất cả' : a}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Thời gian</th>
              <th>Trưởng ca</th>
              <th>Hành động</th>
              <th>Bệnh nhân</th>
              <th>Mã BN</th>
              <th>Từ</th>
              <th>Đến</th>
              <th>Lý do</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(h => (
              <tr key={h.id}>
                <td style={{ fontWeight: 600, fontSize: 13, fontVariantNumeric: 'tabular-nums' }}>{h.time}</td>
                <td>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <div
                      style={{
                        width: 24,
                        height: 24,
                        borderRadius: '50%',
                        background: h.actor === 'Hệ thống' ? 'var(--surface-sunken)' : 'var(--brand-50)',
                        color: h.actor === 'Hệ thống' ? 'var(--ink-muted)' : 'var(--brand-700)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: 9,
                        fontWeight: 700,
                      }}
                    >
                      {h.actor === 'Hệ thống' ? 'HT' : h.actor.split(' ').slice(-2).map(w => w[0]).join('')}
                    </div>
                    <span style={{ fontSize: 12 }}>{h.actor}</span>
                  </div>
                </td>
                <td>
                  <span
                    className="badge"
                    style={{
                      background: actionColor(h.action).bg,
                      color: actionColor(h.action).text,
                    }}
                  >
                    {h.action}
                  </span>
                </td>
                <td style={{ fontSize: 12, fontWeight: 500 }}>{h.patientName}</td>
                <td style={{ fontSize: 11, color: 'var(--ink-muted)' }}>{h.patientCode}</td>
                <td style={{ fontSize: 12 }}>{h.from}</td>
                <td style={{ fontSize: 12 }}>
                  {h.to !== '-' && <span style={{ color: 'var(--brand-600)', fontWeight: 600 }}>→ {h.to}</span>}
                  {h.to === '-' && <span style={{ color: 'var(--ink-faint)' }}>—</span>}
                </td>
                <td style={{ fontSize: 12, color: 'var(--ink-soft)', maxWidth: 200 }}>{h.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function actionColor(action: string) {
  const map: Record<string, { bg: string; text: string }> = {
    'Điều chuyển phòng': { bg: 'var(--brand-50)', text: 'var(--brand-700)' },
    'Chọn tuyến điều phối': { bg: '#dbeafe', text: '#1d4ed8' },
    'Đổi tuyến giữa chừng': { bg: 'var(--warning-bg)', text: 'var(--warning)' },
    'Ghi chú điều phối': { bg: 'var(--surface-sunken)', text: 'var(--ink-muted)' },
    'Ưu tiên BN': { bg: 'var(--danger-bg)', text: 'var(--danger)' },
    'Cảnh báo SLA': { bg: 'var(--danger-bg)', text: 'var(--danger)' },
    'Mở ca': { bg: 'var(--success-bg)', text: 'var(--success)' },
  };
  return map[action] || { bg: 'var(--surface-sunken)', text: 'var(--ink-muted)' };
}
