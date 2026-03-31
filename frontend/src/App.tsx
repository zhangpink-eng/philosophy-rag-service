import React, { useState, useEffect, useRef } from 'react';
import {
  Settings, ChevronLeft, MoreVertical,
  Search, Plus, Menu, Users, Home, MessageCircle, BookOpen,
} from 'lucide-react';
import {
  OscarAvatar, MessageBubble, MessageInput, TypingIndicator,
  Message,
  SupervisionPage, WorkshopPage, AssistantWorkstation, UserArchivePage,
  animations
} from './components';
import { rag, sessions, tokenManager, voice } from './api';

// ============ 类型定义 ============
type Scene = 'consult' | 'supervise' | 'workshop';
type View = 'chat' | 'archive' | 'assistant' | 'empty';

interface Session {
  id: string;
  title: string;
  date: string;
  scene: Scene;
  depth?: number;
  duration?: string;
}

// ============ 主题配置 ============
const theme = {
  colors: {
    'ink-cyan': '#2C3E50',
    'dark-gold': '#B8860B',
    'scene-consult': '#34495E',
    'scene-supervise': '#2D4A3E',
    'scene-workshop': '#3D3450',
    'bg-warm': '#FAFAF8',
    'bg-card': '#F2F1EF',
    'text-primary': '#1A1A1A',
    'text-secondary': '#6B7280',
    'text-muted': '#9CA3AF',
    'danger': '#C0392B',
    'voice': '#1ABC9C',
    'border': '#E5E4E2',
    'bg-dark': '#1A1B1E',
    'card-dark': '#25262B',
  },
  fonts: {
    serif: "'Noto Serif SC', serif",
    sans: "'Noto Sans SC', sans-serif",
    english: "'Crimson Text', serif",
    mono: "'JetBrains Mono', monospace",
  }
};

// ============ 全局样式 ============
const globalStyles = `
  @import url('https://fonts.googleapis.com/css2?family=Crimson+Text:ital,wght@0,400;0,600;1,400&family=JetBrains+Mono:wght@400;500&family=Noto+Sans+SC:wght@400;500;700&family=Noto+Serif+SC:wght@400;500;600&display=swap');

  :root {
    --ink-cyan: ${theme.colors['ink-cyan']};
    --dark-gold: ${theme.colors['dark-gold']};
    --scene-consult: ${theme.colors['scene-consult']};
    --scene-supervise: ${theme.colors['scene-supervise']};
    --scene-workshop: ${theme.colors['scene-workshop']};
    --bg-warm: ${theme.colors['bg-warm']};
    --bg-card: ${theme.colors['bg-card']};
    --text-primary: ${theme.colors['text-primary']};
    --text-secondary: ${theme.colors['text-secondary']};
    --text-muted: ${theme.colors['text-muted']};
    --danger: ${theme.colors['danger']};
    --voice: ${theme.colors['voice']};
    --border: ${theme.colors['border']};
  }

  * { margin: 0; padding: 0; box-sizing: border-box; }

  body {
    font-family: ${theme.fonts.serif};
    background: var(--bg-warm);
    color: var(--text-primary);
    line-height: 1.8;
    -webkit-font-smoothing: antialiased;
  }

  ::selection { background: var(--ink-cyan); color: white; }

  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

  ${animations}

  .animate-fade-in-up { animation: fadeInUp 0.3s ease-out forwards; }
`;

