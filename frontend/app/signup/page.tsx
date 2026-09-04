// Destination path: frontend/app/signup/page.tsx
// New file.
//
// Phase 6 item 4: public signup page for researchers who want to
// submit a benchmark. Every account created here is role="researcher"
// server-side regardless of anything sent from this form -- see the
// security fix in schemas/user.py and routers/auth.py. After
// successful signup, logs the user in immediately and redirects to
// /submit.

"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Cookies from "js-cookie";
import { login, registerUser } from "../../lib/api";

export default function SignupPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await registerUser(email, password);
      const { access_token } = await login(email, password);
      Cookies.set("access_token", access_token, { expires: 1 });
      router.push("/submit");
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Signup failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="auth-shell">
      <header className="auth-heading">
        <p className="eyebrow">Researcher workspace</p>
        <h1>Create an account</h1>
        <p>
        Researcher accounts can submit benchmark papers by DOI for automatic
        extraction and admin review. Every account created here is a
        researcher account. There is no self-service admin access.
        </p>
      </header>
      <form onSubmit={handleSubmit} className="card">
        <div className="field">
          <label htmlFor="signup-email">Email</label>
          <input id="signup-email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
        </div>
        <div className="field">
          <label htmlFor="signup-password">Password</label>
          <input id="signup-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} autoComplete="new-password" />
        </div>
        {error && <p className="error">{error}</p>}
        <button type="submit" disabled={submitting}>{submitting ? "Creating account..." : "Sign Up"}</button>
      </form>
      <p className="auth-footer">
        Already have an account? <Link href="/login">Log in</Link>
      </p>
    </main>
  );
}
