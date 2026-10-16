import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AlertCircle, ArrowRight } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { Input } from '../components/common/Input';
import { Button } from '../components/common/Button';
import { IntelligenceBackground } from '../components/common/IntelligenceBackground';
import { HudCornerBrackets } from '../components/common/HudCornerBrackets';

export const Login: React.FC = () => {
  const navigate = useNavigate();
  const { signIn } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({});
  const [apiError, setApiError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const validate = () => {
    const newErrors: { email?: string; password?: string } = {};
    const trimmedEmail = email.trim();

    if (!trimmedEmail) {
      newErrors.email = 'Email address is required.';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmedEmail)) {
      newErrors.email = 'Please enter a valid email address.';
    }

    if (!password) {
      newErrors.password = 'Password is required.';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setApiError(null);

    if (!validate()) return;

    setSubmitting(true);
    try {
      const { error } = await signIn(email.trim(), password);
      if (error) {
        const msg = error.message.toLowerCase();
        if (msg.includes('invalid login credentials') || msg.includes('invalid_grant')) {
          setApiError('Invalid email or password.');
        } else if (msg.includes('email not confirmed')) {
          setApiError('Your email address has not been confirmed. Please check your inbox.');
        } else {
          setApiError('Unable to sign in. Please check your credentials and try again.');
        }
      } else {
        navigate('/dashboard', { replace: true });
      }
    } catch {
      setApiError('A network error occurred. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="auth-container">
      <IntelligenceBackground />
      <div className="ambient-glow" />

      <div className="auth-card hud-bracket-container">
        <HudCornerBrackets size={10} />

        <div className="auth-header">
          <div className="brand-logo" style={{ margin: '0 auto', width: 42, height: 42, fontSize: '1.2rem' }}>
            ⌬
          </div>
          <div style={{ marginTop: 12, display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <span className="hero-eyebrow" style={{ padding: '2px 8px', fontSize: '0.62rem', marginBottom: 0 }}>
              SECURITY GATEWAY // AUTH
            </span>
          </div>
          <h1 className="auth-title">Welcome Back</h1>
          <p className="auth-subtitle">Sign in to your Document Intelligence workspace</p>
        </div>

        {apiError && (
          <div className="alert-box alert-danger" style={{ marginBottom: 18 }}>
            <AlertCircle size={16} style={{ flexShrink: 0 }} />
            <span>{apiError}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="auth-form" noValidate>
          <Input
            label="Email Address"
            type="email"
            placeholder="operator@system.io"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            error={errors.email}
            autoComplete="email"
            autoFocus
          />

          <Input
            label="Password"
            type="password"
            placeholder="••••••••"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            error={errors.password}
            autoComplete="current-password"
          />

          <Button type="submit" isLoading={submitting} style={{ width: '100%', marginTop: 6 }}>
            <span>Sign In</span>
            <ArrowRight size={15} />
          </Button>
        </form>

        <div className="auth-footer">
          Don't have an account?{' '}
          <Link to="/signup">Create one now</Link>
        </div>
      </div>
    </div>
  );
};

export default Login;
