import React from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { FileText, FileSpreadsheet, FileCode, Layers } from 'lucide-react';
import type { ChatSource } from '../../types/chat';
import { HudCornerBrackets } from '../common/HudCornerBrackets';

interface SourceCardProps {
  source: ChatSource;
  index: number;
}

export const SourceCard: React.FC<SourceCardProps> = ({ source, index }) => {
  const shouldReduceMotion = useReducedMotion();

  const getFileIcon = (fileType?: string | null, filename?: string) => {
    const ext = (fileType || filename?.split('.').pop() || '').toLowerCase();
    switch (ext) {
      case 'xlsx':
      case 'csv':
        return <FileSpreadsheet size={13} color="var(--color-primary)" />;
      case 'txt':
        return <FileCode size={13} color="var(--color-primary)" />;
      case 'pdf':
      case 'docx':
      default:
        return <FileText size={13} color="var(--color-primary)" />;
    }
  };

  const filename = source.source || 'Document';
  const paddedIndex = String(index + 1).padStart(2, '0');
  const matchPct =
    source.score !== null && source.score !== undefined
      ? source.score > 1
        ? `${Math.round(source.score)}%`
        : `${Math.round(source.score * 100)}% match`
      : null;

  return (
    <motion.div
      className="pro-source-card hud-bracket-container"
      title={filename}
      initial={shouldReduceMotion ? false : { opacity: 0, y: 8 }}
      animate={shouldReduceMotion ? false : { opacity: 1, y: 0 }}
      transition={{
        duration: 0.3,
        delay: index * 0.05,
        ease: [0.16, 1, 0.3, 1],
      }}
    >
      <HudCornerBrackets size={5} />

      <div className="source-card-top">
        <span className="source-ordinal">SOURCE {paddedIndex}</span>
        {matchPct && (
          <span className="source-match-pill" title={`Relevance: ${source.score}`}>
            <Layers size={9} />
            <span>{matchPct}</span>
          </span>
        )}
      </div>

      <div className="source-filename-row">
        {getFileIcon(source.file_type, filename)}
        <span className="source-filename-text">{filename}</span>
      </div>

      {source.page !== null && source.page !== undefined && (
        <div className="source-page-badge">
          <span>Page {source.page}</span>
        </div>
      )}
    </motion.div>
  );
};
