"use client";

import type { Ask } from "@/lib/api";

const rowsOf = (ask: Ask) => (ask.items.length ? ask.items : [""]);

// A status is picked, so it's always a word the checker knows
const CHOICES: Record<string, string[]> = {
  "What is the status (Done or In progress)?": ["Done", "In progress"],
  "What is the status of the PR (for example Merged or In review)?": ["Merged", "In review", "Draft", "Open", "Closed"],
};

// The answers written as notes, "item: answer". An empty box is skipped
export function answersAsNotes(asks: Ask[], answers: Record<string, string>): string[] {
  return asks.flatMap((ask, i) =>
    rowsOf(ask).flatMap((item, j) => {
      const answer = answers[`${i}-${j}`]?.trim();
      return answer ? [item ? `${item}: ${answer}` : answer] : [];
    }),
  );
}

// Each item of a question has its own box. "open" is what the written report still asks, or null before it's written
export function Questions({ asks, answers, onAnswer, open, disabled, writing, onWrite }: {
  asks: Ask[];
  answers: Record<string, string>;
  onAnswer: (key: string, value: string) => void;
  open: Ask[] | null;
  disabled: boolean;
  writing: boolean;
  onWrite: () => void;
}) {
  const solved = (ask: Ask, item: string) => open !== null && !open.some((other) => other.ask === ask.ask && (!item || other.items.includes(item)));
  const done = open !== null && open.length === 0;

  return (
    <section id="questions" className={`card stack questions ${done ? "done" : ""}`} aria-live="polite">
      <div>
        <h2>Before we write</h2>
        <p className="soft small">Leave a box empty to skip it. Changed your notes? Click Check notes again.</p>
      </div>
      {/* the part of the notes first, then the question about it */}
      {asks.map((ask, i) =>
        rowsOf(ask).map((item, j) => (
          // not a label: a click on the words shouldn't open the dropdown
          <div key={`${i}-${j}`} className="stack" style={{ gap: 4, fontSize: 14 }}>
            {item && <i>{item}</i>}
            <span id={`ask-${i}-${j}`} style={{ fontWeight: 600 }}>
              {ask.ask}
              {solved(ask, item) && <span className="solved" aria-label="Answered"> ✓</span>}
            </span>
            {CHOICES[ask.ask] ? (
              <select aria-labelledby={`ask-${i}-${j}`} value={answers[`${i}-${j}`] ?? ""} onChange={(event) => onAnswer(`${i}-${j}`, event.target.value)} disabled={disabled}>
                <option value="">Choose…</option>
                {CHOICES[ask.ask].map((choice) => <option key={choice}>{choice}</option>)}
              </select>
            ) : (
              <input aria-labelledby={`ask-${i}-${j}`} value={answers[`${i}-${j}`] ?? ""} onChange={(event) => onAnswer(`${i}-${j}`, event.target.value)} disabled={disabled}
                onKeyDown={(event) => event.key === "Enter" && event.preventDefault()} /* Enter would check the notes again */ />
            )}
          </div>
        )),
      )}
      <div className="row" style={{ justifyContent: "flex-end" }}>
        <button type="button" className="btn main" onClick={onWrite} disabled={disabled}>
          {writing ? "Writing…" : "Write report"}
        </button>
      </div>
    </section>
  );
}
