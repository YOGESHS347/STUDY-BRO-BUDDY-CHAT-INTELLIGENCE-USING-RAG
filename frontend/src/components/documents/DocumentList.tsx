import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { FileText, RefreshCw, AlertCircle } from 'lucide-react';
import type { DocumentItem, IngestionJobStatus } from '../../types/document';
import { DocumentCard } from './DocumentCard';
import { DeleteConfirmModal } from './DeleteConfirmModal';
import { LoadingSpinner } from '../common/LoadingSpinner';

interface DocumentListProps {
  documents: DocumentItem[];
  jobStatuses: Record<string, IngestionJobStatus>;
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
  onDeleteDocument: (doc: DocumentItem) => Promise<void>;
  onDownloadDocument: (doc: DocumentItem) => Promise<void>;
}

export const DocumentList: React.FC<DocumentListProps> = ({
  documents,
  jobStatuses,
  loading,
  error,
  onRefresh,
  onDeleteDocument,
  onDownloadDocument,
}) => {
  const [docToDelete, setDocToDelete] = useState<DocumentItem | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [downloadingDocId, setDownloadingDocId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const handleDeleteRequest = (doc: DocumentItem) => {
    setActionError(null);
    setDocToDelete(doc);
  };

  const handleConfirmDelete = async () => {
    if (!docToDelete) return;
    setIsDeleting(true);
    setActionError(null);
    try {
      await onDeleteDocument(docToDelete);
      setDocToDelete(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to delete document.';
      setActionError(msg);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleDownload = async (doc: DocumentItem) => {
    if (downloadingDocId) return; // Prevent duplicate clicks
    setDownloadingDocId(doc.id);
    setActionError(null);
    try {
      await onDownloadDocument(doc);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to download document.';
      setActionError(msg);
    } finally {
      setDownloadingDocId(null);
    }
  };

  return (
    <div className="document-list-container">
      <div className="document-list-header">
        <div className="list-header-left">
          <h3 className="section-title">My Documents</h3>
          <span className="doc-count-badge">
            {documents.length} {documents.length === 1 ? 'file' : 'files'}
          </span>
        </div>

        <button
          type="button"
          className="btn-refresh"
          onClick={onRefresh}
          disabled={loading}
          title="Refresh documents list"
        >
          <RefreshCw size={15} className={loading ? 'icon-spin' : ''} />
          <span>Refresh</span>
        </button>
      </div>

      {actionError && (
        <div className="alert-box alert-danger" style={{ marginBottom: 16 }}>
          <AlertCircle size={16} />
          <span>{actionError}</span>
        </div>
      )}

      {/* Loading state (initial) */}
      {loading && documents.length === 0 && (
        <div className="document-loading-state">
          <LoadingSpinner size={32} />
          <p>Loading your documents...</p>
        </div>
      )}

      {/* Error state */}
      {!loading && error && documents.length === 0 && (
        <div className="document-error-state">
          <AlertCircle size={36} color="var(--color-danger)" />
          <h4>Unable to load your documents</h4>
          <p>{error}</p>
          <button type="button" className="btn-secondary" onClick={onRefresh}>
            Retry
          </button>
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && documents.length === 0 && (
        <motion.div
          className="document-empty-state"
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.4 }}
        >
          <div className="empty-state-icon">
            <FileText size={40} />
          </div>
          <h4>No documents yet</h4>
          <p>
            Upload your first document above to start asking questions about your files.
            Supported formats: PDF, DOCX, XLSX, CSV, TXT.
          </p>
        </motion.div>
      )}

      {/* Document Items Grid */}
      {documents.length > 0 && (
        <div className="document-grid">
          {documents.map((doc) => {
            // Check if there is an active job matching this document
            const matchingJob = Object.values(jobStatuses).find(
              (job) => job.document_id === doc.id
            );

            return (
              <DocumentCard
                key={doc.id}
                document={doc}
                jobStatus={matchingJob}
                isDownloading={downloadingDocId === doc.id}
                onDownload={handleDownload}
                onDelete={handleDeleteRequest}
              />
            );
          })}
        </div>
      )}

      {/* Delete Confirmation Modal */}
      <DeleteConfirmModal
        isOpen={docToDelete !== null}
        filename={docToDelete?.filename || 'this document'}
        isDeleting={isDeleting}
        onConfirm={handleConfirmDelete}
        onCancel={() => {
          if (!isDeleting) setDocToDelete(null);
        }}
      />
    </div>
  );
};
