import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { IntelligenceBackground } from '../components/common/IntelligenceBackground';
import { PageTransition } from '../components/common/PageTransition';
import { CustomCursor } from '../components/common/CustomCursor';

describe('Motion & Visual Design System Components', () => {
  it('renders IntelligenceBackground canvas without crashing', () => {
    const { container } = render(<IntelligenceBackground />);
    const canvas = container.querySelector('.intelligence-canvas');
    expect(canvas).toBeInTheDocument();
  });

  it('renders PageTransition with children', () => {
    render(
      <PageTransition className="custom-test-transition">
        <div data-testid="page-child">Test Page Content</div>
      </PageTransition>
    );

    expect(screen.getByTestId('page-child')).toBeInTheDocument();
    expect(screen.getByText('Test Page Content')).toBeInTheDocument();
  });

  it('renders and tracks CustomCursor on mousemove', () => {
    const { container } = render(<CustomCursor />);
    
    // Initially hidden before interaction
    expect(container.querySelector('.cinematic-cursor-follower')).toBeNull();

    // Trigger mousemove
    fireEvent.mouseMove(window, { clientX: 150, clientY: 250 });

    const cursor = container.querySelector('.cinematic-cursor-follower');
    expect(cursor).toBeInTheDocument();
  });
});
