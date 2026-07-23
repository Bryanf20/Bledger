import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createStaff,
  fetchBusiness,
  fetchPreferences,
  fetchStaff,
  resetStaffPin,
  updateBusiness,
  updatePreferences,
  updateStaff,
} from "../api/settings";

export function useBusiness() {
  return useQuery({ queryKey: ["settings", "business"], queryFn: fetchBusiness, staleTime: 60_000 });
}

export function usePreferences() {
  return useQuery({ queryKey: ["settings", "preferences"], queryFn: fetchPreferences, staleTime: 60_000 });
}

export function useStaff() {
  return useQuery({ queryKey: ["staff"], queryFn: fetchStaff, staleTime: 30_000 });
}

export function useUpdateBusiness() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: updateBusiness,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings", "business"] }),
  });
}

export function useUpdatePreferences() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: updatePreferences,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["settings", "preferences"] }),
  });
}

export function useCreateStaff() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createStaff,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["staff"] }),
  });
}

export function useUpdateStaff() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }) => updateStaff(id, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["staff"] }),
  });
}

export function useResetStaffPin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, pin }) => resetStaffPin(id, pin),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["staff"] }),
  });
}
