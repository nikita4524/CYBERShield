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
  CheckCircle2,
  Filter,
  Info,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface QuizQuestion {
  id: string;
  question_text: string;
  options: string[];
  difficulty: number;
  category?: string;
  correct_option_index?: number;
  explanation?: string;
}

interface QuestionsResponse {
  category: string;
  language: string;
  total_questions: number;
  questions: QuizQuestion[];
}

const CATEGORIES = [
  { value: "phishing", label: "Phishing" },
  { value: "deepfake", label: "Deepfake" },
  { value: "upi_qr", label: "UPI/QR Scams" },
  { value: "kyc_otp", label: "KYC/OTP Fraud" },
  { value: "general", label: "General Security" },
  { value: "smart_home", label: "Smart Home" },
];

const DIFFICULTY_COLORS = {
  1: "bg-green-500/20 text-green-400 border-green-500/30",
  2: "bg-amber-500/20 text-amber-400 border-amber-500/30",
  3: "bg-red-500/20 text-red-400 border-red-500/30",
};

export function QuizQuestionsManager() {
  const [questions, setQuestions] = useState<QuizQuestion[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState("phishing");
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    if (selectedCategory) {
      loadQuestions(selectedCategory);
    }
  }, [selectedCategory]);

  const loadQuestions = async (category: string) => {
    setIsLoading(true);
    try {
      const data = await api.request<QuestionsResponse>(
        `/awareness/quizzes?category=${category}&language=en`
      );
      setQuestions(data.questions);
    } catch (error) {
      console.error("Failed to load questions:", error);
      setQuestions([]);
    } finally {
      setIsLoading(false);
    }
  };

  const filteredQuestions = questions.filter((q) =>
    q.question_text.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const toggleExpand = (id: string) => {
    setExpandedId(expandedId === id ? null : id);
  };

  return (
    <div className="space-y-4">
      {/* Info Banner */}
      <Card className="border-blue-500/30 bg-blue-500/10">
        <CardContent className="flex items-start gap-3 p-4">
          <Info className="h-5 w-5 text-blue-400 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <p className="text-sm text-blue-300 font-medium">Read-Only View</p>
            <p className="text-xs text-blue-400/80">
              Quiz questions are currently seeded from <code className="bg-blue-500/20 px-1 rounded">seed_quizzes.json</code>.
              Full CRUD operations require backend API implementation.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Filters */}
      <Card className="border-zinc-800/60 bg-zinc-900/70 backdrop-blur-sm">
        <CardHeader className="pb-4">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-lg">Quiz Questions</CardTitle>
              <CardDescription className="mt-1">
                {filteredQuestions.length} question{filteredQuestions.length !== 1 ? "s" : ""} in{" "}
                {CATEGORIES.find((c) => c.value === selectedCategory)?.label}
              </CardDescription>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => loadQuestions(selectedCategory)}
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
                placeholder="Search questions..."
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

          {/* Questions List */}
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <div className="flex items-center gap-3 text-zinc-500">
                <RefreshCw className="h-5 w-5 animate-spin" />
                <span>Loading questions...</span>
              </div>
            </div>
          ) : filteredQuestions.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-12 text-center">
              <div className="h-16 w-16 rounded-full border-2 border-dashed border-zinc-700 flex items-center justify-center mb-3">
                <Search className="h-6 w-6 text-zinc-600" />
              </div>
              <p className="text-sm text-zinc-400">
                {searchQuery ? "No questions match your search" : "No questions found"}
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {filteredQuestions.map((question, idx) => {
                const isExpanded = expandedId === question.id;
                return (
                  <motion.div
                    key={question.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.2, delay: idx * 0.03 }}
                  >
                    <Card className="border-zinc-800 bg-zinc-900/50 hover:border-zinc-700 transition-colors">
                      <CardContent className="p-4">
                        {/* Question Header */}
                        <div
                          className="flex items-start gap-3 cursor-pointer"
                          onClick={() => toggleExpand(question.id)}
                        >
                          <div className="flex-1 space-y-2">
                            <div className="flex items-start justify-between gap-2">
                              <p className="text-sm text-zinc-200 leading-relaxed">
                                {question.question_text}
                              </p>
                              <Badge
                                className={cn(
                                  "shrink-0 border",
                                  DIFFICULTY_COLORS[question.difficulty as keyof typeof DIFFICULTY_COLORS]
                                )}
                              >
                                Level {question.difficulty}
                              </Badge>
                            </div>
                          </div>
                          <Button variant="ghost" size="sm" className="shrink-0 h-8 w-8 p-0">
                            {isExpanded ? (
                              <ChevronUp className="h-4 w-4" />
                            ) : (
                              <ChevronDown className="h-4 w-4" />
                            )}
                          </Button>
                        </div>

                        {/* Expanded Content */}
                        {isExpanded && (
                          <motion.div
                            initial={{ opacity: 0, height: 0 }}
                            animate={{ opacity: 1, height: "auto" }}
                            exit={{ opacity: 0, height: 0 }}
                            transition={{ duration: 0.2 }}
                            className="mt-4 pt-4 border-t border-zinc-800 space-y-3"
                          >
                            <div>
                              <p className="text-xs font-semibold text-zinc-400 mb-2">Options:</p>
                              <div className="space-y-1.5">
                                {question.options.map((option, optIdx) => (
                                  <div
                                    key={optIdx}
                                    className={cn(
                                      "flex items-center gap-2 rounded-lg border px-3 py-2 text-sm",
                                      question.correct_option_index === optIdx
                                        ? "border-green-500/50 bg-green-500/10 text-green-300"
                                        : "border-zinc-800 bg-zinc-900/50 text-zinc-400"
                                    )}
                                  >
                                    <span className="font-mono text-xs font-semibold">
                                      {String.fromCharCode(65 + optIdx)}.
                                    </span>
                                    <span className="flex-1">{option}</span>
                                    {question.correct_option_index === optIdx && (
                                      <CheckCircle2 className="h-4 w-4 text-green-400" />
                                    )}
                                  </div>
                                ))}
                              </div>
                            </div>

                            {question.explanation && (
                              <div className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-3">
                                <p className="text-xs font-semibold text-zinc-400 mb-1">
                                  Explanation:
                                </p>
                                <p className="text-xs text-zinc-300 leading-relaxed">
                                  {question.explanation}
                                </p>
                              </div>
                            )}
                          </motion.div>
                        )}
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
