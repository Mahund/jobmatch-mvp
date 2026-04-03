interface Listing {
  url: string;
  title: string;
  company: string;
  city: string;
  region: string;
  specialty: string | null;
  contract_type: string | null;
  schedule: string | null;
  salary_raw: string | null;
  summary: string | null;
  modality: string | null;
  years_experience: number;
  published_date: string | null;
}

function daysAgo(dateStr: string | null): string | null {
  if (!dateStr) return null;
  const diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 86_400_000);
  if (diff < 0) return null;
  if (diff === 0) return "Hoy";
  if (diff === 1) return "Ayer";
  if (diff <= 30) return `Hace ${diff} días`;
  return null;
}

interface Match {
  score: number;
  specialty_tier: string;
  is_new: boolean;
  listings: Listing;
}

const TIER_LABEL: Record<string, string> = {
  exact: "Especialidad exacta",
  related: "Especialidad afín",
  general: "Enfermería general",
};

const TIER_COLOR: Record<string, string> = {
  exact: "bg-green-100 text-green-800",
  related: "bg-blue-100 text-blue-800",
  general: "bg-gray-100 text-gray-600",
};

export default function JobCard({ match }: { match: Match }) {
  const l = match.listings;

  return (
    <a
      href={l.url}
      target="_blank"
      rel="noopener noreferrer"
      className="block bg-white border border-gray-200 rounded-xl p-5 hover:shadow-md transition-shadow"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            {match.is_new && (
              <span className="text-xs font-semibold bg-blue-600 text-white px-2 py-0.5 rounded-full">
                Nuevo
              </span>
            )}
            <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${TIER_COLOR[match.specialty_tier] ?? TIER_COLOR.general}`}>
              {TIER_LABEL[match.specialty_tier] ?? match.specialty_tier}
            </span>
          </div>
          <h2 className="text-base font-semibold text-gray-900 truncate">{l.title}</h2>
          <p className="text-sm text-gray-600">{l.company}</p>
        </div>
      </div>

      <p className="mt-3 text-sm text-gray-500 line-clamp-2">{l.summary}</p>

      <div className="mt-3 flex flex-wrap gap-2 text-xs text-gray-500">
        <span>📍 {l.city}</span>
        {l.contract_type && l.contract_type !== "unknown" && <span>· {l.contract_type}</span>}
        {l.schedule && <span>· {l.schedule}</span>}
        {l.salary_raw && l.salary_raw !== "A convenir" && <span>· {l.salary_raw}</span>}
        {l.years_experience > 0 && <span>· {l.years_experience}+ años exp.</span>}
        {(() => {
          const ago = daysAgo(l.published_date);
          if (!ago) return null;
          const isStale = l.published_date
            ? (Date.now() - new Date(l.published_date).getTime()) / 86_400_000 > 14
            : false;
          return (
            <span className={isStale ? "text-orange-500" : ""}>
              · {isStale ? "⚠️ " : ""}{ago}
            </span>
          );
        })()}
      </div>
    </a>
  );
}
