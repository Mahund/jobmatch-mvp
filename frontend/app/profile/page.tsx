"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase";
import { api } from "@/lib/api";

const CONTRACT_OPTIONS = ["full-time", "part-time", "per diem", "contract", "temporary"];

const SPECIALTY_OPTIONS = [
  "APS (Atención Primaria de Salud)",
  "Acreditación",
  "Ambulancias",
  "Atención de pacientes",
  "Atención prehospitalaria",
  "Capacitación y Formación",
  "Cardiología",
  "Cateterismo Cardíaco y Hemodinamia",
  "Clínica Administrativa",
  "Clínica de Neurorrehabilitación",
  "Clínica y Laboratorio",
  "Consultorio Adosado de Especialidades (CAE)",
  "Cuidado del Adulto Mayor",
  "Domiciliaria",
  "Emergencia",
  "Emergencia pediátrica",
  "Enfermería",
  "Enfermería en Atención Primaria",
  "Estética",
  "Estética - Depilación Láser",
  "General",
  "Gestión Quirúrgica",
  "Gestión de Camas (GRD)",
  "Gestión y Liderazgo de Equipos de Enfermería",
  "Hemodinamia",
  "Hemodiálisis",
  "Hospitalización",
  "Medicina pediátrica",
  "Médico Quirúrgico",
  "Pabellón",
  "Pabellón Quirúrgico",
  "Pabellón central",
  "Pediatría",
  "Prehospitalaria",
  "Prehospitalaria/Ambulancias",
  "Procedimiento cardiovascular y hemodinamia",
  "Procedimientos Gastroenterológicos",
  "Procedimientos cardiovasculares y manejo de insumos clínicos",
  "Procedimientos y exámenes",
  "Proyectos ferroviarios",
  "Residencia de Adulto Mayor",
  "Salud Ocupacional",
  "Salud Penitenciaria",
  "Seguimiento Clínico",
  "Supervisión de Convenios",
  "Toma de Muestras",
  "UCI Cardiovascular Pediátrico",
];

export default function ProfilePage() {
  const router = useRouter();
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [specialtyOptions, setSpecialtyOptions] = useState<string[]>(SPECIALTY_OPTIONS);

  useEffect(() => {
    let isMounted = true;

    api.getSpecialties()
      .then(opts => {
        if (isMounted && opts.length > 0) setSpecialtyOptions(opts);
      })
      .catch(() => { /* keep fallback */ });

    return () => {
      isMounted = false;
    };
  }, []);

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

  async function handleDelete() {
    if (!window.confirm("¿Seguro que quieres eliminar tu cuenta? Esta acción no se puede deshacer.")) return;
    setDeleting(true);
    setError("");
    try {
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) { router.push("/"); return; }
      await api.deleteAccount(session.access_token);
      await supabase.auth.signOut();
      router.push("/");
    } catch {
      setError("Error al eliminar la cuenta. Intenta de nuevo.");
      setDeleting(false);
    }
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
          <Field label="Especialidad" htmlFor="specialty-input">
            <SpecialtyCombobox
              id="specialty-input"
              value={form.specialty}
              onChange={v => setForm(f => ({ ...f, specialty: v }))}
              options={specialtyOptions}
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

        <div className="mt-10 pt-6 border-t border-gray-200">
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="text-sm text-red-600 hover:text-red-800 disabled:opacity-50 transition-colors"
          >
            {deleting ? "Eliminando..." : "Eliminar mi cuenta"}
          </button>
        </div>
      </div>
    </main>
  );
}

const inputClass =
  "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder:text-gray-500";

function Field({ label, htmlFor, children }: { label: string; htmlFor?: string; children: React.ReactNode }) {
  return (
    <div>
      <label htmlFor={htmlFor} className="block text-sm font-medium text-gray-700 mb-1.5">{label}</label>
      {children}
    </div>
  );
}

function normalize(s: string) {
  return s.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase().trim();
}