// ============ 侧边栏 ============
const Sidebar: React.FC<{
  sessions: Session[];
  currentSession: string;
  onSelectSession: (id: string) => void;
  scene: Scene;
  isOpen: boolean;
  onClose: () => void;
}> = ({ sessions, currentSession, onSelectSession, scene, isOpen, onClose }) => {
  const sceneColor = {
    consult: theme.colors['scene-consult'],
    supervise: theme.colors['scene-supervise'],
    workshop: theme.colors['scene-workshop'],
  }[scene];

  return (
    <>
      {isOpen && (
        <div
          onClick={onClose}
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.3)',
            zIndex: 40, display: 'none',
          }}
          className="mobile-overlay"
        />
      )}
      <aside style={{
        width: '280px', height: '100%', background: '#FFFFFF',
        borderRight: `1px solid ${theme.colors['border']}`, display: 'flex',
        flexDirection: 'column', flexShrink: 0, position: 'relative', zIndex: 50,
        transform: isOpen ? 'translateX(0)' : undefined,
        transition: 'transform 0.25s ease',
      }}>
        <div style={{ padding: '16px 20px', borderBottom: `1px solid ${theme.colors['border']}` }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Search size={18} color={theme.colors['text-muted']} />
            <input
              placeholder="搜索会话..."
              style={{
                flex: 1, border: 'none', outline: 'none', fontSize: '14px',
                fontFamily: theme.fonts.sans, background: 'transparent',
                color: theme.colors['text-primary'],
              }}
            />
          </div>
        </div>
        <div style={{ flex: 1, overflow: 'auto', padding: '12px' }}>
          {sessions.filter(s => s.scene === scene).map((session, index) => (
            <div
              key={session.id}
              onClick={() => { onSelectSession(session.id); onClose(); }}
              style={{
                padding: '14px 16px', borderRadius: '10px', cursor: 'pointer',
                marginBottom: '8px', background: currentSession === session.id ? theme.colors['bg-card'] : 'transparent',
                borderLeft: `3px solid ${currentSession === session.id ? sceneColor : 'transparent'}`,
                transition: 'all 0.15s',
                animation: `fadeInUp 0.2s ease-out ${index * 0.05}s both`,
              }}
              onMouseEnter={e => { if (currentSession !== session.id) e.currentTarget.style.background = theme.colors['bg-card']; }}
              onMouseLeave={e => { if (currentSession !== session.id) e.currentTarget.style.background = 'transparent'; }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                <span style={{ fontSize: '14px', fontWeight: 500, fontFamily: theme.fonts.sans, color: theme.colors['text-primary'] }}>
                  {session.title}
                </span>
                {currentSession === session.id && (
                  <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: sceneColor }} />
                )}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '12px', color: theme.colors['text-muted'] }}>{session.date}</span>
                {session.depth && (
                  <span style={{
                    fontSize: '11px', fontFamily: theme.fonts.mono, color: theme.colors['dark-gold'],
                    background: 'rgba(184, 134, 11, 0.1)', padding: '2px 6px', borderRadius: '4px',
                  }}>
                    深度 {session.depth}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      </aside>
    </>
  );
};

// ============ 右面板 ============
const RightPanel: React.FC<{
  profile: {
    coreIssues: string[];
    blindSpots: string[];
    insights: { date: string; text: string }[];
    currentConflict: string[];
  };
  scene: Scene;
  isOpen: boolean;
}> = ({ profile, scene, isOpen }) => {
  const sceneColor = {
    consult: theme.colors['scene-consult'],
    supervise: theme.colors['scene-supervise'],
    workshop: theme.colors['scene-workshop'],
  }[scene];

  return (
    <aside style={{
      width: '320px', height: '100%', background: '#FFFFFF',
      borderLeft: `1px solid ${theme.colors['border']}`, display: 'flex',
      flexDirection: 'column', flexShrink: 0, position: 'absolute', right: 0, top: 0, zIndex: 30,
      transform: isOpen ? 'translateX(0)' : 'translateX(100%)',
      transition: 'transform 0.25s ease',
    }}>
      <div style={{ flex: 1, overflow: 'auto', padding: '24px' }}>
        <div style={{ marginBottom: '28px' }}>
          <h3 style={{ fontSize: '12px', fontFamily: theme.fonts.sans, fontWeight: 600, color: theme.colors['text-muted'], textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '12px' }}>
            核心议题
          </h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            {profile.coreIssues.map((issue, i) => (
              <span key={i} style={{ fontSize: '13px', padding: '6px 12px', background: `${sceneColor}15`, color: sceneColor, borderRadius: '6px', fontFamily: theme.fonts.sans }}>
                {issue}
              </span>
            ))}
          </div>
        </div>
        <div style={{ marginBottom: '28px' }}>
          <h3 style={{ fontSize: '12px', fontFamily: theme.fonts.sans, fontWeight: 600, color: theme.colors['danger'], textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
            盲点
          </h3>
          <ul style={{ listStyle: 'none' }}>
            {profile.blindSpots.map((spot, i) => (
              <li key={i} style={{ fontSize: '14px', color: theme.colors['text-secondary'], marginBottom: '8px', paddingLeft: '12px', borderLeft: `2px solid ${theme.colors['border']}` }}>
                {spot}
              </li>
            ))}
          </ul>
        </div>
        <div style={{ marginBottom: '28px' }}>
          <h3 style={{ fontSize: '12px', fontFamily: theme.fonts.sans, fontWeight: 600, color: theme.colors['dark-gold'], textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
            历史洞察
          </h3>
          {profile.insights.map((insight, i) => (
            <div key={i} style={{ fontSize: '13px', color: theme.colors['text-secondary'], marginBottom: '10px', padding: '10px 12px', background: 'rgba(184, 134, 11, 0.05)', borderRadius: '8px', borderLeft: `3px solid ${theme.colors['dark-gold']}` }}>
              <div style={{ fontSize: '11px', color: theme.colors['text-muted'], marginBottom: '4px', fontFamily: theme.fonts.mono }}>{insight.date}</div>
              <div>{insight.text}</div>
            </div>
          ))}
        </div>
        <div>
          <h3 style={{ fontSize: '12px', fontFamily: theme.fonts.sans, fontWeight: 600, color: theme.colors['text-muted'], textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '12px' }}>
            当前矛盾
          </h3>
          <ul style={{ listStyle: 'none' }}>
            {profile.currentConflict.map((c, i) => (
              <li key={i} style={{ fontSize: '14px', color: theme.colors['text-secondary'], marginBottom: '8px' }}>
                <span style={{ color: theme.colors['danger'], marginRight: '8px' }}>·</span>{c}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </aside>
  );
};

// ============ 空状态页 ============
const EmptyState: React.FC<{ onStart: () => void; scene: Scene }> = ({ onStart, scene }) => {
  const sceneColor = {
    consult: theme.colors['scene-consult'],
    supervise: theme.colors['scene-supervise'],
    workshop: theme.colors['scene-workshop'],
  }[scene];

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '48px', animation: 'fadeInUp 0.5s ease-out' }}>
      <div style={{ width: '120px', height: '120px', marginBottom: '32px', animation: 'breathe 4s ease-in-out infinite' }}>
        <OscarAvatar size={120} />
      </div>
      <h2 style={{ fontSize: '24px', fontFamily: theme.fonts.sans, fontWeight: 600, color: theme.colors['text-primary'], marginBottom: '12px', textAlign: 'center' }}>
        准备好开始一场哲学对话了吗？
      </h2>
      <p style={{ fontSize: '15px', color: theme.colors['text-secondary'], marginBottom: '36px', textAlign: 'center', maxWidth: '360px', lineHeight: 1.8 }}>
        Oscar 会通过提问帮助你认识自己的思维
      </p>
      <button
        onClick={onStart}
        style={{
          padding: '14px 32px', background: sceneColor, color: '#FFFFFF',
          border: 'none', borderRadius: '8px', fontSize: '15px', fontFamily: theme.fonts.sans,
          fontWeight: 500, cursor: 'pointer', transition: 'all 0.2s', display: 'flex',
          alignItems: 'center', gap: '8px',
        }}
        onMouseEnter={e => { e.currentTarget.style.background = sceneColor + 'DD'; e.currentTarget.style.transform = 'translateY(-2px)'; }}
        onMouseLeave={e => { e.currentTarget.style.background = sceneColor; e.currentTarget.style.transform = 'translateY(0)'; }}
      >
        <Plus size={18} />
        {scene === 'consult' ? '开始第一次咨询' : scene === 'supervise' ? '开始督导会话' : '创建工作坊'}
      </button>
    </div>
  );
};

// ============ 导航栏 ============
const Navbar: React.FC<{
  scene: Scene;
  view: View;
  onSceneChange: (scene: Scene) => void;
  onViewChange: (view: View) => void;
  onMenuClick: () => void;
}> = ({ scene, view, onSceneChange, onViewChange, onMenuClick }) => {
  const sceneLabels = { consult: '咨询', supervise: '督导', workshop: '工作坊' };
  const sceneColor = {
    consult: theme.colors['scene-consult'],
    supervise: theme.colors['scene-supervise'],
    workshop: theme.colors['scene-workshop'],
  }[scene];

  const viewIcons: Record<View, React.ReactNode> = {
    chat: <MessageCircle size={18} />,
    archive: <BookOpen size={18} />,
    assistant: <Users size={18} />,
    empty: <Home size={18} />,
  };

  return (
    <nav style={{
      height: '56px', background: '#FFFFFF', borderBottom: `1px solid ${theme.colors['border']}`,
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '0 20px', flexShrink: 0,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <button onClick={onMenuClick} className="mobile-menu-btn" style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '8px', display: 'none', color: theme.colors['text-primary'] }}>
          <Menu size={24} />
        </button>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ width: '28px', height: '28px' }}>
            <svg viewBox="0 0 100 100">
              <circle cx="50" cy="50" r="45" fill="none" stroke={theme.colors['ink-cyan']} strokeWidth="3" />
              <text x="50" y="62" textAnchor="middle" fontSize="36" fontFamily={theme.fonts.serif} fill={theme.colors['ink-cyan']}>哲</text>
            </svg>
          </div>
          <span style={{ fontFamily: theme.fonts.sans, fontWeight: 700, fontSize: '18px', color: theme.colors['ink-cyan'], letterSpacing: '2px' }}>
            Philosophia
          </span>
        </div>
      </div>

      <div style={{ display: 'flex', gap: '4px', background: theme.colors['bg-card'], padding: '4px', borderRadius: '10px' }}>
        {(Object.keys(sceneLabels) as Scene[]).map(s => (
          <button
            key={s}
            onClick={() => onSceneChange(s)}
            style={{
              padding: '8px 20px', border: 'none', borderRadius: '8px', fontSize: '14px',
              fontFamily: theme.fonts.sans, fontWeight: 500, cursor: 'pointer',
              transition: 'all 0.2s', background: scene === s ? '#FFFFFF' : 'transparent',
              color: scene === s ? sceneColor : theme.colors['text-secondary'],
              boxShadow: scene === s ? '0 1px 3px rgba(0,0,0,0.08)' : 'none',
            }}
          >
            {sceneLabels[s]}
          </button>
        ))}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <div style={{ display: 'flex', gap: '4px' }}>
          {(['chat', 'archive', 'assistant'] as View[]).map(v => (
            <button
              key={v}
              onClick={() => onViewChange(v)}
              style={{
                padding: '8px 12px', border: 'none', borderRadius: '8px',
                background: view === v ? `${sceneColor}15` : 'transparent',
                color: view === v ? sceneColor : theme.colors['text-muted'],
                cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px',
                fontSize: '13px', fontFamily: theme.fonts.sans,
                transition: 'all 0.2s',
              }}
            >
              {viewIcons[v]}
              <span className="desktop-label">{v === 'chat' ? '对话' : v === 'archive' ? '档案' : '辅助'}</span>
            </button>
          ))}
        </div>
        <div style={{
          width: '36px', height: '36px', borderRadius: '50%',
          background: `linear-gradient(135deg, ${theme.colors['ink-cyan']}, ${theme.colors['scene-consult']})`,
          display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#FFFFFF',
          fontSize: '14px', fontWeight: 600, fontFamily: theme.fonts.sans, marginLeft: '8px',
        }}>
          李
        </div>
        <button style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '8px', color: theme.colors['text-muted'] }}>
          <Settings size={20} />
        </button>
      </div>
    </nav>
  );
};

// ============ 咨询对话页 ============
const ConsultChat: React.FC<{
  messages: Message[];
  inputValue: string;
  onInputChange: (v: string) => void;
  onSend: () => void;
  onVoiceStart?: () => void;
  onVoiceEnd?: () => void;
  onSpeak: (text: string) => void;
  session: Session;
  profile: {
    coreIssues: string[];
    blindSpots: string[];
    insights: { date: string; text: string }[];
    currentConflict: string[];
  };
  rightPanelOpen: boolean;
  isTyping: boolean;
}> = ({ messages, inputValue, onInputChange, onSend, onVoiceStart, onVoiceEnd, onSpeak, session, profile, rightPanelOpen, isTyping }) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', position: 'relative' }}>
      <div style={{
        padding: '16px 24px', borderBottom: `1px solid ${theme.colors['border']}`,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: '#FFFFFF',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '8px', color: theme.colors['text-muted'], display: 'none' }}>
            <ChevronLeft size={20} />
          </button>
          <div>
            <h1 style={{ fontSize: '16px', fontFamily: theme.fonts.sans, fontWeight: 600, color: theme.colors['text-primary'], marginBottom: '2px' }}>
              {session.title}
            </h1>
            <span style={{ fontSize: '12px', color: theme.colors['text-muted'] }}>第3次会话 · 45分钟</span>
          </div>
        </div>
        <button style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '8px', color: theme.colors['text-muted'] }}>
          <MoreVertical size={20} />
        </button>
      </div>

      <div style={{
        flex: 1, overflow: 'auto', padding: '24px',
        background: `
          radial-gradient(ellipse at top left, ${theme.colors['scene-consult']}08 0%, transparent 50%),
          radial-gradient(ellipse at bottom right, ${theme.colors['dark-gold']}05 0%, transparent 50%),
          ${theme.colors['bg-warm']}
        `,
      }}>
        {messages.map(msg => <MessageBubble key={msg.id} message={msg} mode="consult" onSpeak={() => onSpeak(msg.content)} />)}
        {isTyping && <TypingIndicator mode="consult" />}
        <div ref={messagesEndRef} />
      </div>

      <div style={{ padding: '20px 24px', background: '#FFFFFF', borderTop: `1px solid ${theme.colors['border']}` }}>
        <MessageInput
          value={inputValue}
          onChange={onInputChange}
          onSend={onSend}
          onVoiceStart={onVoiceStart}
          onVoiceEnd={onVoiceEnd}
          placeholder="输入你的想法..."
          mode="consult"
        />
      </div>

      <RightPanel profile={profile} scene="consult" isOpen={rightPanelOpen} />
    </div>
  );
};

