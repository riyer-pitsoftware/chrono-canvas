import { useMemo, useState, useEffect } from 'react';
import { useNavigation } from '@/stores/navigation';
import { useTimelineFigures } from '@/api/hooks/useTimeline';
import type { Figure } from '@/api/types';
import { QuillIcon } from '@/components/icons/QuillIcon';

// ── Year formatting ────────────────────────────────────────────────────────────

function fmtYear(y: number): string {
  if (y < 0) return `${Math.abs(y)} BCE`;
  return `${y} CE`;
}

// ── Nearest figure ─────────────────────────────────────────────────────────────

function nearestFigure(figures: Figure[], year: number): Figure | null {
  if (!figures.length) return null;
  return figures.reduce((best, f) => {
    const d = Math.abs((f.birth_year ?? 9999) - year);
    const bd = Math.abs((best.birth_year ?? 9999) - year);
    return d < bd ? f : best;
  });
}

// ── Parchment SVG border (mandala-inspired) ────────────────────────────────────

function MandalaBorder() {
  return (
    <svg
      className="absolute inset-0 w-full h-full pointer-events-none"
      viewBox="0 0 800 500"
      preserveAspectRatio="none"
      aria-hidden
    >
      {/* Corner lotus petals */}
      {[
        [20, 20],
        [780, 20],
        [20, 480],
        [780, 480],
      ].map(([cx, cy], i) => (
        <g key={i} transform={`translate(${cx},${cy})`}>
          {[0, 45, 90, 135, 180, 225, 270, 315].map((deg) => (
            <ellipse
              key={deg}
              cx={0}
              cy={-14}
              rx={3}
              ry={10}
              fill="none"
              stroke="#C2410C"
              strokeOpacity={0.25}
              strokeWidth={1}
              transform={`rotate(${deg})`}
            />
          ))}
          <circle cx={0} cy={0} r={3} fill="#C2410C" fillOpacity={0.2} />
        </g>
      ))}
      {/* Top & bottom border lines */}
      <line
        x1="40"
        y1="12"
        x2="760"
        y2="12"
        stroke="#C2410C"
        strokeOpacity={0.2}
        strokeWidth={1}
        strokeDasharray="4 4"
      />
      <line
        x1="40"
        y1="488"
        x2="760"
        y2="488"
        stroke="#C2410C"
        strokeOpacity={0.2}
        strokeWidth={1}
        strokeDasharray="4 4"
      />
      {/* Left & right border lines */}
      <line
        x1="12"
        y1="40"
        x2="12"
        y2="460"
        stroke="#C2410C"
        strokeOpacity={0.2}
        strokeWidth={1}
        strokeDasharray="4 4"
      />
      <line
        x1="788"
        y1="40"
        x2="788"
        y2="460"
        stroke="#C2410C"
        strokeOpacity={0.2}
        strokeWidth={1}
        strokeDasharray="4 4"
      />
    </svg>
  );
}

// ── Slider track ───────────────────────────────────────────────────────────────

const YEAR_MIN = -500;
const YEAR_MAX = 1700;
const YEAR_SPAN = YEAR_MAX - YEAR_MIN;

function TimelineSlider({
  year,
  onChange,
  figures,
}: {
  year: number;
  onChange: (y: number) => void;
  figures: Figure[];
}) {
  const pct = ((year - YEAR_MIN) / YEAR_SPAN) * 100;

  return (
    <div className="relative px-6 py-4">
      {/* Tick marks for figures */}
      <div className="relative h-6 mb-1">
        {figures.map((f) => {
          if (f.birth_year == null) return null;
          const p = ((f.birth_year - YEAR_MIN) / YEAR_SPAN) * 100;
          return (
            <button
              key={f.id}
              onClick={() => onChange(f.birth_year!)}
              title={`${f.name} (${fmtYear(f.birth_year!)})`}
              className="absolute top-1 w-1 h-4 rounded-full transition-all cursor-pointer hover:scale-150"
              style={{
                left: `${p}%`,
                transform: 'translateX(-50%)',
                backgroundColor: '#C2410C',
                opacity: 0.5,
              }}
            />
          );
        })}
      </div>

      {/* Range input */}
      <input
        type="range"
        min={YEAR_MIN}
        max={YEAR_MAX}
        step={10}
        value={year}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full h-2 rounded-full appearance-none cursor-pointer"
        style={{
          background: `linear-gradient(to right, #C2410C ${pct}%, #92400E44 ${pct}%)`,
          accentColor: '#C2410C',
        }}
      />

      {/* Year labels */}
      <div className="flex justify-between mt-2 text-xs font-mono" style={{ color: '#92400E' }}>
        <span>500 BCE</span>
        <span>250 BCE</span>
        <span>1 CE</span>
        <span>500 CE</span>
        <span>1000 CE</span>
        <span>1500 CE</span>
        <span>1700 CE</span>
      </div>
    </div>
  );
}

