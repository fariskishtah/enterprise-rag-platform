import type { Verification } from "../types";

const labels = {
  supported: "Supported by sources",
  partially_supported: "Partially supported",
  unsupported: "Not sufficiently supported",
};

export function VerificationBadge({ verification }: { verification: Verification }) {
  return (
    <div className={`verification verification-${verification.status}`}>
      <strong>{labels[verification.status]}</strong>
      <span>{verification.explanation}</span>
      {verification.unsupported_statements.length > 0 && (
        <details>
          <summary>Review unsupported statements</summary>
          <ul>
            {verification.unsupported_statements.map((statement) => (
              <li key={statement}>{statement}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

