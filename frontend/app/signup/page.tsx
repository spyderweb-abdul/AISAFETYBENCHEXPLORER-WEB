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
    <div className="container" style={{ maxWidth: 420 }}>
      <h2>Create a Researcher Account</h2>
      <p style={{ color: "#666", fontSize: 13 }}>
        Researcher accounts can submit benchmark papers by DOI for automatic
        extraction and admin review. Every account created here is a
        researcher account -- there is no self-service way to become an admin.
      </p>
      <form onSubmit={handleSubmit} className="card">
        <div className="field">
          <label>Email</label>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div className="field">
          <label>Password</label>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} />
        </div>
        {error && <p className="error">{error}</p>}
        <button type="submit" disabled={submitting}>{submitting ? "Creating account..." : "Sign Up"}</button>
      </form>
      <p style={{ fontSize: 13 }}>
        Already have an account? <Link href="/login">Log in</Link>
      </p>
    </div>
  );
}
