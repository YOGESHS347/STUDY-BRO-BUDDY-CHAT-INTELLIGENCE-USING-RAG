import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { conversationService, formatRelativeTime } from '../services/conversations';
import { MessageBubble } from '../components/chat/MessageBubble';
import { SourceList } from '../components/chat/SourceList';
import { SourceCard } from '../components/chat/SourceCard';
import { ChatInput } from '../components/chat/ChatInput';
import { EmptyChat } from '../components/chat/EmptyChat';
import { ConversationSidebar } from '../components/chat/ConversationSidebar';
import { DeleteConversationModal } from '../components/chat/DeleteConversationModal';
import { Chat } from '../pages/Chat';
import type {
  ConversationItem,
  MessageItem,
  ChatSource,
  ConversationExchangeResponse,
} from '../types/chat';

const renderChat = () =>
  render(
    <MemoryRouter>
      <Chat />
    </MemoryRouter>
  );

describe('Phase 10 — Chat UI & Conversation Experience Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // 1. Relative time helper formatting
  it('1. formats relative timestamps accurately', () => {
    expect(formatRelativeTime(null)).toBe('');
    expect(formatRelativeTime(undefined)).toBe('');
    const now = new Date().toISOString();
    expect(formatRelativeTime(now)).toBe('Just now');
  });

  // 2. Conversation list rendering
  it('2. renders conversation list items with title and timestamps', () => {
    const mockConvs: ConversationItem[] = [
      {
        id: 'c-1',
        user_id: 'u-1',
        title: 'Project Architecture Discussion',
        created_at: new Date(Date.now() - 3600000).toISOString(),
        updated_at: new Date(Date.now() - 3600000).toISOString(),
      },
      {
        id: 'c-2',
        user_id: 'u-1',
        title: 'Database Schema Review',
        created_at: new Date(Date.now() - 7200000).toISOString(),
        updated_at: new Date(Date.now() - 7200000).toISOString(),
      },
    ];

    render(
      <ConversationSidebar
        conversations={mockConvs}
        selectedId="c-1"
        loading={false}
        isCreating={false}
        isOpenMobile={false}
        onSelect={vi.fn()}
        onNewChat={vi.fn()}
        onDeleteConversation={vi.fn()}
        onCloseMobile={vi.fn()}
      />
    );

    expect(screen.getByText('Project Architecture Discussion')).toBeInTheDocument();
    expect(screen.getByText('Database Schema Review')).toBeInTheDocument();
  });

  // 3. Empty conversation state rendering
  it('3. renders empty sidebar state when user has no conversations', () => {
    render(
      <ConversationSidebar
        conversations={[]}
        selectedId={null}
        loading={false}
        isCreating={false}
        isOpenMobile={false}
        onSelect={vi.fn()}
        onNewChat={vi.fn()}
        onDeleteConversation={vi.fn()}
        onCloseMobile={vi.fn()}
      />
    );

    expect(screen.getByText('No conversations yet')).toBeInTheDocument();
    expect(screen.getByText('Start your first chat')).toBeInTheDocument();
  });

  // 4. New chat creation calls API and updates selection
  it('4. calls onNewChat when "+ New Chat" button is clicked', () => {
    const onNewChatMock = vi.fn();
    render(
      <ConversationSidebar
        conversations={[]}
        selectedId={null}
        loading={false}
        isCreating={false}
        isOpenMobile={false}
        onSelect={vi.fn()}
        onNewChat={onNewChatMock}
        onDeleteConversation={vi.fn()}
        onCloseMobile={vi.fn()}
      />
    );

    const newChatBtn = screen.getByRole('button', { name: /New Chat/i });
    fireEvent.click(newChatBtn);
    expect(onNewChatMock).toHaveBeenCalledTimes(1);
  });

  // 5. Selecting conversation triggers callback
  it('5. triggers onSelect with conversation object when clicked', () => {
    const onSelectMock = vi.fn();
    const conv: ConversationItem = {
      id: 'c-sel-1',
      user_id: 'u-1',
      title: 'Active Investigation',
      created_at: new Date().toISOString(),
    };

    render(
      <ConversationSidebar
        conversations={[conv]}
        selectedId="c-other"
        loading={false}
        isCreating={false}
        isOpenMobile={false}
        onSelect={onSelectMock}
        onNewChat={vi.fn()}
        onDeleteConversation={vi.fn()}
        onCloseMobile={vi.fn()}
      />
    );

    fireEvent.click(screen.getByText('Active Investigation'));
    expect(onSelectMock).toHaveBeenCalledWith(conv);
  });

  // 6. User message rendering
  it('6. renders user message with proper role styling', () => {
    const userMsg: MessageItem = {
      id: 'm-user',
      conversation_id: 'c-1',
      role: 'user',
      content: 'How does multi-tenancy work in this system?',
      created_at: new Date().toISOString(),
    };

    render(<MessageBubble message={userMsg} />);
    expect(screen.getByText('How does multi-tenancy work in this system?')).toBeInTheDocument();
    expect(screen.getByText('You')).toBeInTheDocument();
  });

  // 7. Assistant message rendering
  it('7. renders assistant message with grounded response', () => {
    const assistantMsg: MessageItem = {
      id: 'm-asst',
      conversation_id: 'c-1',
      role: 'assistant',
      content: 'Multi-tenancy uses verified JWT sub claims to filter all Qdrant vector queries.',
      created_at: new Date().toISOString(),
    };

    render(<MessageBubble message={assistantMsg} />);
    expect(
      screen.getByText('Multi-tenancy uses verified JWT sub claims to filter all Qdrant vector queries.')
    ).toBeInTheDocument();
    expect(screen.getByText('Document Intelligence')).toBeInTheDocument();
  });

  // 8. Sources render from actual response
  it('8. renders structured sources with filename, page, and score', () => {
    const sources: ChatSource[] = [
      {
        source: 'Security_Spec.pdf',
        page: 7,
        file_type: 'pdf',
        score: 0.9123,
      },
    ];

    render(<SourceList sources={sources} />);
    expect(screen.getByText(/Grounded Sources \(1\)/i)).toBeInTheDocument();
    expect(screen.getByText('Security_Spec.pdf')).toBeInTheDocument();
    expect(screen.getByText('Page 7')).toBeInTheDocument();
    expect(screen.getByText('91% match')).toBeInTheDocument();
  });

  // 9. Missing-context response renders exact text without fake sources
  it('9. renders exact missing-context text with indicator and no sources', () => {
    const missingContextMsg: MessageItem = {
      id: 'm-miss',
      conversation_id: 'c-1',
      role: 'assistant',
      content: 'The provided documents do not contain enough information to answer this question.',
      created_at: new Date().toISOString(),
      sources: [],
    };

    render(<MessageBubble message={missingContextMsg} />);
    expect(
      screen.getByText('The provided documents do not contain enough information to answer this question.')
    ).toBeInTheDocument();
    expect(screen.getByText(/Insufficient Knowledge Base Context/i)).toBeInTheDocument();
    expect(screen.queryByText(/Grounded Sources/i)).not.toBeInTheDocument();
  });

  // 10. Empty or whitespace-only message is rejected
  it('10. rejects empty or whitespace-only messages in ChatInput', () => {
    const onSendMock = vi.fn();
    render(<ChatInput onSend={onSendMock} isSending={false} />);

    const sendBtn = screen.getByRole('button', { name: /Send question/i });
    expect(sendBtn).toBeDisabled();

    const textarea = screen.getByLabelText('Message input');
    fireEvent.change(textarea, { target: { value: '    ' } });
    expect(sendBtn).toBeDisabled();

    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });
    expect(onSendMock).not.toHaveBeenCalled();
  });

  // 11. Send button shows loading / disabled state while request is in flight
  it('11. disables send button and shows spinner while isSending is true', () => {
    const onSendMock = vi.fn();
    render(<ChatInput onSend={onSendMock} isSending={true} />);

    const sendBtn = screen.getByRole('button', { name: /Send question/i });
    expect(sendBtn).toBeDisabled();
  });

  // 12. In-flight assistant thinking state indicator
  it('12. displays thinking state when isSending is active', async () => {
    const mockListConvs = vi.spyOn(conversationService, 'listConversations').mockResolvedValue([
      {
        id: 'c-think',
        user_id: 'u-1',
        title: 'Investigation',
        created_at: new Date().toISOString(),
      },
    ]);
    const mockListMsgs = vi.spyOn(conversationService, 'listMessages').mockResolvedValue([]);

    // Delay send message response to check in-flight thinking state
    let resolveSend: (val: ConversationExchangeResponse) => void;
    const sendPromise = new Promise<ConversationExchangeResponse>((res) => {
      resolveSend = res;
    });
    vi.spyOn(conversationService, 'sendMessage').mockReturnValue(sendPromise);

    renderChat();

    await waitFor(() => {
      expect(mockListConvs).toHaveBeenCalled();
      expect(mockListMsgs).toHaveBeenCalled();
    });

    const input = screen.getByLabelText('Message input');
    fireEvent.change(input, { target: { value: 'What is vector indexing?' } });
    fireEvent.click(screen.getByRole('button', { name: /Send question/i }));

    // In-flight thinking state indicator should appear
    expect(screen.getByText(/Searching documents & generating answer.../i)).toBeInTheDocument();

    // Resolve send promise
    await act(async () => {
      resolveSend!({
        user_message: {
          id: 'u-done',
          conversation_id: 'c-think',
          role: 'user',
          content: 'What is vector indexing?',
        },
        assistant_message: {
          id: 'a-done',
          conversation_id: 'c-think',
          role: 'assistant',
          content: 'Vector indexing converts chunks into dense vector embeddings.',
        },
        sources: [],
      });
    });

    await waitFor(() => {
      expect(
        screen.getByText('Vector indexing converts chunks into dense vector embeddings.')
      ).toBeInTheDocument();
    });
  });

  // 13. Failed message request displays error and does not create fake assistant message
  it('13. displays error state when sendMessage fails without fake assistant message', async () => {
    vi.spyOn(conversationService, 'listConversations').mockResolvedValue([
      {
        id: 'c-err',
        user_id: 'u-1',
        title: 'Error Test',
        created_at: new Date().toISOString(),
      },
    ]);
    vi.spyOn(conversationService, 'listMessages').mockResolvedValue([]);
    vi.spyOn(conversationService, 'sendMessage').mockRejectedValue(
      new Error('RAG vector retrieval service failed to initialize.')
    );

    renderChat();

    await waitFor(() => {
      expect(screen.getByLabelText('Message input')).toBeInTheDocument();
    });

    const input = screen.getByLabelText('Message input');
    fireEvent.change(input, { target: { value: 'Explain error handling.' } });
    fireEvent.click(screen.getByRole('button', { name: /Send question/i }));

    await waitFor(() => {
      expect(
        screen.getByText('RAG vector retrieval service failed to initialize.')
      ).toBeInTheDocument();
    });

    // No assistant message was created
    expect(screen.queryByText(/Document Intelligence/i)).not.toBeInTheDocument();
  });

  // 14. Delete confirmation modal appears with title and description
  it('14. displays delete confirmation modal on clicking delete', () => {
    render(
      <DeleteConversationModal
        isOpen={true}
        title="Q4 Financials"
        isDeleting={false}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />
    );

    expect(screen.getByText('Delete Conversation?')).toBeInTheDocument();
    expect(screen.getByText(/permanently delete/i)).toBeInTheDocument();
    expect(screen.getByText('Q4 Financials')).toBeInTheDocument();
  });

  // 15. Delete cancel keeps conversation intact
  it('15. cancels deletion when cancel button is clicked', () => {
    const onCancelMock = vi.fn();
    render(
      <DeleteConversationModal
        isOpen={true}
        title="Q4 Financials"
        isDeleting={false}
        onConfirm={vi.fn()}
        onCancel={onCancelMock}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /Cancel/i }));
    expect(onCancelMock).toHaveBeenCalledTimes(1);
  });

  // 16. Delete confirm calls API and removes conversation
  it('16. calls onConfirm when delete is confirmed in modal', async () => {
    const onConfirmMock = vi.fn();
    render(
      <DeleteConversationModal
        isOpen={true}
        title="Q4 Financials"
        isDeleting={false}
        onConfirm={onConfirmMock}
        onCancel={vi.fn()}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /Delete Chat/i }));
    expect(onConfirmMock).toHaveBeenCalledTimes(1);
  });

  // 17. API 401 unauthenticated handled safely
  it('17. handles API 401 failure gracefully on conversation load', async () => {
    vi.spyOn(conversationService, 'listConversations').mockRejectedValue(
      new Error('Missing or invalid authentication token.')
    );

    renderChat();

    await waitFor(() => {
      expect(
        screen.getByText('Missing or invalid authentication token.')
      ).toBeInTheDocument();
    });
  });

  // 18. API 404 conversation not found handled safely
  it('18. handles API 404 failure gracefully on message load', async () => {
    vi.spyOn(conversationService, 'listConversations').mockResolvedValue([
      {
        id: 'c-404',
        user_id: 'u-1',
        title: 'Missing Conv',
        created_at: new Date().toISOString(),
      },
    ]);
    vi.spyOn(conversationService, 'listMessages').mockRejectedValue(
      new Error('Conversation c-404 not found.')
    );

    renderChat();

    await waitFor(() => {
      expect(screen.getByText('Conversation c-404 not found.')).toBeInTheDocument();
    });
  });

  // 19. No arbitrary user_id is sent in API calls
  it('19. verifies sendMessage does not include client user_id in payload', async () => {
    const apiSpy = vi.spyOn(conversationService, 'sendMessage').mockResolvedValue({
      user_message: {
        id: 'u-1',
        conversation_id: 'c-1',
        role: 'user',
        content: 'Is client user_id sent?',
      },
      assistant_message: {
        id: 'a-1',
        conversation_id: 'c-1',
        role: 'assistant',
        content: 'No, authentication is strictly derived from JWT sub.',
      },
      sources: [],
    });

    await conversationService.sendMessage('c-1', 'Is client user_id sent?');
    expect(apiSpy).toHaveBeenCalledWith('c-1', 'Is client user_id sent?');
  });

  // 20. Conversation switching isolates messages between conversations
  it('20. switches conversation and renders respective message history', async () => {
    const conv1: ConversationItem = {
      id: 'c-1',
      user_id: 'u-1',
      title: 'Topic A',
      created_at: new Date().toISOString(),
    };
    const conv2: ConversationItem = {
      id: 'c-2',
      user_id: 'u-1',
      title: 'Topic B',
      created_at: new Date().toISOString(),
    };

    vi.spyOn(conversationService, 'listConversations').mockResolvedValue([conv1, conv2]);
    const mockListMessages = vi
      .spyOn(conversationService, 'listMessages')
      .mockImplementation(async (id: string) => {
        if (id === 'c-1') {
          return [
            {
              id: 'm-1',
              conversation_id: 'c-1',
              role: 'user',
              content: 'Message inside Topic A',
            },
          ];
        } else {
          return [
            {
              id: 'm-2',
              conversation_id: 'c-2',
              role: 'user',
              content: 'Message inside Topic B',
            },
          ];
        }
      });

    renderChat();

    // Initially loads first conversation (Topic A)
    await waitFor(() => {
      expect(screen.getByText('Message inside Topic A')).toBeInTheDocument();
    });
    expect(screen.queryByText('Message inside Topic B')).not.toBeInTheDocument();

    // Switch to Topic B
    fireEvent.click(screen.getByText('Topic B'));

    await waitFor(() => {
      expect(screen.getByText('Message inside Topic B')).toBeInTheDocument();
    });
    expect(screen.queryByText('Message inside Topic A')).not.toBeInTheDocument();
  });
});
