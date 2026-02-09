/* eslint-disable @typescript-eslint/no-explicit-any */
"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkBreaks from "remark-breaks";

function startBrowserSTT(
  onFinal: (text: string) => void,
  onError?: (e: any) => void
) {
  const SR =
    (window as any).SpeechRecognition ||
    (window as any).webkitSpeechRecognition;

  if (!SR) {
    throw new Error("SpeechRecognition not supported in this browser");
  }

  const rec = new SR();
  rec.lang = "en-US";
  rec.interimResults = true;
  rec.continuous = false;

  let finalText = "";

  rec.onresult = (event: any) => {
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const transcript = event.results[i][0].transcript;
      if (event.results[i].isFinal) {
        finalText += transcript + " ";
      }
    }
  };

  rec.onerror = (e: any) => onError?.(e);

  rec.onend = () => {
    const text = finalText.trim();
    if (text) onFinal(text);
  };

  rec.start();
  return rec;
}

type ChatMsg = {
  id: string;
  role: "user" | "assistant";
  text: string;
  route?: string;
};

export default function Page() {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [listening, setListening] = useState(false);
  const [conversationId, setConversationId] = useState<string>("");
  const listRef = useRef<HTMLDivElement | null>(null);

  //input ref to focus after voice transcription
  const inputRef = useRef<HTMLInputElement | null>(null);

  const apiBase = useMemo(() => process.env.NEXT_PUBLIC_API_BASE, []);

  useEffect(() => {
    listRef.current?.scrollTo({
      top: listRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [messages, loading]);

  useEffect(() => {
    const key = "electromart_conversation_id";
    const existing = localStorage.getItem(key);
    if (existing) {
      setConversationId(existing);
      return;
    }
    const id = crypto.randomUUID();
    localStorage.setItem(key, id);
    setConversationId(id);
  }, []);

  useEffect(() => {
    if (!apiBase || !conversationId) return;

    (async () => {
      try {
        const res = await fetch(`${apiBase}/conversations/${conversationId}`);
        if (!res.ok) return;

        const data = await res.json();
        const loaded: ChatMsg[] = (data.messages ?? []).map((m: any) => ({
          id: crypto.randomUUID(),
          role: m.role,
          text: m.text ?? m.content ?? "",
          route: m.route ?? undefined,
        }));

        if (loaded.length > 0) setMessages(loaded);
      } catch {
        setMessages([
          {
            id: crypto.randomUUID(),
            role: "assistant",
            text: "Hi! Welcome to ElectroMart👋🏻\nAsk me about products, promotions, order tracking, returns or for support.",
          },
        ]);
      }
    })();
  }, [apiBase, conversationId]);

  async function send() {
    const text = input.trim();

    if (!text || loading || !conversationId || !apiBase) {
      return;
    }

    setInput("");
    const userMsg: ChatMsg = { id: crypto.randomUUID(), role: "user", text };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await fetch(`${apiBase}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          conversation_id: conversationId,
          input_type: "text",
        }),
      });

      const data: { route: string; response: string } = await res.json();

      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          text: data.response,
          route: data.route,
        },
      ]);
    } catch (e: any) {
      setMessages((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          text: "Sorry — request failed.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  // ✅ FIXED: voice fills textbox ONLY (no auto submit)
  function startVoice() {
    try {
      setListening(true);

      startBrowserSTT(
        (text) => {
          setListening(false);

          setInput(text);

          inputRef.current?.focus();
        },
        (err) => {
          console.error(err);
          setListening(false);
          alert("Voice recognition failed");
        },
      );
    } catch (e) {
      alert("Voice input not supported. Use Chrome or Edge.");
      setListening(false);
    }
  }

  async function clearChat() {
    if (!conversationId || loading) return;

    const ok = confirm("Clear this chat history?");
    if (!ok) return;

    try {
      const res = await fetch(`${apiBase}/conversations/${conversationId}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error(await res.text());

      setMessages([
        {
          id: crypto.randomUUID(),
          role: "assistant",
          text: "Hi! Ask me about products, promotions, order tracking, returns or for support.",
        },
      ]);
      setInput("");
      setListening(false);
      setLoading(false);

      const key = "electromart_conversation_id";
      const newId = crypto.randomUUID();
      localStorage.setItem(key, newId);
      setConversationId(newId);
    } catch (e) {
      alert("Failed to clear chat");
    }
  }

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 flex justify-center">
      <div className="w-full max-w-2xl p-4 flex flex-col gap-4 h-screen">
        <header className="py-2 flex items-center justify-between flex-shrink-0">
          <div>
            <h1 className="text-xl font-semibold text-amber-300">
              ElectroMart Chat
            </h1>
            <p className="text-sm text-neutral-400">
              Chat history is saved (Clear chat to reset)
            </p>
          </div>

          <button
            onClick={clearChat}
            disabled={loading}
            className="text-xs px-3 py-1.5 rounded-lg border border-neutral-700
                      text-neutral-300 hover:bg-neutral-800 hover:text-neutral-100
                      disabled:opacity-50 cursor-pointer"
            title="Clear chat history"
          >
            Clear chat
          </button>
        </header>

        <div
          ref={listRef}
          className="flex-1 min-h-0 rounded-xl border border-neutral-800 bg-neutral-900 p-4 overflow-y-auto space-y-3"
          style={{ scrollbarWidth: "thin", scrollbarColor: "#404040 #171717" }}
        >
          {messages.map((m) => (
            <div
              key={m.id}
              className={`flex ${
                m.role === "user" ? "justify-end" : "justify-start"
              }`}
            >
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-2 text-sm leading-relaxed
                ${m.role === "user" ? "bg-blue-600" : "bg-neutral-800"}`}
              >
                {m.route && (
                  <div className="text-[11px] text-neutral-300 mb-1">
                    route: <span className="font-medium">{m.route}</span>
                  </div>
                )}
                {m.role === "assistant" ? (
                  <div className="text-sm space-y-2 leading-relaxed">
                    <ReactMarkdown remarkPlugins={[remarkBreaks]}>
                      {m.text}
                    </ReactMarkdown>
                  </div>
                ) : (
                  <div className="whitespace-pre-wrap">{m.text}</div>
                )}
              </div>
            </div>
          ))}
          {loading && (
            <div className="text-xl font-bold animate-pulse text-neutral-400">
              …
            </div>
          )}
        </div>

        <div className="flex gap-2">
          <input
            ref={inputRef}
            className="flex-1 rounded-xl bg-neutral-900 border border-neutral-800 px-4 py-3 text-sm outline-none"
            placeholder='Try: "Where is my order 101?"'
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") send();
            }}
          />

          <button
            className={`rounded-xl px-4 py-3 text-sm font-medium cursor-pointer hover:bg-slate-600 transition duration-300
              ${listening ? "bg-red-500 text-white" : "bg-neutral-700 text-neutral-100"}
            `}
            onClick={startVoice}
            disabled={loading}
            title="Voice input"
          >
            {listening ? "🎙️" : "🎤"}
          </button>

          <button
            className="rounded-xl px-4 py-3 bg-neutral-100 text-neutral-900 text-sm font-medium disabled:opacity-50 cursor-pointer hover:bg-slate-200"
            onClick={send}
            disabled={loading || !input.trim()}
          >
            Send
          </button>
        </div>

        <div className="text-xs text-neutral-500">Backend: {apiBase}</div>
      </div>
    </div>
  );
}
