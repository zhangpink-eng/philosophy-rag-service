import React, { useState, useEffect, useRef } from 'react';
import {
  FileText, Send, Mic, Volume2, Hand, Clock, Sparkles,
  AlertTriangle, BookOpen, TrendingUp,
  User, Mic2, Lightbulb,
  BarChart3, Zap, ChevronRight
} from 'lucide-react';

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
    'insight-bg': '#FFFDF5',
    'workshop-fire': '#E74C3C',
  },
  fonts: {
    serif: "'Noto Serif SC', serif",
    sans: "'Noto Sans SC', sans-serif",
    english: "'Crimson Text', serif",
    mono: "'JetBrains Mono', monospace",
  }
};

// ============ Oscar 头像组件 ============
export const OscarAvatar: React.FC<{ size?: number; thinking?: boolean; mode?: 'consult' | 'supervise' | 'workshop' }> = ({
  size = 40,
  thinking = false,
  mode = 'consult'
}) => {
  const borderColor = {
    consult: theme.colors['scene-consult'],
    supervise: theme.colors['scene-supervise'],
    workshop: theme.colors['scene-workshop'],
  }[mode];

  return (
    <svg width={size} height={size} viewBox="0 0 100 100" style={{ flexShrink: 0 }}>
      <circle cx="50" cy="50" r="48" fill="none" stroke={borderColor} strokeWidth="2" />
      <circle cx="50" cy="38" r="16" fill="none" stroke={borderColor} strokeWidth="1.5" />
      <circle cx="44" cy="36" r="5" fill="none" stroke={borderColor} strokeWidth="1.5" />
      <circle cx="56" cy="36" r="5" fill="none" stroke={borderColor} strokeWidth="1.5" />
      <line x1="49" y1="36" x2="51" y2="36" stroke={borderColor} strokeWidth="1.5" />
      <path d="M30 85 Q35 65 50 62 Q65 65 70 85" fill="none" stroke={borderColor} strokeWidth="1.5" strokeLinecap="round" />
      {thinking && (
        <g transform="translate(70, 25)">
          <circle cx="0" cy="0" r="3" fill={theme.colors['dark-gold']} opacity="0.6">
            <animate attributeName="opacity" values="0.3;1;0.3" dur="1.5s" repeatCount="indefinite" />
          </circle>
          <circle cx="12" cy="0" r="3" fill={theme.colors['dark-gold']} opacity="0.6">
            <animate attributeName="opacity" values="0.3;1;0.3" dur="1.5s" begin="0.2s" repeatCount="indefinite" />
          </circle>
          <circle cx="24" cy="0" r="3" fill={theme.colors['dark-gold']} opacity="0.6">
            <animate attributeName="opacity" values="0.3;1;0.3" dur="1.5s" begin="0.4s" repeatCount="indefinite" />
          </circle>
        </g>
      )}
    </svg>
  );
};

// ============ 打字指示器 ============
export const TypingIndicator: React.FC<{ mode?: 'consult' | 'supervise' | 'workshop' }> = ({ mode = 'consult' }) => (
  <div style={{
    display: 'flex', alignItems: 'center', gap: '6px',
    padding: '12px 16px', background: theme.colors['bg-card'],
    borderRadius: '16px 16px 16px 4px', width: 'fit-content',
    animation: 'fadeInUp 0.2s ease-out'
  }}>
    <OscarAvatar size={32} thinking mode={mode} />
    <div style={{ display: 'flex', gap: '4px', marginLeft: '8px' }}>
      {[0, 1, 2].map(i => (
        <div key={i} style={{
          width: '6px', height: '6px', borderRadius: '50%',
          background: theme.colors['text-muted'],
          animation: `typing 1.5s ease-in-out infinite`,
          animationDelay: `${i * 0.2}s`
        }} />
      ))}
    </div>
  </div>
);

// ============ 洞察标记 ============
export const InsightMarker: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div style={{
    display: 'flex', justifyContent: 'center', margin: '20px 0',
    animation: 'fadeInUp 0.4s ease-out'
  }}>
    <div style={{
      background: theme.colors['insight-bg'],
      border: `1px dashed ${theme.colors['dark-gold']}`,
      borderRadius: '12px', padding: '14px 20px',
      maxWidth: '420px', width: 'fit-content',
      display: 'flex', alignItems: 'flex-start', gap: '10px',
    }}>
      <Sparkles size={18} color={theme.colors['dark-gold']} style={{ marginTop: '2px', flexShrink: 0 }} />
      <div style={{ color: theme.colors['dark-gold'], fontSize: '14px', lineHeight: 1.7 }}>
        {children}
      </div>
    </div>
  </div>
);

// ============ 沉默气泡 ============
export const SilenceBubble: React.FC = () => (
  <div style={{
    display: 'flex', justifyContent: 'flex-start', margin: '16px 0',
    paddingLeft: '56px', animation: 'fadeInUp 0.3s ease-out'
  }}>
    <div style={{
      color: theme.colors['text-muted'], fontSize: '28px',
      letterSpacing: '6px', fontStyle: 'italic', fontFamily: theme.fonts.english,
    }}>
      ……
    </div>
  </div>
);

// ============ 消息气泡 ============
export interface Message {
  id: string;
  role: 'oscar' | 'user' | 'system' | 'participant';
  content: string;
  timestamp: Date;
  isInsight?: boolean;
  isStreaming?: boolean;
  isSilence?: boolean;
  participantName?: string;
}

interface MessageBubbleProps {
  message: Message;
  onSpeak?: () => void;
  mode?: 'consult' | 'supervise' | 'workshop';
}

