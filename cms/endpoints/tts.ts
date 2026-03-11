/**
 * /api/tts — Text-to-Speech
 * Ported from: supabase/functions/elevenlabs-tts/index.ts (76 lines)
 * Primary: ElevenLabs API (multilingual v2)
 * Fallback: Self-hosted Piper TTS via AI service
 */
import type { PayloadHandler } from "payload";

export const tts: PayloadHandler = async (req) => {
  try {
    const body = (await (req as any).json?.()) || (req as any).body || {};
    const { text, voiceId = "JBFqnCBsd6RMkjVDRZzb", language = "en", useSelfHosted = false } = body;

    if (!text) return Response.json({ error: "text is required" }, { status: 400 });

    // ── Self-hosted Piper TTS (for Kinyarwanda or cost savings) ──
    if (useSelfHosted || language === "rw") {
      const aiServiceUrl = process.env.AI_SERVICE_URL || "http://ai-service:8000";
      const aiRes = await fetch(`${aiServiceUrl}/api/v1/tts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, language }),
      });

      if (aiRes.ok) {
        const audioBuffer = await aiRes.arrayBuffer();
        return new Response(audioBuffer, {
          headers: { "Content-Type": "audio/mpeg" },
        });
      }
      req.payload.logger?.warn?.("Self-hosted TTS failed, falling back to ElevenLabs");
    }

    // ── ElevenLabs API ───────────────────────────────────
    const apiKey = process.env.ELEVENLABS_API_KEY;
    if (!apiKey) {
      return Response.json({ error: "TTS service not configured" }, { status: 503 });
    }

    const elResponse = await fetch(
      `https://api.elevenlabs.io/v1/text-to-speech/${voiceId}?output_format=mp3_44100_128`,
      {
        method: "POST",
        headers: { "xi-api-key": apiKey, "Content-Type": "application/json" },
        body: JSON.stringify({
          text,
          model_id: "eleven_multilingual_v2",
          voice_settings: {
            stability: 0.6,
            similarity_boost: 0.75,
            style: 0.4,
            use_speaker_boost: true,
            speed: 0.95,
          },
        }),
      }
    );

    if (!elResponse.ok) {
      const errText = await elResponse.text();
      req.payload.logger?.error?.(`ElevenLabs error [${elResponse.status}]: ${errText}`);
      return Response.json({ error: "TTS generation failed" }, { status: elResponse.status });
    }

    const audioBuffer = await elResponse.arrayBuffer();
    return new Response(audioBuffer, {
      headers: {
        "Content-Type": "audio/mpeg",
        "Content-Length": String(audioBuffer.byteLength),
      },
    });
  } catch (err: any) {
    req.payload.logger?.error?.(`TTS error: ${err.message}`);
    return Response.json({ error: err.message }, { status: 500 });
  }
};
