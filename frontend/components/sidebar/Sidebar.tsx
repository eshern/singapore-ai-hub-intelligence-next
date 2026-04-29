'use client';

import { useState } from 'react';
import { Bot, ChevronLeft, ChevronRight, Lightbulb, X } from 'lucide-react';
import { SuggestedQueries } from './SuggestedQueries';
import { AgentRoster } from './AgentRoster';
import { ThemeToggle } from '@/components/ThemeToggle';
import { cn } from '@/lib/utils';

interface SidebarProps {
  onSelectQuestion: (q: string) => void;
  mobileOpen: boolean;
  onMobileClose: () => void;
}

function SidebarContent({
  onSelectQuestion,
  onMobileClose,
  collapsed,
  setCollapsed,
}: {
  onSelectQuestion: (q: string) => void;
  onMobileClose: () => void;
  collapsed: boolean;
  setCollapsed: (v: (prev: boolean) => boolean) => void;
}) {
  const [tab, setTab] = useState<'questions' | 'agents'>('questions');

  return (
    <>
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-3 border-b border-slate-200 dark:border-slate-700 flex-shrink-0 min-h-[52px]">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-xl flex-shrink-0" role="img" aria-label="Singapore">🇸🇬</span>
          {!collapsed && (
            <div className="min-w-0">
              <p className="text-xs font-bold text-slate-800 dark:text-slate-200 leading-tight truncate">
                SG AI Hub
              </p>
              <p className="text-[10px] text-slate-500 dark:text-slate-500 truncate">
                Investment Intelligence
              </p>
            </div>
          )}
        </div>
        <div className="flex items-center gap-0.5 flex-shrink-0">
          <ThemeToggle />
          {/* Mobile close */}
          <button
            onClick={onMobileClose}
            className="md:hidden p-1.5 rounded-lg text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            aria-label="Close sidebar"
          >
            <X className="w-4 h-4" />
          </button>
          {/* Desktop collapse */}
          <button
            onClick={() => setCollapsed(v => !v)}
            className="hidden md:flex p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed ? (
              <ChevronRight className="w-4 h-4" />
            ) : (
              <ChevronLeft className="w-4 h-4" />
            )}
          </button>
        </div>
      </div>

      {!collapsed && (
        <>
          {/* Tab switcher */}
          <div className="flex border-b border-slate-200 dark:border-slate-700 flex-shrink-0">
            {(
              [
                { id: 'questions', label: 'Questions', Icon: Lightbulb },
                { id: 'agents', label: 'Agents', Icon: Bot },
              ] as const
            ).map(({ id, label, Icon }) => (
              <button
                key={id}
                onClick={() => setTab(id)}
                className={cn(
                  'flex-1 flex items-center justify-center gap-1.5 py-2.5 text-xs font-medium transition-colors',
                  tab === id
                    ? 'text-indigo-600 dark:text-indigo-400 border-b-2 border-indigo-600 dark:border-indigo-400'
                    : 'text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-300',
                )}
              >
                <Icon className="w-3.5 h-3.5" />
                {label}
              </button>
            ))}
          </div>

          {/* Scrollable content */}
          <div className="flex-1 overflow-y-auto p-3">
            {tab === 'questions' ? (
              <SuggestedQueries
                onSelect={q => {
                  onSelectQuestion(q);
                  onMobileClose();
                }}
              />
            ) : (
              <AgentRoster />
            )}
          </div>
        </>
      )}
    </>
  );
}

export function Sidebar({ onSelectQuestion, mobileOpen, onMobileClose }: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <>
      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
          onClick={onMobileClose}
          aria-hidden="true"
        />
      )}

      {/* Mobile drawer */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-50 flex flex-col w-72',
          'bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-700',
          'transition-transform duration-200 md:hidden',
          mobileOpen ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <SidebarContent
          onSelectQuestion={onSelectQuestion}
          onMobileClose={onMobileClose}
          collapsed={false}
          setCollapsed={setCollapsed}
        />
      </aside>

      {/* Desktop sidebar */}
      <aside
        className={cn(
          'hidden md:flex flex-col flex-shrink-0 bg-white dark:bg-slate-900',
          'border-r border-slate-200 dark:border-slate-700',
          'transition-all duration-200',
          collapsed ? 'w-14' : 'w-64',
        )}
      >
        <SidebarContent
          onSelectQuestion={onSelectQuestion}
          onMobileClose={onMobileClose}
          collapsed={collapsed}
          setCollapsed={setCollapsed}
        />
      </aside>
    </>
  );
}
