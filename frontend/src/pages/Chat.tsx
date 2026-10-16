import React, { useEffect, useState, useCallback } from 'react';
import { conversationService } from '../services/conversations';
import type { ConversationItem, MessageItem } from '../types/chat';
import { ConversationSidebar } from '../components/chat/ConversationSidebar';
import { ChatWindow } from '../components/chat/ChatWindow';
import { PageTransition } from '../components/common/PageTransition';

export const Chat: React.FC = () => {
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [selectedConversationId, setSelectedConversationId] = useState<string | null>(null);
  const [messagesMap, setMessagesMap] = useState<Record<string, MessageItem[]>>({});
  const [loadingConversations, setLoadingConversations] = useState(true);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isOpenMobileSidebar, setIsOpenMobileSidebar] = useState(false);

  // Fetch conversation message history
  const loadMessages = useCallback(async (convId: string) => {
    setLoadingMessages(true);
    setError(null);
    try {
      const msgs = await conversationService.listMessages(convId);
      setMessagesMap((prev) => ({ ...prev, [convId]: msgs }));
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load messages.';
      setError(msg);
    } finally {
      setLoadingMessages(false);
    }
  }, []);

  // Fetch conversations list on mount
  const fetchConversations = useCallback(async () => {
    setLoadingConversations(true);
    setError(null);
    try {
      const list = await conversationService.listConversations();
      setConversations(list);

      if (list.length > 0) {
        // Automatically select the most recently updated conversation
        const first = list[0];
        setSelectedConversationId(first.id);
        loadMessages(first.id);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load conversations.';
      setError(msg);
    } finally {
      setLoadingConversations(false);
    }
  }, [loadMessages]);

  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  // Handle conversation selection
  const handleSelectConversation = (conv: ConversationItem) => {
    setSelectedConversationId(conv.id);
    if (!messagesMap[conv.id]) {
      loadMessages(conv.id);
    }
  };

  // Create new conversation
  const handleNewChat = async () => {
    setIsCreating(true);
    setError(null);
    try {
      const newConv = await conversationService.createConversation('New Conversation');
      setConversations((prev) => [newConv, ...prev]);
      setSelectedConversationId(newConv.id);
      setMessagesMap((prev) => ({ ...prev, [newConv.id]: [] }));
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to create new conversation.';
      setError(msg);
    } finally {
      setIsCreating(false);
    }
  };

  // Delete conversation
  const handleDeleteConversation = async (conv: ConversationItem) => {
    try {
      await conversationService.deleteConversation(conv.id);
      const remaining = conversations.filter((c) => c.id !== conv.id);
      setConversations(remaining);

      // Clean up cached messages
      setMessagesMap((prev) => {
        const next = { ...prev };
        delete next[conv.id];
        return next;
      });

      if (selectedConversationId === conv.id) {
        if (remaining.length > 0) {
          const nextConv = remaining[0];
          setSelectedConversationId(nextConv.id);
          loadMessages(nextConv.id);
        } else {
          setSelectedConversationId(null);
        }
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to delete conversation.';
      setError(msg);
    }
  };

  // Send message in current conversation
  const handleSendMessage = async (content: string) => {
    let convId = selectedConversationId;

    // If no conversation is selected, create one first
    if (!convId) {
      try {
        const created = await conversationService.createConversation();
        setConversations((prev) => [created, ...prev]);
        setSelectedConversationId(created.id);
        convId = created.id;
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Failed to create chat session.';
        setError(msg);
        return;
      }
    }

    const targetConvId = convId;
    const tempId = `temp-${Date.now()}`;
    const optimisticUserMsg: MessageItem = {
      id: tempId,
      conversation_id: targetConvId,
      role: 'user',
      content,
      created_at: new Date().toISOString(),
      isPending: true,
    };

    // Optimistically update message stream
    setMessagesMap((prev) => ({
      ...prev,
      [targetConvId]: [...(prev[targetConvId] || []), optimisticUserMsg],
    }));

    setIsSending(true);
    setError(null);

    try {
      const exchange = await conversationService.sendMessage(targetConvId, content);

      // Replace optimistic message with actual persisted messages and sources
      setMessagesMap((prev) => {
        const currentMsgs = (prev[targetConvId] || []).filter((m) => m.id !== tempId);
        const assistantWithSources: MessageItem = {
          ...exchange.assistant_message,
          sources: exchange.sources,
        };
        return {
          ...prev,
          [targetConvId]: [...currentMsgs, exchange.user_message, assistantWithSources],
        };
      });

      // Update conversation in sidebar: move to top and sync title
      setConversations((prev) => {
        const currentConv = prev.find((c) => c.id === targetConvId);
        const otherConvs = prev.filter((c) => c.id !== targetConvId);
        if (!currentConv) return prev;

        // Auto-updated title if it was "New Conversation"
        let updatedTitle = currentConv.title;
        if (currentConv.title === 'New Conversation' || !currentConv.title) {
          updatedTitle = content.split('\n')[0].substring(0, 80);
        }

        const updatedConv: ConversationItem = {
          ...currentConv,
          title: updatedTitle,
          updated_at: new Date().toISOString(),
        };

        return [updatedConv, ...otherConvs];
      });
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : 'Failed to generate answer. Please verify backend service.';
      setError(msg);

      // Mark optimistic message with error
      setMessagesMap((prev) => ({
        ...prev,
        [targetConvId]: (prev[targetConvId] || []).map((m) =>
          m.id === tempId ? { ...m, isPending: false, isError: true } : m
        ),
      }));
    } finally {
      setIsSending(false);
    }
  };

  const activeConversation =
    conversations.find((c) => c.id === selectedConversationId) || null;
  const currentMessages =
    (selectedConversationId && messagesMap[selectedConversationId]) || [];

  return (
    <PageTransition>
      <div className="chat-layout-root">
        {/* Mobile Backdrop Overlay */}
        {isOpenMobileSidebar && (
          <div
            className="chat-sidebar-backdrop"
            onClick={() => setIsOpenMobileSidebar(false)}
          />
        )}

        {/* Conversation Sidebar */}
        <ConversationSidebar
          conversations={conversations}
          selectedId={selectedConversationId}
          loading={loadingConversations}
          isCreating={isCreating}
          isOpenMobile={isOpenMobileSidebar}
          onSelect={handleSelectConversation}
          onNewChat={handleNewChat}
          onDeleteConversation={handleDeleteConversation}
          onCloseMobile={() => setIsOpenMobileSidebar(false)}
        />

        {/* Main Chat Area */}
        <ChatWindow
          activeConversation={activeConversation}
          messages={currentMessages}
          loadingMessages={loadingMessages}
          isSending={isSending}
          error={error}
          onSend={handleSendMessage}
          onToggleMobileSidebar={() => setIsOpenMobileSidebar((prev) => !prev)}
        />
      </div>
    </PageTransition>
  );
};

export default Chat;
