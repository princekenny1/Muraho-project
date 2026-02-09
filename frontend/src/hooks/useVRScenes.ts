/**
 * useVRScenes + useVRHotspots — VR tour data hooks
 * =================================================
 * Replaces: Legacy queries
 * Backend: Payload CMS /api/vr-scenes (scenes as embedded array in panoramas)
 *
 * Exports: VRScene, VRHotspot types, useVRScenes(), useVRHotspots()
 * Used by: VRAdminPanel, VRSceneCard, VRSceneForm, VRHotspotManager, VRHotspotForm,
 *          VRBulkActions, PanoramaUploader, PanoramaPositionPicker
 */

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";

// ── Types ─────────────────────────────────────────────

export interface VRScene {
  id: string;
  museum_id: string;
  title: string;
  description: string | null;
  panorama_url: string;
  scene_order: number;
  narration_text: string | null;
  narration_audio_url: string | null;
  is_active: boolean;
  createdAt: string;
}

export interface VRHotspot {
  id: string;
  scene_id: string;
  type: "info" | "audio" | "video" | "next-scene" | "landmark";
  title: string;
  description: string | null;
  position_x: number;
  position_y: number;
  content: Record<string, unknown> | null;
  target_scene_id: string | null;
  is_active: boolean;
}

// ── Query Hooks ───────────────────────────────────────

/**
 * Fetch all VR scenes for a museum's virtual tour
 * In Payload, scenes are stored as panoramas[] within virtual-tours collection
 */
export function useVRScenes(museumId?: string, includeInactive = false) {
  return useQuery<VRScene[]>({
    queryKey: ["vr-scenes", museumId, includeInactive],
    queryFn: async () => {
      if (!museumId) return [];

      // Find the virtual tour for this museum
      const result = await api.find("vr-scenes", {
        where: { museum: { equals: museumId } },
        limit: 1,
        depth: 2,
      });

      if (result.docs.length === 0) return [];

      const tour = result.docs[0] as any;
      const panoramas = tour.panoramas || [];

      return panoramas
        .map((p: any, i: number) => mapScene(p, museumId, i))
        .filter((s: VRScene) => includeInactive || s.is_active)
        .sort((a: VRScene, b: VRScene) => a.scene_order - b.scene_order);
    },
    enabled: !!museumId,
  });
}

/**
 * Fetch hotspots for a specific VR scene
 * In Payload, hotspots are embedded within each panorama object
 */
export function useVRHotspots(sceneId?: string) {
  return useQuery<VRHotspot[]>({
    queryKey: ["vr-hotspots", sceneId],
    queryFn: async () => {
      if (!sceneId) return [];

      // We need to search all virtual tours for this scene
      // In practice the admin panel already has the museum context
      const result = await api.find("vr-scenes", {
        limit: 50,
        depth: 2,
      });

      for (const tour of result.docs as any[]) {
        const panoramas = tour.panoramas || [];
        const scene = panoramas.find((p: any) => p.id === sceneId);
        if (scene) {
          const hotspots = scene.hotspots || [];
          return hotspots.map((h: any, i: number) => mapHotspot(h, sceneId, i));
        }
      }

      return [];
    },
    enabled: !!sceneId,
  });
}

// ── Field mappers ─────────────────────────────────────

function mapScene(p: any, museumId: string, index: number): VRScene {
  return {
    id: p.id || `scene-${index}`,
    museum_id: museumId,
    title: p.title || `Scene ${index + 1}`,
    description: p.description || null,
    panorama_url: p.image?.url || p.panorama_url || "",
    scene_order: p.order || p.scene_order || index + 1,
    narration_text: p.narrationText || p.narration_text || null,
    narration_audio_url: p.narrationAudio?.url || p.narration_audio_url || null,
    is_active: p.isActive ?? p.is_active ?? true,
    createdAt: p.createdAt || new Date().toISOString(),
  };
}

function mapHotspot(h: any, sceneId: string, index: number): VRHotspot {
  return {
    id: h.id || `hotspot-${index}`,
    scene_id: sceneId,
    type: h.type || "info",
    title: h.title || `Hotspot ${index + 1}`,
    description: h.description || null,
    position_x: h.positionX ?? h.position_x ?? 50,
    position_y: h.positionY ?? h.position_y ?? 50,
    content: h.content || null,
    target_scene_id: h.targetScene || h.target_scene_id || null,
    is_active: h.isActive ?? h.is_active ?? true,
  };
}
