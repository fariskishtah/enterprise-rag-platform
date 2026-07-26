import type { ReactNode } from "react";
import { contentDirection } from "../utils/language";

interface EmptyStateProps {
  title: string;
  description: string;
  action?: ReactNode;
}

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className="empty-state" dir={contentDirection(`${title} ${description}`)}>
      <div className="empty-icon" aria-hidden="true">
        +
      </div>
      <h3>{title}</h3>
      <p>{description}</p>
      {action}
    </div>
  );
}
