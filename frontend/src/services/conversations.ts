import { api } from './api';
import type {
  ConversationItem,
  ConversationCreateRequest,
  ConversationDeleteResponse,
  MessageItem,
  ConversationExchangeResponse,
} from '../types/chat';

export function formatRelativeTime(isoString?: string | null): string {
  if (!isoString) return '';
  try {
    const date = new Date(isoString);
    if (isNaN(date.getTime())) return '';

    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);

    if (diffSec < 60) return 'Just now';
    if (diffMin < 60) return `${diffMin}m ago`;
    if (diffHour < 24) return `${diffHour}h ago`;
    if (diffDay < 7) return `${diffDay}d ago`;

    return date.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
    });
  } catch {
    return '';
  }
}

class ConversationService {
  /**
   * Retrieves all conversations belonging to the authenticated user.
   * Ordered by updated_at DESC from backend.
   */
  async listConversations(skip = 0, limit = 100): Promise<ConversationItem[]> {
    return api.get<ConversationItem[]>(`/api/v1/conversations?skip=${skip}&limit=${limit}`);
  }

  /**
   * Creates a new conversation with a default or custom title.
   */
  async createConversation(title?: string): Promise<ConversationItem> {
    const payload: ConversationCreateRequest = title ? { title } : { title: 'New Conversation' };
    return api.post<ConversationItem>('/api/v1/conversations', payload);
  }

  /**
   * Fetches metadata for a single conversation.
   */
  async getConversation(conversationId: string): Promise<ConversationItem> {
    return api.get<ConversationItem>(`/api/v1/conversations/${conversationId}`);
  }

  /**
   * Deletes a conversation and cascades message deletion in the database.
   */
  async deleteConversation(conversationId: string): Promise<ConversationDeleteResponse> {
    return api.delete<ConversationDeleteResponse>(`/api/v1/conversations/${conversationId}`);
  }

  /**
   * Retrieves chronological message history for a conversation (created_at ASC).
   */
  async listMessages(conversationId: string, skip = 0, limit = 100): Promise<MessageItem[]> {
    return api.get<MessageItem[]>(
      `/api/v1/conversations/${conversationId}/messages?skip=${skip}&limit=${limit}`
    );
  }

  /**
   * Sends a user question, executes RAG retrieval, reranking, and generation on the backend,
   * persists both messages, and returns the conversation exchange with sources.
   */
  async sendMessage(
    conversationId: string,
    content: string
  ): Promise<ConversationExchangeResponse> {
    const cleanContent = content.trim();
    if (!cleanContent) {
      throw new Error('Message content cannot be empty.');
    }
    return api.post<ConversationExchangeResponse>(
      `/api/v1/conversations/${conversationId}/messages`,
      { content: cleanContent }
    );
  }
}

export const conversationService = new ConversationService();
