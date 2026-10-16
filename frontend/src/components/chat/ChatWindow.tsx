import React, { useRef, useEffect } from 'react';
import { Menu, AlertCircle, Loader2, Cpu } from 'lucide-react';
import type { ConversationItem, MessageItem } from '../../types/chat';
import { MessageBubble } from './MessageBubble';
import { ChatInput } from './ChatInput';
import { EmptyChat } from './EmptyChat';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { HudCornerBrackets } from '../common/HudCornerBrackets';

interface ChatWindowProps {
  activeConversation: ConversationItem | null;
  messages: MessageItem[];
  loadingMessages: boolean;
  isSending: boolean;
  error: string | null;
  onSend: (message: string) => void;
  onToggleMobileSidebar: () => void;
  onRetryMessage?: (msg: MessageItem) => void;
}

export const ChatWindow: React.FC<ChatWindowProps> = ({
  activeConversation,
  messages,
  loadingMessages,
  isSending,
  error,
  onSend,
  onToggleMobileSidebar,
  onRetryMessage,
}) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom on new messages or when sending starts
  const scrollToBottom = (smooth = true) => {
    messagesEndRef.current?.scrollIntoView({
      behavior: smooth ? 'smooth' : 'auto',
    });
  };

  useEffect(() => {
    scrollToBottom(true);
  }, [messages, isSending]);

  const conversationTitle = activeConversation?.title || 'Research Console';

  return (
    <div className="chat-window">
      {/* Console Header with Precision Telemetry */}
      <div className="chat-window-header">
        <div className="header-title-group">
          <button
            type="button"
            className="mobile-sidebar-toggle"
            onClick={onToggleMobileSidebar}
            aria-label="Toggle conversation history"
          >
            <Menu size={18} />
          </button>
          <div>
            <h2 className="active-conv-title" title={conversationTitle}>
              {conversationTitle}
            </h2>
            <div className="active-conv-subtitle">
              <span className="status-dot" style={{ backgroundColor: 'var(--color-primary)' }} />
              <span>RETRIEVAL: DENSE + RERANK // TENANT ISOLATED</span>
            </div>
          </div>
        </div>

        {/* Right Console Readout */}
        <div className="desktop-only" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.68rem', color: 'var(--color-text-dim)', letterSpacing: '0.08em' }}>
            LOCAL QWEN ENGINE
          </span>
        </div>
      </div>

      {/* Message Viewport */}
      <div className="chat-messages-viewport">
        {error && (
          <div className="chat-error-banner">
            <AlertCircle size={15} />
            <span>{error}</span>
          </div>
        )}

        {loadingMessages && messages.length === 0 ? (
          <div className="chat-loading-state">
            <LoadingSpinner size={28} />
            <p>SYNCING KNOWLEDGE THREAD...</p>
          </div>
        ) : !loadingMessages && messages.length === 0 ? (
          <EmptyChat onSelectPrompt={(prompt) => onSend(prompt)} />
        ) : (
          <div className="messages-stream">
            {messages.map((msg) => (
              <MessageBubble
                key={msg.id}
                message={msg}
                onRetry={onRetryMessage ? () => onRetryMessage(msg) : undefined}
              />
            ))}

            {/* In-flight thinking state */}
            {isSending && (
              <div className="message-row assistant-row">
                <div className="message-avatar">
                  <div className="avatar assistant-avatar-icon">
                    <Cpu size={15} />
                  </div>
                </div>
                <div className="message-content-wrapper">
                  <div className="message-header-info">
                    <span className="sender-name">Document Intelligence</span>
                    <span className="message-time">IN-FLIGHT</span>
                  </div>
                  <div className="message-bubble bubble-assistant thinking-bubble hud-bracket-container">
                    <HudCornerBrackets size={6} />
                    <Loader2 size={15} className="icon-spin" color="var(--color-primary)" />
                    <span>Searching documents & generating answer...</span>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Chat Input Dock */}
      <div className="chat-input-dock">
        <ChatInput
          onSend={onSend}
          disabled={!activeConversation}
          isSending={isSending}
        />
      </div>
    </div>
  );
};
