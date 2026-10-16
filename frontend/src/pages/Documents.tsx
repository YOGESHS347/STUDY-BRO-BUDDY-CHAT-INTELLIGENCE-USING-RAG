import React, { useEffect, useRef, useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { FileText, Terminal } from 'lucide-react';
import { documentService } from '../services/documents';
import type {
  DocumentItem,
  DocumentUploadResponse,
  IngestionJobStatus,
} from '../types/document';
import { DocumentUploader } from '../components/documents/DocumentUploader';
import { DocumentList } from '../components/documents/DocumentList';
import { PageTransition } from '../components/common/PageTransition';
import { HudCornerBrackets } from '../components/common/HudCornerBrackets';

export const Documents: React.FC = () => {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [jobStatuses, setJobStatuses] = useState<Record<string, IngestionJobStatus>>({});

  // Track active polling intervals by job_id to prevent duplicates and ensure clean unmount
  const pollingTimers = useRef<Map<string, ReturnType<typeof setInterval>>>(new Map());

  // Stop polling for a specific job
  const stopJobPolling = useCallback((jobId: string) => {
    const timer = pollingTimers.current.get(jobId);
    if (timer) {
      clearInterval(timer);
      pollingTimers.current.delete(jobId);
    }
  }, []);

  // Fetch document list from backend
  const fetchDocuments = useCallback(async (isInitial = false) => {
    if (isInitial) setLoading(true);
    setError(null);
    try {
      const data = await documentService.listDocuments();
      setDocuments(data);
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : 'Failed to load documents. Please check backend service.';
      setError(msg);
    } finally {
      if (isInitial) setLoading(false);
    }
  }, []);

  // Start polling an ingestion job until completed or failed
  const startJobPolling = useCallback(
    (jobId: string) => {
      if (pollingTimers.current.has(jobId)) {
        return;
      }

      const poll = async () => {
        try {
          const status = await documentService.getIngestionStatus(jobId);
          setJobStatuses((prev) => ({ ...prev, [jobId]: status }));

          if (status.status === 'completed' || status.status === 'failed') {
            stopJobPolling(jobId);
            fetchDocuments(false);
          }
        } catch {
          // Retry next tick
        }
      };

      poll();
      const timer = setInterval(poll, 2000);
      pollingTimers.current.set(jobId, timer);
    },
    [stopJobPolling, fetchDocuments]
  );

  useEffect(() => {
    fetchDocuments(true);

    const activeTimers = pollingTimers.current;
    return () => {
      activeTimers.forEach((timer) => clearInterval(timer));
      activeTimers.clear();
    };
  }, [fetchDocuments]);

  const handleUploadSuccess = (response: DocumentUploadResponse) => {
    setDocuments((prev) => {
      if (prev.some((d) => d.id === response.document_id)) return prev;
      const optimisticDoc: DocumentItem = {
        id: response.document_id,
        user_id: '',
        filename: response.filename,
        status: response.status,
        created_at: new Date().toISOString(),
      };
      return [optimisticDoc, ...prev];
    });

    if (response.job_id) {
      startJobPolling(response.job_id);
    }

    fetchDocuments(false);
  };

  const handleDeleteDocument = async (doc: DocumentItem) => {
    await documentService.deleteDocument(doc.id);

    Object.entries(jobStatuses).forEach(([jobId, job]) => {
      if (job.document_id === doc.id) {
        stopJobPolling(jobId);
      }
    });

    setDocuments((prev) => prev.filter((d) => d.id !== doc.id));
  };

  const handleDownloadDocument = async (doc: DocumentItem) => {
    await documentService.downloadDocument(doc.id, doc.filename);
  };

  const completedCount = documents.filter((d) => d.status === 'completed').length;

  return (
    <PageTransition>
      <div className="documents-page">
        {/* Editorial Page Header */}
        <motion.div
          className="documents-page-header"
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
        >
          <div className="hero-eyebrow" style={{ padding: '2px 8px', fontSize: '0.62rem', marginBottom: 8 }}>
            <Terminal size={12} color="var(--color-primary)" />
            <span>KNOWLEDGE REPOSITORY // ARCHIVE INVENTORY</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 20, flexWrap: 'wrap' }}>
            <div>
              <h1 className="page-heading">Documents</h1>
              <p className="page-subheading">
                Upload and manage knowledge files indexed for AI-assisted semantic search, cross-encoder reranking, and grounded RAG.
              </p>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 4 }}>
              <span className="status-badge neutral" title="Total Indexed Documents">
                <FileText size={12} />
                <span>{documents.length} {documents.length === 1 ? 'FILE' : 'FILES'}</span>
              </span>
              <span className="status-badge connected" title="Ready for RAG Q&A">
                <span className="status-dot" />
                <span>{completedCount} READY</span>
              </span>
            </div>
          </div>
        </motion.div>

        {/* Upload Dropzone Section */}
        <motion.div
          className="card hud-bracket-container"
          style={{ marginBottom: 28 }}
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, delay: 0.08, ease: [0.16, 1, 0.3, 1] }}
        >
          <HudCornerBrackets size={10} />
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
            <h3 className="section-title">
              Upload Documents
            </h3>
            <span style={{ fontSize: '0.72rem', color: 'var(--color-primary)', fontFamily: 'var(--font-mono)', letterSpacing: '0.08em' }}>
              VECTOR PIPELINE // AUTO-INDEX
            </span>
          </div>
          <DocumentUploader onUploadSuccess={handleUploadSuccess} />
        </motion.div>

        {/* Document Inventory Section */}
        <DocumentList
          documents={documents}
          jobStatuses={jobStatuses}
          loading={loading}
          error={error}
          onRefresh={() => fetchDocuments(true)}
          onDeleteDocument={handleDeleteDocument}
          onDownloadDocument={handleDownloadDocument}
        />
      </div>
    </PageTransition>
  );
};

export default Documents;
