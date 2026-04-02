"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase";
import { api } from "@/lib/api";
import JobCard from "@/components/JobCard";

export default function MatchesPage() {
  const router = useRouter();
  const [matches, setMatches] = useState<object[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function load() {
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) { router.push("/"); return; }

      try {
        const data = await api.getMatches(session.access_token);
        setMatches(data);
      } catch {
        setError("Error loading matches. Please try again.");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [router]);

  async function handleSignOut() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/");
  }

  return (
    <main className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between">
        <h1 className="text-lg font-bold text-gray-900">JobMatch</h1>
        <nav className="flex items-center gap-4 text-sm">
          <a href="/profile" className="text-gray-500 hover:text-gray-900">Perfil</a>
          <button onClick={handleSignOut} className="text-gray-500 hover:text-gray-900">Salir</button>
        </nav>
      </header>

      <div className="max-w-2xl mx-auto px-4 py-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-semibold text-gray-900">
            {loading ? "Cargando..." : `${matches.length} empleos para ti`}
          </h2>
        </div>

        {error && <p className="text-sm text-red-600 mb-4">{error}</p>}

        {!loading && matches.length === 0 && !error && (
          <div className="text-center py-16 text-gray-400">
            <p className="text-lg">No hay coincidencias aún.</p>
            <p className="text-sm mt-1">Completa tu <a href="/profile" className="text-blue-600 underline">perfil</a> para ver empleos relevantes.</p>
          </div>
        )}

        <div className="space-y-3">
          {matches.map((match, i) => (
            <JobCard key={i} match={match as Parameters<typeof JobCard>[0]["match"]} />
          ))}
        </div>
      </div>
    </main>
  );
}