export const MessageBubble: React.FC<MessageBubbleProps> = ({ message, onSpeak, mode = 'consult' }) => {
  const isOscar = message.role === 'oscar';
  const isSystem = message.role === 'system';
  const isParticipant = message.role === 'participant';
  const isSilence = message.isSilence;

  if (isSystem) {
    return (
      <InsightMarker>
        {message.content}
      </InsightMarker>
    );
  }

  if (isSilence) {
    return <SilenceBubble />;
  }

  const bubbleBg = isOscar || isParticipant
    ? theme.colors['bg-card']
    : isSystem
      ? 'transparent'
      : mode === 'consult'
        ? theme.colors['scene-consult']
        : mode === 'supervise'
          ? theme.colors['scene-supervise']
          : theme.colors['scene-workshop'];

  const textColor = isOscar || isParticipant
    ? theme.colors['text-primary']
    : '#FFFFFF';

  return (
    <div style={{
      display: 'flex', justifyContent: isOscar || isParticipant ? 'flex-start' : 'flex-end',
      margin: '12px 0', animation: 'fadeInUp 0.3s ease-out'
    }}>
      <div style={{
        display: 'flex', flexDirection: isOscar || isParticipant ? 'row' : 'row-reverse',
        alignItems: 'flex-start', gap: '12px', maxWidth: '72%',
      }}>
        {isOscar && <OscarAvatar size={40} mode={mode} />}
        {isParticipant && (
          <div style={{
            width: 36, height: 36, borderRadius: '50%',
            background: theme.colors['scene-workshop'],
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: '#fff', fontSize: '12px', fontWeight: 600,
            flexShrink: 0,
          }}>
            {message.participantName?.charAt(0) || 'P'}
          </div>
        )}
        <div style={{
          background: bubbleBg, color: textColor, padding: '14px 18px',
          borderRadius: isOscar || isParticipant
            ? '16px 16px 16px 4px'
            : '16px 16px 4px 16px',
          fontSize: '15px', lineHeight: 1.8, position: 'relative',
          fontFamily: theme.fonts.serif,
        }}>
          {isParticipant && (
            <div style={{
              fontSize: '11px', fontWeight: 600, marginBottom: '6px',
              color: theme.colors['text-muted'], fontFamily: theme.fonts.sans,
            }}>
              {message.participantName}
            </div>
          )}
          <span>{message.content}</span>
          {message.isStreaming && (
            <span style={{
              display: 'inline-block', width: '2px', height: '18px',
              background: textColor, marginLeft: '2px',
              animation: 'blink 1s step-end infinite', verticalAlign: 'middle'
            }} />
          )}
          {isOscar && onSpeak && (
            <button
              onClick={onSpeak}
              style={{
                position: 'absolute', top: '8px', right: '8px',
                background: 'none', border: 'none', cursor: 'pointer',
                color: theme.colors['text-muted'], padding: '4px',
                borderRadius: '50%', display: 'flex', alignItems: 'center',
                justifyContent: 'center', transition: 'all 0.2s',
              }}
              onMouseEnter={e => {
                e.currentTarget.style.color = theme.colors['voice'];
                e.currentTarget.style.background = 'rgba(26, 188, 156, 0.1)';
              }}
              onMouseLeave={e => {
                e.currentTarget.style.color = theme.colors['text-muted'];
                e.currentTarget.style.background = 'none';
              }}
            >
              <Volume2 size={16} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

// ============ 输入框 ============
interface MessageInputProps {
  value: string;
  onChange: (v: string) => void;
  onSend: () => void;
  onVoiceStart?: () => void;
  onVoiceEnd?: () => void;
  placeholder?: string;
  mode: 'consult' | 'supervise' | 'workshop';
  disabled?: boolean;
}

export const MessageInput: React.FC<MessageInputProps> = ({
  value, onChange, onSend, onVoiceStart, onVoiceEnd,
  placeholder, mode, disabled
}) => {
  const [isRecording, setIsRecording] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 160) + 'px';
    }
  }, [value]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  const sceneColor = {
    consult: theme.colors['scene-consult'],
    supervise: theme.colors['scene-supervise'],
    workshop: theme.colors['scene-workshop'],
  }[mode];

  return (
    <div style={{
      display: 'flex', alignItems: 'flex-end', gap: '12px',
      background: '#FFFFFF', border: `1px solid ${theme.colors['border']}`,
      borderRadius: '24px', padding: '8px 8px 8px 20px',
      transition: 'border-color 0.2s, box-shadow 0.2s',
    }}>
      <textarea
        ref={textareaRef}
        value={value}
        onChange={e => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder || '输入你的想法...'}
        rows={1}
        disabled={disabled}
        style={{
          flex: 1, border: 'none', outline: 'none', fontSize: '16px',
          fontFamily: theme.fonts.serif, lineHeight: 1.6, resize: 'none',
          background: 'transparent', color: theme.colors['text-primary'],
          minHeight: '32px', maxHeight: '160px',
        }}
      />
      <button
        onMouseDown={() => { setIsRecording(true); onVoiceStart?.(); }}
        onMouseUp={() => { setIsRecording(false); onVoiceEnd?.(); }}
        onTouchStart={() => { setIsRecording(true); onVoiceStart?.(); }}
        onTouchEnd={() => { setIsRecording(false); onVoiceEnd?.(); }}
        style={{
          width: '44px', height: '44px', borderRadius: '50%', border: 'none',
          background: isRecording ? theme.colors['voice'] : 'transparent',
          cursor: 'pointer', display: 'flex', alignItems: 'center',
          justifyContent: 'center', transition: 'all 0.2s', position: 'relative',
        }}
      >
        {isRecording && (
          <span style={{
            position: 'absolute', width: '100%', height: '100%', borderRadius: '50%',
            border: `2px solid ${theme.colors['voice']}`,
            animation: 'pulse 1.5s ease-out infinite',
          }} />
        )}
        <Mic size={20} color={isRecording ? '#FFFFFF' : theme.colors['text-muted']} />
      </button>
      <button
        onClick={onSend}
        disabled={!value.trim() || disabled}
        style={{
          width: '44px', height: '44px', borderRadius: '50%', border: 'none',
          background: value.trim() && !disabled ? sceneColor : theme.colors['border'],
          cursor: value.trim() && !disabled ? 'pointer' : 'not-allowed',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          transition: 'all 0.2s',
        }}
      >
        <Send size={18} color="#FFFFFF" />
      </button>
    </div>
  );
};

// ============ 督导页面 ============
interface SupervisionPageProps {
  messages: Message[];
  inputValue: string;
  onInputChange: (v: string) => void;
  onSend: () => void;
  onVoiceStart?: () => void;
  onVoiceEnd?: () => void;
  caseInfo: {
    clientName: string;
    issue: string;
    duration: string;
  };
  isTyping?: boolean;
}

export const SupervisionPage: React.FC<SupervisionPageProps> = ({
  messages, inputValue, onInputChange, onSend, onVoiceStart, onVoiceEnd, caseInfo, isTyping
}) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div style={{ flex: 1, display: 'flex', overflow: 'hidden', position: 'relative' }}>
      {/* 左侧案例信息 */}
      <div style={{
        width: '260px', background: '#FFFFFF', borderRight: `1px solid ${theme.colors['border']}`,
        padding: '24px', display: 'flex', flexDirection: 'column', gap: '24px',
        flexShrink: 0, overflow: 'auto',
      }}>
        <div>
          <h3 style={{
            fontSize: '11px', fontFamily: theme.fonts.sans, fontWeight: 600,
            color: theme.colors['text-muted'], textTransform: 'uppercase',
            letterSpacing: '1px', marginBottom: '12px',
          }}>
            案例信息
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div>
              <div style={{ fontSize: '12px', color: theme.colors['text-muted'], marginBottom: '4px' }}>来访者</div>
              <div style={{ fontSize: '14px', fontWeight: 500, color: theme.colors['text-primary'] }}>
                {caseInfo.clientName}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: theme.colors['text-muted'], marginBottom: '4px' }}>议题</div>
              <div style={{ fontSize: '14px', color: theme.colors['text-primary'] }}>
                {caseInfo.issue}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: theme.colors['text-muted'], marginBottom: '4px' }}>咨询时长</div>
              <div style={{ fontSize: '14px', color: theme.colors['text-primary'] }}>
                {caseInfo.duration}
              </div>
            </div>
          </div>
        </div>

        <div>
          <h3 style={{
            fontSize: '11px', fontFamily: theme.fonts.sans, fontWeight: 600,
            color: theme.colors['text-muted'], textTransform: 'uppercase',
            letterSpacing: '1px', marginBottom: '12px',
          }}>
            方法论参考
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {['苏格拉底追问', '矛盾暴露', '极端推演', '概念澄清'].map((tech, i) => (
              <div key={i} style={{
                padding: '10px 12px', background: theme.colors['bg-card'],
                borderRadius: '8px', fontSize: '13px', color: theme.colors['text-secondary'],
                borderLeft: `3px solid ${theme.colors['scene-supervise']}`,
              }}>
                {tech}
              </div>
            ))}
          </div>
        </div>

        <div>
          <h3 style={{
            fontSize: '11px', fontFamily: theme.fonts.sans, fontWeight: 600,
            color: theme.colors['text-muted'], textTransform: 'uppercase',
            letterSpacing: '1px', marginBottom: '12px',
          }}>
            相关案例
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {['案例#12: 职业困惑', '案例#28: 选择困难'].map((c, i) => (
              <div key={i} style={{
                padding: '10px 12px', background: 'rgba(184, 134, 11, 0.05)',
                borderRadius: '8px', fontSize: '13px', color: theme.colors['dark-gold'],
                cursor: 'pointer', transition: 'all 0.2s',
              }}
              onMouseEnter={e => e.currentTarget.style.background = 'rgba(184, 134, 11, 0.1)'}
              onMouseLeave={e => e.currentTarget.style.background = 'rgba(184, 134, 11, 0.05)'}
              >
                {c}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 中间对话区域 */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{
          padding: '16px 24px', borderBottom: `1px solid ${theme.colors['border']}`,
          background: '#FFFFFF', display: 'flex', alignItems: 'center', gap: '12px',
        }}>
          <div style={{
            padding: '4px 12px', background: `${theme.colors['scene-supervise']}15`,
            borderRadius: '6px', fontSize: '12px', fontWeight: 500,
            color: theme.colors['scene-supervise'], fontFamily: theme.fonts.sans,
          }}>
            督导模式
          </div>
          <span style={{ fontSize: '15px', fontWeight: 600, color: theme.colors['text-primary'] }}>
            督导会话
          </span>
        </div>

        <div style={{
          flex: 1, overflow: 'auto', padding: '24px',
          background: `
            radial-gradient(ellipse at top left, ${theme.colors['scene-supervise']}10 0%, transparent 50%),
            radial-gradient(ellipse at bottom right, ${theme.colors['dark-gold']}05 0%, transparent 50%),
            ${theme.colors['bg-warm']}
          `,
        }}>
          {messages.map(msg => (
            <MessageBubble key={msg.id} message={msg} mode="supervise" />
          ))}
          {isTyping && <TypingIndicator mode="supervise" />}
          <div ref={messagesEndRef} />
        </div>

        <div style={{
          padding: '20px 24px', background: '#FFFFFF',
          borderTop: `1px solid ${theme.colors['border']}`,
        }}>
          <MessageInput
            value={inputValue}
            onChange={onInputChange}
            onSend={onSend}
            onVoiceStart={onVoiceStart}
            onVoiceEnd={onVoiceEnd}
            placeholder="描述你的咨询情境..."
            mode="supervise"
          />
        </div>
      </div>
    </div>
  );
};

