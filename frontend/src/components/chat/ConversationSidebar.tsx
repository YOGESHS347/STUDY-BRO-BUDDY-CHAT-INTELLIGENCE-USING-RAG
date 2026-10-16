import React, { useState } from 'react';
import { Plus, Search, MessageSquare, X, Loader2 } from 'lucide-react';
import type { ConversationItem as ConversationItemType } from '../../types/chat';
import { ConversationItem } from './ConversationItem';
import { DeleteConversationModal } from './DeleteConversationModal';
import { LoadingSpinner } from '../common/LoadingSpinner';

interface ConversationSidebarProps {
  conversations: ConversationItemType[];
  selectedId: string | null;
  loading: boolean;
  isCreating: boolean;
  isOpenMobile: boolean;
  onSelect: (conv: ConversationItemType) => void;
  onNewChat: () => void;
  onDeleteConversation: (conv: ConversationItemType) => Promise<void>;
  onCloseMobile: () => void;
}

export const ConversationSidebar: React.FC<ConversationSidebarProps> = ({
  conversations,
  selectedId,
  loading,
  isCreating,
  isOpenMobile,
  onSelect,
  onNewChat,
  onDeleteConversation,
  onCloseMobile,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [convToDelete, setConvToDelete] = useState<ConversationItemType | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const filteredConversations = conversations.filter((c) =>
    (c.title || 'New Conversation').toLowerCase().includes(searchQuery.toLowerCase().trim())
  );

  const handleDeleteRequest = (conv: ConversationItemType, e: React.MouseEvent) => {
    e.stopPropagation();
    setConvToDelete(conv);
  };

  const handleConfirmDelete = async () => {
    if (!convToDelete) return;
    setIsDeleting(true);
    try {
      await onDeleteConversation(convToDelete);
      setConvToDelete(null);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <>
      <aside className={`chat-sidebar ${isOpenMobile ? 'mobile-open' : ''}`}>
        <div className="chat-sidebar-header">
          <button
            type="button"
            className="btn-new-chat"
            onClick={onNewChat}
            disabled={isCreating}
            title="Start a new conversation"
          >
            {isCreating ? (
              <Loader2 size={16} className="icon-spin" />
            ) : (
              <Plus size={16} />
            )}
            <span>New Chat</span>
          </button>

          <button
            type="button"
            className="mobile-close-btn"
            onClick={onCloseMobile}
            aria-label="Close conversation list"
          >
            <X size={18} />
          </button>
        </div>

        {/* Search bar */}
        {conversations.length > 1 && (
          <div className="chat-sidebar-search">
            <Search size={14} className="search-icon" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search chats..."
              className="chat-search-input"
            />
          </div>
        )}

        {/* Conversation list */}
        <div className="chat-sidebar-list">
          {loading && conversations.length === 0 ? (
            <div className="sidebar-loading-state">
              <LoadingSpinner size={24} />
              <span>Loading chats...</span>
            </div>
          ) : filteredConversations.length === 0 ? (
            <div className="sidebar-empty-state">
              <MessageSquare size={28} className="empty-icon" />
              <p>{searchQuery ? 'No matching conversations' : 'No conversations yet'}</p>
              {!searchQuery && (
                <button
                  type="button"
                  className="btn-link-sm"
                  onClick={onNewChat}
                  disabled={isCreating}
                >
                  Start your first chat
                </button>
              )}
            </div>
          ) : (
            filteredConversations.map((conv) => (
              <ConversationItem
                key={conv.id}
                conversation={conv}
                isActive={conv.id === selectedId}
                onSelect={(c) => {
                  onSelect(c);
                  onCloseMobile();
                }}
                onDeleteRequest={handleDeleteRequest}
              />
            ))
          )}
        </div>
      </aside>

      {/* Delete Conversation Dialog */}
      <DeleteConversationModal
        isOpen={convToDelete !== null}
        title={convToDelete?.title || 'this conversation'}
        isDeleting={isDeleting}
        onConfirm={handleConfirmDelete}
        onCancel={() => {
          if (!isDeleting) setConvToDelete(null);
        }}
      />
    </>
  );
};
