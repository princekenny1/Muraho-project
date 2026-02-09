/**
 * /api/ask-rwanda — RAG-powered AI assistant
 * Ported from: supabase/functions/ask-rwanda/index.ts (380 lines)
 * Routes to: FastAPI AI service (self-hosted vLLM/Ollama)
 *
 * Flow: Frontend → Payload endpoint → FastAPI AI service → vLLM → pgvector RAG → response
 * Supports: streaming SSE, kid-friendly mode, trauma-aware safety, context-aware prompts
 */
import type { PayloadHandler } from "payload";

interface AskRwandaBody {
  messages: Array<{ role: "user" | "assistant" | "system"; content: string }>;
  context: { type: "location" | "route" | "museum" | "story" | null; id: string; title: string } | null;
  filter: string;
  mode: "standard" | "personal_voices" | "kid_friendly";
  isPreview?: boolean;
}

export const askRwanda: PayloadHandler = async (req) => {
  try {
    const body = ((await req.json?.()) || (req as any).body) as AskRwandaBody;
    const { messages, context, filter, mode = "standard", isPreview = false } = body || {};

    if (!messages?.length) {
      return Response.json({ error: "messages array is required" }, { status: 400 });
    }

    // ── 1. Fetch AI config from Payload collections ──────
    const [toneResult, modeResult, safetyResult, modelResult] = await Promise.all([
      req.payload.find({ collection: "ai-tone-profiles", where: { mode: { equals: mode } }, limit: 1 }),
      req.payload.find({ collection: "ai-mode-configs", where: { mode: { equals: mode } }, limit: 1 }),
      req.payload.find({ collection: "ai-safety-settings", limit: 1 }),
      req.payload.find({ collection: "ai-model-settings", limit: 1 }),
    ]);

    const toneProfile = toneResult.docs[0] || null;
    const modeConfig = modeResult.docs[0] || null;
    const safetySettings = safetyResult.docs[0] || null;
    const modelSettings = modelResult.docs[0] || null;

    // ── 2. Sensitivity check ─────────────────────────────
    const lastUserMsg = messages.filter((m) => m.role === "user").pop();
    const sensitiveThemes: string[] = (safetySettings?.sensitiveThemes as string[]) || [
      "genocide history", "violence", "trauma", "memorial testimonies",
    ];
    const isSensitive = lastUserMsg
      ? sensitiveThemes.some((t) => lastUserMsg.content.toLowerCase().includes(t.toLowerCase()))
      : false;

    // Kid-friendly mode: block sensitive content
    if (mode === "kid_friendly" && safetySettings?.hideGraphicInKidMode && isSensitive) {
      return Response.json({
        response: "This topic is for older visitors. Would you like to learn about Rwanda's beautiful nature and wildlife instead? 🌿🦍",
        sources: ["Visit Rwanda"],
        metadata: { isSensitive: true, mode, blocked: true },
      });
    }

    // ── 3. Build system prompt ───────────────────────────
    let systemPrompt = (toneProfile?.systemPrompt as string) ||
      `You are Ask Rwanda, a knowledgeable and respectful AI assistant for the Muraho Rwanda app.
Your purpose is to help users understand Rwanda's history, heritage, culture, memorials, and travel experiences.

CRITICAL KNOWLEDGE BOUNDARY:
- You MUST ONLY use information from the Muraho Rwanda content library (stories, museums, routes, testimonies, documentaries, and other platform content).
- NEVER draw on external knowledge, general training data, or any source outside the Muraho Rwanda platform.
- If you do not have enough information from the platform content to answer a question, say so honestly and suggest the user explore related content on the platform.
- Do NOT fabricate, hallucinate, or supplement answers with information not present in the platform's content library.
- If asked to use external sources, politely explain that you only use verified content from the Muraho Rwanda platform to ensure accuracy and cultural sensitivity.`;

    if (safetySettings?.enableHarmSensitivity) {
      systemPrompt += `\n\nSAFETY GUIDELINES:\n${safetySettings.safetyGuidelines || "Always be respectful and avoid harmful content."}`;
    }
    if (safetySettings?.enableTraumaAwareLanguage) {
      systemPrompt += `\n\nTRAUMA-INFORMED COMMUNICATION:
- Use survivor-informed language
- Never sensationalize or use graphic descriptions
- Acknowledge the gravity of sensitive topics
- Prioritize educational focus over emotional exploitation`;
    }

    // Mode-specific instructions
    if (modeConfig) {
      let modeInstr = "\n\nMODE-SPECIFIC INSTRUCTIONS:";
      if (modeConfig.preferTestimonies) modeInstr += "\n- Prioritize personal testimonies and survivor stories";
      if (modeConfig.blockSensitiveContent) {
        modeInstr += "\n- Filter out disturbing or graphic content\n- Use age-appropriate language";
      }
      if (modeConfig.useSimplifiedLanguage) {
        modeInstr += "\n- Use simple, clear language\n- Keep sentences short\n- Use friendly, encouraging tone";
      }
      const sources = [];
      if (modeConfig.includeStories) sources.push("stories");
      if (modeConfig.includePanels) sources.push("museum panels");
      if (modeConfig.includeTestimonies) sources.push("testimonies");
      if (modeConfig.includeRoutes) sources.push("route narratives");
      if (sources.length) modeInstr += `\n- You may reference: ${sources.join(", ")}`;
      systemPrompt += modeInstr;
    }

    // Context
    if (context?.type) {
      const contextMap: Record<string, string> = {
        location: `The user is asking about location: "${context.title}". Focus on history, significance, and visitor experience.`,
        museum: `The user is exploring museum: "${context.title}". Focus on exhibits, history, and visitor guidance.`,
        route: `The user is on journey: "${context.title}". Focus on stops, historical significance, and travel tips.`,
        story: `The user is exploring story: "${context.title}". Focus on deeper context and related stories.`,
      };
      systemPrompt += `\n\nCONTEXT: ${contextMap[context.type] || ""}`;
    }
    if (filter && filter !== "all") {
      systemPrompt += `\n\nFOCUS AREA: Prioritize "${filter}" category.`;
    }

    // ── 4. Forward to FastAPI AI service ─────────────────
    const aiServiceUrl = process.env.AI_SERVICE_URL || "http://ai-service:8000";
    const aiPayload = {
      messages: [{ role: "system" as const, content: systemPrompt }, ...messages],
      mode,
      model: (modelSettings?.modelName as string) || "mistral-nemo",
      temperature: (modeConfig?.temperature as number) ?? 0.4,
      max_tokens: (modeConfig?.maxAnswerTokens as number) ?? 512,
      context: context || undefined,
      stream: !isPreview,
    };

    const aiResponse = await fetch(`${aiServiceUrl}/api/v1/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(aiPayload),
    });

    if (!aiResponse.ok) {
      const errText = await aiResponse.text();
      req.payload.logger?.error?.(`AI service error: ${aiResponse.status} — ${errText}`);
      return Response.json({ error: "AI service unavailable" }, { status: aiResponse.status });
    }

    // ── 5. Log conversation ──────────────────────────────
    const logData = {
      user: (req as any).user?.id || undefined,
      query: lastUserMsg?.content || "",
      mode,
      modelUsed: (modelSettings?.modelName as string) || "mistral-nemo",
      safetyFlagged: isSensitive,
      context: context ? JSON.stringify(context) : undefined,
    };

    req.payload.create({ collection: "ai-conversations", data: logData as any }).catch(() => {});

    // ── 6. Return (streaming or JSON) ────────────────────
    if (isPreview) {
      const data = await aiResponse.json();
      return Response.json({
        response: data.response || data.choices?.[0]?.message?.content || "",
        sources: data.sources || [],
        metadata: { isSensitive, mode, toneProfile: toneProfile?.name },
      });
    }

    // Stream SSE: pipe AI response body to client
    return new Response(aiResponse.body, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      },
    });
  } catch (err: any) {
    req.payload.logger?.error?.(`ask-rwanda error: ${err.message}`);
    return Response.json({ error: err.message }, { status: 500 });
  }
};
