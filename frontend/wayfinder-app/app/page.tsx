"use client";

import { useState, useRef, useEffect, useCallback } from "react";

// ---------- Types ----------
interface ToolCall {
  toolCallId: string;
  toolName: string;
  args: any;
  result?: any;
}

interface MessagePart {
  type: "text" | "tool-call";
  text?: string;
  toolCall?: ToolCall;
}

interface Message {
  role: "user" | "assistant";
  parts: MessagePart[];
}

// ---------- Tool UI Components ----------

function WeatherCard({ args }: { args: any }) {
  const getEmoji = (c: string) => {
    const l = c.toLowerCase();
    if (l.includes("clear") || l.includes("sunny")) return "☀️";
    if (l.includes("cloud") || l.includes("overcast")) return "⛅";
    if (l.includes("rain")) return "🌧️";
    if (l.includes("fog")) return "🌫️";
    return "🌤️";
  };
  return (
    <div className="my-4 overflow-hidden rounded-xl border border-zinc-700 bg-gradient-to-br from-sky-950 to-blue-950">
      <div className="p-4">
        <div className="flex items-start justify-between">
          <div>
            <div className="text-xs font-medium text-sky-400 uppercase tracking-wider mb-1">
              Weather at Destination
            </div>
            <div className="text-sm text-zinc-300">{args.location}</div>
          </div>
          <span className="text-3xl">{getEmoji(args.conditions)}</span>
        </div>
        <div className="mt-3 flex items-baseline gap-1">
          <span className="text-4xl font-bold text-white">
            {Math.round(args.temperature)}
          </span>
          <span className="text-lg text-zinc-400">&deg;F</span>
        </div>
        <div className="text-sm text-zinc-300 mt-1">{args.conditions}</div>
        <div className="mt-3 grid grid-cols-2 gap-2">
          {args.humidity !== undefined && (
            <div className="rounded-lg bg-zinc-800/50 px-3 py-2">
              <div className="text-xs text-zinc-500">Humidity</div>
              <div className="text-sm text-zinc-200">{args.humidity}%</div>
            </div>
          )}
          {args.wind_speed !== undefined && (
            <div className="rounded-lg bg-zinc-800/50 px-3 py-2">
              <div className="text-xs text-zinc-500">Wind</div>
              <div className="text-sm text-zinc-200">
                {args.wind_speed} mph
              </div>
            </div>
          )}
        </div>
        {args.best_time_note && (
          <div className="mt-3 rounded-lg bg-amber-900/30 border border-amber-800/30 px-3 py-2">
            <div className="text-xs text-amber-400">
              💡 {args.best_time_note}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function MapRoute({ args }: { args: any }) {
  if (!args.origin || !args.destination) return null;
  const bbox = `${Math.min(args.origin.lng, args.destination.lng) - 0.02},${Math.min(args.origin.lat, args.destination.lat) - 0.01},${Math.max(args.origin.lng, args.destination.lng) + 0.02},${Math.max(args.origin.lat, args.destination.lat) + 0.01}`;
  const mapUrl = `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${args.destination.lat},${args.destination.lng}`;

  return (
    <div className="my-4 overflow-hidden rounded-xl border border-zinc-700 bg-zinc-900">
      <iframe
        src={mapUrl}
        className="h-56 w-full border-0"
        title="Journey Route Map"
        loading="lazy"
      />
      <div className="p-4">
        <div className="flex items-center justify-between mb-3">
          <div className="text-sm font-medium text-white">
            {args.origin.name} &rarr; {args.destination.name}
          </div>
        </div>
        {args.segments && args.segments.length > 0 && (
          <div className="flex items-center gap-1 overflow-x-auto pb-2">
            {args.segments.map((seg: any, i: number) => {
              const isTransit =
                seg.mode === "TRANSIT" || seg.mode === "BUS";
              return (
                <div key={i} className="flex items-center gap-1 flex-shrink-0">
                  <div
                    className={`rounded-full px-2 py-1 text-xs ${
                      isTransit
                        ? "bg-blue-900/50 text-blue-300 border border-blue-700"
                        : "bg-zinc-800 text-zinc-400"
                    }`}
                  >
                    {isTransit ? "🚌" : "🚶"} {seg.duration}
                  </div>
                  {i < args.segments.length - 1 && (
                    <div className="w-4 h-px bg-zinc-700" />
                  )}
                </div>
              );
            })}
          </div>
        )}
        {args.pois && args.pois.length > 0 && (
          <div className="mt-3 border-t border-zinc-800 pt-3">
            <div className="text-xs text-zinc-400 mb-2">
              Points of Interest Along Route
            </div>
            <div className="grid grid-cols-2 gap-1">
              {args.pois.slice(0, 6).map((poi: any, i: number) => (
                <div
                  key={i}
                  className="flex items-center gap-1 text-xs text-zinc-300 bg-zinc-800/50 rounded px-2 py-1"
                >
                  <span className="text-zinc-500">📍</span>
                  {poi.name}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function JourneyChapter({ args }: { args: any }) {
  const segmentColors: Record<string, string> = {
    DEPARTURE: "from-indigo-950 to-indigo-900",
    WALKING: "from-emerald-950 to-emerald-900",
    TRANSIT: "from-blue-950 to-blue-900",
    ARRIVAL: "from-amber-950 to-amber-900",
    EXPLORE: "from-purple-950 to-purple-900",
  };
  const segmentIcons: Record<string, string> = {
    DEPARTURE: "🚶",
    WALKING: "🚶‍♂️",
    TRANSIT: "🚌",
    ARRIVAL: "📍",
    EXPLORE: "🔍",
  };
  const bg = segmentColors[args.segment_type] || "from-zinc-900 to-zinc-800";
  const icon = segmentIcons[args.segment_type] || "📍";

  return (
    <div
      className={`my-4 overflow-hidden rounded-xl border border-zinc-700 bg-gradient-to-br ${bg}`}
    >
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-700/50">
        <div className="flex items-center gap-2">
          <span className="text-lg">{icon}</span>
          <div>
            <div className="text-xs font-medium text-zinc-400 uppercase tracking-wider">
              Chapter {args.chapter_number}
            </div>
            <div className="text-sm font-semibold text-white">{args.title}</div>
          </div>
        </div>
        {args.duration && (
          <div className="text-xs text-zinc-400 bg-zinc-800/50 px-2 py-1 rounded-full">
            {args.duration}
          </div>
        )}
      </div>

      <div className="px-4 py-3">
        <p className="text-sm text-zinc-200 leading-relaxed italic">
          &ldquo;{args.narration}&rdquo;
        </p>
      </div>

      {args.transit_info && (
        <div className="mx-4 mb-3 flex items-center gap-2 rounded-lg bg-zinc-800/50 px-3 py-2">
          <span className="text-xs">🚏</span>
          <span className="text-xs text-zinc-300">{args.transit_info}</span>
        </div>
      )}

      {args.pois && args.pois.length > 0 && (
        <div className="mx-4 mb-3">
          <div className="text-xs text-zinc-400 mb-1">Along the way:</div>
          <div className="flex flex-wrap gap-1">
            {args.pois.map((poi: string, i: number) => (
              <span
                key={i}
                className="text-xs bg-zinc-800 text-zinc-300 px-2 py-0.5 rounded-full"
              >
                {poi}
              </span>
            ))}
          </div>
        </div>
      )}

      {args.spotify_embed_url && (
        <div className="mx-4 mb-3">
          <div className="text-xs text-zinc-400 mb-1">
            🎵 {args.spotify_playlist_name || "Soundtrack"}
          </div>
          <iframe
            src={args.spotify_embed_url}
            width="100%"
            height="80"
            frameBorder="0"
            allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture"
            loading="lazy"
            className="rounded-lg"
          />
        </div>
      )}
    </div>
  );
}

function ToolCallLoading({ name }: { name: string }) {
  const labels: Record<string, string> = {
    plan_journey: "Planning your journey...",
    show_weather_card: "Checking weather...",
    show_map_route: "Mapping your route...",
    generate_journey_chapter: "Creating chapter...",
    search_knowledge_base: "Searching knowledge base...",
  };
  return (
    <div className="my-4 rounded-xl border border-zinc-700 bg-zinc-900 p-4 animate-pulse">
      <div className="flex items-center gap-2 text-sm text-zinc-400">
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-zinc-600 border-t-blue-400" />
        {labels[name] || `Running ${name}...`}
      </div>
    </div>
  );
}

function ToolResult({ tc }: { tc: ToolCall }) {
  if (!tc.result) return <ToolCallLoading name={tc.toolName} />;

  switch (tc.toolName) {
    case "show_weather_card":
      return <WeatherCard args={tc.result} />;
    case "show_map_route":
      return <MapRoute args={tc.result} />;
    case "generate_journey_chapter":
      return <JourneyChapter args={tc.result} />;
    case "plan_journey":
    case "search_knowledge_base":
      return null; // Data-only tools, no visual rendering
    default:
      return null;
  }
}

// ---------- Main App ----------

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = useCallback(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  const sendMessage = async () => {
    const text = input.trim();
    if (!text || isLoading) return;

    setInput("");
    setIsLoading(true);

    const userMsg: Message = { role: "user", parts: [{ type: "text", text }] };
    const assistantMsg: Message = { role: "assistant", parts: [] };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);

    // Build messages payload for the API
    const apiMessages = [...messages, userMsg].map((m) => {
      const content: any[] = [];
      for (const p of m.parts) {
        if (p.type === "text" && p.text) {
          content.push({ type: "text", text: p.text });
        } else if (p.type === "tool-call" && p.toolCall) {
          content.push({
            type: "tool-call",
            toolCallId: p.toolCall.toolCallId,
            toolName: p.toolCall.toolName,
            args: p.toolCall.args,
          });
          if (p.toolCall.result) {
            content.push({
              type: "tool-result",
              toolCallId: p.toolCall.toolCallId,
              result: p.toolCall.result,
            });
          }
        }
      }
      return { role: m.role, content };
    });

    try {
      const resp = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages: apiMessages }),
      });

      if (!resp.ok) {
        throw new Error(`API error: ${resp.status}`);
      }

      const reader = resp.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      // Track current assistant message state
      let currentText = "";
      const toolCalls: Map<string, ToolCall> = new Map();
      let pendingToolIds: string[] = [];

      const updateAssistant = () => {
        const parts: MessagePart[] = [];
        if (currentText) {
          parts.push({ type: "text", text: currentText });
        }
        for (const tc of toolCalls.values()) {
          parts.push({ type: "tool-call", toolCall: tc });
        }
        // Also show pending (streaming) tool calls
        for (const id of pendingToolIds) {
          if (!toolCalls.has(id)) {
            // Already added above
          }
        }
        setMessages((prev) => {
          const updated = [...prev];
          updated[updated.length - 1] = { role: "assistant", parts };
          return updated;
        });
      };

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split("\n");
        buffer = lines.pop()!;

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const jsonStr = line.slice(6).trim();
          if (jsonStr === "[DONE]" || !jsonStr) continue;

          let event: any;
          try {
            event = JSON.parse(jsonStr);
          } catch {
            continue;
          }

          switch (event.type) {
            case "text-delta":
              currentText += event.delta;
              updateAssistant();
              break;

            case "tool-input-start":
              pendingToolIds.push(event.toolCallId);
              toolCalls.set(event.toolCallId, {
                toolCallId: event.toolCallId,
                toolName: event.toolName,
                args: {},
              });
              updateAssistant();
              break;

            case "tool-call":
              toolCalls.set(event.toolCallId, {
                toolCallId: event.toolCallId,
                toolName: event.toolName,
                args: event.args,
              });
              updateAssistant();
              break;

            case "tool-result":
              if (toolCalls.has(event.toolCallId)) {
                const tc = toolCalls.get(event.toolCallId)!;
                tc.result = event.result;
                toolCalls.set(event.toolCallId, { ...tc });
                updateAssistant();
              }
              break;

            case "error":
              currentText += `\n\n[Error: ${event.errorText}]`;
              updateAssistant();
              break;
          }
        }
      }
    } catch (err: any) {
      setMessages((prev) => {
        const updated = [...prev];
        updated[updated.length - 1] = {
          role: "assistant",
          parts: [{ type: "text", text: `Error: ${err.message}` }],
        };
        return updated;
      });
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  };

  return (
    <div className="flex h-dvh flex-col bg-zinc-950">
      {/* Header */}
      <header className="flex items-center justify-center border-b border-zinc-800 px-4 py-3">
        <h1 className="text-lg font-semibold text-white tracking-tight">
          Wayfinder
        </h1>
        <span className="ml-2 text-xs text-zinc-500">
          AI-Guided City Journeys
        </span>
      </header>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-6">
        <div className="mx-auto max-w-2xl space-y-4">
          {messages.length === 0 && (
            <div className="text-center py-20">
              <div className="text-4xl mb-4">🏙️</div>
              <h2 className="text-xl font-semibold text-white mb-2">
                Welcome to Wayfinder
              </h2>
              <p className="text-sm text-zinc-400 max-w-md mx-auto">
                Tell me where you want to go in San Francisco, and I&apos;ll create an
                immersive guided journey with transit directions, local stories,
                weather, and the perfect soundtrack.
              </p>
              <div className="mt-6 flex flex-wrap justify-center gap-2">
                {[
                  "Take me to Golden Gate Bridge",
                  "I want to visit Chinatown",
                  "Explore the Mission District",
                  "Show me Fisherman's Wharf",
                ].map((suggestion) => (
                  <button
                    key={suggestion}
                    onClick={() => {
                      setInput(suggestion);
                      setTimeout(() => {
                        const form = document.querySelector("form");
                        if (form) form.requestSubmit();
                      }, 50);
                    }}
                    className="text-xs bg-zinc-800 hover:bg-zinc-700 text-zinc-300 px-3 py-2 rounded-full transition-colors"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i}>
              {msg.role === "user" ? (
                <div className="flex justify-end">
                  <div className="bg-blue-600 text-white rounded-2xl rounded-br-md px-4 py-2 max-w-md text-sm">
                    {msg.parts
                      .filter((p) => p.type === "text")
                      .map((p) => p.text)
                      .join("")}
                  </div>
                </div>
              ) : (
                <div className="space-y-1">
                  {msg.parts.map((part, j) => {
                    if (part.type === "text" && part.text) {
                      return (
                        <div
                          key={j}
                          className="text-sm text-zinc-200 leading-relaxed whitespace-pre-wrap"
                        >
                          {part.text}
                        </div>
                      );
                    }
                    if (part.type === "tool-call" && part.toolCall) {
                      return (
                        <ToolResult key={j} tc={part.toolCall} />
                      );
                    }
                    return null;
                  })}
                  {msg.parts.length === 0 && isLoading && i === messages.length - 1 && (
                    <div className="flex items-center gap-2 text-sm text-zinc-400">
                      <div className="h-4 w-4 animate-spin rounded-full border-2 border-zinc-600 border-t-blue-400" />
                      Thinking...
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Input */}
      <div className="border-t border-zinc-800 px-4 py-3">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            sendMessage();
          }}
          className="mx-auto max-w-2xl flex gap-2"
        >
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Where do you want to go in San Francisco?"
            className="flex-1 bg-zinc-800 text-white text-sm rounded-xl px-4 py-3 outline-none ring-1 ring-zinc-700 focus:ring-blue-500 transition-all placeholder:text-zinc-500"
            disabled={isLoading}
            autoFocus
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="bg-blue-600 hover:bg-blue-500 disabled:bg-zinc-700 disabled:text-zinc-500 text-white rounded-xl px-5 py-3 text-sm font-medium transition-colors"
          >
            {isLoading ? "..." : "Go"}
          </button>
        </form>
      </div>
    </div>
  );
}
