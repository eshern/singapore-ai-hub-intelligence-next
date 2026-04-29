'use client';

import { FormEvent, KeyboardEvent, useRef, useState } from 'react';
import { Send } from 'lucide-react';
import { cn } from '@/lib/utils';

interface InputBarProps {
  onSend: (question: string) => void;
  isLoading: boolean;
}

export function InputBar({ onSend, isLoading }: InputBarProps) {
  const [value, setValue] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    const q = value.trim();
    if (!q || isLoading) return;
    onSend(q);
    setValue('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const handleInput = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  };

  const canSend = value.trim().length > 0 && !isLoading;

  return (
    <div className="border-t border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-4 py-3 flex-shrink-0">
      <form onSubmit={submit} className="flex gap-2 items-end max-w-4xl mx-auto">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={e => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onInput={handleInput}
          placeholder="Ask about Singapore AI policy, EDB incentives, ASEAN comparisons… (Enter to send)"
          rows={1}
          disabled={isLoading}
          className={cn(
            'flex-1 resize-none rounded-xl border border-slate-200 dark:border-slate-700',
            'bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-slate-100',
            'placeholder:text-slate-400 dark:placeholder:text-slate-500',
            'px-4 py-2.5 text-sm leading-relaxed',
            'focus:outline-none focus:ring-2 focus:ring-indigo-500 dark:focus:ring-indigo-400 focus:border-transparent',
            'disabled:opacity-60 disabled:cursor-not-allowed transition-colors',
          )}
        />
        <button
          type="submit"
          disabled={!canSend}
          aria-label="Send message"
          className={cn(
            'flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center transition-colors',
            canSend
              ? 'bg-indigo-600 hover:bg-indigo-700 text-white shadow-sm'
              : 'bg-slate-200 dark:bg-slate-700 text-slate-400 dark:text-slate-500 cursor-not-allowed',
          )}
        >
          <Send className="w-4 h-4" />
        </button>
      </form>
      <p className="text-center text-[11px] text-slate-400 dark:text-slate-600 mt-2 max-w-4xl mx-auto">
        Powered by LangGraph · ChromaDB · Groq · DuckDuckGo &nbsp;|&nbsp; Shift+Enter for new line
      </p>
    </div>
  );
}
