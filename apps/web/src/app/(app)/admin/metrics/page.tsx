"use client";

import { useEffect, useState, useCallback } from "react";
import { motion } from "framer-motion";
import {
  Users,
  Shield,
  AlertTriangle,
  TrendingUp,
  RefreshCw,
  BarChart3,
  Award,
  Target,
} from "lucide-react";
import { PageHeader } from "@/components/shared/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { OrgMetrics } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Legend as RechartsLegend,
} from "recharts";

const RISK_COLORS: Record<string, string> = {
  safe: "#22c55e",
  suspicious: "#f59e0b",
  dangerous: "#ef4444",
};

const TYPE_COLORS: Record<string, string> = {
  email: "#06b6d4",
  url: "#8b5cf6",
  qr: "#ec4899",
  audio: "#f59e0b",
  video: "#10b981",
};

/* ── Animated Counter Hook ── */
function useAnimatedCounter(target: number, duration = 1000) {
  const [value, setValue] = useState(0);

  useEffect(() => {
    if (target === 0) {
      setValue(0);
      return;
    }

    let start: number | null = null;
    let raf: number;

    const step = (ts: number) => {
      if (!start) start = ts;
      const progress = Math.min((ts - start) / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round(eased * target));
      if (progress < 1) raf = requestAnimationFrame(step);
    };

    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target, duration]);

  return value;
}

/* ── Metric Card Component ── */
interface MetricCardProps {
  title: string;
  value: number;
  suffix?: string;
  icon: React.ElementType;
  iconColor: string;
  iconBg: string;
  glowColor: string;
  index: number;
}

function MetricCard({
  title,
  value,
  suffix,
  icon: Icon,
  iconColor,
  iconBg,
  glowColor,
  index,
}: MetricCardProps) {
  const displayValue = useAnimatedCounter(value);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: index * 0.1 }}
    >
      <Card className="relative overflow-hidden border-zinc-800/60 bg-zinc-900/70 backdrop-blur-sm transition-all duration-300 hover:border-zinc-700/80 group">
        <div
          className="absolute inset-x-0 top-0 h-[2px] opacity-60 transition-opacity group-hover:opacity-100"
          style={{
            background: `linear-gradient(90deg, transparent, ${glowColor}, transparent)`,
          }}
        />
        <CardContent className="flex items-center gap-4 p-5">
          <div className={cn("flex h-12 w-12 shrink-0 items-center justify-center rounded-xl", iconBg)}>
            <Icon className={cn("h-6 w-6", iconColor)} />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-zinc-400">{title}</p>
            <div className="flex items-baseline gap-1.5">
              <span className="font-mono text-2xl font-bold tracking-tight text-zinc-100">
                {displayValue}
              </span>
              {suffix && <span className="text-sm font-semibold text-zinc-400">{suffix}</span>}
            </div>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  );
}

/* ── Chart: Risk Distribution ── */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function CustomTooltip({ active, payload }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0];
  return (
    <div className="rounded-lg border border-zinc-700 bg-zinc-900 px-3 py-2 text-xs shadow-xl">
      <span style={{ color: d.payload.fill }} className="font-semibold capitalize">
        {d.name}
      </span>
      <span className="ml-2 text-zinc-300">{d.value}</span>
    </div>
  );
}

