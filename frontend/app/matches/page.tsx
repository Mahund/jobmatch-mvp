"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase";
import { api } from "@/lib/api";
import JobCard from "@/components/JobCard";

function timeAgo(isoString: string): string {
  const diff = Math.floor((Date.now() - new Date(isoString).getTime()) / 1000);
  if (diff < 60) return "hace un momento";
  if (diff < 3600) return `hace ${Math.floor(diff / 60)} min`;
  if (diff < 86400) return `hace ${Math.floor(diff / 3600)} h`;
  return `hace ${Math.floor(diff / 86400)} días`;
}

function SkeletonCard() {
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-4 animate-pulse">
      <div className="h-4 bg-gray-200 rounded w-2/3 mb-2" />
      <div className="h-3 bg-gray-100 rounded w-1/3 mb-3" />
      <div className="h-3 bg-gray-100 rounded w-full mb-1" />
      <div className="h-3 bg-gray-100 rounded w-4/5" />
    </div>
  );
}

export default function MatchesPage() {
  const router = useRouter();
  const [matches, setMatches] = useState<object[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 20;
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [sort, setSort] = useState<"score" | "published_date">("score");

  useEffect(() => {
    async function load() {
      setLoading(true);
      setError("");
      setLastUpdated(null);
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) { router.push("/"); return; }

      try {
        const data = await api.getMatches(session.access_token, page, PAGE_SIZE, sort);
        setMatches(data.matches);
        const newTotal = data.total ?? 0;
        setTotal(newTotal);
        const newTotalPages = Math.ceil(newTotal / PAGE_SIZE);
        if (page > Math.max(1, newTotalPages)) {
          setPage(1);
          return;
        }
        // Pick the most recent matched_at as the last-updated timestamp
        const dates = data.matches
          .map((m: object) => (m as { matched_at?: string }).matched_at)
          .filter(Boolean) as string[];
        setLastUpdated(dates.length > 0 ? dates.sort().reverse()[0] : null);
      } catch {
        setError("Error al cargar los empleos. Intenta de nuevo.");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [router, page, sort]);

  async function handleSignOut() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/");
  }

  const totalPages = Math.ceil(total / PAGE_SIZE);

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
        <div className="flex items-baseline justify-between mb-4">
          <h2 className="text-xl font-semibold text-gray-900">
            {loading ? "Cargando..." : `${total} empleos para ti`}
          </h2>
          <div className="flex items-center gap-3">
            {lastUpdated && !loading && (
              <span className="text-xs text-gray-400">Actualizado {timeAgo(lastUpdated)}</span>
            )}
            {!loading && total > 0 && (
              <button
                onClick={() => { setSort(s => s === "score" ? "published_date" : "score"); setPage(1); }}
                className="text-xs text-blue-600 hover:underline"
              >
                {sort === "score" ? "Más recientes" : "Por relevancia"}
              </button>
            )}
          </div>
        </div>

        {error && <p className="text-sm text-red-600 mb-4">{error}</p>}

        {!loading && matches.length === 0 && !error && (
          <div className="text-center py-16 text-gray-400">
            <p className="text-lg">No hay coincidencias aún.</p>
            <p className="text-sm mt-1">
              Completa tu <a href="/profile" className="text-blue-600 underline">perfil</a> para ver empleos relevantes.
            </p>
          </div>
        )}

        <div className="space-y-3">
          {loading
            ? Array.from({ length: 5 }).map((_, i) => <SkeletonCard key={i} />)
            : matches.map((match) => (
                <JobCard key={(match as { listings: { url_hash: string } }).listings.url_hash} match={match as Parameters<typeof JobCard>[0]["match"]} />
              ))}
        </div>

        {!loading && totalPages > 1 && (
          <div className="flex items-center justify-between mt-6 text-sm text-gray-600">
            <button
              onClick={() => setPage(p => p - 1)}
              disabled={page === 1}
              className="px-3 py-1.5 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              ← Anterior
            </button>
            <span>Página {page} de {totalPages}</span>
            <button
              onClick={() => setPage(p => p + 1)}
              disabled={page === totalPages}
              className="px-3 py-1.5 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Siguiente →
            </button>
          </div>
        )}
      </div>
    </main>
  );
}
