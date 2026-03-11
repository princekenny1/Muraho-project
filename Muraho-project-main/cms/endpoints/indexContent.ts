/**
 * /api/index-content — Extract text and create embedding records
 * Ported from: supabase/functions/index-content/index.ts (389 lines)
 * Called by: triggerEmbedding hook after content create/update
 * Flow: Payload hook → this endpoint → content-embeddings collection → AI service picks up pending
 */
import type { PayloadHandler } from "payload";

type ContentType = "story" | "testimony" | "documentary" | "panel" | "quote" | "route";

interface IndexRequest {
  contentId: string;
  contentType: ContentType;
  operation?: "create" | "update";
}

/** Extract indexable text from any content type */
async function extractText(
  payload: any,
  contentId: string,
  contentType: ContentType
): Promise<{ text: string; metadata: Record<string, any> }> {
  let text = "";
  let metadata: Record<string, any> = {};

  switch (contentType) {
    case "story": {
      const story = await payload.findByID({ collection: "stories", id: contentId });
      text = `${story.title}\n\n${story.summary || ""}\n\n`;

      // Get story blocks
      const blocks = await payload.find({
        collection: "story-blocks",
        where: { story: { equals: contentId } },
        sort: "blockOrder",
        limit: 100,
      });
      for (const block of blocks.docs) {
        const c = block.content || {};
        if (block.blockType === "text") text += `${c.text || ""}\n\n`;
        else if (block.blockType === "quote") text += `Quote: "${c.text || ""}" — ${c.attribution || ""}\n\n`;
        else if (block.blockType === "timeline") {
          for (const ev of c.events || []) text += `${ev.year}: ${ev.description}\n`;
        }
      }

      // Tags
      const tags = await payload.find({
        collection: "content-tags",
        where: { contentId: { equals: contentId }, contentType: { equals: "story" } },
      });

      metadata = {
        title: story.title, slug: story.slug, isFeatured: story.isFeatured,
        hasSensitiveContent: story.hasSensitiveContent, sensitivityLevel: story.sensitivityLevel,
        tags: tags.docs.map((t: any) => ({ tagType: t.tagType, tagId: t.tagId })),
      };
      break;
    }

    case "testimony": {
      const t = await payload.findByID({ collection: "testimonies", id: contentId });
      text = `${t.title}\n\nSpeaker: ${t.personName}\nContext: ${t.context}\n\n`;

      const segments = t.transcriptSegments || [];
      if (Array.isArray(segments)) {
        for (const seg of segments) {
          if (seg.speaker) text += `${seg.speaker}: `;
          text += `${seg.text}\n`;
        }
      }

      metadata = {
        title: t.title, personName: t.personName, category: t.category,
        location: t.location, year: t.year,
      };
      break;
    }

    case "documentary": {
      const doc = await payload.findByID({ collection: "documentaries", id: contentId });
      text = `${doc.title}\nDirector: ${doc.director || "Unknown"}\nYear: ${doc.year}\n\n${doc.synopsis}\n\n`;

      // Chapters + transcripts (embedded arrays)
      for (const ch of doc.chapters || []) {
        text += `Chapter ${ch.chapterNumber}: ${ch.title}\n`;
        for (const tr of ch.transcripts || []) {
          if (tr.speaker) text += `${tr.speaker}: `;
          text += `${tr.text}\n`;
        }
        text += "\n";
      }

      // Clips
      const clips = await payload.find({
        collection: "documentary-clips",
        where: { documentary: { equals: contentId } },
      });
      if (clips.docs.length) {
        text += "Clips:\n";
        for (const clip of clips.docs) text += `- ${clip.title}: ${clip.description || ""}\n`;
      }

      metadata = {
        title: doc.title, slug: doc.slug, director: doc.director,
        year: doc.year, runtime: doc.runtime, type: doc.type,
      };
      break;
    }

    case "panel": {
      // Museum panels (embedded blocks)
      const panel = await payload.findByID({ collection: "museum-panels", id: contentId, depth: 1 });
      text = `Panel: ${panel.title}\nNumber: ${panel.panelNumber || ""}\n\n`;

      for (const block of panel.blocks || []) {
        const c = block.content || {};
        if (block.blockType === "text") text += `${c.text || ""}\n\n`;
        else if (block.blockType === "quote") text += `"${c.text || ""}" — ${c.attribution || ""}\n\n`;
        else if (block.blockType === "context") text += `Context: ${c.text || ""}\n\n`;
      }

      metadata = { title: panel.title, panelNumber: panel.panelNumber };
      break;
    }

    case "quote": {
      const q = await payload.findByID({ collection: "quotes", id: contentId, depth: 1 });
      text = `"${q.text}"\n`;
      if (q.attribution) text += `— ${q.attribution}\n`;
      else if (q.person?.name) text += `— ${q.person.name}\n`;

      metadata = { text: q.text, attribution: q.attribution, isFeatured: q.isFeatured };
      break;
    }

    case "route": {
      const route = await payload.findByID({ collection: "routes", id: contentId });
      text = `${route.title}\n\n${route.description || ""}\n\n`;

      // Get stops
      const stops = await payload.find({
        collection: "route-stops",
        where: { route: { equals: contentId } },
        sort: "stopOrder",
        limit: 50,
      });
      for (const stop of stops.docs) {
        text += `Stop: ${stop.title}\n${stop.description || ""}\n\n`;
      }

      metadata = { title: route.title, slug: route.slug, difficulty: route.difficulty };
      break;
    }
  }

  return { text: text.trim(), metadata };
}

export const indexContent: PayloadHandler = async (req) => {
  try {
    const body = await (req as any).json?.() || (req as any).body || {};
    const { contentId, contentType, operation }: IndexRequest = body;

    if (!contentId || !contentType) {
      return Response.json({ error: "contentId and contentType are required" }, { status: 400 });
    }

    // Extract text
    const { text, metadata } = await extractText(req.payload, contentId, contentType);

    if (!text) {
      return Response.json({ success: false, message: "No text content to index" });
    }

    // Upsert embedding record
    const existing = await req.payload.find({
      collection: "content-embeddings",
      where: {
        contentId: { equals: contentId },
        contentType: { equals: contentType },
      },
      limit: 1,
    });

    if (existing.docs.length) {
      await req.payload.update({
        collection: "content-embeddings",
        id: existing.docs[0].id,
        data: { textContent: text, metadata, embeddingStatus: "pending" },
      });
    } else {
      await req.payload.create({
        collection: "content-embeddings",
        data: { contentId, contentType, textContent: text, metadata, embeddingStatus: "pending" },
      });
    }

    // Notify AI service to generate actual vector embedding
    const aiServiceUrl = process.env.AI_SERVICE_URL || "http://ai-service:8000";
    fetch(`${aiServiceUrl}/api/v1/embed`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ contentId, contentType, text }),
    }).catch(err => req.payload.logger?.warn?.(`Embed notification failed: ${err}`));

    return Response.json({
      success: true,
      textLength: text.length,
      contentType,
      contentId,
    });
  } catch (err: any) {
    req.payload.logger?.error?.(`index-content error: ${err.message}`);
    return Response.json({ error: err.message }, { status: 500 });
  }
};
