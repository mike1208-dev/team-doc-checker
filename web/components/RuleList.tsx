import type { RuleResult } from "@/lib/api";

const MARKS: Record<RuleResult["status"], [string, string]> = { PASS: ["✓", "ok"], FAIL: ["!", "bad"], WARN: ["!", "warn"], SKIP: ["–", "off"] };

export function RuleList({ rules }: { rules: RuleResult[] }) {
  return (
    <ul className="rules" style={{ marginTop: 10 }}>
      {rules.map((rule) => (
        <li key={rule.title}>
          <span className={`tag ${MARKS[rule.status][1]}`} aria-label={rule.status}>{MARKS[rule.status][0]}</span> {rule.title}
        </li>
      ))}
    </ul>
  );
}
