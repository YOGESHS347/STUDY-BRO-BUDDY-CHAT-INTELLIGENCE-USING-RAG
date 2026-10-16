import React from 'react';
import { LoadingSpinner } from './LoadingSpinner';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  isLoading?: boolean;
  variant?: 'primary' | 'secondary' | 'outline' | 'danger' | 'hud';
  children: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
  isLoading = false,
  variant = 'primary',
  disabled,
  children,
  className = '',
  ...props
}) => {
  const getVariantClass = () => {
    switch (variant) {
      case 'secondary':
        return 'btn-secondary';
      case 'danger':
        return 'btn-danger';
      case 'outline':
        return 'btn-secondary btn-outline';
      case 'hud':
        return 'btn-hud';
      case 'primary':
      default:
        return 'btn-primary';
    }
  };

  return (
    <button
      className={`${getVariantClass()} ${className}`}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading && <LoadingSpinner size={16} />}
      {children}
    </button>
  );
};