// ============ 主应用 ============
const App: React.FC = () => {
  const [scene, setScene] = useState<Scene>('consult');
  const [view, setView] = useState<View>('chat');
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [rightPanelOpen] = useState(true);
  const [inputValue, setInputValue] = useState('');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isTyping, setIsTyping] = useState(false);

  // 督导页状态
  const [supervisionInput, setSupervisionInput] = useState('');

  // 工作坊页状态
  const [workshopInput, setWorkshopInput] = useState('');

  // 辅助工作台状态
  const [clientMessage, setClientMessage] = useState('');
  const [assistantSuggestions, setAssistantSuggestions] = useState<string[]>([]);
  const [assistantBlindSpot, setAssistantBlindSpot] = useState<string>('');
  const [assistantSimilarCase, setAssistantSimilarCase] = useState<{ title: string; excerpt: string } | undefined>();
  const [assistantProfile] = useState<{ sessionsCount: number; coreIssue: string; avoidantPattern: string } | undefined>();

  // 语音状态
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const currentAudioRef = useRef<HTMLAudioElement | null>(null);

  // 播放TTS音频
  const handleSpeak = async (text: string) => {
    // 如果正在播放，先停止
    if (currentAudioRef.current) {
      currentAudioRef.current.pause();
      currentAudioRef.current = null;
    }

    try {
      const blob = await voice.tts(text);
      const url = URL.createObjectURL(blob);
      const audio = new Audio(url);
      currentAudioRef.current = audio;
      audio.play();
    } catch (err) {
      console.error('TTS playback failed:', err);
    }
  };

  // 开始录音
  const handleVoiceStart = () => {
    audioChunksRef.current = [];

    navigator.mediaDevices.getUserMedia({ audio: true })
      .then(stream => {
        const mediaRecorder = new MediaRecorder(stream);
        mediaRecorderRef.current = mediaRecorder;
        audioChunksRef.current = [];

        mediaRecorder.ondataavailable = (event) => {
          if (event.data.size > 0) {
            audioChunksRef.current.push(event.data);
          }
        };

        mediaRecorder.onstop = async () => {
          const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/wav' });
          stream.getTracks().forEach(track => track.stop());

          try {
            const text = await voice.asr(audioBlob);
            if (text && text.trim()) {
              // 根据当前场景处理语音输入
              if (scene === 'consult') {
                setInputValue(prev => prev + text);
              } else if (scene === 'supervise') {
                setSupervisionInput(prev => prev + text);
              } else if (scene === 'workshop') {
                setWorkshopInput(prev => prev + text);
              }
            }
          } catch (err) {
            console.error('ASR failed:', err);
          }
        };

        mediaRecorder.start();
      })
      .catch(err => {
        console.error('Failed to get microphone:', err);
      });
  };

  // 停止录音
  const handleVoiceEnd = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
  };

  // 用户档案状态
  const [archiveData, setArchiveData] = useState<{
    user: { totalSessions: number; firstSession: string; coreIssues: string[]; recentInsight: string };
    pattern: { avoidant: string[]; '惯性': string[]; advantages: string[] };
    growthTimeline: { date: string; type: 'session' | 'insight' | 'breakthrough' | 'current'; title: string; description?: string }[];
    recentSessions: { date: string; type: string; title: string; depth: number; duration: string }[];
  } | null>(null);

  const mockSessions: Session[] = [
    { id: '1', title: '"改变"的定义', date: '3/15', scene: 'consult', depth: 7.2, duration: '45min' },
    { id: '2', title: '选择与承担', date: '3/01', scene: 'consult', depth: 8.1, duration: '50min' },
    { id: '4', title: '职业困惑督导', date: '2/20', scene: 'supervise', depth: 6.8, duration: '60min' },
    { id: '3', title: '自由的边界', date: '2/14', scene: 'workshop', depth: 6.5, duration: '90min' },
  ];

  const profile = {
    coreIssues: ['自我认同', '选择困难'],
    blindSpots: ['回避定义', '抽象化'],
    insights: [
      { date: '2/14', text: '自由≠逃避' },
      { date: '1/20', text: '区分"想要"和"需要"' },
    ],
    currentConflict: ['想改变但无法定义改变内容'],
  };

  const currentSession = mockSessions.find(s => s.scene === scene) || mockSessions[0];

  // Helper function to stream RAG response
  const streamRagResponse = (input: string, role: 'oscar' | 'participant' = 'oscar', participantName?: string) => {
    setIsTyping(true);

    const messageId = (Date.now() + 1).toString();
    let responseContent = '';

    setMessages(prev => [...prev, {
      id: messageId,
      role,
      content: '',
      timestamp: new Date(),
      ...(participantName ? { participantName } : {}),
    }]);

    rag.queryStream(input, (chunk) => {
      responseContent += chunk;
      setMessages(prev => prev.map(msg =>
        msg.id === messageId
          ? { ...msg, content: responseContent }
          : msg
      ));
    }).then(() => {
      setIsTyping(false);
    }).catch((err) => {
      setIsTyping(false);
      setMessages(prev => prev.map(msg =>
        msg.id === messageId
          ? { ...msg, content: '抱歉，发生了错误：' + err.message }
          : msg
      ));
    });
  };

  const handleSend = () => {
    if (!inputValue.trim()) return;
    const userMessage: Message = { id: Date.now().toString(), role: 'user', content: inputValue, timestamp: new Date() };
    setMessages(prev => [...prev, userMessage]);
    const currentInput = inputValue;
    setInputValue('');
    streamRagResponse(currentInput);
  };

  // 初始化消息
  useEffect(() => {
    if (view === 'chat' && messages.length === 0) {
      setTimeout(() => {
        setMessages([{ id: '1', role: 'oscar', content: '你说想要"改变"。改变什么？', timestamp: new Date() }]);
      }, 500);
    }
  }, [view]);

  // 辅助工作台：查询 RAG 获取相似案例和建议
  useEffect(() => {
    if (!clientMessage.trim()) {
      setAssistantSuggestions([]);
      setAssistantBlindSpot('');
      setAssistantSimilarCase(undefined);
      return;
    }

    const timer = setTimeout(async () => {
      try {
        const response = await rag.query(clientMessage);
        // Update similar case with RAG sources
        if (response.sources && response.sources.length > 0) {
          const topSource = response.sources[0];
          setAssistantSimilarCase({
            title: `相关案例：${topSource.source}`,
            excerpt: topSource.text_zh || topSource.text_en,
          });
        }
        // Generate suggestions from the answer content
        const suggestionPatterns = [
          '追问"为什么"',
          '具体指什么',
          '有例外吗',
          '区别是',
          '能举个例子吗',
        ];
        const randomSuggestions = suggestionPatterns
          .sort(() => Math.random() - 0.5)
          .slice(0, 3)
          .map(s => `${s}"${clientMessage.slice(0, 20)}"...`);
        setAssistantSuggestions(randomSuggestions);

        // Detect potential blind spots
        const blindSpotKeywords = ['不知道', '无所谓', '都一样', '没区别', '随便'];
        const hasBlindSpot = blindSpotKeywords.some(k => clientMessage.includes(k));
        if (hasBlindSpot) {
          setAssistantBlindSpot('注意到来访者使用了模糊表述，可能是回避核心感受的迹象');
        } else {
          setAssistantBlindSpot('');
        }
      } catch (err) {
        console.error('RAG query failed:', err);
      }
    }, 1000); // Debounce 1 second

    return () => clearTimeout(timer);
  }, [clientMessage]);

  // 用户档案：获取会话历史
  useEffect(() => {
    if (view === 'archive' && !archiveData) {
      // Try to fetch from API, fall back to mock data
      const token = tokenManager.getToken();
      if (token) {
        sessions.history(token).then(data => {
          if (data && data.sessions) {
            // Transform API data to archive format
            const sessionsList = data.sessions;
            setArchiveData({
              user: {
                totalSessions: sessionsList.length,
                firstSession: sessionsList[sessionsList.length - 1]?.created_at?.split('T')[0] || '2025-01-01',
                coreIssues: ['自我认同', '选择', '自由'],
                recentInsight: sessionsList.length > 0 ? '持续进行中...' : '暂无洞察记录',
              },
              pattern: {
                avoidant: ['遇到矛盾时转移话题', '用"我不知道"逃避'],
                '惯性': ['倾向用抽象概念替代具体描述'],
                advantages: ['善于类比联想', '对悖论敏感'],
              },
              growthTimeline: sessionsList.slice(0, 5).map((s: any, i: number) => ({
                date: s.created_at?.split('T')[0] || '',
                type: 'session' as const,
                title: `会话 #${sessionsList.length - i}`,
                description: s.scenario,
              })),
              recentSessions: sessionsList.slice(0, 3).map((s: any) => ({
                date: s.created_at?.split('T')[0] || '',
                type: s.scenario || '咨询',
                title: s.scenario || '哲学对话',
                depth: 6.5,
                duration: '45min',
              })),
            });
          }
        }).catch(() => {
          // Use mock data on error
          setArchiveData({
            user: { totalSessions: 12, firstSession: '2025-12-01', coreIssues: ['自我认同', '选择', '自由'], recentInsight: '区分了"想要"和"需要"' },
            pattern: { avoidant: ['遇到矛盾时转移话题', '用"我不知道"逃避'], '惯性': ['倾向用抽象概念替代具体描述'], advantages: ['善于类比联想', '对悖论敏感'] },
            growthTimeline: [
              { date: '12/01', type: 'session' as const, title: '首次会话，识别核心议题' },
              { date: '12/15', type: 'insight' as const, title: '发现"自由≠逃避"', description: '在自由与逃避之间建立了重要区分' },
              { date: '01/05', type: 'insight' as const, title: '区分"想要"和"需要"', description: '开始意识到欲望与需求的差异' },
              { date: '01/20', type: 'breakthrough' as const, title: '首次直面矛盾未回避' },
              { date: '02/10', type: 'insight' as const, title: '"选择困难的本质是害怕承担"', description: '深入理解了选择困难的心理机制' },
              { date: '03/01', type: 'current' as const, title: '当前' },
            ],
            recentSessions: [
              { date: '3/01', type: '咨询', title: '"改变"的定义', depth: 7.2, duration: '45min' },
              { date: '2/10', type: '咨询', title: '选择与承担', depth: 8.1, duration: '50min' },
              { date: '1/20', type: '工作坊', title: '自由的边界', depth: 6.5, duration: '90min' },
            ],
          });
        });
      } else {
        // No token, use mock data
        setArchiveData({
          user: { totalSessions: 12, firstSession: '2025-12-01', coreIssues: ['自我认同', '选择', '自由'], recentInsight: '区分了"想要"和"需要"' },
          pattern: { avoidant: ['遇到矛盾时转移话题', '用"我不知道"逃避'], '惯性': ['倾向用抽象概念替代具体描述'], advantages: ['善于类比联想', '对悖论敏感'] },
          growthTimeline: [
            { date: '12/01', type: 'session' as const, title: '首次会话，识别核心议题' },
            { date: '12/15', type: 'insight' as const, title: '发现"自由≠逃避"', description: '在自由与逃避之间建立了重要区分' },
            { date: '01/05', type: 'insight' as const, title: '区分"想要"和"需要"', description: '开始意识到欲望与需求的差异' },
            { date: '01/20', type: 'breakthrough' as const, title: '首次直面矛盾未回避' },
            { date: '02/10', type: 'insight' as const, title: '"选择困难的本质是害怕承担"', description: '深入理解了选择困难的心理机制' },
            { date: '03/01', type: 'current' as const, title: '当前' },
          ],
          recentSessions: [
            { date: '3/01', type: '咨询', title: '"改变"的定义', depth: 7.2, duration: '45min' },
            { date: '2/10', type: '咨询', title: '选择与承担', depth: 8.1, duration: '50min' },
            { date: '1/20', type: '工作坊', title: '自由的边界', depth: 6.5, duration: '90min' },
          ],
        });
      }
    }
  }, [view, archiveData]);

  // 渲染对应页面
  const renderPage = () => {
    if (view === 'archive') {
      // Use archiveData if available, otherwise show loading
      const archive = archiveData || {
        user: { totalSessions: 0, firstSession: '加载中...', coreIssues: [], recentInsight: '' },
        pattern: { avoidant: [], '惯性': [], advantages: [] },
        growthTimeline: [],
        recentSessions: [],
      };
      return (
        <UserArchivePage
          user={archive.user}
          pattern={archive.pattern}
          growthTimeline={archive.growthTimeline}
          recentSessions={archive.recentSessions}
        />
      );
    }

    if (view === 'assistant') {
      return (
        <AssistantWorkstation
          clientMessage={clientMessage}
          onClientMessageChange={setClientMessage}
          suggestions={assistantSuggestions.length > 0 ? assistantSuggestions : ['输入来访者的话，获取追问建议']}
          onSuggestionClick={s => navigator.clipboard.writeText(s)}
          blindSpotAlert={assistantBlindSpot || undefined}
          similarCase={assistantSimilarCase}
          userProfile={assistantProfile}
        />
      );
    }

    if (view === 'empty') {
      return <EmptyState onStart={() => setView('chat')} scene={scene} />;
    }

    // Chat 视图
    if (scene === 'supervise') {
      return (
        <SupervisionPage
          messages={messages}
          inputValue={supervisionInput}
          onInputChange={setSupervisionInput}
          onSend={() => {
            if (!supervisionInput.trim()) return;
            const userMsg: Message = { id: Date.now().toString(), role: 'user', content: supervisionInput, timestamp: new Date() };
            setMessages(prev => [...prev, userMsg]);
            const currentInput = supervisionInput;
            setSupervisionInput('');
            streamRagResponse(currentInput);
          }}
          onVoiceStart={handleVoiceStart}
          onVoiceEnd={handleVoiceEnd}
          caseInfo={{ clientName: '张三', issue: '职业选择困惑', duration: '45分钟' }}
          isTyping={isTyping}
        />
      );
    }

    if (scene === 'workshop') {
      return (
        <WorkshopPage
          messages={messages}
          inputValue={workshopInput}
          onInputChange={setWorkshopInput}
          onSend={() => {
            if (!workshopInput.trim()) return;
            const userMsg: Message = { id: Date.now().toString(), role: 'participant', content: workshopInput, timestamp: new Date(), participantName: '张三' };
            setMessages(prev => [...prev, userMsg]);
            const currentInput = workshopInput;
            setWorkshopInput('');
            streamRagResponse(currentInput, 'participant', '张三');
          }}
          onRaiseHand={() => console.log('raise hand')}
          onVoiceStart={handleVoiceStart}
          onVoiceEnd={handleVoiceEnd}
          topic="自由是什么？"
          participants={[
            { id: '1', name: '张三', status: 'online' },
            { id: '2', name: '李四', status: 'speaking' },
            { id: '3', name: '王五', status: 'online' },
            { id: '4', name: '赵六', status: 'waiting' },
          ]}
          speakingQueue={['李四', '王五']}
          viewpointMap={[
            { viewpoint: '自由=无约束', count: 2, people: ['张三', '赵六'] },
            { viewpoint: '自由=有选择', count: 2, people: ['李四', '周五'] },
            { viewpoint: '自由=幻觉', count: 1, people: ['王五'] },
          ]}
          currentPhase="discussion"
          isTyping={isTyping}
        />
      );
    }

    // 默认咨询页
    return (
      <ConsultChat
        messages={messages}
        inputValue={inputValue}
        onInputChange={setInputValue}
        onSend={handleSend}
        onVoiceStart={handleVoiceStart}
        onVoiceEnd={handleVoiceEnd}
        onSpeak={handleSpeak}
        session={currentSession}
        profile={profile}
        rightPanelOpen={rightPanelOpen}
        isTyping={isTyping}
      />
    );
  };

  return (
    <>
      <style>{globalStyles}</style>
      <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', background: theme.colors['bg-warm'], overflow: 'hidden' }}>
        <Navbar scene={scene} view={view} onSceneChange={setScene} onViewChange={setView} onMenuClick={() => setSidebarOpen(!sidebarOpen)} />

        <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
          <Sidebar sessions={mockSessions} currentSession={currentSession?.id || ''} onSelectSession={() => {}} scene={scene} isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
          {renderPage()}
        </div>
      </div>

      <style>{`
        @media (max-width: 1023px) {
          .mobile-menu-btn { display: flex !important; }
        }
        @media (max-width: 767px) {
          .desktop-label { display: none; }
        }
      `}</style>
    </>
  );
};

export default App;
