import React from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import {
  FileText,
  FileSpreadsheet,
  FileCode,
  Download,
  Trash2,
  CheckCircle2,
  Clock,
  AlertCircle,
  Loader2,
} from 'lucide-react';
import type { DocumentItem, IngestionJobStatus } from '../../types/document';
import { formatFileSize, formatTimestamp } from '../../services/documents';
import { HudCornerBrackets } from '../common/HudCornerBrackets';

interface DocumentCardProps {
  document: DocumentItem;
  jobStatus?: IngestionJobStatus;
  isDownloading: boolean;
  onDownload: (doc: DocumentItem) => void;
  onDelete: (doc: DocumentItem) => void;
}

export const DocumentCard: React.FC<DocumentCardProps> = ({
  document,
  jobStatus,
  isDownloading,
  onDownload,
  onDelete,
}) => {
  const shouldReduceMotion = useReducedMotion();

  const getFileIcon = (fileType?: string | null, filename?: string) => {
    const ext = (fileType || filename?.split('.').pop() || '').toLowerCase();
    switch (ext) {
      case 'xlsx':
      case 'csv':
        return <FileSpreadsheet size={20} className="doc-icon spreadsheet" />;
      case 'txt':
        return <FileCode size={20} className="doc-icon text" />;
      case 'pdf':
      case 'docx':
      default:
        return <FileText size={20} className="doc-icon document" />;
    }
  };

  // Determine effective status: ingestion job status takes precedence if active/failed
  const effectiveStatus = jobStatus?.status || document.status;

  const renderStatusBadge = () => {
    switch (effectiveStatus) {
      case 'completed':
        return (
          <span className="status-badge connected" title="Indexed and ready for RAG queries">
            <CheckCircle2 size={11} />
            <span>Ready</span>
          </span>
        );
      case 'processing':
        return (
          <span className="status-badge processing" title="Vectorization in progress">
            <Loader2 size={11} className="icon-spin" />
            <span>Processing</span>
          </span>
        );
      case 'queued':
      case 'uploaded':
        return (
          <span className="status-badge queued" title="Queued for indexing">
            <Clock size={11} />
            <span>Queued</span>
          </span>
        );
      case 'failed':
        return (
          <span
            className="status-badge disconnected"
            title={jobStatus?.error_message || 'Ingestion encountered an error'}
          >
            <AlertCircle size={11} />
            <span>Failed</span>
          </span>
        );
      default:
        return (
          <span className="status-badge neutral">
            <span className="status-dot" />
            <span>{effectiveStatus}</span>
          </span>
        );
    }
  };

  // Real chunk progress if available
  const hasChunkProgress =
    jobStatus &&
    effectiveStatus === 'processing' &&
    jobStatus.total_chunks > 0;

  return (
    <motion.div
      className="document-card hud-bracket-container"
      data-testid={`document-card-${document.id}`}
      initial={shouldReduceMotion ? false : { opacity: 0, y: 10 }}
      animate={shouldReduceMotion ? false : { opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      whileHover={shouldReduceMotion ? undefined : { y: -2 }}
    >
      <HudCornerBrackets size={7} />

      <div className="document-card-main">
        <div className="document-icon-wrapper">
          {getFileIcon(document.file_type, document.filename)}
        </div>

        <div className="document-info">
          <h4 className="document-title" title={document.filename}>
            {document.filename}
          </h4>
          <div className="document-meta">
            <span className="meta-tag">{document.file_type ? document.file_type.toUpperCase() : 'FILE'}</span>
            <span className="meta-dot">•</span>
            <span>{formatFileSize(document.file_size)}</span>
            <span className="meta-dot">•</span>
            <span title={`Uploaded on ${document.created_at || 'unknown'}`}>
              {formatTimestamp(document.created_at)}
            </span>
          </div>

          {hasChunkProgress && (
            <div className="chunk-progress-box">
              <div className="chunk-progress-label">
                <span>Indexing chunks</span>
                <span>
                  {jobStatus.processed_chunks} / {jobStatus.total_chunks}
                </span>
              </div>
              <div className="progress-track-sm">
                <div
                  className="progress-fill-sm"
                  style={{
                    width: `${Math.min(
                      100,
                      Math.round((jobStatus.processed_chunks / jobStatus.total_chunks) * 100)
                    )}%`,
                  }}
                />
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="document-card-actions">
        <div>{renderStatusBadge()}</div>

        <div className="doc-action-btn-group">
          <button
            type="button"
            className="doc-action-btn"
            onClick={() => onDownload(document)}
            disabled={isDownloading}
            aria-label={`Download ${document.filename}`}
            title="Download document file"
          >
            {isDownloading ? (
              <Loader2 size={13} className="icon-spin" />
            ) : (
              <Download size={13} />
            )}
          </button>

          <button
            type="button"
            className="doc-action-btn delete-btn"
            onClick={() => onDelete(document)}
            aria-label={`Delete ${document.filename}`}
            title="Delete document file"
          >
            <Trash2 size={13} />
          </button>
        </div>
      </div>
    </motion.div>
  );
};
