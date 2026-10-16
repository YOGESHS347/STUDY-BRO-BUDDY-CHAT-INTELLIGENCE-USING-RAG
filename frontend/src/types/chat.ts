export interface ChatSource {
  source: string;
  page?: number | null;
  file_type?: string | null;
  score?: number | null;
}

export interface MessageItem {
  id: string;
  conversation_id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at?: string | null;
  sources?: ChatSource[];
  isPending?: boolean;
  isError?: boolean;
}

export interface ConversationItem {
  id: string;
  user_id: string;
  title?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ConversationCreateRequest {
  title?: string;
}

export interface MessageSendRequest {
  content: string;
}

export interface ConversationExchangeResponse {
  user_message: MessageItem;
  assistant_message: MessageItem;
  sources: ChatSource[];
}

export interface ConversationDeleteResponse {
  message: string;
  conversation_id: string;
}
