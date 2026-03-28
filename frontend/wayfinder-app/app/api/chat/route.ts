export const maxDuration = 120;

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
const ANTHROPIC_API_KEY = process.env.ANTHROPIC_API_KEY!;

const SYSTEM_PROMPT = `You are Wayfinder, an AI-powered immersive city guide for San Francisco.

When a user asks about visiting a place, wants directions, or mentions a destination:
1. Call plan_journey to get transit directions, weather, and knowledge base context
2. Use the plan_journey result to call show_weather_card with weather data
3. Use the plan_journey result to call show_map_route with route data
4. Generate 4-6 journey chapters using generate_journey_chapter for each segment:
   - Chapter 0: "The Departure" — user's starting point
   - Chapters 1-N: Each transit/walking segment
   - Final Chapter: "The Arrival" — the destination
5. Each chapter should have engaging narration with specific street names, landmarks, and insider tips

For music_mood, use one of: "departure", "transit_urban", "walking", "anticipation", "arrival", "scenic", "evening", "explore", "cafe", "cultural".

If no destination is specified, ask what they want to explore or suggest popular SF spots.

Be enthusiastic but authentic. Sound like a knowledgeable local friend.

IMPORTANT: When you have journey data from plan_journey, ALWAYS call the display tools to render the rich UI. Don't just describe things in text.`;

const TOOLS = [
  {
    name: "plan_journey",
    description:
      "Plan a complete journey from user's location to a destination. Returns transit directions, weather, POIs, and knowledge base context.",
    input_schema: {
      type: "object" as const,
      properties: {
        destination: {
          type: "string",
          description: "Destination name in San Francisco",
        },
        user_location: {
          type: "string",
          description:
            "User's current location (default: Downtown San Francisco)",
        },
      },
      required: ["destination"],
    },
  },
  {
    name: "search_knowledge_base",
    description:
      "Search the San Francisco knowledge base for information about locations, neighborhoods, food, history, or hidden gems.",
    input_schema: {
      type: "object" as const,
      properties: {
        query: { type: "string", description: "What to search for" },
        question: { type: "string", description: "Specific question to answer" },
      },
      required: ["query"],
    },
  },
  {
    name: "generate_journey_chapter",
    description:
      "Generate a single journey chapter with narration, music, and scene description. Call this for each segment of the journey.",
    input_schema: {
      type: "object" as const,
      properties: {
        chapter_number: { type: "integer" },
        title: { type: "string" },
        segment_type: {
          type: "string",
          description: "DEPARTURE, WALKING, TRANSIT, ARRIVAL, or EXPLORE",
        },
        location: { type: "string" },
        duration: { type: "string" },
        transit_info: { type: "string" },
        narration: {
          type: "string",
          description:
            "Vivid 2-4 sentence narration as a local friend guiding them",
        },
        music_mood: {
          type: "string",
          description:
            "One of: departure, transit_urban, walking, anticipation, arrival, scenic, evening, explore, cafe, cultural",
        },
        pois: {
          type: "array",
          items: { type: "string" },
          description: "Points of interest near this segment",
        },
        image_prompt: { type: "string" },
        spotify_embed_url: { type: "string" },
        spotify_playlist_name: { type: "string" },
      },
      required: ["chapter_number", "title", "segment_type", "narration"],
    },
  },
  {
    name: "show_weather_card",
    description: "Display weather information for the destination.",
    input_schema: {
      type: "object" as const,
      properties: {
        location: { type: "string" },
        temperature: { type: "number" },
        conditions: { type: "string" },
        humidity: { type: "number" },
        wind_speed: { type: "number" },
        uv_index: { type: "number" },
        sunrise: { type: "string" },
        sunset: { type: "string" },
        best_time_note: { type: "string" },
      },
      required: ["location", "temperature", "conditions"],
    },
  },
  {
    name: "show_map_route",
    description:
      "Display transit route on a map with origin, destination, and points of interest.",
    input_schema: {
      type: "object" as const,
      properties: {
        origin: {
          type: "object",
          properties: {
            lat: { type: "number" },
            lng: { type: "number" },
            name: { type: "string" },
          },
        },
        destination: {
          type: "object",
          properties: {
            lat: { type: "number" },
            lng: { type: "number" },
            name: { type: "string" },
          },
        },
        polyline: { type: "string" },
        segments: {
          type: "array",
          items: {
            type: "object",
            properties: {
              mode: { type: "string" },
              duration: { type: "string" },
              transit_info: { type: "string" },
            },
          },
        },
        pois: {
          type: "array",
          items: {
            type: "object",
            properties: {
              name: { type: "string" },
              lat: { type: "number" },
              lng: { type: "number" },
              type: { type: "string" },
            },
          },
        },
      },
      required: ["origin", "destination"],
    },
  },
];

