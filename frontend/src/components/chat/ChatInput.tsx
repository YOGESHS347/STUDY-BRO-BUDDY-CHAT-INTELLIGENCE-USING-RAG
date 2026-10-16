import React, { useRef, useState, useEffect } from 'react';
import { Send, Loader2 } from 'lucide-react';
import { HudCornerBrackets } from '../common/HudCornerBrackets';

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled?: boolean;
  isSending?: boolean;
  placeholder?: string;
}

export const ChatInput: React.FC<ChatInputProps> = ({
  onSend,
  disabled = false,
  isSending = false,
  placeholder = 'Transmit research query to intelligence core...',
}) => {
  const [content, setContent] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea height
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(
        textareaRef.current.scrollHeight,
        140
      )}px`;
    }
  }, [content]);

  const handleSend = () => {
    const trimmed = content.trim();
    if (!trimmed || isSending || disabled) return;

    onSend(trimmed);
    setContent('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const isButtonDisabled = disabled || isSending || !content.trim();

  return (
    <div className="chat-input-wrapper">
      <div className="chat-input-container hud-bracket-container">
        <HudCornerBrackets size={6} />
        <textarea
          ref={textareaRef}
          value={content}
          onChange={(e) => setContent(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled || isSending}
          rows={1}
          className="chat-textarea"
          aria-label="Message input"
        />

        <button
          type="button"
          onClick={handleSend}
          disabled={isButtonDisabled}
          className="chat-send-btn"
          aria-label="Send question"
          title="Send question (Enter)"
        >
          {isSending ? (
            <Loader2 size={16} className="icon-spin" />
          ) : (
            <Send size={15} />
          )}
        </button>
      </div>
      <div className="chat-input-hints">
        <span>PRESS <strong>ENTER</strong> TO TRANSMIT // <strong>SHIFT+ENTER</strong> FOR NEWLINE</span>
      </div>
    </div>
  );
};
