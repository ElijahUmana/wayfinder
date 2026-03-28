"use client";

import { AssistantRuntimeProvider } from "@assistant-ui/react";
import {
  useChatRuntime,
  AssistantChatTransport,
} from "@assistant-ui/react-ai-sdk";
import { Thread } from "@/components/assistant-ui/thread";
import { JourneyChapterToolUI } from "@/components/tool-uis/journey-chapter";
import { WeatherCardToolUI } from "@/components/tool-uis/weather-card";
import { MapRouteToolUI } from "@/components/tool-uis/map-route";

export const Assistant = () => {
  const runtime = useChatRuntime({
    transport: new AssistantChatTransport({
      api: "/api/chat",
    }),
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <JourneyChapterToolUI />
      <WeatherCardToolUI />
      <MapRouteToolUI />
      <div className="flex h-dvh flex-col bg-zinc-950">
        <header className="flex items-center justify-center border-b border-zinc-800 px-4 py-3">
          <h1 className="text-lg font-semibold text-white tracking-tight">
            Wayfinder
          </h1>
          <span className="ml-2 text-xs text-zinc-500">AI-Guided City Journeys</span>
        </header>
        <div className="flex-1 overflow-hidden">
          <Thread />
        </div>
      </div>
    </AssistantRuntimeProvider>
  );
};
