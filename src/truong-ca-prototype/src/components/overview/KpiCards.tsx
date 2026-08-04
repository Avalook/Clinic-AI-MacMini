import { Users, Clock, AlertTriangle, AlertOctagon, UserCheck } from 'lucide-react';
import { KPI } from '../../data/mock-data';

const cards = [
  { label: 'Đang trong phòng khám', value: KPI.totalInClinic, icon: Users, color: 'var(--brand-600)', bg: 'var(--brand-50)' },
  { label: 'Đang chờ', value: KPI.waiting, icon: Clock, color: 'var(--warning)', bg: 'var(--warning-bg)' },
  { label: 'Bị chậm', value: KPI.delayed, icon: AlertTriangle, color: '#d97706', bg: '#fef3c7' },
  { label: 'Quá SLA', value: KPI.overSla, icon: AlertOctagon, color: 'var(--danger)', bg: 'var(--danger-bg)' },
  { label: 'Nguồn lực khả dụng', value: `${KPI.resourceAvailable} / ${KPI.resourceTotal}`, icon: UserCheck, color: 'var(--brand-600)', bg: 'var(--brand-50)' },
];

export default function KpiCards() {
  return (
    <div
      className="fade-in"
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(5, 1fr)',
        gap: 0,
        background: 'var(--surface)',
        border: '1px solid var(--line)',
        borderRadius: 'var(--radius-card)',
        boxShadow: 'var(--shadow-card)',
        overflow: 'hidden',
      }}
    >
      {cards.map((card, i) => {
        const Icon = card.icon;
        return (
          <div
            key={i}
            style={{
              padding: '16px 20px',
              borderRight: i < cards.length - 1 ? '1px solid var(--line)' : 'none',
              display: 'flex',
              alignItems: 'center',
              gap: 12,
            }}
          >
            <div
              style={{
                width: 42,
                height: 42,
                borderRadius: '50%',
                background: card.bg,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              <Icon size={20} color={card.color} />
            </div>
            <div>
              <div style={{ fontSize: 12, color: 'var(--ink-muted)', marginBottom: 2 }}>{card.label}</div>
              <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--ink)', lineHeight: 1 }}>{card.value}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
