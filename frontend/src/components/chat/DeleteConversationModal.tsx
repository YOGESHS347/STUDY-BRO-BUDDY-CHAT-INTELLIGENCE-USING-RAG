import React, { useEffect } from 'react';
import { AlertTriangle } from 'lucide-react';
import { Button } from '../common/Button';

interface DeleteConversationModalProps {
  isOpen: boolean;
  title: string;
  isDeleting: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export const DeleteConversationModal: React.FC<DeleteConversationModalProps> = ({
  isOpen,
  title,
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
      aria-labelledby="delete-conv-title"
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
            <h3 id="delete-conv-title" className="modal-title">
              Delete Conversation?
            </h3>
            <p className="modal-desc">
              This will permanently delete <strong style={{ color: 'var(--color-text-main)' }}>{title}</strong> and all of its messages. This action cannot be undone.
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
            {isDeleting ? 'Deleting...' : 'Delete Chat'}
          </Button>
        </div>
      </div>
    </div>
  );
};
