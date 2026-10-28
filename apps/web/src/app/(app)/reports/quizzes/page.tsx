'use client';

import { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { PageHeader } from '@/components/shared/page-header';
import { EmptyState } from '@/components/shared/empty-state';
import { LoadingSpinner } from '@/components/shared/loading-spinner';
import { BadgeDisplay } from '@/components/awareness/badge-display';
import {
  Trophy,
  Brain,
  Target,
  TrendingUp,
  Calendar,
  Clock,
  Award,
  RefreshCw,
  RotateCcw,
  CheckCircle2,
  XCircle,
  AlertTriangle,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { api } from '@/lib/api';
import { motion } from 'framer-motion';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */
interface CategoryScore {
  attempts: number;
  best_score: number;
  average_score: number;
}

interface AwarenessSummary {
  total_quizzes_completed: number;
  average_score_pct: number;
  badges: { category: string; badge: string; earned_at: string }[];
  category_scores: Record<string, CategoryScore>;
  weakest_category: string;
  scenarios_completed: number;
}

interface QuizHistorySession {
  id: string;
  category: string;
  total_questions: number;
  correct_count: number;
  score_pct: number;
  badge_earned: string | null;
  started_at?: string | null;
  completed_at: string | null;
}

/* ------------------------------------------------------------------ */
/*  Stat card                                                          */
/* ------------------------------------------------------------------ */
function StatItem({
  icon: Icon,
  label,
  value,
  color,
}: {
  icon: React.ElementType;
  label: string;
  value: string | number;
  color: string;
}) {
  return (
    <div className="rounded-xl border border-zinc-800/60 bg-zinc-800/30 p-4 text-center">
      <Icon className={cn('mx-auto h-5 w-5', color)} />
      <p className="mt-2 font-mono text-xl font-bold text-zinc-200">{value}</p>
      <p className="mt-0.5 text-[11px] text-zinc-500">{label}</p>
    </div>
  );
}

const CATEGORY_LABELS: Record<string, string> = {
  phishing: 'Phishing Detection',
  upi_qr: 'UPI & QR Scams',
  deepfake: 'Deepfake Awareness',
  kyc_otp: 'KYC & OTP Frauds',
  smart_home: 'Smart Home Security',
  general: 'General Cybersecurity',
};

function fmtDate(d?: string | null) {
  if (!d) return 'Just now';
  try {
    return new Date(d).toLocaleDateString('en-IN', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return d;
  }
}

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */
export default function QuizReportPage() {
  const [data, setData] = useState<AwarenessSummary | null>(null);
  const [sessions, setSessions] = useState<QuizHistorySession[]>([]);
  const [loading, setLoading] = useState(true);
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [summaryRes, historyRes] = await Promise.all([
        api.getAwarenessSummary().catch(() => null),
        api.getQuizHistory(1, 50).catch(() => ({ sessions: [] })),
      ]);

      const historySessions: QuizHistorySession[] = historyRes?.sessions ?? [];
      setSessions(historySessions);

      if (summaryRes && summaryRes.total_quizzes_completed > 0) {
        setData(summaryRes);
      } else if (historySessions.length > 0) {
        // Synthesize summary if direct summary returned empty
        const total = historySessions.length;
        const avg = Math.round(
          historySessions.reduce((acc, s) => acc + (s.score_pct || 0), 0) / total
        );
        const catMap: Record<string, CategoryScore> = {};
        const badges: { category: string; badge: string; earned_at: string }[] = [];

        historySessions.forEach((s) => {
          const cat = s.category || 'general';
          if (!catMap[cat]) {
            catMap[cat] = { attempts: 0, best_score: 0, average_score: 0 };
          }
          catMap[cat].attempts += 1;
          catMap[cat].best_score = Math.max(catMap[cat].best_score, s.score_pct || 0);

          if (s.badge_earned && !badges.some((b) => b.category === cat && b.badge === s.badge_earned)) {
            badges.push({
              category: cat,
              badge: s.badge_earned.toLowerCase(),
              earned_at: s.completed_at || new Date().toISOString(),
            });
          }
        });

        // Compute cat averages
        Object.keys(catMap).forEach((c) => {
          const catSessions = historySessions.filter((s) => (s.category || 'general') === c);
          const cAvg = Math.round(
            catSessions.reduce((acc, s) => acc + (s.score_pct || 0), 0) / catSessions.length
          );
          catMap[c].average_score = cAvg;
        });

        let weakest = Object.keys(catMap)[0] || 'general';
        let lowest = 101;
        Object.entries(catMap).forEach(([c, sc]) => {
          if (sc.average_score < lowest) {
            lowest = sc.average_score;
            weakest = c;
          }
        });

        setData({
          total_quizzes_completed: total,
          average_score_pct: avg,
          badges,
          category_scores: catMap,
          weakest_category: weakest,
          scenarios_completed: 0,
        });
      } else {
        setData(summaryRes || null);
      }
    } catch {
      setData(null);
      setSessions([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <LoadingSpinner label="Loading quiz history…" />
      </div>
    );
  }

  const hasData = (data && data.total_quizzes_completed > 0) || sessions.length > 0;

  if (!hasData) {
    return (
      <div className="space-y-6">
        <PageHeader title="Quiz History & Badges" icon={Trophy} />
        <EmptyState
          title="No quizzes completed yet"
          description="Take your first quiz to track progress, test your threat awareness, and earn badges."
          action={{ label: 'Start a Quiz', href: '/awareness/quizzes' }}
        />
      </div>
    );
  }

  const safeData = data || {
    total_quizzes_completed: sessions.length,
    average_score_pct: 0,
    badges: [],
    category_scores: {},
    weakest_category: 'None',
    scenarios_completed: 0,
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <PageHeader
          title="Quiz History & Badges"
          description="Track your cybersecurity knowledge scores, earned certifications, and past sessions."
          icon={Trophy}
        />

        {/* Guest mode banner */}
        {mounted && !localStorage.getItem('access_token') && (
          <div className="flex items-start gap-3 rounded-lg border border-amber-500/30 bg-amber-500/8 px-4 py-3 text-xs text-amber-300">
            <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-400" />
            <div className="flex-1">
              <span className="font-semibold">Guest Mode:</span> Your quiz history is stored locally and will be lost if you clear browser data.{' '}
              <a href="/auth/login" className="underline hover:text-amber-200 font-medium">Sign in</a> to save your progress permanently.
            </div>
          </div>
        )}
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => fetchData()}
            disabled={loading}
            className="h-8 gap-1.5 border-zinc-700 bg-zinc-800/60 text-xs text-zinc-300 hover:text-white"
          >
            <RefreshCw className={cn('h-3.5 w-3.5', loading && 'animate-spin')} />
            Refresh
          </Button>
          <Button
            size="sm"
            asChild
            className="h-8 gap-1.5 bg-cyan-600 hover:bg-cyan-500 text-xs font-medium text-white"
          >
            <Link href="/awareness/quizzes">
              Take New Quiz
            </Link>
          </Button>
        </div>
      </div>

      {/* Overview stats */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatItem
          icon={Brain}
          label="Quizzes Completed"
          value={safeData.total_quizzes_completed}
          color="text-cyan-400"
        />
        <StatItem
          icon={Target}
          label="Average Score"
          value={`${safeData.average_score_pct}%`}
          color="text-purple-400"
        />
        <StatItem
          icon={TrendingUp}
          label="Weakest Area"
          value={CATEGORY_LABELS[safeData.weakest_category] ?? safeData.weakest_category}
          color="text-amber-400"
        />
        <StatItem
          icon={Award}
          label="Badges Earned"
          value={safeData.badges.length}
          color="text-emerald-400"
        />
      </div>

      {/* Badges Section */}
      <Card className="border-zinc-800/60 bg-zinc-900/70 backdrop-blur-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold uppercase tracking-wider text-zinc-400">
            Earned Cyber Awareness Badges
          </CardTitle>
        </CardHeader>
        <CardContent>
          {safeData.badges.length === 0 ? (
            <p className="py-4 text-center text-xs text-zinc-500">
              Score ≥ 50% in any quiz category to unlock Bronze, Silver (≥70%), or Gold (≥90%) badges.
            </p>
          ) : (
            <div className="flex flex-wrap gap-3">
              {safeData.badges.map((b, i) => (
                <motion.div
                  key={`${b.category}-${b.badge}-${i}`}
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ delay: i * 0.1, type: 'spring', stiffness: 200 }}
                  className="flex flex-col items-center gap-1.5 rounded-xl border border-zinc-800 bg-zinc-800/40 p-3 min-w-[110px]"
                >
                  <BadgeDisplay badge={b.badge} size="md" showLabel={false} />
                  <span className="text-[11px] font-semibold text-zinc-200 capitalize">
                    {b.badge}
                  </span>
                  <span className="text-[10px] text-zinc-500">
                    {CATEGORY_LABELS[b.category] ?? b.category}
                  </span>
                </motion.div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Category Breakdown */}
      {Object.keys(safeData.category_scores).length > 0 && (
        <Card className="border-zinc-800/60 bg-zinc-900/70 backdrop-blur-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold uppercase tracking-wider text-zinc-400">
              Category Mastery Breakdown
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {Object.entries(safeData.category_scores).map(([cat, score]) => {
                const label = CATEGORY_LABELS[cat] ?? cat;
                return (
                  <div key={cat} className="space-y-1.5">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-medium text-zinc-300">{label}</span>
                      <span className="text-zinc-500">
                        {score.attempts} {score.attempts === 1 ? 'attempt' : 'attempts'} · Best: {score.best_score}%
                      </span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-zinc-800">
                      <motion.div
                        className={cn(
                          'h-full rounded-full',
                          score.average_score >= 70
                            ? 'bg-emerald-500'
                            : score.average_score >= 50
                            ? 'bg-amber-500'
                            : 'bg-red-500'
                        )}
                        initial={{ width: 0 }}
                        animate={{ width: `${score.average_score}%` }}
                        transition={{ duration: 0.8 }}
                      />
                    </div>
                    <p className="text-right font-mono text-[11px] text-zinc-500">
                      Average Score: {score.average_score}%
                    </p>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Past Quiz Sessions Table */}
      <Card className="border-zinc-800/60 bg-zinc-900/70 backdrop-blur-sm">
        <CardHeader className="pb-3 border-b border-zinc-800/60">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-semibold uppercase tracking-wider text-zinc-300 flex items-center gap-2">
              <Calendar className="h-4 w-4 text-cyan-400" />
              Recorded Quiz Sessions History ({sessions.length})
            </CardTitle>
          </div>
        </CardHeader>
        <CardContent className="p-4">
          {sessions.length === 0 ? (
            <p className="py-6 text-center text-xs text-zinc-500">
              No individual session logs recorded yet. Complete a quiz to view detailed session records.
            </p>
          ) : (
            <div className="space-y-2.5">
              {sessions.map((s, idx) => {
                const isPassed = s.score_pct >= 50;
                const catLabel = CATEGORY_LABELS[s.category] ?? s.category;

                return (
                  <motion.div
                    key={s.id || idx}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: idx * 0.03 }}
                    className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-zinc-800/50 bg-zinc-800/20 p-3.5 hover:bg-zinc-800/40 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className={cn(
                          'flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border',
                          isPassed
                            ? 'border-emerald-500/20 bg-emerald-500/10 text-emerald-400'
                            : 'border-red-500/20 bg-red-500/10 text-red-400'
                        )}
                      >
                        {isPassed ? (
                          <CheckCircle2 className="h-4 w-4" />
                        ) : (
                          <XCircle className="h-4 w-4" />
                        )}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <p className="text-sm font-medium text-zinc-200">
                            {catLabel}
                          </p>
                          {s.badge_earned && (
                            <Badge
                              variant="outline"
                              className={cn(
                                'text-[10px] uppercase font-bold tracking-wider px-2 py-0 border',
                                s.badge_earned.toLowerCase() === 'gold'
                                  ? 'border-amber-400/30 bg-amber-400/10 text-amber-300'
                                  : s.badge_earned.toLowerCase() === 'silver'
                                  ? 'border-zinc-300/30 bg-zinc-300/10 text-zinc-200'
                                  : 'border-amber-700/30 bg-amber-700/10 text-amber-600'
                              )}
                            >
                              🏆 {s.badge_earned}
                            </Badge>
                          )}
                        </div>
                        <p className="mt-0.5 flex items-center gap-1.5 text-[11px] text-zinc-500">
                          <Clock className="h-3 w-3" />
                          {fmtDate(s.completed_at)}
                          <span className="text-zinc-600">•</span>
                          <span>
                            {s.correct_count} / {s.total_questions} correct
                          </span>
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-4">
                      <div className="text-right">
                        <span
                          className={cn(
                            'font-mono text-base font-bold',
                            s.score_pct >= 70
                              ? 'text-emerald-400'
                              : s.score_pct >= 50
                              ? 'text-amber-400'
                              : 'text-red-400'
                          )}
                        >
                          {s.score_pct}%
                        </span>
                        <p className="text-[10px] text-zinc-500 uppercase tracking-wider font-semibold">
                          {isPassed ? 'Passed' : 'Needs Practice'}
                        </p>
                      </div>
                      <Button
                        size="sm"
                        variant="ghost"
                        asChild
                        className="h-8 gap-1.5 text-xs text-zinc-400 hover:text-cyan-400 hover:bg-cyan-500/10"
                      >
                        <Link href={`/awareness/quizzes/${s.category || 'general'}`}>
                          <RotateCcw className="h-3.5 w-3.5" />
                          Retake
                        </Link>
                      </Button>
                    </div>
                  </motion.div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}