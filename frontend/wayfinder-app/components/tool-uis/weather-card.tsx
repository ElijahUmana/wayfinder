"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";

export const WeatherCardToolUI = makeAssistantToolUI<
  {
    location: string;
    temperature: number;
    conditions: string;
    humidity?: number;
    wind_speed?: number;
    uv_index?: number;
    sunrise?: string;
    sunset?: string;
    best_time_note?: string;
  },
  Record<string, unknown>
>({
  toolName: "show_weather_card",
  render: ({ args, status }) => {
    if (status.type === "running") {
      return (
        <div className="my-4 rounded-xl border border-zinc-700 bg-zinc-900 p-4 animate-pulse">
          <div className="flex items-center gap-2 text-sm text-zinc-400">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-zinc-600 border-t-sky-400" />
            Checking weather...
          </div>
        </div>
      );
    }

    if (!args) return null;

    const getWeatherEmoji = (conditions: string) => {
      const c = conditions.toLowerCase();
      if (c.includes("clear") || c.includes("sunny")) return "☀️";
      if (c.includes("cloud") || c.includes("overcast")) return "⛅";
      if (c.includes("rain") || c.includes("drizzle")) return "🌧️";
      if (c.includes("fog")) return "🌫️";
      if (c.includes("snow")) return "❄️";
      if (c.includes("thunder")) return "⛈️";
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
            <span className="text-3xl">{getWeatherEmoji(args.conditions)}</span>
          </div>

          <div className="mt-3 flex items-baseline gap-1">
            <span className="text-4xl font-bold text-white">{Math.round(args.temperature)}</span>
            <span className="text-lg text-zinc-400">°F</span>
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
            {args.uv_index !== undefined && (
              <div className="rounded-lg bg-zinc-800/50 px-3 py-2">
                <div className="text-xs text-zinc-500">UV Index</div>
                <div className="text-sm text-zinc-200">{args.uv_index}</div>
              </div>
            )}
            {args.sunset && (
              <div className="rounded-lg bg-zinc-800/50 px-3 py-2">
                <div className="text-xs text-zinc-500">Sunset</div>
                <div className="text-sm text-zinc-200">{args.sunset}</div>
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
  },
});
