import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createCustomer,
  fetchAgedDebt,
  fetchCustomers,
  recordCustomerPayment,
  updateCustomer,
} from "../api/customers";

export function useCustomers() {
  return useQuery({ queryKey: ["customers"], queryFn: fetchCustomers, staleTime: 30_000 });
}

export function useAgedDebt() {
  return useQuery({ queryKey: ["aged-debt"], queryFn: fetchAgedDebt, staleTime: 30_000 });
}

export function useCreateCustomer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createCustomer,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["customers"] }),
  });
}

export function useUpdateCustomer() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }) => updateCustomer(id, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["customers"] }),
  });
}

export function useRecordCustomerPayment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ customerId, payload }) => recordCustomerPayment(customerId, payload),
    onSuccess: () => {
      // A payment changes the customer's balance and the aged-debt report.
      qc.invalidateQueries({ queryKey: ["customers"] });
      qc.invalidateQueries({ queryKey: ["aged-debt"] });
    },
  });
}
