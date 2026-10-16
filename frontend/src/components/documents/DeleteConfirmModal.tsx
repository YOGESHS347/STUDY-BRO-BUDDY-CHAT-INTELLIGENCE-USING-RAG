import React, { useEffect } from 'react';
import { AlertTriangle } from 'lucide-react';
import { Button } from '../common/Button';

interface DeleteConfirmModalProps {
  isOpen: boolean;
  filename: string;
  isDeleting: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export const DeleteConfirmModal: React.FC<DeleteConfirmModalProps> = ({
  isOpen,
  filename,
  isDeleting,
  onConfirm,
  onCancel,
}) => {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isDeleting && isOpen) {
        onCancel();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, isDeleting, onCancel]);

  if (!isOpen) return null;

  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="delete-modal-title"
      onClick={(e) => {
        if (e.target === e.currentTarget && !isDeleting) {
          onCancel();
        }
      }}
    >
      <div className="modal-content">
        <div className="modal-header">
          <div className="modal-icon-warning">
            <AlertTriangle size={24} />
          </div>
          <div>
            <h3 id="delete-modal-title" className="modal-title">
              Delete Document?
            </h3>
            <p className="modal-desc">
              This will permanently remove <strong style={{ color: 'var(--color-text-main)' }}>{filename}</strong> and all of its indexed vector embeddings.
            </p>
          </div>
        </div>

        <div className="modal-actions">
          <button
            type="button"
            className="btn-secondary"
            onClick={onCancel}
            disabled={isDeleting}
          >
            Cancel
          </button>
          <Button
            type="button"
            variant="danger"
            onClick={onConfirm}
            isLoading={isDeleting}
            disabled={isDeleting}
            className="btn-danger"
          >
            {isDeleting ? 'Deleting...' : 'Delete Document'}
          </Button>
        </div>
      </div>
    </div>
  );
};
