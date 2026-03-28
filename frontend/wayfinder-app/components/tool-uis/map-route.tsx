"use client";

import { makeAssistantToolUI } from "@assistant-ui/react";

export const MapRouteToolUI = makeAssistantToolUI<
  {
    origin: { lat: number; lng: number; name: string };
    destination: { lat: number; lng: number; name: string };
    polyline?: string;
    segments?: Array<{
      mode: string;
      duration: string;
      transit_info?: string;
    }>;
    pois?: Array<{
      name: string;
      lat: number;
      lng: number;
      type: string;
    }>;
  },
  Record<string, unknown>
>({
  toolName: "show_map_route",
  render: ({ args, status }) => {
    if (status.type === "running") {
      return (
        <div className="my-4 rounded-xl border border-zinc-700 bg-zinc-900 p-4 animate-pulse">
          <div className="flex items-center gap-2 text-sm text-zinc-400">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-zinc-600 border-t-emerald-400" />
            Mapping your route...
          </div>
        </div>
      );
    }

    if (!args) return null;

    // Build OpenStreetMap embed URL centered on the midpoint
    const midLat = (args.origin.lat + args.destination.lat) / 2;
    const midLng = (args.origin.lng + args.destination.lng) / 2;
    const bbox = `${Math.min(args.origin.lng, args.destination.lng) - 0.02},${Math.min(args.origin.lat, args.destination.lat) - 0.01},${Math.max(args.origin.lng, args.destination.lng) + 0.02},${Math.max(args.origin.lat, args.destination.lat) + 0.01}`;

    const mapUrl = `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${args.destination.lat},${args.destination.lng}`;

    return (
      <div className="my-4 overflow-hidden rounded-xl border border-zinc-700 bg-zinc-900">
        {/* Map */}
        <iframe
          src={mapUrl}
          className="h-56 w-full border-0"
          title="Journey Route Map"
          loading="lazy"
        />

        {/* Route Summary */}
        <div className="p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="text-sm font-medium text-white">
              {args.origin.name} → {args.destination.name}
            </div>
          </div>

          {/* Segment Timeline */}
          {args.segments && args.segments.length > 0 && (
            <div className="flex items-center gap-1 overflow-x-auto pb-2">
              {args.segments.map((seg, i) => {
                const isTransit = seg.mode === "TRANSIT";
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
                    {i < (args.segments?.length ?? 0) - 1 && (
                      <div className="w-4 h-px bg-zinc-700" />
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* POIs */}
          {args.pois && args.pois.length > 0 && (
            <div className="mt-3 border-t border-zinc-800 pt-3">
              <div className="text-xs text-zinc-400 mb-2">Points of Interest Along Route</div>
              <div className="grid grid-cols-2 gap-1">
                {args.pois.slice(0, 6).map((poi, i) => (
                  <div key={i} className="flex items-center gap-1 text-xs text-zinc-300 bg-zinc-800/50 rounded px-2 py-1">
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
  },
});
