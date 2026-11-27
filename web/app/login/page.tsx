"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, setToken } from "@/lib/api";
import { Icon } from "@/components/Icon";

// The first version has sample accounts only. Every one uses the same password
const ACCOUNTS = [
  ["dan@zeenote.ai", "Company Owner (Dan)"],
  ["illia@zeenote.ai", "Team Manager (Illia), Cova, Commity and AI-Training teams"],
  ["mike@zeenote.ai", "Team Member (Mike), Cova and AI-Training teams"],
  ["admin@zeenote.ai", "ZeeNote Admin"],
];
// Shown only on this computer. Through a shared link, people get their email and the password from you
const isLocal = () => typeof location !== "undefined" && ["localhost", "127.0.0.1"].includes(location.hostname);

export default function Login() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [local, setLocal] = useState(false);
  const [shown, setShown] = useState(false);
  useEffect(() => setLocal(isLocal()), []);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const { token } = await api<{ token: string }>("/login", { body: { email, password } });
      setToken(token);
      router.replace("/write"); // an owner is sent on to their own first page
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  return (
    <div className="center">
      <div className="stack" style={{ width: "min(100%, 420px)" }}>
        <div className="brand" style={{ justifyContent: "center", fontSize: 24 }}>
          <img src="/zeenote-mark.png" alt="" /> ZeeNote
        </div>
        <form className="card stack" onSubmit={submit}>
          <h1>Sign in</h1>
          <label>
            Email
            <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="username" required />
          </label>
          <label>
            Password
            <span className="with-button">
              <input type={shown ? "text" : "password"} value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" required />
              <button type="button" className="btn ghost icon" onClick={() => setShown(!shown)} aria-label={shown ? "Hide password" : "Show password"} aria-pressed={shown} title={shown ? "Hide password" : "Show password"}>
                <Icon name={shown ? "eyeOff" : "eye"} />
              </button>
            </span>
          </label>
          {error && <p className="error" role="alert">{error}</p>}
          <button className="btn main" disabled={busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
        {local && (
          <div className="card stack small">
            <p>
              <b>Sample accounts</b> · the password is <code>ZEENOTE_PASSWORD</code> in <code>.env</code>, or <code>zeenote</code> if it isn&apos;t set
            </p>
            {ACCOUNTS.map(([address, role]) => (
              <button key={address} className="link" style={{ textAlign: "left" }} onClick={() => setEmail(address)}>
                {address} <span className="soft">· {role}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
