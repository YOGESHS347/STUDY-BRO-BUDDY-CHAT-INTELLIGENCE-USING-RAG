export type DocumentStatus = 'uploaded' | 'processing' | 'completed' | 'failed' | string;
export type IngestionStatus = 'queued' | 'processing' | 'completed' | 'failed' | string;

export interface DocumentItem {
  id: string;
  user_id: string;
  filename: string;
  file_type?: string | null;
  file_size?: number | null;
  storage_path?: string | null;
  status: DocumentStatus;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface DocumentUploadResponse {
  document_id: string;
  job_id: string;
  filename: string;
  status: string;
}

export interface DocumentDeleteResponse {
  message: string;
  document_id: string;
}

export interface IngestionJobStatus {
  job_id: string;
  document_id: string;
  status: IngestionStatus;
  total_chunks: number;
  processed_chunks: number;
  error_message?: string | null;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface UploadQueueItem {
  id: string;
  file: File;
  status: 'validating' | 'uploading' | 'processing' | 'completed' | 'error';
  progress: number; // 0 - 100
  bytesUploaded: number;
  totalBytes: number;
  errorMessage?: string;
  documentId?: string;
  jobId?: string;
}