// ── Era band ───────────────────────────────────────────────────────────────────

function eraLabel(year: number): string {
  if (year < -300) return 'Classical Antiquity';
  if (year < 0) return 'Late Antiquity / Hellenistic';
  if (year < 500) return 'Early Common Era';
  if (year < 1000) return 'Early Medieval';
  if (year < 1300) return 'High Medieval';
  if (year < 1500) return 'Late Medieval';
  return 'Early Modern';
}

// ── Figure card ────────────────────────────────────────────────────────────────

function FigureCard({ figure, onGenerate }: { figure: Figure; onGenerate: () => void }) {
  return (
    <div
      key={figure.id}
      className="relative overflow-hidden rounded-xl p-6 border-2 shadow-lg"
      style={{
        background: 'linear-gradient(135deg, #fffbeb 0%, #fef3c7 50%, #fde68a33 100%)',
        borderColor: '#C2410C55',
        animation: 'fadeSlideIn 0.35s ease-out',
      }}
    >
      <MandalaBorder />

      <div className="relative z-10 flex gap-6">
        {/* Portrait placeholder */}
        <div
          className="shrink-0 w-28 h-36 rounded-lg border-2 flex items-center justify-center text-4xl shadow-inner"
          style={{ borderColor: '#C2410C44', background: '#92400E11' }}
        >
          🎨
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2 flex-wrap">
            <div>
              <h2
                className="text-2xl font-bold leading-tight"
                style={{ color: '#7C2D12', fontFamily: 'Georgia, serif' }}
              >
                {figure.name}
              </h2>
              {figure.occupation && (
                <p className="text-sm mt-0.5 font-medium" style={{ color: '#C2410C' }}>
                  {figure.occupation}
                </p>
              )}
            </div>

            <div className="flex gap-2 flex-wrap">
              {figure.nationality && (
                <span
                  className="px-2.5 py-0.5 rounded-full text-xs font-semibold border"
                  style={{
                    background: '#C2410C18',
                    borderColor: '#C2410C44',
                    color: '#9A3412',
                  }}
                >
                  {figure.nationality}
                </span>
              )}
            </div>
          </div>

          {/* Years */}
          <p className="mt-2 text-xs font-mono" style={{ color: '#92400E' }}>
            {figure.birth_year != null ? fmtYear(figure.birth_year) : '?'}
            {figure.death_year != null ? ` – ${fmtYear(figure.death_year)}` : ''}
          </p>

          {/* Description */}
          {figure.description && (
            <p
              className="mt-3 text-sm leading-relaxed line-clamp-4"
              style={{ color: '#44200A', fontFamily: 'Georgia, serif' }}
            >
              {figure.description}
            </p>
          )}

          {/* Actions */}
          <div className="mt-4 flex gap-3">
            <button
              onClick={onGenerate}
              className="px-3 py-1.5 rounded-full text-xs font-semibold text-white shadow transition-all hover:opacity-90 active:scale-95 flex items-center justify-center"
              style={{ background: 'linear-gradient(135deg, #C2410C, #9A3412)' }}
              title="Generate portrait"
              aria-label="Generate portrait"
            >
              <QuillIcon className="h-5 w-5 text-white" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Nearby figures strip ───────────────────────────────────────────────────────

function NearbyStrip({
  figures,
  activeId,
  year,
  onSelect,
}: {
  figures: Figure[];
  activeId: string;
  year: number;
  onSelect: (y: number) => void;
}) {
  // Show the 5 closest figures by birth_year proximity
  const nearby = useMemo(() => {
    return [...figures]
      .sort(
        (a, b) => Math.abs((a.birth_year ?? 9999) - year) - Math.abs((b.birth_year ?? 9999) - year),
      )
      .slice(0, 7);
  }, [figures, year]);

  return (
    <div className="mt-6">
      <p
        className="text-xs font-semibold uppercase tracking-widest mb-3"
        style={{ color: '#92400E' }}
      >
        Nearby Figures
      </p>
      <div className="flex gap-2 flex-wrap">
        {nearby.map((f) => (
          <button
            key={f.id}
            onClick={() => onSelect(f.birth_year ?? year)}
            className="px-3 py-1.5 rounded-full text-xs border transition-all"
            style={{
              background: f.id === activeId ? '#C2410C' : '#C2410C11',
              borderColor: f.id === activeId ? '#C2410C' : '#C2410C44',
              color: f.id === activeId ? '#fff' : '#7C2D12',
              fontWeight: f.id === activeId ? 600 : 400,
            }}
          >
            {f.name}
            {f.birth_year != null && (
              <span className="ml-1 opacity-70">({fmtYear(f.birth_year)})</span>
            )}
          </button>
        ))}
      </div>
    </div>
  );
}

// ── Main page ──────────────────────────────────────────────────────────────────

export function Timeline() {
  const { navigate } = useNavigation();
  const [year, setYear] = useState(0);
  const { data, isLoading } = useTimelineFigures(YEAR_MIN, YEAR_MAX);

  const figures = useMemo(() => data?.items ?? [], [data]);

  const active = useMemo(() => nearestFigure(figures, year), [figures, year]);

  // When data loads snap to the first interesting figure near year 0
  useEffect(() => {
    if (figures.length && year === 0) {
      const f = nearestFigure(figures, 0);
      if (f?.birth_year != null) setYear(f.birth_year);
    }
  }, [figures, year]);

  function handleGenerate() {
    if (!active) return;
    navigate(`/generate?figure_id=${active.id}`);
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h2
          className="text-3xl font-bold"
          style={{ color: '#7C2D12', fontFamily: 'Georgia, serif' }}
        >
          Timeline Explorer
        </h2>
        <p className="mt-1 text-sm" style={{ color: '#92400E' }}>
          500 BCE → 1700 CE · {data?.total ?? '…'} historical figures ·{' '}
          <span className="font-medium">India-centered</span>
        </p>
      </div>

      {/* Current year badge */}
      <div className="flex items-center gap-4">
        <div
          className="px-5 py-2 rounded-full text-2xl font-bold font-mono shadow-md"
          style={{
            background: 'linear-gradient(135deg, #C2410C, #9A3412)',
            color: '#fff',
            letterSpacing: '0.04em',
          }}
        >
          {fmtYear(year)}
        </div>
        <span
          className="text-sm px-3 py-1 rounded-full border"
          style={{
            background: '#fef3c711',
            borderColor: '#C2410C33',
            color: '#92400E',
          }}
        >
          {eraLabel(year)}
        </span>
      </div>

      {/* Slider */}
      <div
        className="rounded-xl border p-1"
        style={{
          background: 'linear-gradient(135deg, #fffbeb, #fef3c7)',
          borderColor: '#C2410C33',
        }}
      >
        {isLoading ? (
          <div
            className="h-24 flex items-center justify-center text-sm"
            style={{ color: '#92400E' }}
          >
            Loading figures…
          </div>
        ) : (
          <TimelineSlider year={year} onChange={setYear} figures={figures} />
        )}
      </div>

      {/* Figure card */}
      {active ? (
        <FigureCard figure={active} onGenerate={handleGenerate} />
      ) : (
        !isLoading && (
          <div
            className="rounded-xl border-2 p-10 text-center text-sm"
            style={{
              borderColor: '#C2410C33',
              color: '#92400E',
              background: '#fffbeb',
            }}
          >
            No figures found near {fmtYear(year)}. Drag the slider to explore.
          </div>
        )
      )}

      {/* Nearby strip */}
      {active && figures.length > 0 && (
        <NearbyStrip figures={figures} activeId={active.id} year={year} onSelect={setYear} />
      )}

      {/* Keyframe animation */}
      <style>{`
        @keyframes fadeSlideIn {
          from { opacity: 0; transform: translateY(10px); }
          to   { opacity: 1; transform: translateY(0);    }
        }
      `}</style>
    </div>
  );
}
