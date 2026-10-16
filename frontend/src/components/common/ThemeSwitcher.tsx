import React from 'react';
import { Sun, Moon, Monitor } from 'lucide-react';
import { useTheme, type Theme } from '../../context/ThemeContext';

export const ThemeSwitcher: React.FC<{ className?: string }> = ({ className = '' }) => {
  const { theme, setTheme } = useTheme();

  const options: { value: Theme; label: string; icon: React.ReactNode }[] = [
    { value: 'light', label: 'Light theme', icon: <Sun size={15} /> },
    { value: 'dark', label: 'Dark theme', icon: <Moon size={15} /> },
    { value: 'system', label: 'System theme', icon: <Monitor size={15} /> },
  ];

  return (
    <div className={`theme-switcher-group ${className}`} role="radiogroup" aria-label="Theme selection">
      {options.map((opt) => {
        const isActive = theme === opt.value;
        return (
          <button
            key={opt.value}
            type="button"
            className={`theme-switcher-btn ${isActive ? 'active' : ''}`}
            onClick={() => setTheme(opt.value)}
            role="radio"
            aria-checked={isActive}
            aria-label={opt.label}
            title={opt.label}
          >
            {opt.icon}
          </button>
        );
      })}
    </div>
  );
};
