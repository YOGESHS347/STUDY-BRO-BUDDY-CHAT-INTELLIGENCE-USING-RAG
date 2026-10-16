import React from 'react';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  icon?: React.ReactNode;
}

export const Input: React.FC<InputProps> = ({
  label,
  error,
  icon,
  id,
  className = '',
  ...props
}) => {
  const inputId = id || (label ? label.toLowerCase().replace(/\s+/g, '-') : undefined);

  return (
    <div className="form-group">
      {label && (
        <label htmlFor={inputId} className="form-label">
          <span>{label}</span>
        </label>
      )}
      <div className="input-wrapper-hud">
        {icon && <span className="input-icon-left">{icon}</span>}
        <input
          id={inputId}
          className={`form-input ${icon ? 'has-icon' : ''} ${error ? 'border-danger' : ''} ${className}`}
          {...props}
        />
      </div>
      {error && <span className="form-error">{error}</span>}
    </div>
  );
};