const MOOD_PLAYLISTS: Record<string, { id: string; name: string }> = {
  departure: { id: "37i9dQZF1DX1s9knjP51Oa", name: "Calm Vibes" },
  transit_urban: { id: "37i9dQZF1DXc8kgYqMLFJR", name: "Lo-Fi Beats" },
  walking: { id: "37i9dQZF1DX0SM0LYsmbMT", name: "Confidence Boost" },
  anticipation: { id: "37i9dQZF1DX4fpCWaHOned", name: "Building Energy" },
  arrival: { id: "37i9dQZF1DX2sUQwD7tbmL", name: "Feel-Good Indie" },
  scenic: { id: "37i9dQZF1DX4sWSpwq3LiO", name: "Peaceful Piano" },
  evening: { id: "37i9dQZF1DX6VdMW310YC7", name: "Chill Hits" },
  explore: { id: "37i9dQZF1DX2apWzyECwyZ", name: "This Is San Francisco" },
  cafe: { id: "37i9dQZF1DX6ziVCJnEm59", name: "Coffee Shop Jazz" },
  cultural: { id: "37i9dQZF1DWWEJlAGA9gs0", name: "Classical Essentials" },
};

async function executeTool(
  name: string,
  args: Record<string, any>
): Promise<any> {
  if (name === "plan_journey") {
    const resp = await fetch(`${BACKEND_URL}/api/tools/plan_journey`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        destination: args.destination,
        user_location: args.user_location || "Downtown San Francisco",
      }),
    });
    return resp.json();
  }

  if (name === "search_knowledge_base") {
    const resp = await fetch(`${BACKEND_URL}/api/tools/search_knowledge`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(args),
    });
    return resp.json();
  }

  if (name === "generate_journey_chapter") {
    const mood = args.music_mood || "explore";
    const playlist = MOOD_PLAYLISTS[mood] || MOOD_PLAYLISTS.explore;
    return {
      ...args,
      spotify_embed_url: `https://open.spotify.com/embed/playlist/${playlist.id}?utm_source=generator&theme=0`,
      spotify_playlist_name: playlist.name,
    };
  }

  if (name === "show_weather_card" || name === "show_map_route") {
    return args;
  }

  return { error: `Unknown tool: ${name}` };
}

function sseEvent(data: any): string {
  return `data: ${JSON.stringify(data)}\n\n`;
}

