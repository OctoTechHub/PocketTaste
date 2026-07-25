"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { discoveryApi, systemApi } from "@/lib/api/endpoints";
import { queryKeys } from "@/lib/api/keys";

/** GET /health — service health and active backends. */
export function useHealth() {
  return useQuery({
    queryKey: queryKeys.health,
    queryFn: () => systemApi.health(),
    refetchInterval: 30_000,
  });
}

/** GET /system/architecture — how the layer is put together. */
export function useArchitecture() {
  return useQuery({
    queryKey: queryKeys.architecture,
    queryFn: () => systemApi.architecture(),
  });
}

/** GET /discovery/pipeline — retrieval pipeline topology. */
export function useDiscoveryPipeline() {
  return useQuery({
    queryKey: queryKeys.discoveryPipeline,
    queryFn: () => discoveryApi.pipeline(),
  });
}

/** POST /discovery/reindex — rebuild the retrieval index from Mongo. */
export function useReindex() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => discoveryApi.reindex(),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.discoveryPipeline }),
  });
}
