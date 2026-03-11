import type { CollectionConfig } from "payload";
import { publicReadAdminWrite, isAdmin, ownerAccess } from "../access";

const aiModeOptions = [
  { label: "Standard", value: "standard" },
  { label: "Personal Voices", value: "personal_voices" },
  { label: "Kid-Friendly", value: "kid_friendly" },
];

// ── AI TONE PROFILES (maps: public.ai_tone_profiles) ─────
export const AIToneProfiles: CollectionConfig = {
  slug: "ai-tone-profiles",
  admin: { useAsTitle: "name", defaultColumns: ["name", "mode", "isActive"], group: "AI" },
  access: publicReadAdminWrite,
  fields: [
    { name: "mode", type: "select", required: true, unique: true, options: aiModeOptions },
    { name: "name", type: "text", required: true },
    { name: "description", type: "textarea" },
    { name: "systemPrompt", type: "textarea", required: true },
    { name: "exampleResponse", type: "textarea" },
    { name: "isActive", type: "checkbox", defaultValue: true, admin: { position: "sidebar" } },
  ],
};

// ── AI MODE CONFIGS (maps: public.ai_mode_configs) ───────
export const AIModeConfigs: CollectionConfig = {
  slug: "ai-mode-configs",
  admin: { useAsTitle: "mode", defaultColumns: ["mode", "maxAnswerTokens", "temperature"], group: "AI" },
  access: publicReadAdminWrite,
  fields: [
    { name: "mode", type: "select", required: true, unique: true, options: aiModeOptions },
    { name: "toneProfile", type: "relationship", relationTo: "ai-tone-profiles" },
    { name: "maxAnswerTokens", type: "number", required: true, defaultValue: 512 },
    { name: "temperature", type: "number", required: true, defaultValue: 0.4 },
    { name: "includeStories", type: "checkbox", defaultValue: true },
    { name: "includePanels", type: "checkbox", defaultValue: true },
    { name: "includeTestimonies", type: "checkbox", defaultValue: true },
    { name: "includeRoutes", type: "checkbox", defaultValue: true },
    { name: "preferTestimonies", type: "checkbox", defaultValue: false },
    { name: "blockSensitiveContent", type: "checkbox", defaultValue: false },
    { name: "useSimplifiedLanguage", type: "checkbox", defaultValue: false },
  ],
};

// ── AI SAFETY SETTINGS (maps: public.ai_safety_settings) ─
export const AISafetySettings: CollectionConfig = {
  slug: "ai-safety-settings",
  admin: { useAsTitle: "id", defaultColumns: ["enableHarmSensitivity", "enableTraumaAwareLanguage"], group: "AI" },
  access: publicReadAdminWrite,
  fields: [
    { name: "enableHarmSensitivity", type: "checkbox", defaultValue: true },
    { name: "enableTraumaAwareLanguage", type: "checkbox", defaultValue: true },
    { name: "hideGraphicInKidMode", type: "checkbox", defaultValue: true },
    { name: "allowRawTestimonies", type: "checkbox", defaultValue: false },
    { name: "safetyGuidelines", type: "textarea" },
    { name: "sensitiveThemes", type: "json", defaultValue: ["genocide history", "violence", "trauma", "memorial testimonies"] },
  ],
};

// ── AI SOURCE RULES (maps: public.ai_source_rules) ───────
export const AISourceRules: CollectionConfig = {
  slug: "ai-source-rules",
  admin: { useAsTitle: "ruleName", defaultColumns: ["ruleName", "ruleType", "isActive"], group: "AI" },
  access: publicReadAdminWrite,
  fields: [
    { name: "ruleName", type: "text", required: true },
    { name: "ruleType", type: "select", defaultValue: "global", options: [
      { label: "Global", value: "global" }, { label: "Location", value: "location" },
      { label: "Route", value: "route" }, { label: "Mode", value: "mode" },
    ]},
    { name: "targetId", type: "text" },
    { name: "targetMode", type: "select", options: aiModeOptions },
    { name: "includeStories", type: "checkbox", defaultValue: true },
    { name: "includePanels", type: "checkbox", defaultValue: true },
    { name: "includeTestimonies", type: "checkbox", defaultValue: true },
    { name: "includeRoutes", type: "checkbox", defaultValue: true },
    { name: "includeArContent", type: "checkbox", defaultValue: false },
    { name: "includeDrafts", type: "checkbox", defaultValue: false },
    { name: "toneOverride", type: "select", options: aiModeOptions },
    { name: "customInstructions", type: "textarea" },
    { name: "isActive", type: "checkbox", defaultValue: true, admin: { position: "sidebar" } },
  ],
};

// ── AI MODEL SETTINGS (maps: public.ai_model_settings) ───
export const AIModelSettings: CollectionConfig = {
  slug: "ai-model-settings",
  admin: { useAsTitle: "modelName", defaultColumns: ["modelName", "contextWindow", "defaultTemperature"], group: "AI" },
  access: publicReadAdminWrite,
  fields: [
    { name: "modelName", type: "text", required: true, defaultValue: "mistral-nemo" },
    { name: "contextWindow", type: "number", required: true, defaultValue: 8000 },
    { name: "defaultTemperature", type: "number", required: true, defaultValue: 0.4 },
    { name: "defaultMaxTokens", type: "number", required: true, defaultValue: 512 },
    { name: "embeddingModel", type: "text", defaultValue: "multilingual-e5-large" },
    { name: "vectorSimilarity", type: "select", defaultValue: "cosine", options: [
      { label: "Cosine", value: "cosine" }, { label: "Euclidean", value: "euclidean" }, { label: "Inner Product", value: "inner_product" },
    ]},
  ],
};

// ── AI CONVERSATIONS (audit log) ─────────────────────────
export const AIConversations: CollectionConfig = {
  slug: "ai-conversations",
  admin: { useAsTitle: "id", defaultColumns: ["user", "query", "mode", "createdAt"], group: "AI" },
  access: { read: isAdmin, create: () => true, update: isAdmin, delete: isAdmin },
  fields: [
    { name: "user", type: "relationship", relationTo: "users" },
    { name: "query", type: "textarea", required: true },
    { name: "response", type: "textarea" },
    { name: "mode", type: "text" },
    { name: "modelUsed", type: "text" },
    { name: "languageDetected", type: "text" },
    { name: "sourcesUsed", type: "json" },
    { name: "processingMs", type: "number" },
    { name: "safetyFlagged", type: "checkbox", defaultValue: false },
    { name: "safetyReason", type: "text" },
    { name: "feedback", type: "select", options: [
      { label: "Helpful", value: "helpful" }, { label: "Not Helpful", value: "not_helpful" }, { label: "Flagged", value: "flagged" },
    ]},
    { name: "context", type: "json" },
  ],
};
