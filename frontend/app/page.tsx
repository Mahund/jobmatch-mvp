"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase";

type Mode = "login" | "signup" | "forgot";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setMessage("");
    setLoading(true);
    const supabase = createClient();

    if (mode === "login") {
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) {
        setError(error.message);
        setLoading(false);
      } else {
        router.push("/matches");
      }
    } else if (mode === "signup") {
      const { error } = await supabase.auth.signUp({ email, password });
      if (error) {
        setError(error.message);
        setLoading(false);
      } else {
        router.push("/profile");
      }
    } else if (mode === "forgot") {
      const { error } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo: `${window.location.origin}/reset-password`,
      });
      setLoading(false);
      if (error) {
        setError(error.message);
      } else {
        setMessage("Revisa tu correo para el enlace de recuperación.");
      }
    }
  }

  return (
    <main className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-sm">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">JobMatch</h1>
        <p className="text-sm text-gray-500 mb-8">Nursing jobs, matched to you.</p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {mode !== "forgot" && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Contraseña</label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          )}

          {error && <p className="text-sm text-red-600">{error}</p>}
          {message && <p className="text-sm text-green-600">{message}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 text-white rounded-lg py-2 text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {loading
              ? "..."
              : mode === "login"
              ? "Iniciar sesión"
              : mode === "signup"
              ? "Crear cuenta"
              : "Enviar enlace"}
          </button>
        </form>

        <div className="mt-4 space-y-2 text-center text-sm text-gray-500">
          {mode === "login" && (
            <>
              <p>
                ¿No tienes cuenta?{" "}
                <button
                  onClick={() => { setMode("signup"); setError(""); setMessage(""); }}
                  className="text-blue-600 hover:underline"
                >
                  Crear cuenta
                </button>
              </p>
              <p>
                <button
                  onClick={() => { setMode("forgot"); setError(""); setMessage(""); }}
                  className="text-blue-600 hover:underline"
                >
                  ¿Olvidaste tu contraseña?
                </button>
              </p>
            </>
          )}
          {mode !== "login" && (
            <p>
              <button
                onClick={() => { setMode("login"); setError(""); setMessage(""); }}
                className="text-blue-600 hover:underline"
              >
                ← Volver
              </button>
            </p>
          )}
        </div>
      </div>
    </main>
  );
}
