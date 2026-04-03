"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase";
import { api } from "@/lib/api";

const CONTRACT_OPTIONS = ["full-time", "part-time", "per diem", "contract", "temporary"];

export default function ProfilePage() {
  const router = useRouter();
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  const [form, setForm] = useState({
    specialty: "",
    years_experience: 0,
    region: "",
    accepted_contracts: [] as string[],
    preferred_schedule: "",
    min_salary: "",
    licensure_held: "",
  });

  useEffect(() => {
    async function load() {
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) { router.push("/"); return; }

      try {
        const profile = await api.getProfile(session.access_token) as {
          specialty?: string;
          years_experience?: number;
          region?: string;
          accepted_contracts?: string[];
          preferred_schedule?: string | null;
          min_salary?: number | null;
          licensure_held?: string[];
        };
        setForm({
          specialty: profile.specialty ?? "",
          years_experience: profile.years_experience ?? 0,
          region: profile.region ?? "",
          accepted_contracts: profile.accepted_contracts ?? [],
          preferred_schedule: profile.preferred_schedule ?? "",
          min_salary: profile.min_salary ? String(profile.min_salary) : "",
          licensure_held: (profile.licensure_held ?? []).join(", "),
        });
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : String(err);
        if (!msg.includes("404") && !msg.includes("No rows")) {
          setError("Error al cargar el perfil. Intenta de nuevo.");
        }
        // else: no profile yet — blank form is fine
      }
    }
    load();
  }, [router]);

  function toggleContract(c: string) {
    setForm(f => ({
      ...f,
      accepted_contracts: f.accepted_contracts.includes(c)
        ? f.accepted_contracts.filter(x => x !== c)
        : [...f.accepted_contracts, c],
    }));
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    try {
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) { router.push("/"); return; }
      await api.saveProfile(session.access_token, {
        specialty: form.specialty,
        years_experience: Number(form.years_experience),
        region: form.region,
        accepted_contracts: form.accepted_contracts,
        preferred_schedule: form.preferred_schedule || null,
        min_salary: form.min_salary ? Number(form.min_salary) : null,
        licensure_held: form.licensure_held
          ? form.licensure_held.split(",").map(s => s.trim()).filter(Boolean)
          : [],
      });
      // Re-fetch session in case apiFetch refreshed the token during saveProfile
      const { data: { session: s2 } } = await supabase.auth.getSession();
      await api.rematch((s2 ?? session).access_token);
      setSaved(true);
      setTimeout(() => { router.push("/matches"); }, 1000);
    } catch {
      setError("Error al guardar. Intenta de nuevo.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between">
        <h1 className="text-lg font-bold text-gray-900">JobMatch</h1>
        <a href="/matches" className="text-sm text-gray-500 hover:text-gray-900">← Volver</a>
      </header>

      <div className="max-w-lg mx-auto px-4 py-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-6">Tu perfil</h2>

        <form onSubmit={handleSave} className="space-y-5">
          <Field label="Especialidad">
            <input
              value={form.specialty}
              onChange={e => setForm(f => ({ ...f, specialty: e.target.value }))}
              placeholder="ej. Urgencias, UCI, Pediatría"
              className={inputClass}
            />
          </Field>

          <Field label="Años de experiencia">
            <input
              type="number"
              min={0}
              value={form.years_experience}
              onChange={e => setForm(f => ({ ...f, years_experience: Number(e.target.value) }))}
              className={inputClass}
            />
          </Field>

          <Field label="Región">
            <input
              value={form.region}
              onChange={e => setForm(f => ({ ...f, region: e.target.value }))}
              placeholder="ej. Metropolitana, Biobío"
              className={inputClass}
            />
          </Field>

          <Field label="Tipo de contrato aceptado">
            <div className="flex flex-wrap gap-2">
              {CONTRACT_OPTIONS.map(c => (
                <button
                  key={c}
                  type="button"
                  onClick={() => toggleContract(c)}
                  className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                    form.accepted_contracts.includes(c)
                      ? "bg-blue-600 text-white border-blue-600"
                      : "bg-white text-gray-600 border-gray-300 hover:border-blue-400"
                  }`}
                >
                  {c}
                </button>
              ))}
            </div>
          </Field>

          <Field label="Turno preferido">
            <select
              value={form.preferred_schedule}
              onChange={e => setForm(f => ({ ...f, preferred_schedule: e.target.value }))}
              className={inputClass}
            >
              <option value="">Sin preferencia</option>
              <option value="diurno">Diurno</option>
              <option value="nocturno">Nocturno</option>
              <option value="rotativo">Rotativo</option>
              <option value="por turnos">Por turnos</option>
            </select>
          </Field>

          <Field label="Licencias / habilitaciones (separadas por coma)">
            <input
              value={form.licensure_held}
              onChange={e => setForm(f => ({ ...f, licensure_held: e.target.value }))}
              placeholder="ej. Enfermera Universitaria, RN"
              className={inputClass}
            />
          </Field>

          <Field label="Salario mínimo (CLP, opcional)">
            <input
              type="number"
              value={form.min_salary}
              onChange={e => setForm(f => ({ ...f, min_salary: e.target.value }))}
              placeholder="ej. 800000"
              className={inputClass}
            />
          </Field>

          {error && <p className="text-sm text-red-600">{error}</p>}
          {saved && <p className="text-sm text-green-600">Guardado. Redirigiendo...</p>}

          <button
            type="submit"
            disabled={saving}
            className="w-full bg-blue-600 text-white rounded-lg py-2.5 text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {saving ? "Guardando..." : "Guardar y ver coincidencias"}
          </button>
        </form>
      </div>
    </main>
  );
}

const inputClass =
  "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder:text-gray-500";

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1.5">{label}</label>
      {children}
    </div>
  );
}
