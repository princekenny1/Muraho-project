import type { CollectionAfterChangeHook, CollectionBeforeValidateHook } from "payload";

/**
 * triggerEmbedding — Fires after content is published/updated.
 * Notifies the AI service to re-generate vector embeddings for RAG.
 */
export const triggerEmbedding: CollectionAfterChangeHook = async ({
  doc, collection, operation, req,
}) => {
  // Only index published content
  if (doc.status && doc.status !== "published" && doc._status !== "published") return doc;

  const url = process.env.AI_SERVICE_URL || "http://ai-service:8000";
  try {
    await fetch(`${url}/api/v1/index-content`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        contentId: doc.id,
        contentType: collection.slug,
        operation,
      }),
    });
    req.payload.logger.info(`Embedding triggered for ${collection.slug}/${doc.id}`);
  } catch (err) {
    // Non-blocking — content save succeeds even if AI service is down
    req.payload.logger.warn(`Embedding trigger failed for ${collection.slug}/${doc.id}: ${err}`);
  }
  return doc;
};

/**
 * autoSlug — Generates URL-safe slug from title/name if not provided.
 */
export const autoSlug: CollectionBeforeValidateHook = async ({ data }) => {
  if (data && !data.slug && (data.title || data.name)) {
    data.slug = (data.title || data.name)
      .toLowerCase()
      .replace(/[^a-z0-9\s-]/g, "")
      .replace(/\s+/g, "-")
      .substring(0, 100);
  }
  return data;
};
