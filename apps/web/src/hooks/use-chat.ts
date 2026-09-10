"use client";

import { useState, useCallback } from "react";
import type { Message } from "@/components/assistant/chat-message";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

interface UseChatOpts {
  mode: string;
}

const ERROR_FALLBACK =
  "⚠️ Couldn't reach the assistant. Check your connection.\n\n" +
  "Report cyber fraud at **cybercrime.gov.in** or call **1930**.";

export function useChat({ mode }: UseChatOpts) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [facts, setFacts] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const sendMessage = useCallback(
    async (content: string) => {
      const userMsg: Message = { role: "user", content };
      const history = [...messages, userMsg].map((m) => ({
        role: m.role,
        content: m.content,
      }));

      // Push the user message plus an empty assistant bubble that fills in as tokens stream.
      setMessages((prev) => [...prev, userMsg, { role: "assistant", content: "" }]);
      setIsLoading(true);
      setError(null);

      let receivedDelta = false;

      try {
        const res = await fetch(`${API}/assistant/chat/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ messages: history, mode }),
        });

        if (!res.ok || !res.body) throw new Error(`API ${res.status}`);

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const events = buffer.split("\n\n");
          buffer = events.pop() ?? "";

          for (const evt of events) {
            const line = evt.trim();
            if (!line.startsWith("data:")) continue;

            const jsonStr = line.slice(5).trim();
            if (!jsonStr) continue;

            let parsed: any;
            try {
              parsed = JSON.parse(jsonStr);
            } catch {
              continue;
            }

            if (parsed.type === "delta") {
              receivedDelta = true;
              setIsLoading(false);
              setMessages((prev) => {
                const next = [...prev];
                const last = next[next.length - 1];
                next[next.length - 1] = { ...last, content: last.content + parsed.content };
                return next;
              });
            } else if (parsed.type === "facts") {
              if (parsed.facts?.length) setFacts(parsed.facts);
            } else if (parsed.type === "error") {
              throw new Error(parsed.message || "Stream error");
            }
          }
        }
      } catch (err: any) {
        setMessages((prev) => {
          const next = [...prev];
          const last = next[next.length - 1];
          if (last?.role === "assistant" && !last.content) {
            next[next.length - 1] = { role: "assistant", content: ERROR_FALLBACK };
          } else {
            next.push({ role: "assistant", content: ERROR_FALLBACK });
          }
          return next;
        });
        setError(err.message);
      } finally {
        if (!receivedDelta) setIsLoading(false);
      }
    },
    [messages, mode],
  );

  const clearChat = useCallback(() => {
    setMessages([]);
    setFacts([]);
    setError(null);
  }, []);

  return { messages, sendMessage, isLoading, clearChat, facts, error };
}
