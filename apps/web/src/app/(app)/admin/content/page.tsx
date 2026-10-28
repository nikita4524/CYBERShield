"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { PageHeader } from "@/components/shared/page-header";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { QuizQuestionsManager } from "@/components/admin/quiz-questions-manager";
import { ScenariosManager } from "@/components/admin/scenarios-manager";
import { ScoringConfigManager } from "@/components/admin/scoring-config-manager";
import { HelpCircle, Layers, Settings } from "lucide-react";

export default function AdminContentPage() {
  const [activeTab, setActiveTab] = useState("quizzes");

  return (
    <div className="space-y-6">
      <PageHeader
        title="Content Management"
        description="Manage quiz questions, scenarios, and system configuration"
      />

      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
          <TabsList className="grid w-full grid-cols-3 lg:w-[500px]">
            <TabsTrigger value="quizzes" className="gap-2">
              <HelpCircle className="h-4 w-4" />
              <span className="hidden sm:inline">Quiz Questions</span>
              <span className="sm:hidden">Quizzes</span>
            </TabsTrigger>
            <TabsTrigger value="scenarios" className="gap-2">
              <Layers className="h-4 w-4" />
              <span className="hidden sm:inline">Scenarios</span>
              <span className="sm:hidden">Scenarios</span>
            </TabsTrigger>
            <TabsTrigger value="scoring" className="gap-2">
              <Settings className="h-4 w-4" />
              <span className="hidden sm:inline">Scoring Config</span>
              <span className="sm:hidden">Config</span>
            </TabsTrigger>
          </TabsList>

          <TabsContent value="quizzes" className="space-y-4">
            <QuizQuestionsManager />
          </TabsContent>

          <TabsContent value="scenarios" className="space-y-4">
            <ScenariosManager />
          </TabsContent>

          <TabsContent value="scoring" className="space-y-4">
            <ScoringConfigManager />
          </TabsContent>
        </Tabs>
      </motion.div>
    </div>
  );
}
