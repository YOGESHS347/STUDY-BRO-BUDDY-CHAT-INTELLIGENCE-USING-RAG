import React from 'react';
import { Link } from 'react-router-dom';
import { motion, useReducedMotion } from 'framer-motion';
import { Sparkles, FileText, ArrowRight, BookOpen, ListChecks, Terminal } from 'lucide-react';
import { HudCornerBrackets } from '../common/HudCornerBrackets';

interface EmptyChatProps {
  onSelectPrompt: (prompt: string) => void;
}

export const EmptyChat: React.FC<EmptyChatProps> = ({ onSelectPrompt }) => {
  const shouldReduceMotion = useReducedMotion();

  const examplePrompts = [
    {
      title: 'Summarize',
      prompt: 'Summarize the key points, main conclusions, and executive takeaways from my documents.',
      icon: <FileText size={15} color="var(--color-primary)" />,
    },
    {
      title: 'Key Insights',
      prompt: 'Extract the most important insights, critical metrics, and core findings.',
      icon: <Sparkles size={15} color="var(--color-primary)" />,
    },
    {
      title: 'Explain Simply',
      prompt: 'Explain the fundamental concepts and technical methodology in clear, accessible terms.',
      icon: <BookOpen size={15} color="var(--color-primary)" />,
    },
    {
      title: 'Action Items & Next Steps',
      prompt: 'What are the actionable recommendations, potential risks, and next steps outlined?',
      icon: <ListChecks size={15} color="var(--color-primary)" />,
    },
  ];

  return (
    <motion.div
      className="empty-chat-container"
      initial={shouldReduceMotion ? false : { opacity: 0, y: 16 }}
      animate={shouldReduceMotion ? false : { opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className="empty-chat-badge hero-eyebrow">
        <Terminal size={13} color="var(--color-primary)" />
        <span>INTELLIGENCE CONSOLE // STANDBY</span>
      </div>

      <h3 className="empty-chat-title">Query Knowledge Space</h3>
      <p className="empty-chat-desc">
        Transmit technical questions to your indexed document repository. Answers are strictly grounded in your verified files with cross-encoder reranked citations.
      </p>

      <div className="example-prompts-grid prompt-suggestions-grid">
        {examplePrompts.map((item, idx) => (
          <motion.button
            key={idx}
            type="button"
            className="example-prompt-card prompt-suggestion-pill hud-bracket-container"
            onClick={() => onSelectPrompt(item.prompt)}
            whileHover={shouldReduceMotion ? undefined : { y: -2 }}
            whileTap={shouldReduceMotion ? undefined : { scale: 0.98 }}
            initial={shouldReduceMotion ? false : { opacity: 0, y: 10 }}
            animate={shouldReduceMotion ? false : { opacity: 1, y: 0 }}
            transition={{ duration: 0.25, delay: idx * 0.05 }}
          >
            <HudCornerBrackets size={5} />
            <div className="prompt-card-header" style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
              <span className="prompt-card-icon">{item.icon}</span>
              <span className="prompt-card-category" style={{ fontFamily: 'var(--font-mono)', fontSize: '0.68rem', textTransform: 'uppercase', color: 'var(--color-primary)', letterSpacing: '0.06em' }}>
                {item.title}
              </span>
            </div>
            <span className="prompt-card-text" style={{ fontSize: '0.84rem', color: 'var(--color-text-main)' }}>
              "{item.prompt}"
            </span>
          </motion.button>
        ))}
      </div>

      <div className="empty-chat-docs-link" style={{ marginTop: 16 }}>
        <Link to="/documents" className="btn-secondary" style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
          <FileText size={15} />
          <span>Manage Knowledge Base Files</span>
          <ArrowRight size={14} />
        </Link>
      </div>
    </motion.div>
  );
};
