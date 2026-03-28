"""
DigitalOcean Gradient AI service client.

Provides: vision analysis, image generation, text-to-speech, and LLM chat.
All via the OpenAI-compatible API at https://inference.do-ai.run/v1/
"""

import os
import base64
import time
from pathlib import Path
from typing import Optional

import httpx
from openai import OpenAI

_client: Optional[OpenAI] = None
_anthropic_client = None

DO_BASE = "https://inference.do-ai.run/v1"


def _get_do_client() -> Optional[OpenAI]:
    global _client
    key = os.environ.get("DIGITAL_OCEAN_MODEL_ACCESS_KEY", "")
    if not key:
        return None
    if _client is None:
        _client = OpenAI(base_url=f"{DO_BASE}/", api_key=key)
    return _client


def _get_do_headers() -> dict:
    key = os.environ.get("DIGITAL_OCEAN_MODEL_ACCESS_KEY", "")
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _get_anthropic_client():
    global _anthropic_client
    if _anthropic_client is None:
        import anthropic
        _anthropic_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _anthropic_client


# ---------------------------------------------------------------------------
# Vision Analysis
# ---------------------------------------------------------------------------

def analyze_image(image_b64: str, prompt: str, mime_type: str = "image/jpeg") -> str:
    """Analyze an image using vision model. Tries DO Gradient first, falls back to Claude."""
    do_client = _get_do_client()
    if do_client:
        try:
            resp = do_client.chat.completions.create(
                model="openai-gpt-4o",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_b64}"}},
                    ],
                }],
                max_completion_tokens=1024,
            )
            return resp.choices[0].message.content
        except Exception as e:
            print(f"DO Gradient vision failed, falling back to Claude: {e}")

    # Fallback to Claude
    client = _get_anthropic_client()
    resp = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": image_b64}},
            ],
        }],
    )
    return resp.content[0].text


def analyze_image_url(image_url: str, prompt: str) -> str:
    """Analyze an image from URL."""
    do_client = _get_do_client()
    if do_client:
        try:
            resp = do_client.chat.completions.create(
                model="openai-gpt-4o",
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                }],
                max_completion_tokens=1024,
            )
            return resp.choices[0].message.content
        except Exception:
            pass

    # Download and use Claude
    img_resp = httpx.get(image_url)
    img_resp.raise_for_status()
    b64 = base64.b64encode(img_resp.content).decode()
    return analyze_image(b64, prompt)


# ---------------------------------------------------------------------------
# LLM Chat
# ---------------------------------------------------------------------------

def chat(messages: list[dict], system: str = "", max_tokens: int = 2048) -> str:
    """Generate chat completion. Tries DO Gradient, falls back to Claude."""
    do_client = _get_do_client()
    if do_client:
        try:
            msgs = messages.copy()
            if system:
                msgs.insert(0, {"role": "system", "content": system})
            resp = do_client.chat.completions.create(
                model="openai-gpt-4o",
                messages=msgs,
                max_completion_tokens=max_tokens,
            )
            return resp.choices[0].message.content
        except Exception as e:
            print(f"DO Gradient chat failed, falling back to Claude: {e}")

    # Fallback to Claude
    client = _get_anthropic_client()
    resp = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=max_tokens,
        system=system if system else "",
        messages=messages,
    )
    return resp.content[0].text


# ---------------------------------------------------------------------------
# Image Generation
# ---------------------------------------------------------------------------

def generate_image(prompt: str, size: str = "1024x1024") -> Optional[str]:
    """Generate an image using fal-ai/flux/schnell. Returns base64 PNG or None."""
    if not os.environ.get("DIGITAL_OCEAN_MODEL_ACCESS_KEY"):
        return None

    try:
        output = _async_invoke_and_poll(
            "fal-ai/flux/schnell",
            {
                "prompt": prompt,
                "image_size": "landscape_4_3",
                "num_images": 1,
                "num_inference_steps": 4,
                "output_format": "jpeg",
            },
            timeout=60,
        )
        images = output.get("images", [])
        if images and images[0].get("url"):
            # Download and convert to base64
            dl = httpx.get(images[0]["url"], timeout=30)
            dl.raise_for_status()
            return base64.b64encode(dl.content).decode()
    except Exception as e:
        print(f"DO image generation failed: {e}")

    return None


# ---------------------------------------------------------------------------
# Text-to-Speech
# ---------------------------------------------------------------------------

def _async_invoke_and_poll(model_id: str, input_data: dict, timeout: int = 120) -> dict:
    """Submit async job and poll until complete."""
    headers = _get_do_headers()
    with httpx.Client(timeout=timeout) as http:
        resp = http.post(f"{DO_BASE}/async-invoke", headers=headers, json={
            "model_id": model_id,
            "input": input_data,
        })
        resp.raise_for_status()
        request_id = resp.json()["request_id"]

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            status_resp = http.get(f"{DO_BASE}/async-invoke/{request_id}/status", headers=headers)
            status_resp.raise_for_status()
            status = status_resp.json()["status"]
            if status == "COMPLETED":
                result = http.get(f"{DO_BASE}/async-invoke/{request_id}", headers=headers)
                result.raise_for_status()
                return result.json()["output"]
            elif status in ("FAILED", "CANCELLED"):
                raise RuntimeError(f"Async job {status}")
            time.sleep(1.5)

        raise TimeoutError(f"Async job timed out after {timeout}s")


def text_to_speech(text: str, voice: str = "Aria") -> Optional[str]:
    """Generate speech audio. Returns URL to MP3 file or None."""
    if not os.environ.get("DIGITAL_OCEAN_MODEL_ACCESS_KEY"):
        return None

    try:
        output = _async_invoke_and_poll(
            "fal-ai/elevenlabs/tts/multilingual-v2",
            {"text": text, "voice": voice, "stability": 0.5, "similarity_boost": 0.75, "speed": 1.0},
        )
        return output["audio"]["url"]
    except Exception as e:
        print(f"TTS failed: {e}")
        return None
