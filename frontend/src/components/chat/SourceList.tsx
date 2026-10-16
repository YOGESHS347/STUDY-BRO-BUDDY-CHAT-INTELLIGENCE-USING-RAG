import React, { useState } from 'react';
import { BookOpen, ChevronDown, ChevronUp } from 'lucide-react';
import type { ChatSource } from '../../types/chat';
import { SourceCard } from './SourceCard';

interface SourceListProps {
  sources: ChatSource[];
}

export const SourceList: React.FC<SourceListProps> = ({ sources }) => {
  const [isExpanded, setIsExpanded] = useState(true);

  if (!sources || sources.length === 0) {
    return null;
  }

  return (
    <div className="source-list-wrapper">
      <button
        type="button"
        className="source-list-header-btn"
        onClick={() => setIsExpanded((prev) => !prev)}
        aria-expanded={isExpanded}
      >
        <div className="source-list-title">
          <BookOpen size={14} color="var(--color-primary)" />
          <span>Grounded Sources ({sources.length})</span>
        </div>
        {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
      </button>

      {isExpanded && (
        <div className="source-list-grid">
          {sources.map((src, idx) => (
            <SourceCard key={`${src.source}-${idx}`} source={src} index={idx} />
          ))}
        </div>
      )}
    </div>
  );
};
