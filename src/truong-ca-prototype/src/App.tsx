import { useState } from 'react';
import Sidebar, { type TabId } from './components/layout/Sidebar';
import Header from './components/layout/Header';
import KpiCards from './components/overview/KpiCards';
import StationCards from './components/overview/StationCards';
import PatientTable from './components/overview/PatientTable';
import PatientDetailPanel from './components/overview/PatientDetailPanel';
import QueueGrid from './components/queues/QueueGrid';
import AlertList from './components/alerts/AlertList';
import DispatchHistory from './components/history/DispatchHistory';
import TvDisplay from './components/tv/TvDisplay';
import NurseVitalsDashboard from './components/nurse/NurseVitalsDashboard';
import TransferRoomModal from './components/modals/TransferRoomModal';
import RouteSelectModal from './components/modals/RouteSelectModal';
import { ALERTS, type Patient } from './data/mock-data';
import { UserCheck, Stethoscope } from 'lucide-react';

export default function App() {
  const [roleView, setRoleView] = useState<'truong_ca' | 'dieu_duong'>('truong_ca');
  const [activeTab, setActiveTab] = useState<TabId>('overview');
  const [selectedPatient, setSelectedPatient] = useState<Patient | null>(null);
  const [showTransferModal, setShowTransferModal] = useState(false);
  const [showRouteModal, setShowRouteModal] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const alertCount = ALERTS.filter(a => !a.acknowledged).length;

  function showToast(message: string) {
    setToast(message);
    setTimeout(() => setToast(null), 3000);
  }

  // TV mode is full-screen, no sidebar/header
  if (activeTab === 'tv') {
    return (
      <div style={{ position: 'relative' }}>
        <button
          onClick={() => setActiveTab('overview')}
          className="btn btn-secondary"
          style={{
            position: 'fixed',
            top: 12,
            left: 12,
            zIndex: 30,
            fontSize: 11,
            padding: '6px 12px',
            background: 'rgba(255,255,255,0.9)',
            backdropFilter: 'blur(8px)',
          }}
        >
          ← Về Dashboard
        </button>
        <TvDisplay />
      </div>
    );
  }

  // Nurse role view
  if (roleView === 'dieu_duong') {
    return (
      <div style={{ position: 'relative' }}>
        {/* Quick Role Switcher Bar */}
        <div
          style={{
            position: 'fixed',
            bottom: 16,
            left: 16,
            zIndex: 50,
            background: 'var(--ink)',
            color: 'white',
            padding: '6px 12px',
            borderRadius: 999,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            boxShadow: 'var(--shadow-lg)',
            fontSize: 12,
          }}
        >
          <span style={{ opacity: 0.8 }}>Đang ở vai: <strong>Điều dưỡng</strong></span>
          <button
            onClick={() => setRoleView('truong_ca')}
            className="btn btn-primary"
            style={{ padding: '3px 10px', fontSize: 11, background: 'var(--brand-500)' }}
          >
            <UserCheck size={12} /> Sang Trưởng ca
          </button>
        </div>

        <NurseVitalsDashboard onSwitchRole={() => setRoleView('truong_ca')} />
      </div>
    );
  }

  // Trưởng Ca role view
  return (
    <div style={{ display: 'flex', minHeight: '100vh', position: 'relative' }}>
      {/* Floating Role Switcher Bar */}
      <div
        style={{
          position: 'fixed',
          bottom: 16,
          left: 256,
          zIndex: 50,
          background: 'var(--ink)',
          color: 'white',
          padding: '6px 12px',
          borderRadius: 999,
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          boxShadow: 'var(--shadow-lg)',
          fontSize: 12,
        }}
      >
        <span style={{ opacity: 0.8 }}>Đang ở vai: <strong>Trưởng ca</strong></span>
        <button
          onClick={() => setRoleView('dieu_duong')}
          className="btn btn-primary"
          style={{ padding: '3px 10px', fontSize: 11, background: 'var(--brand-500)' }}
        >
          <Stethoscope size={12} /> Sang Màn hình Điều dưỡng
        </button>
      </div>

      <Sidebar activeTab={activeTab} onTabChange={setActiveTab} alertCount={alertCount} />

      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
        <Header />

        <div style={{ flex: 1, display: 'flex', minHeight: 0 }}>
          {/* Main content */}
          <div
            style={{
              flex: 1,
              minWidth: 0,
              padding: 24,
              overflowY: 'auto',
            }}
          >
            {activeTab === 'overview' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                {/* Filters row */}
                <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                  {['Tầng', 'Tất cả tầng'].map((l, i) => (
                    <button key={i} className={i === 1 ? 'btn btn-primary' : 'btn btn-secondary'} style={{ padding: '4px 10px', fontSize: 11 }}>
                      {l}
                    </button>
                  ))}
                  <span style={{ width: 1, height: 16, background: 'var(--line)' }} />
                  {['Dịch vụ', 'Tất cả dịch vụ'].map((l, i) => (
                    <button key={i} className={i === 1 ? 'btn btn-primary' : 'btn btn-secondary'} style={{ padding: '4px 10px', fontSize: 11 }}>
                      {l}
                    </button>
                  ))}
                  <span style={{ width: 1, height: 16, background: 'var(--line)' }} />
                  {['Ưu tiên', 'Tất cả'].map((l, i) => (
                    <button key={i} className={i === 1 ? 'btn btn-primary' : 'btn btn-secondary'} style={{ padding: '4px 10px', fontSize: 11 }}>
                      {l}
                    </button>
                  ))}
                  <span style={{ width: 1, height: 16, background: 'var(--line)' }} />
                  {['SA', 'Tất cả'].map((l, i) => (
                    <button key={i} className={i === 1 ? 'btn btn-primary' : 'btn btn-secondary'} style={{ padding: '4px 10px', fontSize: 11 }}>
                      {l}
                    </button>
                  ))}
                  <div style={{ flex: 1 }} />
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--brand-600)' }}>
                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--success)', animation: 'pulse-dot 1.5s ease-in-out infinite' }} />
                    Cập nhật trực tiếp
                  </div>
                </div>

                <KpiCards />
                <StationCards />
                <PatientTable
                  onSelectPatient={setSelectedPatient}
                  selectedPatientId={selectedPatient?.id ?? null}
                />
              </div>
            )}

            {activeTab === 'queues' && (
              <QueueGrid onTransfer={() => setShowTransferModal(true)} />
            )}

            {activeTab === 'alerts' && (
              <AlertList onDispatch={() => setActiveTab('overview')} />
            )}

            {activeTab === 'history' && (
              <DispatchHistory />
            )}
          </div>

          {/* Patient detail panel (overview only) */}
          {activeTab === 'overview' && selectedPatient && (
            <PatientDetailPanel
              patient={selectedPatient}
              onClose={() => setSelectedPatient(null)}
              onTransfer={() => setShowTransferModal(true)}
              onRouteSelect={() => setShowRouteModal(true)}
            />
          )}
        </div>
      </div>

      {/* Modals */}
      {showTransferModal && (
        <TransferRoomModal
          onClose={() => setShowTransferModal(false)}
          onConfirm={() => {
            setShowTransferModal(false);
            showToast('✓ Đã chuyển phòng thành công!');
          }}
        />
      )}

      {showRouteModal && (
        <RouteSelectModal
          patientName={selectedPatient?.name ?? 'Bệnh nhân'}
          onClose={() => setShowRouteModal(false)}
          onConfirm={() => {
            setShowRouteModal(false);
            showToast('✓ Đã chọn tuyến điều phối thành công!');
          }}
        />
      )}

      {/* Toast */}
      {toast && (
        <div className="toast">
          {toast}
        </div>
      )}
    </div>
  );
}
