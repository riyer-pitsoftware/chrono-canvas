import { useState } from 'react';
import { ChevronDown, ChevronRight } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import type { StateSnapshot } from '@/api/types';

const AGENT_LABELS: Record<string, string> = {
  orchestrator: 'Orchestrator',
  extraction: 'Extraction',
  research: 'Research',
  face_search: 'Face Search',
  prompt_generation: 'Prompt Generation',
  image_generation: 'Image Generation',
  validation: 'Validation',
  facial_compositing: 'Facial Compositing',
  export: 'Export',
};

// ── JSON syntax highlighting ──────────────────────────────────────────────────

function highlight(json: string): string {
  return json.replace(
    /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)/g,
    (match) => {
      if (/^"/.test(match)) {
        if (/:$/.test(match)) return `<span class="json-key">${match}</span>`;
        return `<span class="json-string">${match}</span>`;
      }
      if (/true|false/.test(match)) return `<span class="json-bool">${match}</span>`;
      if (/null/.test(match)) return `<span class="json-null">${match}</span>`;
      return `<span class="json-number">${match}</span>`;
    },
  );
}

function JsonView({ data }: { data: Record<string, unknown> }) {
  const json = JSON.stringify(data, null, 2);
  return (
    <pre
      className="text-xs font-mono bg-[var(--muted)] p-3 rounded-md overflow-auto max-h-96 leading-relaxed
        [&_.json-key]:text-blue-600 dark:[&_.json-key]:text-blue-400
        [&_.json-string]:text-green-700 dark:[&_.json-string]:text-green-400
        [&_.json-number]:text-orange-600 dark:[&_.json-number]:text-orange-400
        [&_.json-bool]:text-purple-600 dark:[&_.json-bool]:text-purple-400
        [&_.json-null]:text-red-500"
      dangerouslySetInnerHTML={{ __html: highlight(json) }}
    />
  );
}

// ── Diff computation ──────────────────────────────────────────────────────────

function computeDiff(
  prev: Record<string, unknown> | null,
  curr: Record<string, unknown>,
): { added: Record<string, unknown>; changed: Record<string, unknown>; unchanged: string[] } {
  const added: Record<string, unknown> = {};
  const changed: Record<string, unknown> = {};
  const unchanged: string[] = [];

  for (const key of Object.keys(curr)) {
    if (!prev || !(key in prev)) {
      added[key] = curr[key];
    } else if (JSON.stringify(prev[key]) !== JSON.stringify(curr[key])) {
      changed[key] = curr[key];
    } else {
      unchanged.push(key);
    }
  }

  return { added, changed, unchanged };
}

function DiffView({
  prev,
  curr,
}: {
  prev: Record<string, unknown> | null;
  curr: Record<string, unknown>;
}) {
  const { added, changed, unchanged } = computeDiff(prev, curr);
  const hasChanges = Object.keys(added).length + Object.keys(changed).length > 0;

  if (!hasChanges && prev !== null) {
    return (
      <p className="text-xs text-[var(--muted-foreground)] italic p-3">
        No state changes in this step.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {Object.keys(added).length > 0 && (
        <div>
          <p className="text-xs font-medium text-green-700 mb-1">
            + Added ({Object.keys(added).length} keys)
          </p>
          <pre className="text-xs font-mono bg-green-50 border border-green-200 text-green-900 p-3 rounded-md overflow-auto max-h-64">
            {JSON.stringify(added, null, 2)}
          </pre>
        </div>
      )}
      {Object.keys(changed).length > 0 && (
        <div>
          <p className="text-xs font-medium text-amber-700 mb-1">
            ~ Changed ({Object.keys(changed).length} keys)
          </p>
          <pre className="text-xs font-mono bg-amber-50 border border-amber-200 text-amber-900 p-3 rounded-md overflow-auto max-h-64">
            {JSON.stringify(changed, null, 2)}
          </pre>
        </div>
      )}
      {unchanged.length > 0 && (
        <p className="text-xs text-[var(--muted-foreground)]">Unchanged: {unchanged.join(', ')}</p>
      )}
    </div>
  );
}

// ── Per-agent accordion row ───────────────────────────────────────────────────

function SnapshotRow({
  snapshot,
  prev,
  index,
}: {
  snapshot: StateSnapshot;
  prev: StateSnapshot | null;
  index: number;
}) {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<'full' | 'diff'>('diff');

  const { added, changed } = computeDiff(prev?.snapshot ?? null, snapshot.snapshot);
  const changeCount = Object.keys(added).length + Object.keys(changed).length;

  return (
    <div className="border rounded-md">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-3 p-3 text-left hover:bg-[var(--accent)] transition-colors"
      >
        {open ? (
          <ChevronDown className="w-4 h-4 shrink-0" />
        ) : (
          <ChevronRight className="w-4 h-4 shrink-0" />
        )}
        <span className="text-xs text-[var(--muted-foreground)] w-5 shrink-0">{index + 1}</span>
        <span className="font-medium text-sm">
          {AGENT_LABELS[snapshot.agent] ?? snapshot.agent}
        </span>
        <div className="ml-auto flex gap-2">
          {changeCount > 0 && (
            <Badge variant="outline" className="text-xs">
              {changeCount} change{changeCount !== 1 ? 's' : ''}
            </Badge>
          )}
          <Badge variant="secondary" className="text-xs">
            {Object.keys(snapshot.snapshot).length} keys
          </Badge>
        </div>
      </button>

      {open && (
        <div className="border-t px-3 pb-3 pt-2 space-y-3">
          {/* Tab switcher */}
          <div className="flex gap-1">
            {(['diff', 'full'] as const).map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={`text-xs px-3 py-1 rounded-md transition-colors ${
                  tab === t
                    ? 'bg-[var(--primary)] text-[var(--primary-foreground)]'
                    : 'bg-[var(--muted)] hover:bg-[var(--accent)]'
                }`}
              >
                {t === 'diff' ? 'Diff' : 'Full State'}
              </button>
            ))}
          </div>

          {tab === 'diff' ? (
            <DiffView prev={prev?.snapshot ?? null} curr={snapshot.snapshot} />
          ) : (
            <JsonView data={snapshot.snapshot} />
          )}
        </div>
      )}
    </div>
  );
}

// ── Public component ──────────────────────────────────────────────────────────

export function StateInspector({ snapshots }: { snapshots: StateSnapshot[] }) {
  if (snapshots.length === 0) {
    return (
      <p className="text-sm text-[var(--muted-foreground)]">
        No state snapshots available. Only generations run after this feature was added will have
        snapshots.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {snapshots.map((snap, i) => (
        <SnapshotRow
          key={`${snap.agent}-${i}`}
          snapshot={snap}
          prev={i > 0 ? snapshots[i - 1] : null}
          index={i}
        />
      ))}
    </div>
  );
}
