import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion, type Variants } from 'framer-motion';
import {
  Shield,
  FileText,
  MessageSquare,
  Server,
  CheckCircle2,
  ArrowRight,
} from 'lucide-react';
import { useAuth } from '../hooks/useAuth';
import { api } from '../services/api';
import { documentService } from '../services/documents';
import type { HealthStatus } from '../types/api';
import { PageTransition } from '../components/common/PageTransition';
import { KnowledgeCoreVisualization } from '../components/common/KnowledgeCoreVisualization';
import { HudCornerBrackets } from '../components/common/HudCornerBrackets';

// Cinematic Staged Boot Sequence Variants
const heroContainerVariants: Variants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.12,
      delayChildren: 0.08,
    },
  },
};

const heroElementVariants: Variants = {
  hidden: { opacity: 0, y: 16 },
  visible: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.55,
      ease: [0.16, 1, 0.3, 1],
    },
  },
};

export const Dashboard: React.FC = () => {
  const { user, profile } = useAuth();
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [loadingHealth, setLoadingHealth] = useState(true);
  const [docCount, setDocCount] = useState<number>(0);

  useEffect(() => {
    let mounted = true;

    // Fetch backend health telemetry
    api.getHealth()
      .then((data) => {
        if (mounted) {
          setHealth(data);
          setLoadingHealth(false);
        }
      })
      .catch(() => {
        if (mounted) {
          setHealth(null);
          setLoadingHealth(false);
        }
      });

    // Fetch real document repository count
    documentService.listDocuments()
      .then((docs) => {
        if (mounted) {
          setDocCount(docs.length);
        }
      })
      .catch(() => {
        // keep fallback 0
      });

    return () => {
      mounted = false;
    };
  }, []);

  const displayEmail = profile?.email || user?.email || 'User';
  const isOnline = health?.status === 'ok';

  return (
    <PageTransition>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
        {/* Cinematic Split Hero: Editorial Technical Command Center + Core Visualization */}
        <motion.div
          className="dashboard-hero-split hud-bracket-container"
          variants={heroContainerVariants}
          initial="hidden"
          animate="visible"
        >
          <HudCornerBrackets size={12} />

          {/* Left: Command Statement & Primary Launch Actions */}
          <div style={{ position: 'relative', zIndex: 2 }}>
            <motion.div variants={heroElementVariants} className="hero-eyebrow">
              <span className="status-dot" style={{ backgroundColor: isOnline ? 'var(--color-success)' : 'var(--color-warning)' }} />
              <span>SYSTEM ENGINE // {isOnline ? 'ONLINE' : 'CONNECTING'}</span>
            </motion.div>

            <motion.h1 variants={heroElementVariants} className="hero-title">
              DOCUMENTS <br />
              BECOME <span className="text-gradient">INTELLIGENCE.</span>
            </motion.h1>

            <motion.p variants={heroElementVariants} className="hero-subtitle">
              Welcome back, <strong style={{ color: 'var(--color-text-main)' }}>{displayEmail}</strong>.
              Your enterprise research console is active. Query knowledge collections with
              sub-second vector retrieval, cross-encoder reranking, and local Qwen generation.
            </motion.p>

            <motion.div variants={heroElementVariants} className="hero-actions">
              <Link to="/chat" className="btn-primary">
                <span>Start Research Chat</span>
                <ArrowRight size={15} />
              </Link>

              <Link to="/documents" className="btn-secondary">
                <FileText size={15} />
                <span>Manage Knowledge Files</span>
              </Link>
            </motion.div>
          </div>

          {/* Right: Interactive Knowledge Core & Orbital Reticle Visualization */}
          <motion.div
            variants={heroElementVariants}
            style={{ position: 'relative', width: '100%', minHeight: 340 }}
          >
            <KnowledgeCoreVisualization
              documentCount={docCount}
              isOnline={isOnline}
            />
          </motion.div>
        </motion.div>

        {/* Precision Telemetry & Engineering Modules Grid */}
        <div className="dashboard-grid">
          {/* Backend Services Telemetry */}
          <div className="card hud-bracket-container">
            <HudCornerBrackets size={8} />
            <div className="card-header">
              <h3 className="card-title">
                <Server size={17} color="var(--color-primary)" />
                Backend Services
              </h3>
              {loadingHealth ? (
                <span style={{ fontSize: '0.72rem', color: 'var(--color-text-dim)', fontFamily: 'var(--font-mono)' }}>
                  CHECKING...
                </span>
              ) : health?.status === 'ok' ? (
                <span className="status-badge connected">
                  <span className="status-dot" /> Online
                </span>
              ) : (
                <span className="status-badge disconnected">
                  <span className="status-dot" /> Offline
                </span>
              )}
            </div>

            <p className="card-desc">
              FastAPI gateway connectivity and Supabase PostgreSQL session pooler status:
            </p>

            <div style={{ marginTop: 18, display: 'flex', flexDirection: 'column', gap: 6 }}>
              <div className="telemetry-row">
                <span className="telemetry-label">FastAPI Gateway:</span>
                <span
                  className="telemetry-val"
                  style={{ color: health?.status === 'ok' ? 'var(--color-success)' : 'var(--color-danger)' }}
                >
                  {health?.status === 'ok' ? '200 OK' : 'Unavailable'}
                </span>
              </div>

              <div className="telemetry-row">
                <span className="telemetry-label">PostgreSQL Database:</span>
                <span
                  className="telemetry-val"
                  style={{ color: health?.database === 'connected' ? 'var(--color-success)' : 'var(--color-danger)' }}
                >
                  {health?.database || 'Not Connected'}
                </span>
              </div>

              <div className="telemetry-row">
                <span className="telemetry-label">Object Storage:</span>
                <span className="telemetry-val" style={{ color: 'var(--color-success)' }}>
                  {health?.storage || 'Ready'}
                </span>
              </div>
            </div>
          </div>

          {/* Cryptographic Tenant Isolation */}
          <div className="card hud-bracket-container">
            <HudCornerBrackets size={8} />
            <div className="card-header">
              <h3 className="card-title">
                <Shield size={17} color="var(--color-primary)" />
                Tenant Isolation
              </h3>
              <span className="status-badge connected">
                <span className="status-dot" /> Active
              </span>
            </div>

            <p className="card-desc">
              Cryptographic identity verification is enforced by FastAPI backend for every request.
            </p>

            <div style={{ marginTop: 18, display: 'flex', flexDirection: 'column', gap: 10 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.82rem' }}>
                <CheckCircle2 size={15} color="var(--color-success)" style={{ flexShrink: 0 }} />
                <span>Token: Asymmetric ES256 Supabase JWT</span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.82rem' }}>
                <CheckCircle2 size={15} color="var(--color-success)" style={{ flexShrink: 0 }} />
                <span>Identity Source: Authoritative JWT sub claim</span>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.82rem' }}>
                <CheckCircle2 size={15} color="var(--color-success)" style={{ flexShrink: 0 }} />
                <span>Vector Scope: Qdrant Cloud user_id filtering</span>
              </div>
            </div>
          </div>

          {/* Document Ingestion & Embeddings */}
          <div className="card hud-bracket-container">
            <HudCornerBrackets size={8} />
            <div className="card-header">
              <h3 className="card-title">
                <FileText size={17} color="var(--color-primary)" />
                Document Management
              </h3>
              <span className="status-badge connected">
                <span className="status-dot" /> Active
              </span>
            </div>

            <p className="card-desc">
              Upload PDF, DOCX, XLSX, CSV, and TXT files. Automatic background chunking, local Sentence Transformer embeddings, and Supabase Storage integration are active.
            </p>

            <Link
              to="/documents"
              className="btn-secondary"
              style={{
                marginTop: 18,
                width: 'fit-content',
              }}
            >
              <span>Open Documents</span>
              <ArrowRight size={14} />
            </Link>
          </div>

          {/* RAG Inference & Local Generation */}
          <div className="card hud-bracket-container">
            <HudCornerBrackets size={8} />
            <div className="card-header">
              <h3 className="card-title">
                <MessageSquare size={17} color="var(--color-primary)" />
                RAG Conversations
              </h3>
              <span className="status-badge connected">
                <span className="status-dot" /> Active
              </span>
            </div>

            <p className="card-desc">
              Multi-turn conversation sessions, grounded answers with citations, query-aware cross-encoder reranking, and local Qwen LLM answer generation are active.
            </p>

            <Link
              to="/chat"
              className="btn-secondary"
              style={{
                marginTop: 18,
                width: 'fit-content',
              }}
            >
              <span>Launch Research Console</span>
              <ArrowRight size={14} />
            </Link>
          </div>
        </div>
      </div>
    </PageTransition>
  );
};

export default Dashboard;
