import React from 'react';

interface HudCornerBracketsProps {
  className?: string;
  size?: number; // size in px
  color?: string;
}

export const HudCornerBrackets: React.FC<HudCornerBracketsProps> = ({
  className = '',
  size = 8,
  color,
}) => {
  const style = color ? { borderColor: color } : undefined;
  const bracketStyle: React.CSSProperties = {
    width: size,
    height: size,
    ...style,
  };

  return (
    <div className={`hud-bracket-overlay ${className}`} aria-hidden="true">
      <span className="hud-corner hud-corner-tl" style={bracketStyle} />
      <span className="hud-corner hud-corner-tr" style={bracketStyle} />
      <span className="hud-corner hud-corner-bl" style={bracketStyle} />
      <span className="hud-corner hud-corner-br" style={bracketStyle} />
    </div>
  );
};
