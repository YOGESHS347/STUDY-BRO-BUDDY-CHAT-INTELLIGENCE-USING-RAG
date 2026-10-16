import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  FileText,
  MessageSquare,
  LogOut,
  X,
  PanelLeftClose,
  PanelLeftOpen,
} from 'lucide-react';
import { useAuth } from '../../hooks/useAuth';

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  isCollapsed?: boolean;
  onToggleCollapse?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  isOpen,
  onClose,
  isCollapsed = false,
  onToggleCollapse,
}) => {
  const { user, profile, signOut } = useAuth();
  const displayEmail = profile?.email || user?.email || 'User';

  return (
    <aside className={`sidebar ${isOpen ? 'open' : ''} ${isCollapsed ? 'collapsed' : ''}`}>
      <div className="sidebar-header">
        <div className="brand-wrapper">
          <div className="brand-logo" title="DocIntelligence Command Core">
            ⌬
          </div>
          {!isCollapsed && (
            <div style={{ flex: 1, minWidth: 0 }}>
              <h2 className="brand-title">DocIntelligence</h2>
              <span className="brand-badge">RAG Platform</span>
            </div>
          )}
        </div>

        {onToggleCollapse && (
          <button
            type="button"
            className="sidebar-collapse-btn desktop-only"
            onClick={onToggleCollapse}
            title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {isCollapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
          </button>
        )}

        <button
          type="button"
          className="mobile-menu-btn"
          onClick={onClose}
          aria-label="Close Sidebar"
          style={{ padding: 4 }}
        >
          <X size={18} />
        </button>
      </div>

      <nav className="sidebar-nav">
        <NavLink
          to="/dashboard"
          className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
          onClick={onClose}
          title={isCollapsed ? 'Dashboard' : undefined}
        >
          <LayoutDashboard size={17} />
          {!isCollapsed && <span>Dashboard</span>}
        </NavLink>

        <NavLink
          to="/documents"
          className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
          onClick={onClose}
          title={isCollapsed ? 'Documents' : undefined}
        >
          <FileText size={17} />
          {!isCollapsed && <span>Documents</span>}
        </NavLink>

        <NavLink
          to="/chat"
          className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
          onClick={onClose}
          title={isCollapsed ? 'Chat' : undefined}
        >
          <MessageSquare size={17} />
          {!isCollapsed && <span>Chat</span>}
        </NavLink>
      </nav>

      <div className="sidebar-footer">
        {!isCollapsed && (
          <div className="user-profile-badge">
            <div className="user-avatar" title={displayEmail}>
              {displayEmail.charAt(0).toUpperCase()}
            </div>
            <div className="user-details">
              <div className="user-email" title={displayEmail}>
                {displayEmail}
              </div>
              <div className="user-role">ISOLATED // SHA-256</div>
            </div>
          </div>
        )}

        <button
          type="button"
          className="btn-signout"
          onClick={() => signOut()}
          title="Sign out of application"
        >
          <LogOut size={15} />
          {!isCollapsed && <span>TERMINATE SESSION</span>}
        </button>
      </div>
    </aside>
  );
};
