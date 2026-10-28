"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api";
import {
  RefreshCw,
  Search,
  Clock,
  Filter,
  Info,
  MessageSquare,
  Mail,
  Phone,
  Layers,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface Scenario {
  id: string;
  title: string;
  description: string;
  category: string;
  scenario_type: string;
  estimated_time_minutes: number;
}

interface ScenariosResponse {
  scenarios: Scenario[];
}

const CATEGORIES = [
  { value: "all", label: "All Categories" },
  { value: "phishing", label: "Phishing" },
  { value: "deepfake", label: "Deepfake" },
  { value: "upi_qr", label: "UPI/QR Scams" },
  { value: "kyc_otp", label: "KYC/OTP Fraud" },
  { value: "general", label: "General Security" },
];

const SCENARIO_TYPE_ICONS = {
  chat: MessageSquare,
  email: Mail,
  call: Phone,
};

const CATEGORY_COLORS: Record<string, string> = {
  phishing: "bg-red-500/20 text-red-400 border-red-500/30",
  deepfake: "bg-purple-500/20 text-purple-400 border-purple-500/30",
  upi_qr: "bg-amber-500/20 text-amber-400 border-amber-500/30",
  kyc_otp: "bg-orange-500/20 text-orange-400 border-orange-500/30",
  general: "bg-blue-500/20 text-blue-400 border-blue-500/30",
};

export function ScenariosManager() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    loadScenarios();
  }, [selectedCategory]);

  const loadScenarios = async () => {
    setIsLoading(true);
    try {
      const categoryParam = selectedCategory !== "all" ? `?category=${selectedCategory}` : "";
      const data = await api.request<ScenariosResponse>(`/awareness/scenarios${categoryParam}`);
      setScenarios(data.scenarios);
    } catch (error) {
      console.error("Failed to load scenarios:", error);
      setScenarios([]);
    } finally {
      setIsLoading(false);
    }
  };

  const filteredScenarios = scenarios.filter(
    (s) =>
      s.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.description.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="space-y-4">
      {/* Info Banner */}
      <Card className="border-blue-500/30 bg-blue-500/10">
        <CardContent className="flex items-start gap-3 p-4">
          <Info className="h-5 w-5 text-blue-400 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <p className="text-sm text-blue-300 font-medium">Read-Only View</p>
            <p className="text-xs text-blue-400/80">
              Scenarios are currently seeded from{" "}
              <code className="bg-blue-500/20 px-1 rounded">seed_scenarios.json</code>. Full CRUD
              operations require backend API implementation.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Main Content */}
      <Card className="border-zinc-800/60 bg-zinc-900/70 backdrop-blur-sm">
        <CardHeader className="pb-4">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-lg">Interactive Scenarios</CardTitle>
              <CardDescription className="mt-1">
                {filteredScenarios.length} scenario{filteredScenarios.length !== 1 ? "s" : ""}{" "}
                available
              </CardDescription>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={loadScenarios}
              disabled={isLoading}
              className="gap-2"
            >
              <RefreshCw className={cn("h-4 w-4", isLoading && "animate-spin")} />
              Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Filter Row */}
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
              <Input
                placeholder="Search scenarios..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>
            <Select value={selectedCategory} onValueChange={setSelectedCategory}>
              <SelectTrigger className="w-full sm:w-[200px]">
                <Filter className="h-4 w-4 mr-2" />
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CATEGORIES.map((cat) => (
                  <SelectItem key={cat.value} value={cat.value}>
                    {cat.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Scenarios Grid */}
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <div className="flex items-center gap-3 text-zinc-500">
                <RefreshCw className="h-5 w-5 animate-spin" />
                <span>Loading scenarios...</span>
              </div>
            </div>
          ) : filteredScenarios.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="h-16 w-16 rounded-full border-2 border-dashed border-zinc-700 flex items-center justify-center mb-3">
                <Layers className="h-6 w-6 text-zinc-600" />
              </div>
              <p className="text-sm text-zinc-400">
                {searchQuery ? "No scenarios match your search" : "No scenarios found"}
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {filteredScenarios.map((scenario, idx) => {
                const TypeIcon =
                  SCENARIO_TYPE_ICONS[
                    scenario.scenario_type as keyof typeof SCENARIO_TYPE_ICONS
                  ] || MessageSquare;
                return (
                  <motion.div
                    key={scenario.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.2, delay: idx * 0.05 }}
                  >
                    <Card className="border-zinc-800 bg-zinc-900/50 hover:border-zinc-700 transition-all hover:shadow-lg h-full">
                      <CardContent className="p-5 space-y-3">
                        {/* Header */}
                        <div className="flex items-start gap-3">
                          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-cs-cyan/10 border border-cs-cyan/30">
                            <TypeIcon className="h-5 w-5 text-cs-cyan" />
                          </div>
                          <div className="flex-1 min-w-0">
                            <h3 className="font-semibold text-zinc-100 leading-tight mb-1">
                              {scenario.title}
                            </h3>
                            <div className="flex flex-wrap items-center gap-2">
                              <Badge
                                className={cn(
                                  "text-xs border",
                                  CATEGORY_COLORS[scenario.category] ||
                                    "bg-zinc-500/20 text-zinc-400 border-zinc-500/30"
                                )}
                              >
                                {scenario.category}
                              </Badge>
                              <span className="flex items-center gap-1 text-xs text-zinc-500">
                                <Clock className="h-3 w-3" />
                                {scenario.estimated_time_minutes} min
                              </span>
                            </div>
                          </div>
                        </div>

                        {/* Description */}
                        <p className="text-sm text-zinc-400 leading-relaxed line-clamp-3">
                          {scenario.description}
                        </p>

                        {/* Type Badge */}
                        <div className="pt-2 border-t border-zinc-800">
                          <span className="inline-flex items-center gap-1.5 text-xs text-zinc-500">
                            <TypeIcon className="h-3.5 w-3.5" />
                            <span className="capitalize">{scenario.scenario_type}</span> simulation
                          </span>
                        </div>
                      </CardContent>
                    </Card>
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
