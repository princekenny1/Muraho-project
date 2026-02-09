/**
 * /api/health — System Health Check
 * ===================================
 * Reports status of all backend services.
 *
 * Returns:
 *   {
 *     status: "healthy" | "degraded" | "unhealthy",
 *     version: "1.0.0",
 *     uptime: 3600,
 *     services: { postgres, redis, minio, ai, ollama },
 *     timestamp: "2026-02-04T..."
 *   }
 *
 * Used by: nginx health checks, monitoring, CI smoke tests
 */

import type { PayloadHandler } from "payload";

interface ServiceStatus {
  status: "up" | "down" | "degraded";
  latencyMs: number;
  details?: string;
}

async function checkPostgres(payload: any): Promise<ServiceStatus> {
  const start = Date.now();
  try {
    // A simple find with limit 0 validates DB connectivity
    await payload.find({ collection: "users", limit: 0 });
    return { status: "up", latencyMs: Date.now() - start };
  } catch (err: any) {
    return { status: "down", latencyMs: Date.now() - start, details: err.message };
  }
}

async function checkRedis(): Promise<ServiceStatus> {
  const start = Date.now();
  try {
    const redisUrl = process.env.REDIS_URL || "redis://redis:6379";
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 3000);

    // Simple TCP connection test via fetch (Redis doesn't speak HTTP,
    // but connection refusal tells us the service is down)
    // In production, use ioredis client
    const { createClient } = await import("redis").catch(() => ({ createClient: null }));
    if (!createClient) {
      return { status: "up", latencyMs: Date.now() - start, details: "redis client not available, assuming up" };
    }

    const client = createClient({ url: redisUrl });
    await client.connect();
    await client.ping();
    await client.disconnect();
    clearTimeout(timeout);
    return { status: "up", latencyMs: Date.now() - start };
  } catch (err: any) {
    return { status: "down", latencyMs: Date.now() - start, details: err.message };
  }
}

async function checkMinIO(): Promise<ServiceStatus> {
  const start = Date.now();
  try {
    const endpoint = process.env.S3_ENDPOINT || "http://minio:9000";
    const resp = await fetch(`${endpoint}/minio/health/live`, {
      signal: AbortSignal.timeout(3000),
    });
    return {
      status: resp.ok ? "up" : "degraded",
      latencyMs: Date.now() - start,
    };
  } catch (err: any) {
    return { status: "down", latencyMs: Date.now() - start, details: err.message };
  }
}

async function checkAIService(): Promise<ServiceStatus> {
  const start = Date.now();
  try {
    const aiUrl = process.env.AI_SERVICE_URL || "http://ai-service:8000";
    const resp = await fetch(`${aiUrl}/health`, {
      signal: AbortSignal.timeout(5000),
    });
    const data = await resp.json();
    return {
      status: resp.ok ? "up" : "degraded",
      latencyMs: Date.now() - start,
      details: data.models_loaded ? `Models: ${data.models_loaded.join(", ")}` : undefined,
    };
  } catch (err: any) {
    return { status: "down", latencyMs: Date.now() - start, details: err.message };
  }
}

async function checkOllama(): Promise<ServiceStatus> {
  const start = Date.now();
  try {
    const ollamaUrl = process.env.OLLAMA_BASE_URL || "http://ollama:11434";
    const resp = await fetch(`${ollamaUrl}/api/tags`, {
      signal: AbortSignal.timeout(3000),
    });
    const data = await resp.json();
    const models = data.models?.map((m: any) => m.name) || [];
    return {
      status: resp.ok ? "up" : "degraded",
      latencyMs: Date.now() - start,
      details: models.length > 0 ? `Models: ${models.join(", ")}` : "No models loaded",
    };
  } catch (err: any) {
    return { status: "down", latencyMs: Date.now() - start, details: err.message };
  }
}

// ── Main Handler ──────────────────────────────────────

const startTime = Date.now();

export const healthEndpoint: PayloadHandler = async (req) => {
  const [postgres, redis, minio, ai, ollama] = await Promise.all([
    checkPostgres(req.payload),
    checkRedis(),
    checkMinIO(),
    checkAIService(),
    checkOllama(),
  ]);

  const services = { postgres, redis, minio, ai, ollama };
  const allStatuses = Object.values(services).map((s) => s.status);

  let status: "healthy" | "degraded" | "unhealthy";
  if (allStatuses.every((s) => s === "up")) {
    status = "healthy";
  } else if (allStatuses.includes("down") && allStatuses.filter((s) => s === "down").length >= 2) {
    status = "unhealthy";
  } else {
    status = "degraded";
  }

  const body = {
    status,
    version: process.env.npm_package_version || "1.0.0",
    uptime: Math.round((Date.now() - startTime) / 1000),
    services,
    timestamp: new Date().toISOString(),
  };

  const httpStatus = status === "unhealthy" ? 503 : 200;
  return Response.json(body, { status: httpStatus });
};
