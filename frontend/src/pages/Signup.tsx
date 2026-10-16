import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertCircle, CheckCircle, ArrowRight } from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { Input } from '../components/common/Input';
import { Button } from '../components/common/Button';
import { IntelligenceBackground } from '../components/common/IntelligenceBackground';
import { HudCornerBrackets } from '../components/common/HudCornerBrackets';

export const Signup: React.FC = () => {
  const { signUp } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [errors, setErrors] = useState<{ email?: string; password?: string; confirmPassword?: string }>({});
  const [apiError, setApiError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const validate = () => {
    const newErrors: { email?: string; password?: string; confirmPassword?: string } = {};
    const trimmedEmail = email.trim();

    if (!trimmedEmail) {
      newErrors.email = 'Email address is required.';
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmedEmail)) {
      newErrors.email = 'Please enter a valid email address.';
    }

    if (!password) {
      newErrors.password = 'Password is required.';
    } else if (password.length < 6) {
      newErrors.password = 'Password must be at least 6 characters.';
    }

    if (password !== confirmPassword) {
      newErrors.confirmPassword = 'Passwords do not match.';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setApiError(null);
    setSuccessMessage(null);

    if (!validate()) return;

    setSubmitting(true);
    try {
      const { error, user } = await signUp(email.trim(), password);
      if (error) {
        const msg = error.message.toLowerCase();
        if (msg.includes('already registered') || msg.includes('user already exists')) {
          setApiError('An account with this email already exists.');
        } else {
          setApiError(error.message || 'Unable to create account. Please try again.');
        }
      } else if (user && user.identities && user.identities.length === 0) {
        setApiError('An account with this email already exists.');
      } else {
        setSuccessMessage(
          'Account created successfully! If email confirmation is enabled, please check your inbox to confirm your email before logging in.'
        );
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
              OPERATOR REGISTRATION // PROVISION
            </span>
          </div>
          <h1 className="auth-title">Create Account</h1>
          <p className="auth-subtitle">Provision tenant workspace in Document Intelligence RAG</p>
        </div>

        {apiError && (
          <div className="alert-box alert-danger" style={{ marginBottom: 18 }}>
            <AlertCircle size={16} style={{ flexShrink: 0 }} />
            <span>{apiError}</span>
          </div>
        )}

        {successMessage && (
          <div className="alert-box alert-success" style={{ marginBottom: 18 }}>
            <CheckCircle size={16} style={{ flexShrink: 0 }} />
            <span>{successMessage}</span>
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
            placeholder="At least 6 characters"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            error={errors.password}
            autoComplete="new-password"
          />

          <Input
            label="Confirm Password"
            type="password"
            placeholder="Repeat your password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            error={errors.confirmPassword}
            autoComplete="new-password"
          />

          <Button type="submit" isLoading={submitting} style={{ width: '100%', marginTop: 6 }}>
            <span>Create Account</span>
            <ArrowRight size={15} />
          </Button>
        </form>

        <div className="auth-footer">
          Already have an account?{' '}
          <Link to="/login">Sign in here</Link>
        </div>
      </div>
    </div>
  );
};

export default Signup;
