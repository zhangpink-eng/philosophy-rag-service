// API Service for Philosophia RAG
// Base API URL
const API_BASE = 'http://localhost:8000';

// Types
export interface User {
  id: string;
  name: string;
  email: string;
}

export interface Message {
  id: string;
  role: 'oscar' | 'user';
  content: string;
  timestamp: Date;
}

export interface Session {
  id: string;
  user_id: string;
  scenario: 'consult' | 'supervise' | 'workshop';
  status: 'scheduled' | 'in_progress' | 'completed' | 'cancelled';
  dialogue_history: Array<{ role: string; content: string; timestamp: string }>;
}

export interface QueryResponse {
  answer: string;
  sources: Array<{
    text_zh: string;
    text_en: string;
    source: string;
    score: number;
  }>;
}

// Auth API
export const auth = {
  login: async (email: string, password: string) => {
    const res = await fetch(`${API_BASE}/api/users/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) throw new Error('Login failed');
    return res.json();
  },

  register: async (name: string, email: string, password: string) => {
    const res = await fetch(`${API_BASE}/api/users/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, email, password }),
    });
    if (!res.ok) throw new Error('Register failed');
    return res.json();
  },

  getProfile: async (token: string) => {
    const res = await fetch(`${API_BASE}/api/users/me/profile`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) throw new Error('Get profile failed');
    return res.json();
  },
};

// RAG Query API (no auth required for testing)
export const rag = {
  query: async (question: string): Promise<QueryResponse> => {
    const res = await fetch(`${API_BASE}/api/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: question }),
    });
    if (!res.ok) throw new Error('Query failed');
    return res.json();
  },

  queryStream: async (question: string, onChunk: (chunk: string) => void) => {
    const res = await fetch(`${API_BASE}/api/query/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: question }),
    });

    if (!res.ok) throw new Error('Stream query failed');

    const reader = res.body?.getReader();
    const decoder = new TextDecoder();

    while (reader) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value);
      // Parse SSE format: data: {...}\n\n
      chunk.split('\n').forEach(line => {
        if (line.startsWith('data: ')) {
          const data = line.slice(6).trim();
          if (data && data !== '[DONE]') {
            onChunk(data);
          }
        }
      });
    }
  },
};

// Session API
export const sessions = {
  start: async (token: string, scenario: string = 'consultation') => {
    const res = await fetch(`${API_BASE}/api/sessions/start`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ scenario }),
    });
    if (!res.ok) throw new Error('Start session failed');
    return res.json();
  },

  addMessage: async (token: string, sessionId: string, role: string, content: string) => {
    const res = await fetch(`${API_BASE}/api/sessions/message`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ session_id: sessionId, role, content }),
    });
    if (!res.ok) throw new Error('Add message failed');
    return res.json();
  },

  end: async (token: string, sessionId: string) => {
    const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/end`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({}),
    });
    if (!res.ok) throw new Error('End session failed');
    return res.json();
  },

  history: async (token: string, limit: number = 20) => {
    const res = await fetch(`${API_BASE}/api/sessions/history?limit=${limit}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) throw new Error('Get history failed');
    return res.json();
  },

  get: async (token: string, sessionId: string) => {
    const res = await fetch(`${API_BASE}/api/sessions/${sessionId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) throw new Error('Get session failed');
    return res.json();
  },
};

// Health check
export const health = {
  check: async () => {
    const res = await fetch(`${API_BASE}/`);
    return res.ok;
  },
};

// Voice API (TTS & ASR)
export const voice = {
  // Text-to-Speech: Convert text to audio
  tts: async (text: string, voice: string = "zh-CN-XiaoxiaoNeural"): Promise<Blob> => {
    const res = await fetch(`${API_BASE}/api/voice/tts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text, voice }),
    });
    if (!res.ok) throw new Error('TTS failed');
    return res.blob();
  },

  // Automatic Speech Recognition: Convert audio to text
  asr: async (audioBlob: Blob, language: string = "zh"): Promise<string> => {
    const formData = new FormData();
    formData.append('file', audioBlob, 'audio.wav');
    formData.append('language', language);

    const res = await fetch(`${API_BASE}/api/voice/asr`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) throw new Error('ASR failed');
    const data = await res.json();
    return data.text || '';
  },
};

// Local storage keys
const TOKEN_KEY = 'philosophia_token';
const USER_KEY = 'philosophia_user';

// Token management
export const tokenManager = {
  getToken: () => localStorage.getItem(TOKEN_KEY),
  setToken: (token: string) => localStorage.setItem(TOKEN_KEY, token),
  removeToken: () => localStorage.removeItem(TOKEN_KEY),
  getUser: () => {
    const userStr = localStorage.getItem(USER_KEY);
    return userStr ? JSON.parse(userStr) : null;
  },
  setUser: (user: User) => localStorage.setItem(USER_KEY, JSON.stringify(user)),
  removeUser: () => localStorage.removeItem(USER_KEY),
  clear: () => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  },
};
