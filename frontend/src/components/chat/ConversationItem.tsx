import React from 'react';
import { MessageSquare, Trash2 } from 'lucide-react';
import type { ConversationItem as ConversationItemType } from '../../types/chat';
import { formatRelativeTime } from '../../services/conversations';

interface ConversationItemProps {
  conversation: ConversationItemType;
  isActive: boolean;
  onSelect: (conv: ConversationItemType) => void;
  onDeleteRequest: (conv: ConversationItemType, e: React.MouseEvent) => void;
}

export const ConversationItem: React.FC<ConversationItemProps> = ({
  conversation,
  isActive,
  onSelect,
  onDeleteRequest,
}) => {
  const title = conversation.title || 'New Conversation';
  const timeStr = formatRelativeTime(conversation.updated_at || conversation.created_at);

  return (
    <div
      className={`conversation-item ${isActive ? 'active' : ''}`}
      onClick={() => onSelect(conversation)}
      role="button"
      tabIndex={0}
      aria-label={`Select conversation ${title}`}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          onSelect(conversation);
        }
      }}
      data-testid={`conv-item-${conversation.id}`}
    >
      <div className="conv-item-left">
        <MessageSquare size={16} className="conv-icon" />
        <div className="conv-item-text">
          <span className="conv-title" title={title}>
            {title}
          </span>
          {timeStr && <span className="conv-time">{timeStr}</span>}
        </div>
      </div>

      <button
        type="button"
        className="conv-delete-btn"
        onClick={(e) => {
          e.stopPropagation();
          onDeleteRequest(conversation, e);
        }}
        aria-label={`Delete conversation ${title}`}
        title="Delete conversation"
      >
        <Trash2 size={14} />
      </button>
    </div>
  );
};
