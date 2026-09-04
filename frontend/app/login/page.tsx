"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Cookies from "js-cookie";
import { login } from "../../lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const { access_token } = await login(email, password);
      Cookies.set("access_token", access_token, { expires: 1 });
      router.push("/admin/benchmarks");
    } catch {
      setError("Invalid email or password.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-shell">
      <header className="auth-heading">
        <p className="eyebrow">Private workspace</p>
        <h1>Sign in</h1>
        <p>Access the administration and researcher workflows.</p>
      </header>
      <div className="card">
        <form onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="login-email">Email</label>
            <input id="login-email" value={email} onChange={(e) => setEmail(e.target.value)} type="email" required autoComplete="email" />
          </div>
          <div className="field">
            <label htmlFor="login-password">Password</label>
            <input id="login-password" value={password} onChange={(e) => setPassword(e.target.value)} type="password" required autoComplete="current-password" />
          </div>
          {error && <p className="error">{error}</p>}
          <button type="submit" disabled={loading}>{loading ? "Signing in..." : "Sign in"}</button>
        </form>
      </div>
    </main>
  );
}