// ============ 工作坊页面 ============
interface WorkshopPageProps {
  messages: Message[];
  inputValue: string;
  onInputChange: (v: string) => void;
  onSend: () => void;
  onRaiseHand: () => void;
  onVoiceStart?: () => void;
  onVoiceEnd?: () => void;
  topic: string;
  participants: { id: string; name: string; status: 'online' | 'speaking' | 'waiting' | 'offline' }[];
  speakingQueue: string[];
  viewpointMap: { viewpoint: string; count: number; people: string[] }[];
  currentPhase: 'viewpoint' | 'discussion' | 'summary';
  isTyping?: boolean;
}

export const WorkshopPage: React.FC<WorkshopPageProps> = ({
  messages, inputValue, onInputChange, onSend, onRaiseHand, onVoiceStart, onVoiceEnd,
  topic, participants, speakingQueue, viewpointMap, currentPhase, isTyping
}) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const statusColors = {
    online: theme.colors['voice'],
    speaking: theme.colors['dark-gold'],
    waiting: theme.colors['text-muted'],
    offline: theme.colors['border'],
  };

  return (
    <div style={{ flex: 1, display: 'flex', overflow: 'hidden', position: 'relative' }}>
      {/* 左侧参与者列表 */}
      <div style={{
        width: '220px', background: '#FFFFFF', borderRight: `1px solid ${theme.colors['border']}`,
        display: 'flex', flexDirection: 'column', flexShrink: 0,
      }}>
        <div style={{ padding: '20px', borderBottom: `1px solid ${theme.colors['border']}` }}>
          <h3 style={{
            fontSize: '11px', fontFamily: theme.fonts.sans, fontWeight: 600,
            color: theme.colors['text-muted'], textTransform: 'uppercase',
            letterSpacing: '1px', marginBottom: '12px',
          }}>
            参与者 ({participants.length})
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {participants.map(p => (
              <div key={p.id} style={{
                display: 'flex', alignItems: 'center', gap: '10px',
                padding: '8px', borderRadius: '8px',
                background: p.status === 'speaking' ? `${theme.colors['dark-gold']}10` : 'transparent',
              }}>
                <div style={{
                  width: '10px', height: '10px', borderRadius: '50%',
                  background: statusColors[p.status], flexShrink: 0,
                }} />
                <span style={{ fontSize: '13px', color: theme.colors['text-primary'], flex: 1 }}>
                  {p.name}
                </span>
                {p.status === 'speaking' && <Mic2 size={12} color={theme.colors['dark-gold']} />}
              </div>
            ))}
          </div>
        </div>

        <div style={{ padding: '20px', flex: 1, overflow: 'auto' }}>
          <h3 style={{
            fontSize: '11px', fontFamily: theme.fonts.sans, fontWeight: 600,
            color: theme.colors['text-muted'], textTransform: 'uppercase',
            letterSpacing: '1px', marginBottom: '12px',
          }}>
            发言队列
          </h3>
          {speakingQueue.length === 0 ? (
            <div style={{ fontSize: '13px', color: theme.colors['text-muted'], fontStyle: 'italic' }}>
              暂无排队
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {speakingQueue.map((name, i) => (
                <div key={i} style={{
                  display: 'flex', alignItems: 'center', gap: '8px',
                  fontSize: '13px', color: theme.colors['text-secondary'],
                }}>
                  <span style={{ fontWeight: 600, color: theme.colors['text-muted'] }}>{i + 1}.</span>
                  {name}
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={{ padding: '16px', borderTop: `1px solid ${theme.colors['border']}` }}>
          <button
            onClick={onRaiseHand}
            style={{
              width: '100%', padding: '12px', borderRadius: '8px', border: 'none',
              background: theme.colors['scene-workshop'], color: '#FFFFFF',
              fontSize: '14px', fontWeight: 500, cursor: 'pointer',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
              transition: 'all 0.2s',
            }}
            onMouseEnter={e => e.currentTarget.style.opacity = '0.9'}
            onMouseLeave={e => e.currentTarget.style.opacity = '1'}
          >
            <Hand size={16} /> 举手发言
          </button>
        </div>
      </div>

      {/* 中间对话区域 */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{
          padding: '16px 24px', borderBottom: `1px solid ${theme.colors['border']}`,
          background: '#FFFFFF', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              padding: '4px 12px', background: `${theme.colors['scene-workshop']}15`,
              borderRadius: '6px', fontSize: '12px', fontWeight: 500,
              color: theme.colors['scene-workshop'], fontFamily: theme.fonts.sans,
            }}>
              工作坊
            </div>
            <span style={{ fontSize: '15px', fontWeight: 600, color: theme.colors['text-primary'] }}>
              {topic}
            </span>
          </div>
          <div style={{
            display: 'flex', alignItems: 'center', gap: '16px',
            fontSize: '13px', color: theme.colors['text-muted'],
          }}>
            <span>参与者 {participants.length}</span>
            <span style={{
              padding: '2px 8px', background: theme.colors['bg-card'],
              borderRadius: '4px', fontFamily: theme.fonts.mono,
            }}>
              {currentPhase === 'viewpoint' ? '观点收集' : currentPhase === 'discussion' ? '讨论中' : '总结'}
            </span>
          </div>
        </div>

        <div style={{
          flex: 1, overflow: 'auto', padding: '24px',
          background: `
            radial-gradient(ellipse at top left, ${theme.colors['scene-workshop']}10 0%, transparent 50%),
            ${theme.colors['bg-warm']}
          `,
        }}>
          {messages.map(msg => (
            <MessageBubble key={msg.id} message={msg} mode="workshop" />
          ))}
          {isTyping && <TypingIndicator mode="workshop" />}
          <div ref={messagesEndRef} />
        </div>

        <div style={{
          padding: '20px 24px', background: '#FFFFFF',
          borderTop: `1px solid ${theme.colors['border']}`,
        }}>
          <MessageInput
            value={inputValue}
            onChange={onInputChange}
            onSend={onSend}
            onVoiceStart={onVoiceStart}
            onVoiceEnd={onVoiceEnd}
            placeholder="输入你的观点..."
            mode="workshop"
          />
        </div>
      </div>

      {/* 右侧观点地图 */}
      <div style={{
        width: '280px', background: '#FFFFFF', borderLeft: `1px solid ${theme.colors['border']}`,
        padding: '24px', display: 'flex', flexDirection: 'column', gap: '24px',
        flexShrink: 0, overflow: 'auto',
      }}>
        <div>
          <h3 style={{
            fontSize: '11px', fontFamily: theme.fonts.sans, fontWeight: 600,
            color: theme.colors['text-muted'], textTransform: 'uppercase',
            letterSpacing: '1px', marginBottom: '16px',
            display: 'flex', alignItems: 'center', gap: '6px',
          }}>
            <BarChart3 size={14} /> 观点地图
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {viewpointMap.map((item, i) => (
              <div key={i} style={{
                padding: '12px', background: theme.colors['bg-card'],
                borderRadius: '10px', position: 'relative', overflow: 'hidden',
              }}>
                <div style={{
                  position: 'absolute', left: 0, top: 0, bottom: 0, width: '3px',
                  background: i === 0 ? theme.colors['workshop-fire'] : theme.colors['scene-workshop'],
                }} />
                <div style={{ fontSize: '14px', fontWeight: 500, marginBottom: '8px', paddingLeft: '8px' }}>
                  {item.viewpoint}
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', paddingLeft: '8px' }}>
                  {item.people.map((person, j) => (
                    <span key={j} style={{
                      fontSize: '11px', padding: '2px 8px', borderRadius: '4px',
                      background: '#FFFFFF', color: theme.colors['text-secondary'],
                    }}>
                      {person} ✓
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div>
          <h3 style={{
            fontSize: '11px', fontFamily: theme.fonts.sans, fontWeight: 600,
            color: theme.colors['workshop-fire'], textTransform: 'uppercase',
            letterSpacing: '1px', marginBottom: '12px',
            display: 'flex', alignItems: 'center', gap: '6px',
          }}>
            <Zap size={14} /> 核心张力
          </h3>
          <div style={{
            padding: '12px', background: `rgba(231, 76, 60, 0.05)`,
            borderRadius: '10px', border: `1px dashed rgba(231, 76, 60, 0.3)`,
            fontSize: '13px', color: theme.colors['text-secondary'],
          }}>
            无约束 vs 有选择
          </div>
        </div>
      </div>
    </div>
  );
};

// ============ 咨询师辅助工作台 ============
interface AssistantWorkstationProps {
  clientMessage: string;
  onClientMessageChange: (v: string) => void;
  suggestions: string[];
  onSuggestionClick: (suggestion: string) => void;
  blindSpotAlert?: string;
  similarCase?: { title: string; excerpt: string };
  userProfile?: {
    sessionsCount: number;
    coreIssue: string;
    avoidantPattern: string;
  };
}

export const AssistantWorkstation: React.FC<AssistantWorkstationProps> = ({
  clientMessage, onClientMessageChange, suggestions, onSuggestionClick,
  blindSpotAlert, similarCase, userProfile
}) => {
  return (
    <div style={{ flex: 1, display: 'flex', overflow: 'hidden', position: 'relative' }}>
      {/* 左侧对话监控 */}
      <div style={{
        flex: 1, display: 'flex', flexDirection: 'column',
        borderRight: `1px solid ${theme.colors['border']}`,
      }}>
        <div style={{
          padding: '16px 24px', borderBottom: `1px solid ${theme.colors['border']}`,
          background: '#FFFFFF',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <div style={{
              padding: '4px 12px', background: `${theme.colors['ink-cyan']}15`,
              borderRadius: '6px', fontSize: '12px', fontWeight: 500,
              color: theme.colors['ink-cyan'], fontFamily: theme.fonts.sans,
            }}>
              咨询师工作台
            </div>
            <span style={{ fontSize: '14px', color: theme.colors['text-secondary'] }}>
              当前会话：张三 · 第5次
            </span>
          </div>
        </div>

        <div style={{
          flex: 1, padding: '24px', overflow: 'auto',
          background: theme.colors['bg-warm'],
        }}>
          {/* 模拟对话 */}
          <div style={{ maxWidth: '600px', margin: '0 auto' }}>
            <div style={{
              padding: '16px 20px', background: theme.colors['bg-card'],
              borderRadius: '12px', marginBottom: '16px', fontSize: '14px',
            }}>
              <div style={{ fontSize: '11px', color: theme.colors['text-muted'], marginBottom: '8px' }}>
                咨询师
              </div>
              你觉得这份工作最让你痛苦的是什么？
            </div>

            <div style={{
              padding: '16px 20px', background: '#FFFFFF',
              borderRadius: '12px', marginBottom: '16px', fontSize: '14px',
              border: `1px solid ${theme.colors['border']}`,
            }}>
              <div style={{ fontSize: '11px', color: theme.colors['text-muted'], marginBottom: '8px' }}>
                来访者
              </div>
              就是...每天都很累，没有意义。
            </div>

            <div style={{
              padding: '16px 20px', background: theme.colors['bg-card'],
              borderRadius: '12px', marginBottom: '16px', fontSize: '14px',
            }}>
              <div style={{ fontSize: '11px', color: theme.colors['text-muted'], marginBottom: '8px' }}>
                咨询师
              </div>
              什么样的工作对你来说是有意义的？
            </div>
          </div>
        </div>

        <div style={{
          padding: '16px 24px', background: '#FFFFFF',
          borderTop: `1px solid ${theme.colors['border']}`,
        }}>
          <textarea
            value={clientMessage}
            onChange={e => onClientMessageChange(e.target.value)}
            placeholder="咨询师输入记录..."
            style={{
              width: '100%', minHeight: '80px', padding: '12px',
              border: `1px solid ${theme.colors['border']}`, borderRadius: '8px',
              fontSize: '14px', fontFamily: theme.fonts.serif, resize: 'none',
              outline: 'none', lineHeight: 1.6,
            }}
          />
          <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
            <button style={{
              padding: '8px 16px', background: theme.colors['bg-card'],
              border: 'none', borderRadius: '6px', fontSize: '13px',
              cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px',
              color: theme.colors['text-secondary'],
            }}>
              <FileText size={14} /> 粘贴对话
            </button>
            <button style={{
              padding: '8px 16px', background: theme.colors['bg-card'],
              border: 'none', borderRadius: '6px', fontSize: '13px',
              cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px',
              color: theme.colors['text-secondary'],
            }}>
              <Mic size={14} /> 语音输入
            </button>
          </div>
        </div>
      </div>

      {/* 右侧AI辅助面板 */}
      <div style={{
        width: '360px', background: '#FFFFFF', padding: '24px',
        display: 'flex', flexDirection: 'column', gap: '24px',
        overflow: 'auto', flexShrink: 0,
      }}>
        {/* 盲点提醒 */}
        {blindSpotAlert && (
          <div style={{
            padding: '14px 16px', background: 'rgba(192, 57, 43, 0.08)',
            borderRadius: '10px', border: `1px solid rgba(192, 57, 43, 0.2)`,
            display: 'flex', gap: '12px', animation: 'fadeInUp 0.3s ease-out',
          }}>
            <AlertTriangle size={18} color={theme.colors['danger']} style={{ flexShrink: 0, marginTop: '2px' }} />
            <div>
              <div style={{
                fontSize: '12px', fontWeight: 600, color: theme.colors['danger'],
                marginBottom: '6px',
              }}>
                盲点提醒
              </div>
              <div style={{ fontSize: '13px', color: theme.colors['text-secondary'], lineHeight: 1.6 }}>
                {blindSpotAlert}
              </div>
            </div>
          </div>
        )}

        {/* 追问建议 */}
        <div>
          <h3 style={{
            fontSize: '11px', fontFamily: theme.fonts.sans, fontWeight: 600,
            color: theme.colors['text-muted'], textTransform: 'uppercase',
            letterSpacing: '1px', marginBottom: '12px',
            display: 'flex', alignItems: 'center', gap: '6px',
          }}>
            <Lightbulb size={14} /> 追问建议
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {suggestions.map((s, i) => (
              <div
                key={i}
                onClick={() => onSuggestionClick(s)}
                style={{
                  padding: '14px 16px', background: theme.colors['bg-card'],
                  borderRadius: '10px', cursor: 'pointer', transition: 'all 0.2s',
                  border: '1px solid transparent',
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.borderColor = theme.colors['ink-cyan'];
                  e.currentTarget.style.background = `${theme.colors['ink-cyan']}08`;
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.borderColor = 'transparent';
                  e.currentTarget.style.background = theme.colors['bg-card'];
                }}
              >
                <div style={{ fontSize: '13px', color: theme.colors['text-primary'], lineHeight: 1.6 }}>
                  {s}
                </div>
                <div style={{
                  fontSize: '11px', color: theme.colors['text-muted'], marginTop: '8px',
                  fontFamily: theme.fonts.sans,
                }}>
                  点击复制
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* 类似案例 */}
        {similarCase && (
          <div>
            <h3 style={{
              fontSize: '11px', fontFamily: theme.fonts.sans, fontWeight: 600,
              color: theme.colors['text-muted'], textTransform: 'uppercase',
              letterSpacing: '1px', marginBottom: '12px',
              display: 'flex', alignItems: 'center', gap: '6px',
            }}>
              <BookOpen size={14} /> Oscar 类似案例
            </h3>
            <div style={{
              padding: '14px 16px', background: 'rgba(184, 134, 11, 0.05)',
              borderRadius: '10px', borderLeft: `3px solid ${theme.colors['dark-gold']}`,
            }}>
              <div style={{ fontSize: '14px', fontWeight: 500, marginBottom: '8px' }}>
                {similarCase.title}
              </div>
              <div style={{ fontSize: '13px', color: theme.colors['text-secondary'], lineHeight: 1.6 }}>
                {similarCase.excerpt}
              </div>
              <div style={{
                fontSize: '12px', color: theme.colors['dark-gold'], marginTop: '10px',
                cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px',
              }}>
                查看完整案例 <ChevronRight size={12} />
              </div>
            </div>
          </div>
        )}

        {/* 用户画像速览 */}
        {userProfile && (
          <div>
            <h3 style={{
              fontSize: '11px', fontFamily: theme.fonts.sans, fontWeight: 600,
              color: theme.colors['text-muted'], textTransform: 'uppercase',
              letterSpacing: '1px', marginBottom: '12px',
              display: 'flex', alignItems: 'center', gap: '6px',
            }}>
              <User size={14} /> 用户画像速览
            </h3>
            <div style={{
              padding: '14px 16px', background: theme.colors['bg-card'],
              borderRadius: '10px',
            }}>
              <div style={{ marginBottom: '12px' }}>
                <div style={{ fontSize: '11px', color: theme.colors['text-muted'], marginBottom: '4px' }}>
                  总会话
                </div>
                <div style={{ fontSize: '24px', fontWeight: 600, color: theme.colors['ink-cyan'] }}>
                  {userProfile.sessionsCount}次
                </div>
              </div>
              <div style={{ marginBottom: '12px' }}>
                <div style={{ fontSize: '11px', color: theme.colors['text-muted'], marginBottom: '4px' }}>
                  核心议题
                </div>
                <div style={{ fontSize: '13px', color: theme.colors['text-primary'] }}>
                  {userProfile.coreIssue}
                </div>
              </div>
              <div>
                <div style={{ fontSize: '11px', color: theme.colors['danger'], marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  <AlertTriangle size={10} /> 反复回避
                </div>
                <div style={{ fontSize: '13px', color: theme.colors['text-secondary'] }}>
                  {userProfile.avoidantPattern}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

// ============ 用户成长档案页 ============
interface GrowthTimelineItem {
  date: string;
  type: 'session' | 'insight' | 'breakthrough' | 'current';
  title: string;
  description?: string;
}

interface UserArchivePageProps {
  user: {
    totalSessions: number;
    firstSession: string;
    coreIssues: string[];
    recentInsight: string;
  };
  pattern: {
    avoidant: string[];
   惯性: string[];
    advantages: string[];
  };
  growthTimeline: GrowthTimelineItem[];
  recentSessions: {
    date: string;
    type: string;
    title: string;
    depth: number;
    duration: string;
  }[];
}

export const UserArchivePage: React.FC<UserArchivePageProps> = ({
  user, pattern, growthTimeline, recentSessions
}) => {
  return (
    <div style={{
      flex: 1, overflow: 'auto', padding: '32px',
      background: `
        radial-gradient(ellipse at top, ${theme.colors['ink-cyan']}05 0%, transparent 50%),
        ${theme.colors['bg-warm']}
      `,
    }}>
      <div style={{ maxWidth: '800px', margin: '0 auto' }}>
        {/* 总览卡片 */}
        <div style={{
          background: '#FFFFFF', borderRadius: '16px', padding: '28px',
          marginBottom: '24px', boxShadow: '0 2px 12px rgba(0,0,0,0.04)',
        }}>
          <h1 style={{
            fontSize: '22px', fontFamily: theme.fonts.sans, fontWeight: 600,
            marginBottom: '20px', color: theme.colors['text-primary'],
          }}>
            我的思维档案
          </h1>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '24px' }}>
            <div>
              <div style={{ fontSize: '12px', color: theme.colors['text-muted'], marginBottom: '6px' }}>
                总会话次数
              </div>
              <div style={{ fontSize: '28px', fontWeight: 700, color: theme.colors['ink-cyan'] }}>
                {user.totalSessions}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: theme.colors['text-muted'], marginBottom: '6px' }}>
                首次会话
              </div>
              <div style={{ fontSize: '16px', fontWeight: 500, color: theme.colors['text-primary'] }}>
                {user.firstSession}
              </div>
            </div>
            <div>
              <div style={{ fontSize: '12px', color: theme.colors['text-muted'], marginBottom: '6px' }}>
                最近洞察
              </div>
              <div style={{ fontSize: '14px', color: theme.colors['dark-gold'] }}>
                {user.recentInsight}
              </div>
            </div>
          </div>
          <div style={{ marginTop: '20px', display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            {user.coreIssues.map((issue, i) => (
              <span key={i} style={{
                padding: '6px 14px', borderRadius: '20px',
                background: `${theme.colors['ink-cyan']}10`,
                color: theme.colors['ink-cyan'], fontSize: '13px', fontWeight: 500,
              }}>
                {issue}
              </span>
            ))}
          </div>
        </div>

        {/* 思维模式 */}
        <div style={{
          background: '#FFFFFF', borderRadius: '16px', padding: '28px',
          marginBottom: '24px', boxShadow: '0 2px 12px rgba(0,0,0,0.04)',
        }}>
          <h2 style={{
            fontSize: '16px', fontFamily: theme.fonts.sans, fontWeight: 600,
            marginBottom: '20px', color: theme.colors['text-primary'],
          }}>
            思维模式
          </h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '20px' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                <div style={{
                  width: '12px', height: '12px', borderRadius: '50%',
                  background: theme.colors['danger'],
                }} />
                <span style={{ fontSize: '13px', fontWeight: 600, color: theme.colors['danger'] }}>
                  回避模式
                </span>
              </div>
              <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {pattern.avoidant.map((item, i) => (
                  <li key={i} style={{ fontSize: '13px', color: theme.colors['text-secondary'], paddingLeft: '20px', position: 'relative' }}>
                    <span style={{ position: 'absolute', left: '8px', color: theme.colors['danger'] }}>·</span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                <div style={{
                  width: '12px', height: '12px', borderRadius: '50%',
                  background: theme.colors['text-muted'],
                }} />
                <span style={{ fontSize: '13px', fontWeight: 600, color: theme.colors['text-secondary'] }}>
                  思维惯性
                </span>
              </div>
              <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {pattern['惯性'].map((item, i) => (
                  <li key={i} style={{ fontSize: '13px', color: theme.colors['text-secondary'], paddingLeft: '20px', position: 'relative' }}>
                    <span style={{ position: 'absolute', left: '8px', color: theme.colors['text-muted'] }}>·</span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                <div style={{
                  width: '12px', height: '12px', borderRadius: '50%',
                  background: theme.colors['voice'],
                }} />
                <span style={{ fontSize: '13px', fontWeight: 600, color: theme.colors['voice'] }}>
                  思维优势
                </span>
              </div>
              <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {pattern.advantages.map((item, i) => (
                  <li key={i} style={{ fontSize: '13px', color: theme.colors['text-secondary'], paddingLeft: '20px', position: 'relative' }}>
                    <span style={{ position: 'absolute', left: '8px', color: theme.colors['voice'] }}>·</span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                <TrendingUp size={14} color={theme.colors['dark-gold']} />
                <span style={{ fontSize: '13px', fontWeight: 600, color: theme.colors['dark-gold'] }}>
                  成长趋势
                </span>
              </div>
              <div style={{ fontSize: '13px', color: theme.colors['text-secondary'], paddingLeft: '22px' }}>
                对话深度 ↑ 持续提升<br/>
                回避频率 ↓ 逐步减少
              </div>
            </div>
          </div>
        </div>

        {/* 成长时间线 */}
        <div style={{
          background: '#FFFFFF', borderRadius: '16px', padding: '28px',
          marginBottom: '24px', boxShadow: '0 2px 12px rgba(0,0,0,0.04)',
        }}>
          <h2 style={{
            fontSize: '16px', fontFamily: theme.fonts.sans, fontWeight: 600,
            marginBottom: '24px', color: theme.colors['text-primary'],
            display: 'flex', alignItems: 'center', gap: '8px',
          }}>
            <Clock size={18} /> 成长时间线
          </h2>
          <div style={{ position: 'relative', paddingLeft: '32px' }}>
            <div style={{
              position: 'absolute', left: '7px', top: '8px', bottom: '8px',
              width: '2px', background: theme.colors['border'],
            }} />
            {growthTimeline.map((item, i) => (
              <div key={i} style={{
                position: 'relative', marginBottom: i === growthTimeline.length - 1 ? 0 : '28px',
              }}>
                <div style={{
                  position: 'absolute', left: '-29px', top: '4px',
                  width: '14px', height: '14px', borderRadius: '50%',
                  background: item.type === 'current'
                    ? theme.colors['ink-cyan']
                    : item.type === 'insight' || item.type === 'breakthrough'
                      ? theme.colors['dark-gold']
                      : theme.colors['text-muted'],
                  border: '3px solid #FFFFFF',
                  boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
                }} />
                <div style={{ fontSize: '12px', color: theme.colors['text-muted'], marginBottom: '4px', fontFamily: theme.fonts.mono }}>
                  {item.date}
                </div>
                <div style={{ fontSize: '14px', fontWeight: 500, color: theme.colors['text-primary'], marginBottom: '4px' }}>
                  {item.title}
                </div>
                {item.description && (
                  <div style={{ fontSize: '13px', color: theme.colors['text-secondary'] }}>
                    {item.description}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* 历史会话 */}
        <div style={{
          background: '#FFFFFF', borderRadius: '16px', padding: '28px',
          boxShadow: '0 2px 12px rgba(0,0,0,0.04)',
        }}>
          <h2 style={{
            fontSize: '16px', fontFamily: theme.fonts.sans, fontWeight: 600,
            marginBottom: '16px', color: theme.colors['text-primary'],
          }}>
            历史会话
          </h2>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {recentSessions.map((session, i) => (
              <div key={i} style={{
                padding: '16px', background: theme.colors['bg-card'],
                borderRadius: '10px', display: 'flex', alignItems: 'center',
                justifyContent: 'space-between', cursor: 'pointer',
                transition: 'all 0.2s',
              }}
              onMouseEnter={e => e.currentTarget.style.background = `${theme.colors['ink-cyan']}08`}
              onMouseLeave={e => e.currentTarget.style.background = theme.colors['bg-card']}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
                    <span style={{ fontSize: '13px', color: theme.colors['text-muted'] }}>{session.date}</span>
                    <span style={{
                      fontSize: '11px', padding: '2px 8px', borderRadius: '4px',
                      background: theme.colors['bg-warm'], color: theme.colors['text-secondary'],
                    }}>
                      {session.type}
                    </span>
                  </div>
                  <div style={{ fontSize: '14px', fontWeight: 500, color: theme.colors['text-primary'] }}>
                    {session.title}
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '11px', color: theme.colors['text-muted'] }}>深度</div>
                    <div style={{ fontSize: '14px', fontWeight: 600, color: theme.colors['dark-gold'] }}>
                      {session.depth}
                    </div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '11px', color: theme.colors['text-muted'] }}>时长</div>
                    <div style={{ fontSize: '14px', color: theme.colors['text-secondary'] }}>
                      {session.duration}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

// ============ 动画样式 ============
export const animations = `
  @keyframes fadeInUp {
    from { opacity: 0; transform: translateY(12px); }
    to { opacity: 1; transform: translateY(0); }
  }
  @keyframes typing {
    0%, 60%, 100% { opacity: 0.2; }
    30% { opacity: 1; }
  }
  @keyframes pulse {
    0%, 100% { transform: scale(1); opacity: 0.8; }
    50% { transform: scale(1.5); opacity: 0; }
  }
  @keyframes blink {
    0%, 50% { opacity: 1; }
    51%, 100% { opacity: 0; }
  }
  @keyframes breathe {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.02); }
  }
`;
