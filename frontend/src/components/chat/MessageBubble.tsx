import React, { useState } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { Bot, User, AlertTriangle, Copy, Check } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { MessageItem } from '../../types/chat';
import { SourceList } from './SourceList';
import { CodeBlock } from './CodeBlock';
import { HudCornerBrackets } from '../common/HudCornerBrackets';

interface MessageBubbleProps {
  message: MessageItem;
  onRetry?: () => void;
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({ message, onRetry }) => {
  const [copiedResponse, setCopiedResponse] = useState(false);
  const shouldReduceMotion = useReducedMotion();
  const isUser = message.role === 'user';
  const isMissingContext =
    !isUser &&
    message.content.toLowerCase().includes(
      'the provided documents do not contain enough information to answer this question'
    );

  const handleCopyResponse = async () => {
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(message.content);
      } else {
        const textarea = document.createElement('textarea');
        textarea.value = message.content;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
      }
      setCopiedResponse(true);
      setTimeout(() => setCopiedResponse(false), 2000);
    } catch {
      // ignore
    }
  };

  const reportId = message.id.replace('temp-', '').slice(0, 8).toUpperCase();

  return (
    <motion.div
      className={`message-row ${isUser ? 'user-row' : 'assistant-row'} ${
        message.isError ? 'message-error-row' : ''
      }`}
      data-testid={`message-${message.id}`}
      initial={shouldReduceMotion ? false : { opacity: 0, y: 12 }}
      animate={shouldReduceMotion ? false : { opacity: 1, y: 0 }}
      transition={{
        duration: 0.35,
        ease: [0.16, 1, 0.3, 1],
      }}
    >
      <div className="message-avatar">
        {isUser ? (
          <div className="avatar user-avatar-icon" title="You">
            <User size={15} />
          </div>
        ) : (
          <div className="avatar assistant-avatar-icon" title="Document Intelligence">
            <Bot size={15} />
          </div>
        )}
      </div>

      <div className="message-content-wrapper">
        <div className="message-header-info">
          <span className="sender-name">{isUser ? 'You' : 'Document Intelligence'}</span>
          {message.created_at && (
            <span className="message-time">
              {new Date(message.created_at).toLocaleTimeString(undefined, {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
              })}
            </span>
          )}
          {!isUser && !message.isError && (
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.62rem', color: 'var(--color-primary)', letterSpacing: '0.08em' }}>
              REF #{reportId}
            </span>
          )}
        </div>

        <div
          className={`message-bubble ${isUser ? 'bubble-user' : 'bubble-assistant'} ${
            isMissingContext ? 'bubble-missing-context' : ''
          } ${!isUser ? 'hud-bracket-container' : ''}`}
        >
          {!isUser && <HudCornerBrackets size={7} />}

          {isMissingContext ? (
            <div className="missing-context-callout">
              <div className="callout-header">
                <AlertTriangle size={16} className="callout-icon" />
                <span className="callout-title">Insufficient Knowledge Base Context</span>
              </div>
              <p className="callout-body">
                The provided documents do not contain enough information to answer this question.
              </p>
            </div>
          ) : isUser ? (
            <div className="message-text user-message-text">{message.content}</div>
          ) : (
            <div className="markdown-pro-content">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  // Code block rendering
                  code({ className, children, ...props }) {
                    const match = /language-(\w+)/.exec(className || '');
                    const isInline = !match && !String(children).includes('\n');
                    if (isInline) {
                      return (
                        <code className="inline-code-pill" {...props}>
                          {children}
                        </code>
                      );
                    }
                    return (
                      <CodeBlock
                        language={match ? match[1] : undefined}
                        code={String(children).replace(/\n$/, '')}
                      />
                    );
                  },
                  // Responsive table container
                  table({ children }) {
                    return (
                      <div className="markdown-table-wrapper">
                        <table className="markdown-table">{children}</table>
                      </div>
                    );
                  },
                  // Headings
                  h1({ children }) {
                    return <h1 className="md-h1">{children}</h1>;
                  },
                  h2({ children }) {
                    return <h2 className="md-h2">{children}</h2>;
                  },
                  h3({ children }) {
                    return <h3 className="md-h3">{children}</h3>;
                  },
                  // Paragraphs & Lists
                  p({ children }) {
                    return <p className="md-p">{children}</p>;
                  },
                  ul({ children }) {
                    return <ul className="md-ul">{children}</ul>;
                  },
                  ol({ children }) {
                    return <ol className="md-ol">{children}</ol>;
                  },
                  li({ children }) {
                    return <li className="md-li">{children}</li>;
                  },
                  blockquote({ children }) {
                    return <blockquote className="md-blockquote">{children}</blockquote>;
                  },
                  hr() {
                    return <hr className="md-hr" />;
                  },
                }}
              >
                {message.content}
              </ReactMarkdown>
            </div>
          )}

          {/* Assistant Action Bar */}
          {!isUser && !isMissingContext && !message.isError && (
            <div className="message-actions-bar">
              <button
                type="button"
                className="action-btn"
                onClick={handleCopyResponse}
                aria-label={copiedResponse ? 'Response copied to clipboard' : 'Copy response to clipboard'}
                title="Copy response"
              >
                {copiedResponse ? (
                  <>
                    <Check size={12} color="var(--color-success)" />
                    <span>COPIED</span>
                  </>
                ) : (
                  <>
                    <Copy size={12} />
                    <span>COPY REPORT</span>
                  </>
                )}
              </button>
            </div>
          )}
        </div>

        {/* Citations Evidence Deck */}
        {!isUser && message.sources && message.sources.length > 0 && (
          <SourceList sources={message.sources} />
        )}

        {/* Retry option on error */}
        {message.isError && onRetry && (
          <button
            type="button"
            className="action-btn"
            onClick={onRetry}
            style={{ color: 'var(--color-danger)', borderColor: 'rgba(244, 63, 94, 0.4)', marginTop: 4, width: 'fit-content' }}
          >
            RETRY TRANSMISSION
          </button>
        )}
      </div>
    </motion.div>
  );
};
