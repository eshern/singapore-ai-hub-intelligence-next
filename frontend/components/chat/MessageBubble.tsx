'use client';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { AgentBadgeRow } from './AgentBadgeRow';
import { TypingIndicator } from './TypingIndicator';
import { DebugPanel } from '@/components/debug/DebugPanel';
import { cn } from '@/lib/utils';
import type { ChatMessage } from '@/lib/types';

interface MessageBubbleProps {
  message: ChatMessage;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-2xl rounded-tr-sm px-4 py-3 bg-indigo-600 dark:bg-indigo-700 text-white text-sm leading-relaxed shadow-sm">
          {message.content}
        </div>
      </div>
    );
  }

  // Assistant message
  return (
    <div className="flex justify-start">
      <div className="max-w-[92%] space-y-1.5 min-w-0">
        <div className="flex items-start gap-3">
          {/* Avatar */}
          <div className="flex-shrink-0 mt-0.5 w-7 h-7 rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center text-white text-[10px] font-bold shadow-sm">
            AI
          </div>

          {/* Bubble */}
          <div
            className={cn(
              'flex-1 min-w-0 rounded-2xl rounded-tl-sm px-4 py-3 text-sm leading-relaxed shadow-sm',
              'bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700',
              message.isError &&
                'border-rose-200 dark:border-rose-800 bg-rose-50 dark:bg-rose-950/40',
            )}
          >
            {message.isStreaming && !message.content ? (
              <TypingIndicator />
            ) : (
              <div className="markdown-body">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {message.content}
                </ReactMarkdown>
              </div>
            )}
          </div>
        </div>

        {/* Agent badges */}
        {message.agents && message.agents.length > 0 && (
          <div className="ml-10">
            <AgentBadgeRow agents={message.agents} />
          </div>
        )}

        {/* Debug accordion — only shown when not streaming and debug data is present */}
        {!message.isStreaming &&
          (message.routingReason || message.agentOutputs || message.debugLog) && (
            <div className="ml-10">
              <DebugPanel
                routingReason={message.routingReason}
                agentOutputs={message.agentOutputs}
                debugLog={message.debugLog}
                latencyMs={message.latencyMs}
              />
            </div>
          )}
      </div>
    </div>
  );
}
