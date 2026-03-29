"use client";

import { useState, useRef, useEffect, useCallback } from "react";

// ===== Types =====
interface ToolCall {
  toolCallId: string;
  toolName: string;
  args: any;
  result?: any;
}

interface MessagePart {
  type: "text" | "tool-call" | "image";
  text?: string;
  toolCall?: ToolCall;
  imageUrl?: string;
}

interface Message {
  role: "user" | "assistant";
  parts: MessagePart[];
}

// ===== Tool UI: Weather Card =====
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
              <div className="text-sm text-zinc-200">{args.wind_speed} mph</div>
            </div>
          )}
        </div>
        {args.best_time_note && (
          <div className="mt-3 rounded-lg bg-amber-900/30 border border-amber-800/30 px-3 py-2">
            <div className="text-xs text-amber-400">💡 {args.best_time_note}</div>
          </div>
        )}
      </div>
    </div>
  );
}

// ===== Tool UI: Map Route =====
function MapRoute({ args }: { args: any }) {
  if (!args.origin || !args.destination) return null;
  const bbox = `${Math.min(args.origin.lng, args.destination.lng) - 0.02},${Math.min(args.origin.lat, args.destination.lat) - 0.01},${Math.max(args.origin.lng, args.destination.lng) + 0.02},${Math.max(args.origin.lat, args.destination.lat) + 0.01}`;
  const mapUrl = `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${args.destination.lat},${args.destination.lng}`;
  return (
    <div className="my-4 overflow-hidden rounded-xl border border-zinc-700 bg-zinc-900">
      <iframe src={mapUrl} className="h-56 w-full border-0" title="Route Map" loading="lazy" />
      <div className="p-4">
        <div className="text-sm font-medium text-white mb-3">
          {args.origin.name} → {args.destination.name}
        </div>
        {args.segments && args.segments.length > 0 && (
          <div className="space-y-1.5 mb-3">
            {args.segments.map((seg: any, i: number) => {
              const isTransit = seg.mode === "TRANSIT" || seg.mode === "BUS";
              return (
                <div key={i} className={`flex items-center gap-2 rounded-lg px-3 py-2 text-xs ${isTransit ? "bg-blue-900/30 border border-blue-800/50" : "bg-zinc-800/50"}`}>
                  <span>{isTransit ? "🚌" : "🚶"}</span>
                  <span className={isTransit ? "text-blue-300 font-medium" : "text-zinc-400"}>{seg.duration}</span>
                  {seg.transit_info && <span className="text-zinc-300">— {seg.transit_info}</span>}
                </div>
              );
            })}
          </div>
        )}
        {args.pois && args.pois.length > 0 && (
          <div className="mt-3 border-t border-zinc-800 pt-3">
            <div className="text-xs text-zinc-400 mb-2">Points of Interest Along Route</div>
            <div className="grid grid-cols-2 gap-1">
              {args.pois.slice(0, 6).map((poi: any, i: number) => (
                <div key={i} className="flex items-center gap-1 text-xs text-zinc-300 bg-zinc-800/50 rounded px-2 py-1">
                  <span className="text-zinc-500">📍</span> {poi.name}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ===== Tool UI: Journey Chapter =====
function JourneyChapter({ args, isActive }: { args: any; isActive?: boolean }) {
  const segmentColors: Record<string, string> = {
    DEPARTURE: "from-indigo-950 to-indigo-900",
    WALKING: "from-emerald-950 to-emerald-900",
    TRANSIT: "from-blue-950 to-blue-900",
    ARRIVAL: "from-amber-950 to-amber-900",
    EXPLORE: "from-purple-950 to-purple-900",
  };
  const segmentIcons: Record<string, string> = {
    DEPARTURE: "🚶", WALKING: "🚶‍♂️", TRANSIT: "🚌", ARRIVAL: "📍", EXPLORE: "🔍",
  };
  const bg = segmentColors[args.segment_type] || "from-zinc-900 to-zinc-800";
  const icon = segmentIcons[args.segment_type] || "📍";

  return (
    <div className={`overflow-hidden rounded-xl border bg-gradient-to-br ${bg} transition-all duration-500 ${isActive ? "border-blue-500/50 shadow-lg shadow-blue-500/10" : "border-zinc-700"}`}>
      {/* Chapter Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-700/50">
        <div className="flex items-center gap-2">
          <span className="text-lg">{icon}</span>
          <div>
            <div className="text-xs font-medium text-zinc-400 uppercase tracking-wider">Chapter {args.chapter_number}</div>
            <div className="text-sm font-semibold text-white">{args.title}</div>
          </div>
        </div>
        {args.duration && (
          <div className="text-xs text-zinc-400 bg-zinc-800/50 px-2 py-1 rounded-full">{args.duration}</div>
        )}
      </div>

      {/* Narration */}
      <div className="px-4 py-3">
        <p className="text-sm text-zinc-200 leading-relaxed italic">&ldquo;{args.narration}&rdquo;</p>
      </div>

      {/* Transit Info */}
      {args.transit_info && (
        <div className="mx-4 mb-3 flex items-center gap-2 rounded-lg bg-zinc-800/50 px-3 py-2">
          <span className="text-xs">🚏</span>
          <span className="text-xs text-zinc-300">{args.transit_info}</span>
        </div>
      )}

      {/* POIs */}
      {args.pois && args.pois.length > 0 && (
        <div className="mx-4 mb-3">
          <div className="text-xs text-zinc-400 mb-1">Along the way:</div>
          <div className="flex flex-wrap gap-1">
            {args.pois.map((poi: string, i: number) => (
              <span key={i} className="text-xs bg-zinc-800 text-zinc-300 px-2 py-0.5 rounded-full">{poi}</span>
            ))}
          </div>
        </div>
      )}

      {/* Audio Narration — auto-plays when active */}
      {args.audio_url && (
        <div className="mx-4 mb-3">
          <div className="text-xs text-zinc-400 mb-1">🔊 Audio Narration</div>
          <audio controls autoPlay={isActive} className="w-full h-10" preload="auto">
            <source src={args.audio_url} type="audio/mpeg" />
          </audio>
        </div>
      )}
      {/* Audio appears silently when ready */}

      {/* Spotify */}
      {args.spotify_embed_url && (
        <div className="mx-4 mb-3">
          <div className="text-xs text-zinc-400 mb-1">🎵 {args.spotify_playlist_name || "Soundtrack"}</div>
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

// ===== Main App =====
export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [uploadedImage, setUploadedImage] = useState<{ dataUrl: string } | null>(null);

  // Journey progressive reveal state
  const [journeyChapters, setJourneyChapters] = useState<ToolCall[]>([]);
  const [journeyDestination, setJourneyDestination] = useState("");
  const [journeyDuration, setJourneyDuration] = useState("");
  const [revealedCount, setRevealedCount] = useState(0);
  const [journeyPhase, setJourneyPhase] = useState<"idle" | "loading" | "ready" | "playing" | "complete">("idle");

  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const chaptersRef = useRef<ToolCall[]>([]);
  const chapterElRefs = useRef<Map<number, HTMLDivElement>>(new Map());

  // TTS generation state
  const [ttsLoading, setTtsLoading] = useState<Set<string>>(new Set());

  const scrollToBottom = useCallback(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, revealedCount, scrollToBottom]);

  // Auto-scroll to newly revealed chapter
  const scrollToChapter = useCallback((index: number) => {
    setTimeout(() => {
      const el = chapterElRefs.current.get(index);
      if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 150);
  }, []);

  // TTS is now generated server-side as part of the chapter tool result

  // Start journey playback
  const beginJourney = useCallback(() => {
    setJourneyPhase("playing");
    setRevealedCount(1);
    scrollToChapter(0);
  }, [scrollToChapter]);

  // Advance to next chapter
  const nextChapter = useCallback(() => {
    const next = revealedCount + 1;
    setRevealedCount(next);
    scrollToChapter(next - 1);
    if (next >= journeyChapters.length) {
      setJourneyPhase("complete");
    }
  }, [revealedCount, journeyChapters.length, scrollToChapter]);

  // Handle image upload
  const handleImageUpload = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      setUploadedImage({ dataUrl: reader.result as string });
    };
    reader.readAsDataURL(file);
    e.target.value = "";
  }, []);

  // Reset journey state for new query
  const resetJourney = useCallback(() => {
    setJourneyChapters([]);
    setRevealedCount(0);
    setJourneyPhase("idle");
    setJourneyDestination("");
    setJourneyDuration("");
    chaptersRef.current = [];
    inputRef.current?.focus();
  }, []);

  // Send message
  const sendMessage = async () => {
    const text = input.trim();
    if ((!text && !uploadedImage) || isLoading) return;

    setInput("");
    setIsLoading(true);
    resetJourney();
    setJourneyPhase("loading");

    // Build user message parts
    const userParts: MessagePart[] = [];
    if (uploadedImage) {
      userParts.push({ type: "image", imageUrl: uploadedImage.dataUrl });
    }
    userParts.push({ type: "text", text: text || "What is this place? Plan a journey there from downtown San Francisco." });
    setUploadedImage(null);

    const userMsg: Message = { role: "user", parts: userParts };
    const assistantMsg: Message = { role: "assistant", parts: [] };
    setMessages((prev) => [...prev, userMsg, assistantMsg]);

    // Build API messages
    const apiMessages = [...messages, userMsg].map((m) => {
      const content: any[] = [];
      for (const p of m.parts) {
        if (p.type === "text" && p.text) {
          content.push({ type: "text", text: p.text });
        } else if (p.type === "image" && p.imageUrl) {
          content.push({ type: "image", dataUrl: p.imageUrl });
        } else if (p.type === "tool-call" && p.toolCall) {
          content.push({ type: "tool-call", toolCallId: p.toolCall.toolCallId, toolName: p.toolCall.toolName, args: p.toolCall.args });
          if (p.toolCall.result) {
            content.push({ type: "tool-result", toolCallId: p.toolCall.toolCallId, result: p.toolCall.result });
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
      if (!resp.ok) throw new Error(`API error: ${resp.status}`);

      const reader = resp.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let currentText = "";
      const toolCalls: Map<string, ToolCall> = new Map();

      const updateAssistant = () => {
        const parts: MessagePart[] = [];
        if (currentText) parts.push({ type: "text", text: currentText });
        for (const tc of toolCalls.values()) {
          // Don't render chapter tool calls inline — they go to the journey section
          if (tc.toolName !== "generate_journey_chapter") {
            parts.push({ type: "tool-call", toolCall: tc });
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
          try { event = JSON.parse(jsonStr); } catch { continue; }

          switch (event.type) {
            case "text-delta":
              currentText += event.delta;
              updateAssistant();
              break;

            case "tool-input-start":
              toolCalls.set(event.toolCallId, {
                toolCallId: event.toolCallId,
                toolName: event.toolName,
                args: {},
              });
              if (event.toolName !== "generate_journey_chapter") updateAssistant();
              break;

            case "tool-call":
              toolCalls.set(event.toolCallId, {
                toolCallId: event.toolCallId,
                toolName: event.toolName,
                args: event.args,
              });
              if (event.toolName !== "generate_journey_chapter") updateAssistant();
              break;

            case "tool-result": {
              const tc = toolCalls.get(event.toolCallId);
              if (tc) {
                tc.result = event.result;
                toolCalls.set(event.toolCallId, { ...tc });

                // Collect journey chapters separately
                if (tc.toolName === "generate_journey_chapter") {
                  const newCh = { ...tc };
                  chaptersRef.current = [...chaptersRef.current, newCh].sort(
                    (a, b) => (a.result?.chapter_number || 0) - (b.result?.chapter_number || 0)
                  );
                  setJourneyChapters([...chaptersRef.current]);
                }

                // Extract journey metadata from plan_journey
                if (tc.toolName === "plan_journey" && tc.result?.destination) {
                  setJourneyDestination(tc.result.destination.name || "");
                  setJourneyDuration(tc.result.route?.duration || "");
                }

                updateAssistant();
              }
              break;
            }

            case "error":
              currentText += `\n\n⚠️ ${event.errorText}`;
              updateAssistant();
              break;
          }
        }
      }

      // Streaming complete — if we have chapters, journey is ready
      if (chaptersRef.current.length > 0) {
        setJourneyPhase("ready");
      } else {
        setJourneyPhase("idle");
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
      setJourneyPhase("idle");
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  };

  return (
    <div className="flex h-dvh flex-col bg-zinc-950">
      {/* Header */}
      <header className="flex items-center justify-center border-b border-zinc-800 px-4 py-3 bg-zinc-950/80 backdrop-blur-sm">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-xs font-bold text-white">W</div>
          <h1 className="text-lg font-semibold text-white tracking-tight">Wayfinder</h1>
        </div>
        <span className="ml-2 text-xs text-zinc-500">AI-Guided City Journeys</span>
      </header>

      {/* Main Content */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-2xl px-4 py-6 space-y-4">
          {/* Welcome Screen */}
          {messages.length === 0 && (
            <div className="text-center py-16">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-3xl mx-auto mb-6 shadow-lg shadow-blue-500/20">
                🌉
              </div>
              <h2 className="text-2xl font-bold text-white mb-2">Welcome to Wayfinder</h2>
              <p className="text-sm text-zinc-400 max-w-sm mx-auto mb-8">
                Upload a photo of any place in San Francisco, or tell me where you want to go.
                I&apos;ll create an immersive guided journey with transit directions, local stories, weather, and the perfect soundtrack.
              </p>

              {/* Upload Photo CTA */}
              <button
                onClick={() => fileInputRef.current?.click()}
                className="inline-flex items-center gap-2 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white rounded-xl px-6 py-3 text-sm font-medium transition-all shadow-lg shadow-blue-500/20 hover:shadow-blue-500/30 mb-6"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                Upload a Photo
              </button>

              <p className="text-xs text-zinc-500 mb-4">or try one of these destinations:</p>
              <div className="flex flex-wrap justify-center gap-2">
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
                      setTimeout(() => document.querySelector("form")?.requestSubmit(), 50);
                    }}
                    className="text-xs bg-zinc-800 hover:bg-zinc-700 text-zinc-300 px-3 py-2 rounded-full transition-colors border border-zinc-700 hover:border-zinc-600"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Messages */}
          {messages.map((msg, i) => (
            <div key={i}>
              {msg.role === "user" ? (
                <div className="flex justify-end">
                  <div className="bg-blue-600 text-white rounded-2xl rounded-br-md px-4 py-2 max-w-md">
                    {msg.parts.map((p, j) => {
                      if (p.type === "image" && p.imageUrl) {
                        return <img key={j} src={p.imageUrl} alt="Uploaded" className="rounded-lg max-h-48 mb-2" />;
                      }
                      if (p.type === "text" && p.text) {
                        return <div key={j} className="text-sm">{p.text}</div>;
                      }
                      return null;
                    })}
                  </div>
                </div>
              ) : (
                <div className="space-y-1">
                  {msg.parts.map((part, j) => {
                    if (part.type === "text" && part.text) {
                      return (
                        <div key={j} className="text-sm text-zinc-200 leading-relaxed whitespace-pre-wrap">{part.text}</div>
                      );
                    }
                    if (part.type === "tool-call" && part.toolCall) {
                      if (!part.toolCall.result) {
                        return (
                          <div key={j} className="my-4 rounded-xl border border-zinc-700 bg-zinc-900 p-4 animate-pulse">
                            <div className="flex items-center gap-2 text-sm text-zinc-400">
                              <div className="h-4 w-4 animate-spin rounded-full border-2 border-zinc-600 border-t-blue-400" />
                              {part.toolCall.toolName === "plan_journey" ? "Planning your journey..." :
                               part.toolCall.toolName === "show_weather_card" ? "Checking weather..." :
                               part.toolCall.toolName === "show_map_route" ? "Mapping your route..." :
                               "Loading..."}
                            </div>
                          </div>
                        );
                      }
                      if (part.toolCall.toolName === "show_weather_card") return <WeatherCard key={j} args={part.toolCall.result} />;
                      if (part.toolCall.toolName === "show_map_route") return <MapRoute key={j} args={part.toolCall.result} />;
                      // plan_journey and search_knowledge_base are data-only
                      return null;
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

          {/* Journey Loading Indicator */}
          {(journeyPhase === "loading" || (journeyPhase === "ready" && journeyChapters.length === 0)) && isLoading && (
            <div className="my-6 overflow-hidden rounded-2xl border border-zinc-700/50 bg-gradient-to-br from-zinc-900 via-zinc-900 to-zinc-800 p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="h-5 w-5 animate-spin rounded-full border-2 border-zinc-600 border-t-blue-400" />
                <span className="text-sm font-medium text-white">Building your journey...</span>
              </div>
              <div className="space-y-2 text-xs text-zinc-400">
                <div className="flex items-center gap-2"><span className="text-green-400">✓</span> Planning transit route</div>
                <div className="flex items-center gap-2"><span className="text-green-400">✓</span> Fetching weather data</div>
                <div className="flex items-center gap-2">
                  <div className="h-3 w-3 animate-spin rounded-full border border-zinc-600 border-t-blue-400" />
                  Generating chapters with audio narration...
                </div>
              </div>
              <div className="mt-4 h-1.5 w-full rounded-full bg-zinc-800 overflow-hidden">
                <div className="h-full rounded-full bg-gradient-to-r from-blue-600 to-purple-500 animate-pulse" style={{ width: `${Math.max(20, (journeyChapters.length / 5) * 100)}%`, transition: "width 0.5s ease" }} />
              </div>
              {journeyChapters.length > 0 && (
                <div className="mt-2 text-xs text-zinc-500">{journeyChapters.length} chapter{journeyChapters.length > 1 ? "s" : ""} ready</div>
              )}
            </div>
          )}

          {/* "Begin Journey" CTA */}
          {journeyPhase === "ready" && (
            <div className="my-8 overflow-hidden rounded-2xl border border-blue-500/30 bg-gradient-to-br from-blue-950 via-indigo-950 to-purple-950 p-6 text-center shadow-lg shadow-blue-500/10">
              <div className="text-3xl mb-3">🗺️</div>
              <h3 className="text-xl font-bold text-white mb-1">
                Your Journey to {journeyDestination || "your destination"}
              </h3>
              <p className="text-sm text-zinc-400 mb-1">is ready</p>
              <p className="text-xs text-zinc-500 mb-5">
                {journeyChapters.length} chapters{journeyDuration ? ` · ${journeyDuration}` : ""}
              </p>
              <button
                onClick={beginJourney}
                className="inline-flex items-center gap-2 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white rounded-xl px-8 py-3 text-sm font-semibold transition-all shadow-lg shadow-blue-500/20 hover:shadow-blue-500/30 hover:scale-105"
              >
                🚀 Begin Your Journey
              </button>
            </div>
          )}

          {/* Journey Chapter Carousel (one at a time) */}
          {(journeyPhase === "playing" || journeyPhase === "complete") && journeyChapters.length > 0 && (
            <div className="my-6">
              {/* Current chapter */}
              <div className="animate-in">
                <JourneyChapter
                  key={journeyChapters[Math.min(revealedCount - 1, journeyChapters.length - 1)].toolCallId}
                  args={journeyChapters[Math.min(revealedCount - 1, journeyChapters.length - 1)].result}
                  isActive={true}
                />
              </div>

              {/* Journey Complete */}
              {journeyPhase === "complete" && (
                <div className="text-center py-6">
                  <div className="text-3xl mb-2">🎉</div>
                  <div className="text-lg font-semibold text-white">Journey Complete!</div>
                  <p className="text-xs text-zinc-400 mt-1">
                    You&apos;ve explored the full route to {journeyDestination}
                  </p>
                  <button
                    onClick={resetJourney}
                    className="mt-4 text-sm text-blue-400 hover:text-blue-300 transition-colors"
                  >
                    Explore another destination →
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Bottom Bar: Journey Controls or Chat Input */}
      <div className="border-t border-zinc-800 bg-zinc-950/80 backdrop-blur-sm">
        {/* Journey Carousel Controls */}
        {(journeyPhase === "playing") && (
          <div className="px-4 py-3">
            <div className="mx-auto max-w-2xl">
              {/* Progress dots */}
              <div className="flex items-center justify-center gap-1.5 mb-3">
                {journeyChapters.map((_, i) => (
                  <div
                    key={i}
                    className={`h-1.5 rounded-full transition-all duration-300 ${
                      i === revealedCount - 1 ? "w-6 bg-blue-500" : i < revealedCount ? "w-1.5 bg-blue-500/40" : "w-1.5 bg-zinc-700"
                    }`}
                  />
                ))}
              </div>
              <div className="flex items-center justify-between">
                <button
                  onClick={() => { if (revealedCount > 1) setRevealedCount(revealedCount - 1); }}
                  disabled={revealedCount <= 1}
                  className="flex items-center gap-1 text-zinc-400 hover:text-white disabled:text-zinc-700 text-sm transition-colors px-3 py-2"
                >
                  ← Prev
                </button>
                <div className="text-xs text-zinc-400 font-medium">
                  {revealedCount} / {journeyChapters.length}
                </div>
                {revealedCount < journeyChapters.length ? (
                  <button
                    onClick={nextChapter}
                    className="flex items-center gap-1 bg-blue-600 hover:bg-blue-500 text-white rounded-xl px-4 py-2 text-sm font-medium transition-colors"
                  >
                    Next →
                  </button>
                ) : (
                  <button
                    onClick={() => setJourneyPhase("complete")}
                    className="flex items-center gap-1 bg-green-600 hover:bg-green-500 text-white rounded-xl px-4 py-2 text-sm font-medium transition-colors"
                  >
                    Finish 🎉
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Chat Input */}
        {(journeyPhase === "idle" || journeyPhase === "complete" || journeyPhase === "loading" || journeyPhase === "ready") && (
          <div className="px-4 py-3">
            {/* Image Preview */}
            {uploadedImage && (
              <div className="mx-auto max-w-2xl mb-2">
                <div className="relative inline-block">
                  <img src={uploadedImage.dataUrl} alt="Upload preview" className="h-20 rounded-lg border border-zinc-700" />
                  <button
                    onClick={() => setUploadedImage(null)}
                    className="absolute -top-2 -right-2 bg-red-500 hover:bg-red-400 text-white rounded-full w-5 h-5 text-xs flex items-center justify-center shadow"
                  >
                    ×
                  </button>
                </div>
              </div>
            )}
            <form
              onSubmit={(e) => { e.preventDefault(); sendMessage(); }}
              className="mx-auto max-w-2xl flex gap-2"
            >
              {/* Image upload button */}
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                className="bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-white rounded-xl px-3 py-3 transition-colors border border-zinc-700 hover:border-zinc-600"
                title="Upload a photo"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={handleImageUpload}
              />
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={uploadedImage ? "Where is this place?" : "Where do you want to go in San Francisco?"}
                className="flex-1 bg-zinc-800 text-white text-sm rounded-xl px-4 py-3 outline-none ring-1 ring-zinc-700 focus:ring-blue-500 transition-all placeholder:text-zinc-500"
                disabled={isLoading}
                autoFocus
              />
              <button
                type="submit"
                disabled={isLoading || (!input.trim() && !uploadedImage)}
                className="bg-blue-600 hover:bg-blue-500 disabled:bg-zinc-700 disabled:text-zinc-500 text-white rounded-xl px-5 py-3 text-sm font-medium transition-colors"
              >
                {isLoading ? (
                  <div className="h-4 w-4 animate-spin rounded-full border-2 border-zinc-400 border-t-white" />
                ) : (
                  "Go"
                )}
              </button>
            </form>
          </div>
        )}
      </div>

      {/* CSS for animations */}
      <style jsx global>{`
        @keyframes fadeInUp {
          from { opacity: 0; transform: translateY(16px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .animate-in {
          animation: fadeInUp 0.5s ease-out;
        }
      `}</style>
    </div>
  );
}
