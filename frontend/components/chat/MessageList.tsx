'use client';

import { useEffect, useRef } from 'react';
import { MessageBubble } from './MessageBubble';
import type { ChatMessage } from '@/lib/types';

interface MessageListProps {
  messages: ChatMessage[];
}

export function MessageList({ messages }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center px-6 py-24 space-y-5">
        <span className="text-6xl" role="img" aria-label="Singapore flag">
          🇸🇬
        </span>
        <div className="space-y-2">
          <h2 className="text-xl font-semibold text-slate-700 dark:text-slate-300">
            Singapore AI Hub Intelligence
          </h2>
          <p className="text-sm text-slate-500 dark:text-slate-400 max-w-md">
            Ask about Singapore&apos;s AI strategy, EDB investment incentives,
            ASEAN regional comparisons, cybersecurity compliance, or the latest
            AI news and funding announcements.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-2 max-w-sm text-xs text-slate-400 dark:text-slate-500">
          <span className="px-2.5 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-800">🇸🇬 SG Policy</span>
          <span className="px-2.5 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-800">💼 Investment</span>
          <span className="px-2.5 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-800">🌏 ASEAN Compare</span>
          <span className="px-2.5 py-1.5 rounded-lg bg-slate-100 dark:bg-slate-800">🔒 Cybersecurity</span>
        </div>
        <p className="text-xs text-slate-400 dark:text-slate-500">
          Select a question from the sidebar or type your own below.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4 px-4 py-6">
      {messages.map(msg => (
        <MessageBubble key={msg.id} message={msg} />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
