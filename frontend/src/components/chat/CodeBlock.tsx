import React, { useState } from 'react';
import { Copy, Check, Terminal } from 'lucide-react';
import { HudCornerBrackets } from '../common/HudCornerBrackets';

interface CodeBlockProps {
  language?: string;
  code: string;
}

export const CodeBlock: React.FC<CodeBlockProps> = ({ language, code }) => {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(code);
      } else {
        const textarea = document.createElement('textarea');
        textarea.value = code;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
      }
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
    }
  };

  const displayLang = (language || 'text').toUpperCase();

  return (
    <div className="pro-code-block hud-bracket-container">
      <HudCornerBrackets size={6} />
      <div className="code-block-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Terminal size={12} color="var(--color-primary)" />
          <span className="code-lang-tag">{displayLang}</span>
        </div>
        <button
          type="button"
          className="code-copy-btn"
          onClick={handleCopy}
          aria-label={copied ? 'Code copied to clipboard' : 'Copy code to clipboard'}
          title="Copy code"
        >
          {copied ? (
            <>
              <Check size={12} color="var(--color-success)" />
              <span>Copied!</span>
            </>
          ) : (
            <>
              <Copy size={12} />
              <span>Copy</span>
            </>
          )}
        </button>
      </div>
      <div className="code-content-wrapper">
        <pre className="code-pre">
          <code className={`code-text language-${language || 'text'}`}>{code}</code>
        </pre>
      </div>
    </div>
  );
};
