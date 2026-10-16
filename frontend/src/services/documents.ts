import { api } from './api';
import type {
  DocumentItem,
  DocumentUploadResponse,
  IngestionJobStatus,
  DocumentDeleteResponse,
} from '../types/document';

export const SUPPORTED_EXTENSIONS = ['.pdf', '.docx', '.xlsx', '.csv', '.txt'] as const;
export const MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024; // 50 MB

export interface FileValidationResult {
  valid: boolean;
  error?: string;
}

export function validateDocumentFile(file?: File | null): FileValidationResult {
  if (!file) {
    return { valid: false, error: 'Please select a file to upload.' };
  }

  const name = file.name || '';
  const dotIdx = name.lastIndexOf('.');
  if (dotIdx === -1) {
    return {
      valid: false,
      error: 'File has no extension. Supported types: PDF, DOCX, XLSX, CSV, TXT.',
    };
  }

  const extension = name.slice(dotIdx).toLowerCase();
  const isSupported = (SUPPORTED_EXTENSIONS as readonly string[]).includes(extension);

  if (!isSupported) {
    return {
      valid: false,
      error: `Unsupported file type '${extension}'. Supported formats: PDF, DOCX, XLSX, CSV, TXT.`,
    };
  }

  if (file.size === 0) {
    return { valid: false, error: 'File is empty (0 bytes). Empty files cannot be ingested.' };
  }

  if (file.size > MAX_FILE_SIZE_BYTES) {
    return {
      valid: false,
      error: `File is larger than the 50 MB limit (${(file.size / (1024 * 1024)).toFixed(1)} MB).`,
    };
  }

  return { valid: true };
}

export function formatFileSize(bytes?: number | null): string {
  if (bytes === undefined || bytes === null || isNaN(bytes) || bytes < 0) {
    return '0 B';
  }
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatTimestamp(isoString?: string | null): string {
  if (!isoString) return '—';
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return '—';
    return d.toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return '—';
  }
}

class DocumentService {
  /**
   * Fetches all documents belonging to the authenticated user.
   */
  async listDocuments(skip = 0, limit = 100): Promise<DocumentItem[]> {
    return api.get<DocumentItem[]>(`/api/v1/documents?skip=${skip}&limit=${limit}`);
  }

  /**
   * Fetches single document metadata.
   */
  async getDocument(documentId: string): Promise<DocumentItem> {
    return api.get<DocumentItem>(`/api/v1/documents/${documentId}`);
  }

  /**
   * Uploads a document with real upload byte tracking.
   */
  async uploadDocument(
    file: File,
    onProgress?: (percent: number, loaded: number, total: number) => void
  ): Promise<DocumentUploadResponse> {
    const validation = validateDocumentFile(file);
    if (!validation.valid) {
      throw new Error(validation.error);
    }
    return api.uploadWithProgress<DocumentUploadResponse>(
      '/api/v1/documents/upload',
      file,
      onProgress
    );
  }

  /**
   * Retrieves status and chunk progress for an active ingestion job.
   */
  async getIngestionStatus(jobId: string): Promise<IngestionJobStatus> {
    return api.get<IngestionJobStatus>(`/api/v1/ingestion/${jobId}`);
  }

  /**
   * Securely streams and downloads a document using authenticated GET.
   * Prompts user via browser download dialog with zero secret or URL leakage.
   */
  async downloadDocument(documentId: string, fallbackFilename = 'document'): Promise<void> {
    const { blob, filename } = await api.downloadBlob(`/api/v1/documents/${documentId}/download`);
    const finalFilename = filename || fallbackFilename;

    const downloadUrl = window.URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = downloadUrl;
    anchor.download = finalFilename;
    document.body.appendChild(anchor);
    anchor.click();
    document.body.removeChild(anchor);

    // Revoke object URL to prevent memory leaks
    setTimeout(() => {
      window.URL.revokeObjectURL(downloadUrl);
    }, 1000);
  }

  /**
   * Deletes a document and its associated vectors from the backend.
   */
  async deleteDocument(documentId: string): Promise<DocumentDeleteResponse> {
    return api.delete<DocumentDeleteResponse>(`/api/v1/documents/${documentId}`);
  }
}

export const documentService = new DocumentService();
