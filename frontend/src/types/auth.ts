import type { User as SupabaseUser, Session as SupabaseSession } from '@supabase/supabase-js';

export interface UserProfile {
  id: string;
  email: string;
  created_at?: string;
  updated_at?: string;
}

export interface AuthContextType {
  user: SupabaseUser | null;
  session: SupabaseSession | null;
  profile: UserProfile | null;
  loading: boolean;
  signIn: (email: string, password: string) => Promise<{ error: Error | null }>;
  signUp: (email: string, password: string) => Promise<{ error: Error | null; user: SupabaseUser | null }>;
  signOut: () => Promise<void>;
}
