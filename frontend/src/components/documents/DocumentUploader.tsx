import React, { useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { UploadCloud, FileCheck, AlertCircle, X, Loader2, FileText } from 'lucide-react';
import {
  documentService,
  validateDocumentFile,
  formatFileSize,
} from '../../services/documents';
import type { DocumentUploadResponse, UploadQueueItem } from '../../types/document';
import { HudCornerBrackets } from '../common/HudCornerBrackets';

interface DocumentUploaderProps {
  onUploadSuccess: (response: DocumentUploadResponse) => void;
  disabled?: boolean;
}

export const DocumentUploader: React.FC<DocumentUploaderProps> = ({
  onUploadSuccess,
  disabled = false,
}) => {
  const [isDragActive, setIsDragActive] = useState(false);
  const [queue, setQueue] = useState<UploadQueueItem[]>([]);
  const [generalError, setGeneralError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFiles = async (files: FileList | File[]) => {
    setGeneralError(null);
    const fileList = Array.from(files);

    if (fileList.length === 0) return;

    // Validate client-side first
    const newItems: UploadQueueItem[] = fileList.map((file) => {
      const val = validateDocumentFile(file);
      return {
        id: `${file.name}-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
        file,
        status: val.valid ? 'validating' : 'error',
        progress: 0,
        bytesUploaded: 0,
        totalBytes: file.size,
        errorMessage: val.error,
      };
    });

    setQueue((prev) => [...prev, ...newItems]);

    // Process valid files sequentially
    for (const item of newItems) {
      if (item.status === 'error') continue;

      // Update status to uploading
      setQueue((prev) =>
        prev.map((q) => (q.id === item.id ? { ...q, status: 'uploading' } : q))
      );

      try {
        const response = await documentService.uploadDocument(
          item.file,
          (percent, loaded, total) => {
            setQueue((prev) =>
              prev.map((q) =>
                q.id === item.id
                  ? {
                      ...q,
                      progress: percent,
                      bytesUploaded: loaded,
                      totalBytes: total,
                    }
                  : q
              )
            );
          }
        );

        // Upload phase completed, now backend background ingestion
        setQueue((prev) =>
          prev.map((q) =>
            q.id === item.id
              ? {
                  ...q,
                  status: 'completed',
                  progress: 100,
                  documentId: response.document_id,
                  jobId: response.job_id,
                }
              : q
          )
        );

        // Notify parent to update document list and trigger ingestion polling
        onUploadSuccess(response);
      } catch (err: unknown) {
        const message =
          err instanceof Error
            ? err.message
            : 'Upload failed. Please check backend connection.';

        setQueue((prev) =>
          prev.map((q) =>
            q.id === item.id
              ? {
                  ...q,
                  status: 'error',
                  errorMessage: message,
                }
              : q
          )
        );
      }
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!disabled) setIsDragActive(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);
    if (disabled) return;

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFiles(e.dataTransfer.files);
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFiles(e.target.files);
      e.target.value = '';
    }
  };

  const removeItem = (id: string) => {
    setQueue((prev) => prev.filter((item) => item.id !== id));
  };

  return (
    <div className="upload-container">
      {/* Dropzone Area */}
      <motion.div
        className={`upload-dropzone hud-bracket-container ${isDragActive ? 'drag-active' : ''} ${
          disabled ? 'disabled' : ''
        }`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => {
          if (!disabled && fileInputRef.current) {
            fileInputRef.current.click();
          }
        }}
        whileHover={disabled ? undefined : { scale: 1.002 }}
        whileTap={disabled ? undefined : { scale: 0.998 }}
        role="button"
        tabIndex={0}
        aria-label="Upload document dropzone"
        onKeyDown={(e) => {
          if ((e.key === 'Enter' || e.key === ' ') && !disabled) {
            fileInputRef.current?.click();
          }
        }}
      >
        <HudCornerBrackets size={8} />

        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.docx,.xlsx,.csv,.txt"
          onChange={handleInputChange}
          style={{ display: 'none' }}
          disabled={disabled}
        />

        <div className="dropzone-icon">
          <UploadCloud size={30} />
        </div>

        <div className="dropzone-content">
          <p className="dropzone-title">
            <span className="dropzone-highlight">Drop documents here</span> or click to browse
          </p>
          <p className="dropzone-formats">
            Supported formats: <strong>PDF, DOCX, XLSX, CSV, TXT</strong>
          </p>
          <p className="dropzone-limit">Maximum file size: <strong>50 MB</strong> // Automated Vectorization</p>
        </div>
      </motion.div>

      {generalError && (
        <div className="alert-box alert-danger" style={{ marginTop: 14 }}>
          <AlertCircle size={18} />
          <span>{generalError}</span>
        </div>
      )}

      {/* Upload Queue / Progress Display */}
      {queue.length > 0 && (
        <div className="upload-queue">
          <div className="upload-queue-header">
            <span className="queue-title">Ingestion Queue ({queue.length})</span>
            <button
              type="button"
              className="queue-clear-btn"
              onClick={() => setQueue([])}
            >
              Clear Completed
            </button>
          </div>

          <div className="upload-queue-list">
            <AnimatePresence>
              {queue.map((item) => (
                <motion.div
                  key={item.id}
                  className={`queue-item hud-bracket-container status-${item.status}`}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, height: 0, overflow: 'hidden' }}
                  transition={{ duration: 0.25 }}
                >
                  <HudCornerBrackets size={5} />
                  <div className="queue-item-header">
                    <div className="queue-item-info">
                      <FileText size={14} className="text-cyan-400" />
                      <span className="queue-filename" title={item.file.name}>
                        {item.file.name}
                      </span>
                      <span className="queue-filesize">
                        ({formatFileSize(item.totalBytes)})
                      </span>
                    </div>

                    <div className="queue-item-status">
                      {item.status === 'uploading' && (
                        <span className="status-text uploading">
                          <Loader2 size={12} className="icon-spin" />
                          Uploading {item.progress}%
                        </span>
                      )}
                      {item.status === 'completed' && (
                        <span className="status-text success">
                          <FileCheck size={13} />
                          Uploaded
                        </span>
                      )}
                      {item.status === 'error' && (
                        <span className="status-text error">
                          <AlertCircle size={13} />
                          Failed
                        </span>
                      )}
                      <button
                        type="button"
                        className="queue-remove-btn"
                        onClick={(e) => {
                          e.stopPropagation();
                          removeItem(item.id);
                        }}
                        aria-label="Remove item"
                      >
                        <X size={13} />
                      </button>
                    </div>
                  </div>

                  {/* Progress bar during upload */}
                  {item.status === 'uploading' && (
                    <div className="progress-track">
                      <div
                        className="progress-fill"
                        style={{ width: `${item.progress}%` }}
                      />
                    </div>
                  )}

                  {/* Error message if validation or upload failed */}
                  {item.status === 'error' && item.errorMessage && (
                    <div className="queue-error-text">
                      {item.errorMessage}
                    </div>
                  )}
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        </div>
      )}
    </div>
  );
};