export async function POST(req: Request) {
  const body = await req.json();
  const rawMessages = body.messages ?? [];

  // Convert messages to Anthropic format
  const messages: any[] = rawMessages.map((msg: any) => {
    const role = msg.role || "user";
    const content = msg.content;
    if (typeof content === "string") return { role, content };
    if (Array.isArray(content)) {
      const parts: any[] = [];
      for (const p of content) {
        if (p.type === "text") {
          parts.push({ type: "text", text: p.text });
        } else if (p.type === "tool-call") {
          parts.push({
            type: "tool_use",
            id: p.toolCallId,
            name: p.toolName,
            input: p.args || {},
          });
        } else if (p.type === "tool-result") {
          parts.push({
            type: "tool_result",
            tool_use_id: p.toolCallId,
            content: JSON.stringify(p.result || {}),
          });
        }
      }
      if (parts.length === 0) {
        const text = content
          .filter((p: any) => p.type === "text")
          .map((p: any) => p.text)
          .join("\n");
        return { role, content: text || "" };
      }
      return { role, content: parts };
    }
    return { role, content: String(content || "") };
  });

  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    async start(controller) {
      const send = (data: any) => controller.enqueue(encoder.encode(sseEvent(data)));
      let contentIdx = 0;

      send({ type: "start" });

      let currentMessages = [...messages];
      let maxTurns = 8;

      while (maxTurns-- > 0) {
        send({ type: "start-step" });

        // Call Anthropic API directly
        const anthropicResp = await fetch(
          "https://api.anthropic.com/v1/messages",
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "x-api-key": ANTHROPIC_API_KEY,
              "anthropic-version": "2023-06-01",
            },
            body: JSON.stringify({
              model: "claude-sonnet-4-20250514",
              max_tokens: 8192,
              system: SYSTEM_PROMPT,
              messages: currentMessages,
              tools: TOOLS,
              stream: true,
            }),
          }
        );

        if (!anthropicResp.ok) {
          const errorText = await anthropicResp.text();
          send({
            type: "error",
            errorText: `Anthropic API error: ${anthropicResp.status} ${errorText}`,
          });
          break;
        }

        const reader = anthropicResp.body!.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let textStarted = false;
        let currentToolCalls: {
          id: string;
          name: string;
          argsText: string;
          streamIdx: number;
        }[] = [];
        let hasToolUse = false;
        let stopReason = "end_turn";

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

            if (event.type === "content_block_start") {
              if (event.content_block?.type === "text") {
                const id = String(contentIdx++);
                send({ type: "text-start", id });
                textStarted = true;
              } else if (event.content_block?.type === "tool_use") {
                hasToolUse = true;
                const idx = contentIdx++;
                const tc = {
                  id: event.content_block.id,
                  name: event.content_block.name,
                  argsText: "",
                  streamIdx: idx,
                };
                currentToolCalls.push(tc);
                send({
                  type: "tool-input-start",
                  toolCallId: tc.id,
                  toolName: tc.name,
                });
              }
            } else if (event.type === "content_block_delta") {
              if (event.delta?.type === "text_delta" && event.delta.text) {
                send({
                  type: "text-delta",
                  id: String(
                    textStarted ? contentIdx - 1 - currentToolCalls.length : 0
                  ),
                  delta: event.delta.text,
                });
              } else if (event.delta?.type === "input_json_delta") {
                const tc = currentToolCalls[currentToolCalls.length - 1];
                if (tc) {
                  tc.argsText += event.delta.partial_json;
                  send({
                    type: "tool-input-delta",
                    toolCallId: tc.id,
                    inputTextDelta: event.delta.partial_json,
                  });
                }
              }
            } else if (event.type === "content_block_stop") {
              // If we were in text mode, end the text
              if (
                textStarted &&
                currentToolCalls.length === 0
              ) {
                // text block ended — we'll send text-end when we're sure
              }
            } else if (event.type === "message_delta") {
              stopReason = event.delta?.stop_reason || "end_turn";
            }
          }
        }

        // Close any open text blocks
        if (textStarted) {
          // Find the text content index (first one before tool calls)
          send({ type: "text-end", id: "0" });
        }

        // Process tool calls
        if (hasToolUse && currentToolCalls.length > 0) {
          const assistantContent: any[] = [];
          const toolResults: any[] = [];

          for (const tc of currentToolCalls) {
            let args: any = {};
            try {
              args = tc.argsText ? JSON.parse(tc.argsText) : {};
            } catch {}

            // Send tool-call (complete)
            send({
              type: "tool-call",
              toolCallId: tc.id,
              toolName: tc.name,
              args,
            });

            // Execute the tool
            const result = await executeTool(tc.name, args);

            // Send tool-result
            send({
              type: "tool-result",
              toolCallId: tc.id,
              result,
            });

            // Build messages for next turn
            assistantContent.push({
              type: "tool_use",
              id: tc.id,
              name: tc.name,
              input: args,
            });
            toolResults.push({
              type: "tool_result",
              tool_use_id: tc.id,
              content: JSON.stringify(result),
            });
          }

          send({ type: "finish-step" });

          // Add to message history for next turn
          currentMessages.push({
            role: "assistant",
            content: assistantContent,
          });
          currentMessages.push({ role: "user", content: toolResults });

          // Reset for next turn
          currentToolCalls = [];
          textStarted = false;
          continue;
        }

        // No tool calls — we're done
        send({ type: "finish-step" });
        send({ type: "finish", finishReason: "stop" });
        break;
      }

      controller.enqueue(encoder.encode("data: [DONE]\n\n"));
      controller.close();
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}
