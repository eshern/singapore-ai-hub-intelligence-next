'use client';

import { useState } from 'react';
import { Menu, Trash2 } from 'lucide-react';
import { MessageList } from './MessageList';
import { InputBar } from './InputBar';
import { Sidebar } from '@/components/sidebar/Sidebar';
import { useChat } from '@/lib/hooks/useChat';

export function ChatInterface() {
  const { messages, isLoading, sendMessage, clearMessages } = useChat();
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50 dark:bg-slate-950">
      <Sidebar
        onSelectQuestion={sendMessage}
        mobileOpen={mobileSidebarOpen}
        onMobileClose={() => setMobileSidebarOpen(false)}
      />

      {/* Main panel */}
      <div className="flex flex-col flex-1 min-w-0">
        {/* Top bar */}
        <header className="flex items-center justify-between px-4 py-3 border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 flex-shrink-0">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setMobileSidebarOpen(true)}
              className="md:hidden p-1.5 rounded-lg text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
              aria-label="Open sidebar"
            >
              <Menu className="w-5 h-5" />
            </button>
            <div>
              <h1 className="text-sm font-semibold text-slate-800 dark:text-slate-200 leading-tight">
                Singapore AI Hub Intelligence
              </h1>
              <p className="text-[11px] text-slate-500 dark:text-slate-500">
                Multi-Agent RAG + Live Web Search
              </p>
            </div>
          </div>

          {messages.length > 0 && (
            <button
              onClick={clearMessages}
              className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400 hover:text-rose-600 dark:hover:text-rose-400 px-2.5 py-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" />
              Clear chat
            </button>
          )}
        </header>

        {/* Message list — scrollable */}
        <main className="flex-1 overflow-y-auto">
          <div className="max-w-4xl mx-auto h-full">
            <MessageList messages={messages} />
          </div>
        </main>

        {/* Fixed-at-bottom input bar */}
        <InputBar onSend={sendMessage} isLoading={isLoading} />
      </div>
    </div>
  );
}
