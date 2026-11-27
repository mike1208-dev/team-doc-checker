"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";
import { Icon } from "@/components/Icon";
import { PageHead } from "@/components/Shell";

// The owner's settings of the company. Only its name for now
export default function SettingsPage() {
  const { me, changeMe } = useSession();
  const [name, setName] = useState(me.company);
  const [problem, setProblem] = useState("");
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState("");

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim()) {
      setProblem("Write the company's name.");
      return;
    }
    setBusy(true);
    setProblem("");
    try {
      const saved = await api<{ name: string }>("/company", { method: "PUT", body: { name } });
      changeMe({ company: saved.name });
      setName(saved.name);
      setToast("Saved. Everyone in the company sees the new name.");
      setTimeout(() => setToast(""), 3000);
    } catch (e) {
      setProblem((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const changed = name.trim() !== me.company;
  return (
    <>
      <PageHead title="Settings" sub="Your company's settings in ZeeNote." />
      <main className="content" style={{ maxWidth: 720 }}>
        <form className="card flush" onSubmit={save} noValidate>
          <div className="card-head">
            <div>
              <h2>Company name</h2>
              <p className="soft small">Shown under the ZeeNote logo for everyone in the company.</p>
            </div>
          </div>
          <div className="card-body">
            <label>
              <span>Name</span>
              <input value={name} maxLength={60} onChange={(event) => { setName(event.target.value); setProblem(""); }}
                aria-invalid={Boolean(problem)} aria-describedby={problem ? "company-problem" : undefined} disabled={busy} />
              {problem && <span id="company-problem" className="field-problem">{problem}</span>}
            </label>
          </div>
          <div className="card-foot">
            <span className="faint small">Only you, as the owner, can change it.</span>
            <button className="btn main" disabled={busy || !changed}>
              {busy ? "Saving…" : changed ? "Save" : "Saved"}
            </button>
          </div>
        </form>
      </main>
      {toast && <div className="toast" role="status"><Icon name="check" size={15} />{toast}</div>}
    </>
  );
}
