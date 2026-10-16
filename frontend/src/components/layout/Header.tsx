import React from 'react';
import { useLocation } from 'react-router-dom';
import { Menu, FolderLock, LayoutDashboard, MessageSquare } from 'lucide-react';
import { Badge } from '../common/Badge';
import { ThemeSwitcher } from '../common/ThemeSwitcher';
import type { HealthStatus } from '../../types/api';

interface HeaderProps {
  onMenuToggle: () => void;
  health: HealthStatus | null;
  healthLoading: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  onMenuToggle,
  health,
  healthLoading,
}) => {
  const location = useLocation();
  const isConnected = health?.status === 'ok' && health?.database === 'connected';

  const getRouteInfo = () => {
    switch (location.pathname) {
      case '/documents':
        return {
          title: 'Knowledge Archive',
          category: 'DOCUMENT REPOSITORY',
          icon: <FolderLock size={16} color="var(--color-primary)" />,
        };
      case '/chat':
        return {
          title: 'Research Console',
          category: 'INTELLIGENCE WORKSPACE',
          icon: <MessageSquare size={16} color="var(--color-primary)" />,
        };
      case '/dashboard':
      default:
        return {
          title: 'System Command Overview',
          category: 'TELEMETRY & OPERATIONS',
          icon: <LayoutDashboard size={16} color="var(--color-primary)" />,
        };
    }
  };

  const routeInfo = getRouteInfo();

  return (
    <header className="header">
      <div className="header-title-container">
        <button
          className="mobile-menu-btn"
          onClick={onMenuToggle}
          aria-label="Toggle navigation menu"
        >
          <Menu size={18} />
        </button>
        <div>
          <div className="header-breadcrumb-tag">{routeInfo.category}</div>
          <h1 className="header-title">
            {routeInfo.icon}
            <span>{routeInfo.title}</span>
          </h1>
        </div>
      </div>

      <div className="header-actions">
        <ThemeSwitcher />
        {healthLoading ? (
          <span style={{ fontSize: '0.72rem', color: 'var(--color-text-dim)', fontFamily: 'var(--font-mono)' }}>
            VERIFYING TELEMETRY...
          </span>
        ) : isConnected ? (
          <Badge status="connected">API & DB ONLINE</Badge>
        ) : (
          <Badge status="disconnected">BACKEND OFFLINE</Badge>
        )}
      </div>
    </header>
  );
};
