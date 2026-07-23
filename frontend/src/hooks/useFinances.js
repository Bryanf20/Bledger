import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createCashbookEntry,
  createExpenseCategory,
  deleteCashbookEntry,
  fetchCashbook,
  fetchExpenseCategories,
  fetchPnl,
  seedDefaultCategories,
  updateCashbookEntry,
} from "../api/finances";

export function useExpenseCategories() {
  return useQuery({
    queryKey: ["expense-categories"],
    queryFn: fetchExpenseCategories,
    staleTime: 60_000,
  });
}

export function useCashbook() {
  return useQuery({ queryKey: ["cashbook"], queryFn: fetchCashbook, staleTime: 30_000 });
}

// Owner-only endpoint -- callers gate the query with `enabled` so a
// manager never fires a request that would just 403.
export function usePnl(period, { enabled = true } = {}) {
  return useQuery({
    queryKey: ["pnl", period],
    queryFn: () => fetchPnl(period),
    enabled,
    staleTime: 30_000,
  });
}

export function useSeedDefaultCategories() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: seedDefaultCategories,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["expense-categories"] }),
  });
}

export function useCreateExpenseCategory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createExpenseCategory,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["expense-categories"] }),
  });
}

// A cashbook write moves the net-profit number, so every mutation
// invalidates both the ledger and the P&L.
function invalidateLedgerAndPnl(qc) {
  qc.invalidateQueries({ queryKey: ["cashbook"] });
  qc.invalidateQueries({ queryKey: ["pnl"] });
}

export function useCreateCashbookEntry() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createCashbookEntry,
    onSuccess: () => invalidateLedgerAndPnl(qc),
  });
}

export function useUpdateCashbookEntry() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }) => updateCashbookEntry(id, payload),
    onSuccess: () => invalidateLedgerAndPnl(qc),
  });
}

export function useDeleteCashbookEntry() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteCashbookEntry,
    onSuccess: () => invalidateLedgerAndPnl(qc),
  });
}
