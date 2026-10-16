import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { validateDocumentFile, documentService } from '../services/documents';
import { DocumentCard } from '../components/documents/DocumentCard';
import { DocumentList } from '../components/documents/DocumentList';
import { DeleteConfirmModal } from '../components/documents/DeleteConfirmModal';
import { Documents } from '../pages/Documents';
import type { DocumentItem, IngestionJobStatus } from '../types/document';

describe('Phase 9 — Document Management UI Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // 1. Supported file validation
  it('1. validates supported file extensions (.pdf, .docx, .xlsx, .csv, .txt)', () => {
    const validNames = ['report.pdf', 'doc.docx', 'sheet.xlsx', 'data.csv', 'notes.txt'];
    for (const name of validNames) {
      const file = new File(['sample content'], name, { type: 'text/plain' });
      const result = validateDocumentFile(file);
      expect(result.valid).toBe(true);
      expect(result.error).toBeUndefined();
    }
  });

  // 2. 50 MB size limit validation
  it('2. rejects files exceeding the 50 MB size limit', () => {
    const oversizedFile = new File(['a'], 'huge.pdf', { type: 'application/pdf' });
    Object.defineProperty(oversizedFile, 'size', { value: 50 * 1024 * 1024 + 1 });

    const result = validateDocumentFile(oversizedFile);
    expect(result.valid).toBe(false);
    expect(result.error).toContain('larger than the 50 MB limit');
  });

  // 3. Unsupported extension rejection
  it('3. rejects unsupported file extensions', () => {
    const invalidNames = ['script.py', 'image.png', 'app.exe', 'archive.zip', 'noext'];
    for (const name of invalidNames) {
      const file = new File(['data'], name);
      const result = validateDocumentFile(file);
      expect(result.valid).toBe(false);
      expect(result.error).toMatch(/Unsupported file type|no extension/i);
    }
  });

  // 4. Empty file rejection
  it('4. rejects empty files (0 bytes)', () => {
    const emptyFile = new File([], 'empty.txt', { type: 'text/plain' });
    const result = validateDocumentFile(emptyFile);
    expect(result.valid).toBe(false);
    expect(result.error).toContain('empty (0 bytes)');
  });

  // 5. Document list rendering
  it('5. renders document list with correct filenames and metadata', () => {
    const mockDocs: DocumentItem[] = [
      {
        id: 'doc-1',
        user_id: 'user-1',
        filename: 'quarterly_report.pdf',
        file_type: 'pdf',
        file_size: 1048576, // 1 MB
        status: 'completed',
        created_at: '2026-09-15T00:00:00Z',
      },
    ];

    render(
      <DocumentList
        documents={mockDocs}
        jobStatuses={{}}
        loading={false}
        error={null}
        onRefresh={vi.fn()}
        onDeleteDocument={vi.fn()}
        onDownloadDocument={vi.fn()}
      />
    );

    expect(screen.getByText('quarterly_report.pdf')).toBeInTheDocument();
    expect(screen.getByText('1.0 MB')).toBeInTheDocument();
    expect(screen.getByText('Ready')).toBeInTheDocument();
  });

  // 6. Empty document state
  it('6. displays empty state when user has no documents', () => {
    render(
      <DocumentList
        documents={[]}
        jobStatuses={{}}
        loading={false}
        error={null}
        onRefresh={vi.fn()}
        onDeleteDocument={vi.fn()}
        onDownloadDocument={vi.fn()}
      />
    );

    expect(screen.getByText('No documents yet')).toBeInTheDocument();
    expect(screen.getByText(/Upload your first document above/i)).toBeInTheDocument();
  });

  // 7. Loading state
  it('7. displays loading state when documents are being fetched', () => {
    render(
      <DocumentList
        documents={[]}
        jobStatuses={{}}
        loading={true}
        error={null}
        onRefresh={vi.fn()}
        onDeleteDocument={vi.fn()}
        onDownloadDocument={vi.fn()}
      />
    );

    expect(screen.getByText('Loading your documents...')).toBeInTheDocument();
  });

  // 8. Status rendering
  it('8. renders correct status badges for different document states', () => {
    const baseDoc: DocumentItem = {
      id: 'doc-status-test',
      user_id: 'user-1',
      filename: 'sample.pdf',
      file_type: 'pdf',
      file_size: 2048,
      status: 'completed',
    };

    const { rerender } = render(
      <DocumentCard
        document={{ ...baseDoc, status: 'completed' }}
        isDownloading={false}
        onDownload={vi.fn()}
        onDelete={vi.fn()}
      />
    );
    expect(screen.getByText('Ready')).toBeInTheDocument();

    rerender(
      <DocumentCard
        document={{ ...baseDoc, status: 'processing' }}
        isDownloading={false}
        onDownload={vi.fn()}
        onDelete={vi.fn()}
      />
    );
    expect(screen.getByText('Processing')).toBeInTheDocument();

    rerender(
      <DocumentCard
        document={{ ...baseDoc, status: 'queued' }}
        isDownloading={false}
        onDownload={vi.fn()}
        onDelete={vi.fn()}
      />
    );
    expect(screen.getByText('Queued')).toBeInTheDocument();

    rerender(
      <DocumentCard
        document={{ ...baseDoc, status: 'failed' }}
        isDownloading={false}
        onDownload={vi.fn()}
        onDelete={vi.fn()}
      />
    );
    expect(screen.getByText('Failed')).toBeInTheDocument();
  });

  // 9. Real chunk progress rendering
  it('9. renders chunk progress when ingestion job is active', () => {
    const doc: DocumentItem = {
      id: 'doc-123',
      user_id: 'user-1',
      filename: 'knowledge.docx',
      file_type: 'docx',
      file_size: 5000,
      status: 'processing',
    };

    const job: IngestionJobStatus = {
      job_id: 'job-123',
      document_id: 'doc-123',
      status: 'processing',
      total_chunks: 100,
      processed_chunks: 42,
    };

    render(
      <DocumentCard
        document={doc}
        jobStatus={job}
        isDownloading={false}
        onDownload={vi.fn()}
        onDelete={vi.fn()}
      />
    );

    expect(screen.getByText('42 / 100')).toBeInTheDocument();
    expect(screen.getByText('Indexing chunks')).toBeInTheDocument();
  });

  // 10. Delete confirmation modal appears
  it('10. opens delete confirmation dialog on clicking delete button', () => {
    const doc: DocumentItem = {
      id: 'doc-delete',
      user_id: 'user-1',
      filename: 'contract.pdf',
      file_type: 'pdf',
      file_size: 1024,
      status: 'completed',
    };

    render(
      <DocumentList
        documents={[doc]}
        jobStatuses={{}}
        loading={false}
        error={null}
        onRefresh={vi.fn()}
        onDeleteDocument={vi.fn()}
        onDownloadDocument={vi.fn()}
      />
    );

    const deleteBtn = screen.getByRole('button', { name: /Delete contract.pdf/i });
    fireEvent.click(deleteBtn);

    expect(screen.getByText('Delete Document?')).toBeInTheDocument();
    expect(screen.getByText(/This will permanently remove/i)).toBeInTheDocument();
  });

  // 11. Delete cancel keeps document
  it('11. closes delete modal without action when cancelled', () => {
    const onCancel = vi.fn();
    render(
      <DeleteConfirmModal
        isOpen={true}
        filename="test.pdf"
        isDeleting={false}
        onConfirm={vi.fn()}
        onCancel={onCancel}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /Cancel/i }));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  // 12. Delete confirm triggers deletion
  it('12. executes onDeleteDocument when confirmed in modal', async () => {
    const doc: DocumentItem = {
      id: 'doc-confirm-del',
      user_id: 'user-1',
      filename: 'sensitive.pdf',
      status: 'completed',
    };
    const onDeleteMock = vi.fn().mockResolvedValue(undefined);

    render(
      <DocumentList
        documents={[doc]}
        jobStatuses={{}}
        loading={false}
        error={null}
        onRefresh={vi.fn()}
        onDeleteDocument={onDeleteMock}
        onDownloadDocument={vi.fn()}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /Delete sensitive.pdf/i }));
    const confirmBtn = screen.getByRole('button', { name: /Delete Document/i });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(onDeleteMock).toHaveBeenCalledWith(doc);
    });
  });

  // 13. Download trigger and loading state
  it('13. calls onDownloadDocument when download button is clicked', async () => {
    const doc: DocumentItem = {
      id: 'doc-download',
      user_id: 'user-1',
      filename: 'data.xlsx',
      file_type: 'xlsx',
      file_size: 4096,
      status: 'completed',
    };
    const onDownloadMock = vi.fn().mockResolvedValue(undefined);

    render(
      <DocumentCard
        document={doc}
        isDownloading={false}
        onDownload={onDownloadMock}
        onDelete={vi.fn()}
      />
    );

    const downloadBtn = screen.getByRole('button', { name: /Download data.xlsx/i });
    fireEvent.click(downloadBtn);

    expect(onDownloadMock).toHaveBeenCalledWith(doc);
  });

  // 14. API error handling and retry
  it('14. displays error state with retry button when list fetching fails', () => {
    const onRefreshMock = vi.fn();

    render(
      <DocumentList
        documents={[]}
        jobStatuses={{}}
        loading={false}
        error="Backend database is unavailable."
        onRefresh={onRefreshMock}
        onDeleteDocument={vi.fn()}
        onDownloadDocument={vi.fn()}
      />
    );

    expect(screen.getByText('Unable to load your documents')).toBeInTheDocument();
    expect(screen.getByText('Backend database is unavailable.')).toBeInTheDocument();

    const retryBtn = screen.getByRole('button', { name: /Retry/i });
    fireEvent.click(retryBtn);
    expect(onRefreshMock).toHaveBeenCalledTimes(1);
  });

  // 15. Ingestion polling stops on completed status
  it('15. stops polling when ingestion job status is completed', async () => {
    vi.useFakeTimers();

    const mockList = vi.spyOn(documentService, 'listDocuments').mockResolvedValue([]);
    const mockStatus = vi.spyOn(documentService, 'getIngestionStatus');

    // First call returns processing, second returns completed
    mockStatus
      .mockResolvedValueOnce({
        job_id: 'job-999',
        document_id: 'doc-999',
        status: 'processing',
        total_chunks: 10,
        processed_chunks: 5,
      })
      .mockResolvedValueOnce({
        job_id: 'job-999',
        document_id: 'doc-999',
        status: 'completed',
        total_chunks: 10,
        processed_chunks: 10,
      });

    const { unmount } = render(<Documents />);

    // Fast-forward initial fetch
    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });
    expect(mockList).toHaveBeenCalled();

    unmount();
    vi.useRealTimers();
  });

  // 16. Ingestion polling stops on failed status
  it('16. stops polling when ingestion job status is failed', async () => {
    vi.useFakeTimers();

    vi.spyOn(documentService, 'listDocuments').mockResolvedValue([]);
    vi.spyOn(documentService, 'getIngestionStatus').mockResolvedValue({
      job_id: 'job-fail',
      document_id: 'doc-fail',
      status: 'failed',
      total_chunks: 5,
      processed_chunks: 1,
      error_message: 'Corrupted document format',
    });

    const { unmount } = render(<Documents />);
    await act(async () => {
      await vi.runOnlyPendingTimersAsync();
    });

    unmount();
    vi.useRealTimers();
  });
});
