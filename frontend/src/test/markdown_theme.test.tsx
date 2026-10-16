import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import React from 'react';
import { ThemeProvider, useTheme } from '../context/ThemeContext';
import { ThemeSwitcher } from '../components/common/ThemeSwitcher';
import { CodeBlock } from '../components/chat/CodeBlock';
import { MessageBubble } from '../components/chat/MessageBubble';
import type { MessageItem } from '../types/chat';

const TestThemeConsumer: React.FC = () => {
  const { theme, resolvedTheme, setTheme } = useTheme();
  return (
    <div>
      <span data-testid="current-theme">{theme}</span>
      <span data-testid="resolved-theme">{resolvedTheme}</span>
      <button onClick={() => setTheme('light')}>Set Light</button>
      <button onClick={() => setTheme('dark')}>Set Dark</button>
      <button onClick={() => setTheme('system')}>Set System</button>
    </div>
  );
};

describe('Theme System Tests', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute('data-theme');
  });

  it('1. defaults to system theme when no preference stored and resolves to dark/light', () => {
    render(
      <ThemeProvider>
        <TestThemeConsumer />
      </ThemeProvider>
    );

    expect(screen.getByTestId('current-theme').textContent).toBe('system');
    expect(document.documentElement.getAttribute('data-theme')).toBeTruthy();
  });

  it('2. toggles theme to light and updates DOM and localStorage', () => {
    render(
      <ThemeProvider>
        <TestThemeConsumer />
      </ThemeProvider>
    );

    act(() => {
      screen.getByText('Set Light').click();
    });

    expect(screen.getByTestId('current-theme').textContent).toBe('light');
    expect(screen.getByTestId('resolved-theme').textContent).toBe('light');
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
    expect(localStorage.getItem('rag_theme_preference')).toBe('light');
  });

  it('3. renders ThemeSwitcher with 3 options and updates on click', () => {
    render(
      <ThemeProvider>
        <ThemeSwitcher />
      </ThemeProvider>
    );

    const lightBtn = screen.getByRole('radio', { name: /Light theme/i });
    const darkBtn = screen.getByRole('radio', { name: /Dark theme/i });
    const systemBtn = screen.getByRole('radio', { name: /System theme/i });

    expect(lightBtn).toBeInTheDocument();
    expect(darkBtn).toBeInTheDocument();
    expect(systemBtn).toBeInTheDocument();

    act(() => {
      fireEvent.click(lightBtn);
    });

    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
  });
});

describe('CodeBlock & Markdown Rendering Tests', () => {
  it('4. renders CodeBlock with uppercase language tag and copy button', () => {
    const testCode = 'class Database {\npublic:\n  virtual void connect() = 0;\n};';
    render(<CodeBlock language="cpp" code={testCode} />);

    expect(screen.getByText('CPP')).toBeInTheDocument();
    expect(screen.getByText(/virtual void connect\(\) = 0;/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Copy code to clipboard/i })).toBeInTheDocument();
  });

  it('5. copies code to clipboard and shows temporary feedback', async () => {
    const writeTextMock = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: {
        writeText: writeTextMock,
      },
    });

    const testCode = '#include <iostream>\nint main() { return 0; }';
    render(<CodeBlock language="cpp" code={testCode} />);

    const copyBtn = screen.getByRole('button', { name: /Copy code to clipboard/i });
    await act(async () => {
      fireEvent.click(copyBtn);
    });

    expect(writeTextMock).toHaveBeenCalledWith(testCode);
    expect(screen.getByText('Copied!')).toBeInTheDocument();
  });

  it('6. MessageBubble renders formatted markdown headers, lists, tables, and code blocks', () => {
    const markdownContent = `
# Abstraction in C++

Abstraction separates interface from implementation.

## Key Syntax
\`\`\`cpp
class Shape {
public:
    virtual void draw() = 0;
};
\`\`\`

| Feature | Description |
| :--- | :--- |
| Pure Virtual | Requires \`= 0\` |
| Interface | Abstract class |

- Encapsulation
- Information Hiding
`;

    const message: MessageItem = {
      id: 'm-md-test',
      conversation_id: 'c-test',
      role: 'assistant',
      content: markdownContent,
      created_at: new Date().toISOString(),
      sources: [
        {
          source: 'abstraction.pdf',
          page: 26,
          score: 0.94,
          file_type: 'pdf',
        },
      ],
    };

    render(<MessageBubble message={message} />);

    // Header 1
    expect(screen.getByRole('heading', { level: 1, name: /Abstraction in C\+\+/i })).toBeInTheDocument();
    // Header 2
    expect(screen.getByRole('heading', { level: 2, name: /Key Syntax/i })).toBeInTheDocument();
    // Code block
    expect(screen.getByText('CPP')).toBeInTheDocument();
    expect(screen.getByText(/virtual void draw\(\) = 0;/i)).toBeInTheDocument();
    // Table
    expect(screen.getByText('Pure Virtual')).toBeInTheDocument();
    expect(screen.getByText('= 0')).toBeInTheDocument();
    // List item
    expect(screen.getByText('Information Hiding')).toBeInTheDocument();
    // Grounded source card
    expect(screen.getByText('abstraction.pdf')).toBeInTheDocument();
    expect(screen.getByText('Page 26')).toBeInTheDocument();
    expect(screen.getByText('SOURCE 01')).toBeInTheDocument();
  });
});
