/**
 * useVRAdmin — VR tour mutation hook
 * ===================================
 * Replaces: Legacy queries
 * Backend: Payload CMS /api/vr-scenes, /api/media
 *
 * Used by: VRAdminPanel, VRHotspotManager, VRBulkActions
 */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api/client";

export function useVRAdmin(museumId: string) {
  const queryClient = useQueryClient();

  /**
   * Helper: find the virtual tour document for this museum
   */
  const findTour = async () => {
    const result = await api.find("vr-scenes", {
      where: { museum: { equals: museumId } },
      limit: 1,
      depth: 0,
    });
    if (result.docs.length === 0) {
      throw new Error("No virtual tour found for this museum");
    }
    return result.docs[0] as any;
  };

  // ── Scene CRUD ──────────────────────────────────────

  const createScene = useMutation({
    mutationFn: async (data: Record<string, any>) => {
      const tour = await findTour();
      const existing = tour.panoramas || [];

      const newScene = {
        title: data.title,
        description: data.description || null,
        image: data.panorama_url, // Will need to be a media ID in production
        order: data.scene_order || existing.length + 1,
        narrationText: data.narration_text || null,
        narrationAudio: data.narration_audio_url || null,
        isActive: true,
        hotspots: [],
      };

      return api.update("vr-scenes", tour.id, {
        panoramas: [...existing, newScene],
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["vr-scenes"] });
    },
  });

  const updateScene = useMutation({
    mutationFn: async ({ id, ...data }: { id: string } & Record<string, any>) => {
      const tour = await findTour();
      const panoramas = (tour.panoramas || []).map((p: any) => {
        if (p.id === id) {
          return {
            ...p,
            title: data.title ?? p.title,
            description: data.description ?? p.description,
            image: data.panorama_url ?? p.image,
            narrationText: data.narration_text ?? p.narrationText,
            narrationAudio: data.narration_audio_url ?? p.narrationAudio,
            isActive: data.is_active ?? p.isActive,
          };
        }
        return p;
      });

      return api.update("vr-scenes", tour.id, { panoramas });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["vr-scenes"] });
    },
  });

  const deleteScene = useMutation({
    mutationFn: async (sceneId: string) => {
      const tour = await findTour();
      const panoramas = (tour.panoramas || []).filter(
        (p: any) => p.id !== sceneId
      );
      return api.update("vr-scenes", tour.id, { panoramas });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["vr-scenes"] });
    },
  });

  const reorderScenes = useMutation({
    mutationFn: async (updates: { id: string; scene_order: number }[]) => {
      const tour = await findTour();
      const panoramas = tour.panoramas || [];

      // Sort panoramas according to the new order
      const reordered = updates
        .sort((a, b) => a.scene_order - b.scene_order)
        .map(({ id, scene_order }) => {
          const scene = panoramas.find((p: any) => p.id === id);
          return scene ? { ...scene, order: scene_order } : null;
        })
        .filter(Boolean);

      return api.update("vr-scenes", tour.id, { panoramas: reordered });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["vr-scenes"] });
    },
  });

  // ── Hotspot CRUD ────────────────────────────────────

  const createHotspot = useMutation({
    mutationFn: async (data: Record<string, any>) => {
      const tour = await findTour();
      const panoramas = (tour.panoramas || []).map((p: any) => {
        if (p.id === data.scene_id) {
          return {
            ...p,
            hotspots: [
              ...(p.hotspots || []),
              {
                type: data.type,
                title: data.title,
                description: data.description || null,
                positionX: data.position_x,
                positionY: data.position_y,
                targetScene: data.target_scene_id || null,
                content: data.content || null,
                isActive: true,
              },
            ],
          };
        }
        return p;
      });

      return api.update("vr-scenes", tour.id, { panoramas });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["vr-hotspots"] });
      queryClient.invalidateQueries({ queryKey: ["vr-scenes"] });
    },
  });

  const updateHotspot = useMutation({
    mutationFn: async ({ id, scene_id, ...data }: { id: string; scene_id: string } & Record<string, any>) => {
      const tour = await findTour();
      const panoramas = (tour.panoramas || []).map((p: any) => {
        if (p.id === scene_id) {
          const hotspots = (p.hotspots || []).map((h: any) => {
            if (h.id === id) {
              return {
                ...h,
                type: data.type ?? h.type,
                title: data.title ?? h.title,
                description: data.description ?? h.description,
                positionX: data.position_x ?? h.positionX,
                positionY: data.position_y ?? h.positionY,
                targetScene: data.target_scene_id ?? h.targetScene,
                content: data.content ?? h.content,
              };
            }
            return h;
          });
          return { ...p, hotspots };
        }
        return p;
      });

      return api.update("vr-scenes", tour.id, { panoramas });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["vr-hotspots"] });
    },
  });

  const deleteHotspot = useMutation({
    mutationFn: async ({ hotspotId, sceneId }: { hotspotId: string; sceneId: string }) => {
      const tour = await findTour();
      const panoramas = (tour.panoramas || []).map((p: any) => {
        if (p.id === sceneId) {
          return {
            ...p,
            hotspots: (p.hotspots || []).filter(
              (h: any) => h.id !== hotspotId
            ),
          };
        }
        return p;
      });

      return api.update("vr-scenes", tour.id, { panoramas });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["vr-hotspots"] });
    },
  });

  // ── Media upload (replaces legacy query) ────────

  const uploadPanorama = useMutation({
    mutationFn: async (file: File) => {
      const result = await api.uploadMedia(file, file.name);
      return result;
    },
  });

  return {
    createScene,
    updateScene,
    deleteScene,
    reorderScenes,
    createHotspot,
    updateHotspot,
    deleteHotspot,
    uploadPanorama,
  };
}
