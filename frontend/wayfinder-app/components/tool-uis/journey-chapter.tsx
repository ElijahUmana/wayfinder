"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";

export const JourneyChapterToolUI = makeAssistantToolUI<
  {
    chapter_number: number;
    title: string;
    segment_type: string;
    narration: string;
    duration?: string;
    transit_info?: string;
    music_mood?: string;
    pois?: string[];
    image_prompt?: string;
    image_b64?: string;
    audio_url?: string;
    spotify_embed_url?: string;
    spotify_playlist_name?: string;
    location?: string;
  },
  Record<string, unknown>
>({
  toolName: "generate_journey_chapter",
  render: ({ args, status }) => {
    if (status.type === "running") {
      return (
        <div className="my-4 rounded-xl border border-zinc-700 bg-zinc-900 p-4 animate-pulse">
          <div className="flex items-center gap-2 text-sm text-zinc-400">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-zinc-600 border-t-blue-400" />
            Creating chapter...
          </div>
        </div>
      );
    }

    if (!args) return null;

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

    const bgGradient = segmentColors[args.segment_type] || "from-zinc-900 to-zinc-800";
    const icon = segmentIcons[args.segment_type] || "📍";

    return (
      <div className={`my-4 overflow-hidden rounded-xl border border-zinc-700 bg-gradient-to-br ${bgGradient}`}>
        {/* Chapter Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-700/50">
          <div className="flex items-center gap-2">
            <span className="text-lg">{icon}</span>
            <div>
              <div className="text-xs font-medium text-zinc-400 uppercase tracking-wider">
                Chapter {args.chapter_number}
              </div>
              <div className="text-sm font-semibold text-white">
                {args.title}
              </div>
            </div>
          </div>
          {args.duration && (
            <div className="text-xs text-zinc-400 bg-zinc-800/50 px-2 py-1 rounded-full">
              {args.duration}
            </div>
          )}
        </div>

        {/* AI Generated Image */}
        {args.image_b64 && args.image_b64.length > 10 && (
          <div className="relative">
            <img
              src={`data:image/png;base64,${args.image_b64}`}
              alt={args.title}
              className="w-full h-48 object-cover"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent" />
          </div>
        )}

        {/* Narration */}
        <div className="px-4 py-3">
          <p className="text-sm text-zinc-200 leading-relaxed italic">
            &ldquo;{args.narration}&rdquo;
          </p>
        </div>

        {/* Transit Info */}
        {args.transit_info && (
          <div className="mx-4 mb-3 flex items-center gap-2 rounded-lg bg-zinc-800/50 px-3 py-2">
            <span className="text-xs">🚏</span>
            <span className="text-xs text-zinc-300">{args.transit_info}</span>
          </div>
        )}

        {/* Points of Interest */}
        {args.pois && args.pois.length > 0 && (
          <div className="mx-4 mb-3">
            <div className="text-xs text-zinc-400 mb-1">Along the way:</div>
            <div className="flex flex-wrap gap-1">
              {args.pois.map((poi, i) => (
                <span key={i} className="text-xs bg-zinc-800 text-zinc-300 px-2 py-0.5 rounded-full">
                  {poi}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Audio Narration */}
        {args.audio_url && (
          <div className="mx-4 mb-3">
            <audio controls className="w-full h-8" preload="none">
              <source src={args.audio_url} type="audio/mpeg" />
            </audio>
          </div>
        )}

        {/* Spotify Embed */}
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
  },
});
