"use client";

import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";

interface ConfirmDeleteModalProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  itemName: string;
  isDeleting: boolean;
}

/**
 * The delete-confirmation modal used identically on Jobs, Expenses, and
 * Shifts — same title pattern, same "can't be undone" copy, same
 * Cancel/Delete button pair. Only the title and the item's display name
 * varied between the three call sites.
 */
export function ConfirmDeleteModal({
  open,
  onClose,
  onConfirm,
  title,
  itemName,
  isDeleting,
}: ConfirmDeleteModalProps) {
  return (
    <Modal open={open} onClose={onClose} title={title}>
      <p className="mb-4 text-sm text-muted">
        Remove &quot;{itemName}&quot;? This can&apos;t be undone.
      </p>
      <div className="flex justify-end gap-2">
        <Button variant="ghost" onClick={onClose}>
          Cancel
        </Button>
        <Button variant="danger" onClick={onConfirm} isLoading={isDeleting}>
          Delete
        </Button>
      </div>
    </Modal>
  );
}
