import React from 'react';
import { Link } from 'react-router-dom';
import { FileQuestion, ArrowLeft } from 'lucide-react';
import { Button } from '../components/common/Button';

export const NotFound: React.FC = () => {
  return (
    <div className="auth-container">
      <div className="ambient-glow" />
      <div className="auth-card" style={{ textAlign: 'center' }}>
        <div className="brand-logo" style={{ margin: '0 auto', background: '#334155' }}>
          <FileQuestion size={20} />
        </div>
        <h1 className="auth-title" style={{ marginTop: 16 }}>404 - Page Not Found</h1>
        <p className="auth-subtitle" style={{ marginBottom: 28 }}>
          The page you are looking for does not exist or has been moved.
        </p>

        <Link to="/dashboard">
          <Button style={{ display: 'inline-flex', width: 'auto', padding: '10px 24px' }}>
            <ArrowLeft size={16} /> Return to Dashboard
          </Button>
        </Link>
      </div>
    </div>
  );
};
