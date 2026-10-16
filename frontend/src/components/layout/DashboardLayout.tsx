import React, { useState, useEffect } from 'react';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { IntelligenceBackground } from '../common/IntelligenceBackground';
import { CustomCursor } from '../common/CustomCursor';
import { api } from '../../services/api';
import type { HealthStatus } from '../../types/api';

interface DashboardLayoutProps {
  children: React.ReactNode;
}

export const DashboardLayout: React.FC<DashboardLayoutProps> = ({ children }) => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [healthLoading, setHealthLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    const checkHealth = () => {
      api.getHealth()
        .then((data) => {
          if (mounted) {
            setHealth(data);
            setHealthLoading(false);
          }
        })
        .catch(() => {
          if (mounted) {
            setHealth(null);
            setHealthLoading(false);
          }
        });
    };

    checkHealth();
    const interval = setInterval(checkHealth, 5000);
    window.addEventListener('focus', checkHealth);

    return () => {
      mounted = false;
      clearInterval(interval);
      window.removeEventListener('focus', checkHealth);
    };
  }, []);

  return (
    <div className="app-layout">
      <CustomCursor />
      <IntelligenceBackground />
      <div className="ambient-glow" />
      
      <Sidebar
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        isCollapsed={isSidebarCollapsed}
        onToggleCollapse={() => setIsSidebarCollapsed((prev) => !prev)}
      />
      
      <div className="main-wrapper">
        <Header
          onMenuToggle={() => setSidebarOpen((prev) => !prev)}
          health={health}
          healthLoading={healthLoading}
        />
        <main className="content-body">{children}</main>
      </div>
    </div>
  );
};
