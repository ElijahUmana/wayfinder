export const maxDuration = 60;

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export async function POST(req: Request) {
  const body = await req.json();
  try {
    const resp = await fetch(`${BACKEND_URL}/api/tools/tts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await resp.json();
    return Response.json(data);
  } catch (e: any) {
    return Response.json({ audio_url: null, error: e.message });
  }
}
