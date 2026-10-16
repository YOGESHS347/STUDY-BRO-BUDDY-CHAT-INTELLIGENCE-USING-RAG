import React from 'react';

interface BadgeProps {
  status?: 'connected' | 'disconnected' | 'info' | 'warning';
  children: React.ReactNode;
  className?: string;
}

export const Badge: React.FC<BadgeProps> = ({
  status = 'info',
  children,
  className = '',
}) => {
  return (
    <span className={`status-badge ${status} ${className}`}>
      <span className="status-dot" />
      {children}
    </span>
  );
};