function RiskDistributionChart({ distribution }: { distribution: Record<string, number> }) {
  const data = Object.entries(distribution)
    .filter(([_, value]) => value > 0)
    .map(([name, value]) => ({ name, value }));

  const total = data.reduce((sum, d) => sum + d.value, 0);

  if (total === 0) {
    return (
      <div className="flex h-[240px] items-center justify-center">
        <p className="text-sm text-zinc-500">No analyses yet</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center gap-4 sm:flex-row">
      <div className="relative h-[200px] w-[200px] shrink-0">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={60}
              outerRadius={90}
              paddingAngle={3}
              dataKey="value"
              stroke="none"
              animationDuration={800}
            >
              {data.map((entry) => (
                <Cell key={entry.name} fill={RISK_COLORS[entry.name]} className="outline-none" />
              ))}
            </Pie>
            <Tooltip content={<CustomTooltip />} />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-mono text-2xl font-bold text-zinc-100">{total}</span>
          <span className="text-[10px] uppercase tracking-wider text-zinc-500">Total</span>
        </div>
      </div>
      <div className="flex flex-1 flex-col gap-2">
        {data.map((d) => {
          const pct = Math.round((d.value / total) * 100);
          return (
            <div key={d.name} className="flex items-center gap-2.5">
              <span
                className="h-2.5 w-2.5 shrink-0 rounded-full"
                style={{ backgroundColor: RISK_COLORS[d.name] }}
              />
              <span className="flex-1 text-sm capitalize text-zinc-400">{d.name}</span>
              <span className="font-mono text-sm font-medium text-zinc-200">{d.value}</span>
              <span className="w-10 text-right font-mono text-xs text-zinc-500">{pct}%</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ── Chart: Analysis by Type ── */
function AnalysisByTypeChart({ byType }: { byType: Record<string, number> }) {
  const data = Object.entries(byType)
    .filter(([_, value]) => value > 0)
    .map(([name, value]) => ({ name: name.toUpperCase(), value, fill: TYPE_COLORS[name] }));

  if (data.length === 0) {
    return (
      <div className="flex h-[240px] items-center justify-center">
        <p className="text-sm text-zinc-500">No analyses yet</p>
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
        <XAxis dataKey="name" tick={{ fill: "#a1a1aa", fontSize: 12 }} />
        <YAxis tick={{ fill: "#a1a1aa", fontSize: 12 }} />
        <Tooltip
          contentStyle={{
            backgroundColor: "#18181b",
            border: "1px solid #3f3f46",
            borderRadius: "8px",
            fontSize: "12px",
          }}
          cursor={{ fill: "#27272a" }}
        />
        <Bar dataKey="value" radius={[6, 6, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

/* ── Main Page Component ── */
export default function AdminMetricsPage() {
  const [metrics, setMetrics] = useState<OrgMetrics | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const loadMetrics = useCallback(async (showSpinner = false) => {
    if (showSpinner) setIsRefreshing(true);

    try {
      const data = await api.getOrgMetrics();
      setMetrics(data);
      setLastUpdated(new Date());
    } catch (error) {
      console.error("Failed to load org metrics:", error);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadMetrics();
  }, [loadMetrics]);

  const handleRefresh = () => loadMetrics(true);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="Organization Metrics"
          description="Comprehensive analytics and performance insights"
        />
        <div className="flex items-center justify-center py-20">
          <div className="flex items-center gap-3 text-zinc-500">
            <RefreshCw className="h-5 w-5 animate-spin" />
            <span>Loading metrics...</span>
          </div>
        </div>
      </div>
    );
  }

  if (!metrics) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="Organization Metrics"
          description="Comprehensive analytics and performance insights"
        />
        <Card className="border-zinc-800/60 bg-zinc-900/70">
          <CardContent className="flex flex-col items-center justify-center py-20 text-center">
            <BarChart3 className="h-12 w-12 text-zinc-600 mb-3" />
            <p className="text-sm text-zinc-400">Failed to load metrics</p>
            <Button onClick={handleRefresh} variant="ghost" size="sm" className="mt-4">
              Try Again
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const totalThreats =
    (metrics.risk_distribution.suspicious || 0) + (metrics.risk_distribution.dangerous || 0);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Organization Metrics"
        description="Comprehensive analytics and performance insights across your organization"
      >
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="h-7 gap-1.5 text-xs text-zinc-500 hover:text-zinc-300"
          >
            <RefreshCw className={cn("h-3.5 w-3.5", isRefreshing && "animate-spin")} />
            {isRefreshing ? "Refreshing…" : "Refresh"}
          </Button>
          {lastUpdated && (
            <span className="text-[10px] text-zinc-600 tabular-nums">
              Updated {lastUpdated.toLocaleTimeString()}
            </span>
          )}
        </div>
      </PageHeader>

      {/* Period Badge */}
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.2 }}>
        <span className="inline-flex items-center gap-1.5 rounded-full border border-cs-cyan/30 bg-cs-cyan/10 px-3 py-1 text-xs text-cs-cyan">
          <TrendingUp className="h-3 w-3" />
          Viewing: {metrics.period.replace("_", " ")}
        </span>
      </motion.div>

      {/* Key Metrics Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          title="Total Users"
          value={metrics.total_users}
          icon={Users}
          iconColor="text-blue-400"
          iconBg="bg-blue-500/10"
          glowColor="#3b82f6"
          index={0}
        />
        <MetricCard
          title="Total Analyses"
          value={metrics.total_analyses}
          icon={Shield}
          iconColor="text-cyan-400"
          iconBg="bg-cyan-500/10"
          glowColor="#06b6d4"
          index={1}
        />
        <MetricCard
          title="Threats Detected"
          value={totalThreats}
          icon={AlertTriangle}
          iconColor="text-red-400"
          iconBg="bg-red-500/10"
          glowColor="#ef4444"
          index={2}
        />
        <MetricCard
          title="Avg Quiz Score"
          value={metrics.quiz_metrics.average_score}
          suffix="%"
          icon={Award}
          iconColor="text-amber-400"
          iconBg="bg-amber-500/10"
          glowColor="#f59e0b"
          index={3}
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Risk Distribution */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.4 }}
        >
          <Card className="border-zinc-800/60 bg-zinc-900/70 backdrop-blur-sm">
            <CardHeader>
              <CardTitle className="text-sm font-semibold uppercase tracking-wider text-zinc-400">
                Risk Distribution
              </CardTitle>
            </CardHeader>
            <CardContent>
              <RiskDistributionChart distribution={metrics.risk_distribution} />
            </CardContent>
          </Card>
        </motion.div>

        {/* Analysis by Type */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.5 }}
        >
          <Card className="border-zinc-800/60 bg-zinc-900/70 backdrop-blur-sm">
            <CardHeader>
              <CardTitle className="text-sm font-semibold uppercase tracking-wider text-zinc-400">
                Analyses by Type
              </CardTitle>
            </CardHeader>
            <CardContent>
              <AnalysisByTypeChart byType={metrics.analyses_by_type} />
            </CardContent>
          </Card>
        </motion.div>
      </div>

      {/* Quiz Performance */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.6 }}
      >
        <Card className="border-zinc-800/60 bg-zinc-900/70 backdrop-blur-sm">
          <CardHeader>
            <CardTitle className="text-sm font-semibold uppercase tracking-wider text-zinc-400">
              Quiz Performance Metrics
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <div className="flex items-center gap-3 rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-purple-500/10">
                  <Target className="h-5 w-5 text-purple-400" />
                </div>
                <div>
                  <p className="text-xs text-zinc-500">Total Sessions</p>
                  <p className="font-mono text-xl font-bold text-zinc-100">
                    {metrics.quiz_metrics.total_sessions}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3 rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-500/10">
                  <Award className="h-5 w-5 text-amber-400" />
                </div>
                <div>
                  <p className="text-xs text-zinc-500">Average Score</p>
                  <p className="font-mono text-xl font-bold text-zinc-100">
                    {metrics.quiz_metrics.average_score}%
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-3 rounded-lg border border-zinc-800 bg-zinc-900/50 p-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-500/10">
                  <TrendingUp className="h-5 w-5 text-green-400" />
                </div>
                <div>
                  <p className="text-xs text-zinc-500">Completion Rate</p>
                  <p className="font-mono text-xl font-bold text-zinc-100">
                    {Math.round(metrics.quiz_metrics.completion_rate)}%
                  </p>
                </div>
              </div>
            </div>

            {metrics.quiz_metrics.weakest_category && (
              <div className="mt-4 rounded-lg border border-amber-500/20 bg-amber-500/5 p-3">
                <p className="text-xs text-zinc-400">
                  <span className="font-semibold text-amber-400">Focus Area:</span> Users need more
                  training in <span className="capitalize font-semibold">{metrics.quiz_metrics.weakest_category}</span> category
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </motion.div>
    </div>
  );
}
