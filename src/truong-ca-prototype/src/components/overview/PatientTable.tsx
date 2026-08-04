import { useState } from 'react';
import { Search, Filter, ChevronLeft, ChevronRight } from 'lucide-react';
import { PATIENTS, type Patient } from '../../data/mock-data';

interface PatientTableProps {
  onSelectPatient: (patient: Patient) => void;
  selectedPatientId: string | null;
}

const PAGE_SIZE = 8;

export default function PatientTable({ onSelectPatient, selectedPatientId }: PatientTableProps) {
  const [search, setSearch] = useState('');
  const [filterPriority, setFilterPriority] = useState<string>('all');
  const [filterStation, setFilterStation] = useState<string>('all');
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  let filtered = PATIENTS;
  if (search) {
    const s = search.toLowerCase();
    filtered = filtered.filter(p => p.name.toLowerCase().includes(s) || p.code.toLowerCase().includes(s));
  }
  if (filterPriority !== 'all') {
    filtered = filtered.filter(p => p.priority === filterPriority);
  }
  if (filterStation !== 'all') {
    filtered = filtered.filter(p => p.currentStation === filterStation);
  }

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);
  const paged = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  function toggleSelect(id: string) {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function slaColor(pct: number) {
    if (pct <= 60) return 'var(--success)';
    if (pct <= 85) return 'var(--warning)';
    return 'var(--danger)';
  }

  return (
    <div className="fade-in">
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
          <h2 style={{ fontSize: 15, fontWeight: 700, color: 'var(--ink)', margin: 0 }}>
            Bệnh nhân cần điều phối
          </h2>
          <span style={{ fontSize: 12, color: 'var(--ink-muted)' }}>({filtered.length})</span>
        </div>
        <div style={{ display: 'flex', gap: 6, fontSize: 12, color: 'var(--ink-muted)' }}>
          Sắp xếp: <strong style={{ color: 'var(--ink)' }}>Thời gian chờ ↓</strong>
        </div>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
        <div style={{ position: 'relative', flex: '0 0 220px' }}>
          <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--ink-muted)' }} />
          <input
            type="search"
            placeholder="Tìm bệnh nhân, mã BN, SĐT..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            style={{ paddingLeft: 32, width: '100%' }}
          />
        </div>
        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          <Filter size={13} style={{ color: 'var(--ink-muted)' }} />
          {['all', 'urgent', 'high', 'normal'].map(p => (
            <button
              key={p}
              onClick={() => { setFilterPriority(p); setPage(1); }}
              className={filterPriority === p ? 'btn btn-primary' : 'btn btn-secondary'}
              style={{ padding: '4px 10px', fontSize: 11 }}
            >
              {p === 'all' ? 'Tất cả' : p === 'urgent' ? 'Khẩn' : p === 'high' ? 'Cao' : 'Thường'}
            </button>
          ))}
        </div>
        <select
          value={filterStation}
          onChange={(e) => { setFilterStation(e.target.value); setPage(1); }}
          style={{ fontSize: 12 }}
        >
          <option value="all">SA: Tất cả</option>
          <option value="sa1">SA1</option>
          <option value="sa2">SA2</option>
          <option value="sa3">SA3</option>
        </select>
      </div>

      {/* Table */}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th style={{ width: 36 }}></th>
              <th style={{ width: 36 }}></th>
              <th>BN / Mã</th>
              <th>Trạm hiện tại</th>
              <th>Thời gian chờ</th>
              <th>Ưu tiên</th>
              <th>Lý do chờ</th>
              <th>Phụ trách</th>
              <th>Trạm kế tiếp</th>
              <th>Thời gian chờ</th>
              <th>SLA</th>
            </tr>
          </thead>
          <tbody>
            {paged.map((p) => (
              <tr
                key={p.id}
                className={selectedPatientId === p.id ? 'selected' : ''}
                onClick={() => onSelectPatient(p)}
                style={{ cursor: 'pointer' }}
              >
                <td onClick={(e) => e.stopPropagation()}>
                  <input
                    type="checkbox"
                    checked={selected.has(p.id)}
                    onChange={() => toggleSelect(p.id)}
                  />
                </td>
                <td>
                  <div
                    style={{
                      width: 30,
                      height: 30,
                      borderRadius: '50%',
                      background: p.priority === 'urgent' ? 'var(--danger-bg)' : p.priority === 'high' ? 'var(--warning-bg)' : 'var(--surface-sunken)',
                      color: p.priority === 'urgent' ? 'var(--danger)' : p.priority === 'high' ? 'var(--warning)' : 'var(--ink-muted)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: 11,
                      fontWeight: 700,
                    }}
                  >
                    {p.name.split(' ').slice(-2).map(w => w[0]).join('')}
                  </div>
                </td>
                <td>
                  <div style={{ fontWeight: 600, fontSize: 13, color: 'var(--ink)' }}>{p.name}</div>
                  <div style={{ fontSize: 11, color: 'var(--ink-muted)' }}>{p.code}</div>
                </td>
                <td>
                  <span style={{ fontSize: 12, fontWeight: 500 }}>{p.currentStationName}</span>
                </td>
                <td>
                  <span
                    style={{
                      fontWeight: 700,
                      fontSize: 13,
                      color: p.waitMinutes > 20 ? 'var(--danger)' : p.waitMinutes > 12 ? 'var(--warning)' : 'var(--ink)',
                    }}
                  >
                    {p.waitMinutes} phút
                  </span>
                  {p.waitMinutes > 15 && (
                    <div style={{ fontSize: 10, color: 'var(--ink-muted)' }}>(SLA {p.waitMinutes > 20 ? '30' : '20'} phút)</div>
                  )}
                </td>
                <td>
                  {p.priority !== 'normal' && (
                    <span className={`badge ${p.priority === 'urgent' ? 'badge-danger' : 'badge-warning'}`}>
                      {p.priorityLabel}
                    </span>
                  )}
                </td>
                <td style={{ fontSize: 12, color: 'var(--ink-soft)' }}>{p.waitReason}</td>
                <td style={{ fontSize: 12, color: 'var(--ink-soft)' }}>{p.assignedTo}</td>
                <td>
                  {p.nextStationName ? (
                    <span className="badge badge-brand">{p.nextStationName}</span>
                  ) : (
                    <span style={{ fontSize: 11, color: 'var(--ink-faint)' }}>—</span>
                  )}
                </td>
                <td style={{ fontSize: 12, fontWeight: 600, color: 'var(--ink)' }}>
                  {p.nextStation ? `${Math.max(0, p.waitMinutes - 5)} / ${p.waitMinutes} phút` : '—'}
                </td>
                <td style={{ width: 100 }}>
                  <div className="sla-bar" style={{ width: 80 }}>
                    <div
                      className="sla-bar-fill"
                      style={{
                        width: `${Math.min(p.slaPercent, 100)}%`,
                        background: slaColor(p.slaPercent),
                      }}
                    />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 12 }}>
        <span style={{ fontSize: 12, color: 'var(--ink-muted)' }}>
          Hiển thị {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, filtered.length)} trong {filtered.length}
        </span>
        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          <button
            className="btn btn-ghost"
            disabled={page <= 1}
            onClick={() => setPage(page - 1)}
            style={{ padding: '4px 8px' }}
          >
            <ChevronLeft size={14} />
          </button>
          {Array.from({ length: Math.min(totalPages, 8) }, (_, i) => i + 1).map(n => (
            <button
              key={n}
              className={n === page ? 'btn btn-primary' : 'btn btn-ghost'}
              onClick={() => setPage(n)}
              style={{ padding: '4px 10px', fontSize: 12, minWidth: 30 }}
            >
              {n}
            </button>
          ))}
          {totalPages > 8 && <span style={{ fontSize: 12, color: 'var(--ink-muted)' }}>…</span>}
          <button
            className="btn btn-ghost"
            disabled={page >= totalPages}
            onClick={() => setPage(page + 1)}
            style={{ padding: '4px 8px' }}
          >
            <ChevronRight size={14} />
          </button>
        </div>
      </div>
    </div>
  );
}