function SpecialtyCombobox({
  id,
  value,
  onChange,
  options,
}: {
  id?: string;
  value: string;
  onChange: (v: string) => void;
  options: string[];
}) {
  const [query, setQuery] = useState(value);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const containerRef = useRef<HTMLDivElement>(null);
  const queryRef = useRef(query);
  const valueRef = useRef(value);
  const onChangeRef = useRef(onChange);
  const optionsRef = useRef(options);
  const baseId = useId();

  // Keep queryRef in sync synchronously so reconcile() never sees a stale query
  function updateQuery(q: string) { queryRef.current = q; setQuery(q); }

  // Sync query when value changes externally (e.g. profile load).
  // Uses the React derived-state pattern (setState during render) to avoid
  // calling setState inside an effect.
  const [prevValue, setPrevValue] = useState(value);
  if (prevValue !== value) {
    setPrevValue(value);
    setQuery(value);
  }

  useEffect(() => { valueRef.current = value; queryRef.current = value; }, [value]);
  useEffect(() => { onChangeRef.current = onChange; }, [onChange]);
  useEffect(() => { optionsRef.current = options; }, [options]);

  const filtered = query.trim() === ""
    ? options
    : options.filter(s => normalize(s).includes(normalize(query)));

  function select(s: string) {
    onChangeRef.current(s);
    updateQuery(s);
    setOpen(false);
    setActiveIndex(-1);
  }

  // All data read from refs so this is stable and the effect below registers once
  const reconcile = useCallback(() => {
    setOpen(false);
    setActiveIndex(-1);
    const q = queryRef.current;
    const v = valueRef.current;
    const opts = optionsRef.current;
    // Prefer exact string match before falling back to normalized comparison
    const match = opts.includes(q)
      ? q
      : opts.find(s => normalize(s) === normalize(q));
    if (match) {
      onChangeRef.current(match);
      queryRef.current = match;
      setQuery(match);
    } else {
      queryRef.current = v;
      setQuery(v);
    }
  }, []);


  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (!open && e.key !== "Escape") setOpen(true);
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (filtered.length === 0) { setActiveIndex(-1); return; }
      setActiveIndex(i => (i + 1) % filtered.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (filtered.length === 0) { setActiveIndex(-1); return; }
      setActiveIndex(i => (i <= 0 ? filtered.length - 1 : i - 1));
    } else if (e.key === "Enter") {
      const exactMatch = filtered.includes(query)
        ? query
        : filtered.find(s => normalize(s) === normalize(query));
      const target = activeIndex >= 0 ? filtered[activeIndex] : exactMatch;
      if (target) {
        e.preventDefault();
        select(target);
      } else if (open) {
        e.preventDefault();
        setOpen(false);
        setActiveIndex(-1);
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      setOpen(false);
      setActiveIndex(-1);
      updateQuery(value);
    }
  }

  const listboxId = `${baseId}-specialty-listbox`;

  return (
    <div ref={containerRef} className="relative">
      <input
        id={id}
        role="combobox"
        aria-expanded={open && filtered.length > 0}
        aria-controls={open && filtered.length > 0 ? listboxId : undefined}
        aria-autocomplete="list"
        aria-activedescendant={activeIndex >= 0 ? `${baseId}-specialty-option-${activeIndex}` : undefined}
        value={query}
        onChange={e => { updateQuery(e.target.value); setOpen(true); setActiveIndex(-1); }}
        onFocus={() => setOpen(true)}
        onKeyDown={handleKeyDown}
        onBlur={() => reconcile()}
        placeholder="Escribe para filtrar..."
        className={inputClass}
      />
      {open && filtered.length > 0 && (
        <ul
          id={listboxId}
          role="listbox"
          className="absolute z-10 mt-1 w-full max-h-56 overflow-y-auto bg-white border border-gray-200 rounded-lg shadow-lg text-sm"
        >
          {filtered.map((s, i) => (
            <li
              key={s}
              id={`${baseId}-specialty-option-${i}`}
              role="option"
              aria-selected={s === value}
              onMouseDown={(e) => { e.preventDefault(); select(s); }}
              className={`px-3 py-2 cursor-pointer hover:bg-blue-50 ${
                i === activeIndex ? "bg-blue-100" : s === value ? "bg-blue-50 font-medium" : ""
              }`}
            >
              {s}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
