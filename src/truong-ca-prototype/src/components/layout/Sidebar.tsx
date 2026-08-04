import { useState } from 'react';
import {
  LayoutDashboard,
  Rows3,
  AlertTriangle,
  History,
  Tv,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';

export type TabId = 'overview' | 'queues' | 'alerts' | 'history' | 'tv';

interface SidebarProps {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
  alertCount: number;
}

const TABS: { id: TabId; label: string; icon: typeof LayoutDashboard }[] = [
  { id: 'overview', label: 'Toàn cảnh điều phối', icon: LayoutDashboard },
  { id: 'queues', label: 'Hàng đợi theo trạm', icon: Rows3 },
  { id: 'alerts', label: 'Cảnh báo & SLA', icon: AlertTriangle },
  { id: 'history', label: 'Lịch sử điều phối', icon: History },
  { id: 'tv', label: 'TV Phòng chờ', icon: Tv },
];

export default function Sidebar({ activeTab, onTabChange, alertCount }: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      style={{
        width: collapsed ? 68 : 240,
        minWidth: collapsed ? 68 : 240,
        background: 'var(--surface)',
        borderRight: '1px solid var(--line)',
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        position: 'sticky',
        top: 0,
        transition: 'width 0.2s ease, min-width 0.2s ease',
        zIndex: 20,
      }}
    >
      {/* Logo */}
      <div
        style={{
          padding: collapsed ? '20px 8px' : '20px 16px',
          borderBottom: '1px solid var(--line)',
          display: 'flex',
          alignItems: 'center',
          gap: 10,
          justifyContent: collapsed ? 'center' : 'flex-start',
        }}
      >
        <div
          style={{
            width: 36,
            height: 36,
            borderRadius: 10,
            background: 'linear-gradient(135deg, var(--brand-500), var(--brand-700))',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'white',
            fontWeight: 800,
            fontSize: 14,
            flexShrink: 0,
          }}
        >
          CA
        </div>
        {!collapsed && (
          <div style={{ overflow: 'hidden' }}>
            <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--ink)', whiteSpace: 'nowrap' }}>
              ClinicAI
            </div>
            <div style={{ fontSize: 10, color: 'var(--ink-muted)', whiteSpace: 'nowrap', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Connected Clinic Workflow
            </div>
          </div>
        )}
      </div>

      {/* Role label */}
      {!collapsed && (
        <div style={{ padding: '16px 16px 8px', fontSize: 11, fontWeight: 600, color: 'var(--ink-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
          TRƯỞNG CA
        </div>
      )}

      {/* Nav items */}
      <nav style={{ flex: 1, padding: '4px 8px', display: 'flex', flexDirection: 'column', gap: 2 }}>
        {TABS.map((tab) => {
          const active = activeTab === tab.id;
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              title={collapsed ? tab.label : undefined}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                padding: collapsed ? '10px' : '10px 12px',
                borderRadius: 'var(--radius-control)',
                border: 'none',
                background: active ? 'var(--brand-50)' : 'transparent',
                color: active ? 'var(--brand-700)' : 'var(--ink-soft)',
                fontSize: 13,
                fontWeight: active ? 600 : 500,
                cursor: 'pointer',
                textAlign: 'left',
                width: '100%',
                transition: 'all 0.15s ease',
                justifyContent: collapsed ? 'center' : 'flex-start',
                borderLeft: active ? '3px solid var(--brand-600)' : '3px solid transparent',
                position: 'relative',
                fontFamily: 'inherit',
              }}
              onMouseEnter={(e) => {
                if (!active) e.currentTarget.style.background = 'var(--surface-sunken)';
              }}
              onMouseLeave={(e) => {
                if (!active) e.currentTarget.style.background = 'transparent';
              }}
            >
              <Icon size={18} strokeWidth={2} style={{ flexShrink: 0 }} />
              {!collapsed && <span style={{ flex: 1, whiteSpace: 'nowrap' }}>{tab.label}</span>}
              {!collapsed && tab.id === 'alerts' && alertCount > 0 && (
                <span
                  style={{
                    background: 'var(--danger)',
                    color: 'white',
                    borderRadius: 999,
                    padding: '1px 7px',
                    fontSize: 11,
                    fontWeight: 700,
                    minWidth: 20,
                    textAlign: 'center',
                  }}
                >
                  {alertCount}
                </span>
              )}
              {collapsed && tab.id === 'alerts' && alertCount > 0 && (
                <span
                  style={{
                    position: 'absolute',
                    top: 4,
                    right: 4,
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    background: 'var(--danger)',
                  }}
                />
              )}
            </button>
          );
        })}
      </nav>

      {/* Collapse toggle */}
      <div style={{ padding: '12px 8px', borderTop: '1px solid var(--line)' }}>
        <button
          onClick={() => setCollapsed(!collapsed)}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 6,
            width: '100%',
            padding: '8px',
            borderRadius: 'var(--radius-control)',
            border: '1px solid var(--line)',
            background: 'var(--surface-muted)',
            color: 'var(--ink-muted)',
            fontSize: 12,
            fontWeight: 500,
            cursor: 'pointer',
            fontFamily: 'inherit',
          }}
          title={collapsed ? 'Mở rộng' : 'Thu gọn'}
        >
          {collapsed ? <ChevronRight size={14} /> : <ChevronLeft size={14} />}
          {!collapsed && 'Thu gọn'}
        </button>
      </div>
    </aside>
  );
}
