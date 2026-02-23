import { useState, useCallback } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAgents, useLLMStatus, useCostSummary } from "@/api/hooks/useAgents";
import {
  useValidationRules,
  useUpdateValidationRule,
  useUpdatePassThreshold,
  useValidationQueue,
  useAcceptValidation,
  useRejectValidation,
} from "@/api/hooks/useValidationAdmin";
import type { ValidationRule, ValidationQueueItem } from "@/api/types";
import { useNavigation } from "@/stores/navigation";

// ── Speed Gauge ──────────────────────────────────────────────────────────────

function SpeedGauge({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  const clamp = (v: number) => Math.max(0, Math.min(100, v));
  const angle = (clamp(value) / 100) * 180 - 90; // -90° (left) to +90° (right)

  const zone = value < 50 ? "#ef4444" : value < 70 ? "#f59e0b" : "#22c55e";

  // SVG arc path helper
  function polarToXY(deg: number, r: number) {
    const rad = ((deg - 90) * Math.PI) / 180;
    return { x: 60 + r * Math.cos(rad), y: 60 + r * Math.sin(rad) };
  }

  function arcPath(startDeg: number, endDeg: number, r: number) {
    const s = polarToXY(startDeg, r);
    const e = polarToXY(endDeg, r);
    const large = endDeg - startDeg > 180 ? 1 : 0;
    return `M ${s.x} ${s.y} A ${r} ${r} 0 ${large} 1 ${e.x} ${e.y}`;
  }

  return (
    <div className="flex flex-col items-center gap-2">
      <svg width="120" height="70" viewBox="0 0 120 70">
        {/* Background arc */}
        <path d={arcPath(180, 360, 44)} fill="none" stroke="var(--border)" strokeWidth="10" />
        {/* Red zone 0-50 */}
        <path d={arcPath(180, 270, 44)} fill="none" stroke="#ef4444" strokeWidth="10" opacity="0.25" />
        {/* Amber zone 50-70 */}
        <path d={arcPath(270, 306, 44)} fill="none" stroke="#f59e0b" strokeWidth="10" opacity="0.25" />
        {/* Green zone 70-100 */}
        <path d={arcPath(306, 360, 44)} fill="none" stroke="#22c55e" strokeWidth="10" opacity="0.25" />
        {/* Value arc */}
        <path
          d={arcPath(180, 180 + clamp(value) * 1.8, 44)}
          fill="none"
          stroke={zone}
          strokeWidth="10"
          strokeLinecap="round"
        />
        {/* Needle */}
        <line
          x1="60"
          y1="60"
          x2={60 + 30 * Math.cos(((angle - 90) * Math.PI) / 180)}
          y2={60 + 30 * Math.sin(((angle - 90) * Math.PI) / 180)}
          stroke="var(--foreground)"
          strokeWidth="2"
          strokeLinecap="round"
        />
        <circle cx="60" cy="60" r="4" fill="var(--foreground)" />
        <text x="60" y="68" textAnchor="middle" fontSize="11" fill="var(--foreground)" fontWeight="bold">
          {Math.round(value)}
        </text>
      </svg>
      <input
        type="range"
        min={0}
        max={100}
        step={1}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-28 accent-[var(--primary)]"
      />
      <span className="text-xs text-[var(--muted-foreground)]">Pass threshold</span>
    </div>
  );
}

// ── Rule Row ─────────────────────────────────────────────────────────────────

function RuleRow({ rule, onUpdate }: { rule: ValidationRule; onUpdate: (id: string, weight: number, enabled: boolean) => void }) {
  const [weight, setWeight] = useState(rule.weight);
  const [enabled, setEnabled] = useState(rule.enabled);
  const [dirty, setDirty] = useState(false);

  const handleWeightChange = (v: number) => {
    setWeight(v);
    setDirty(true);
  };

  const handleToggle = () => {
    const next = !enabled;
    setEnabled(next);
    setDirty(true);
  };

  const handleSave = () => {
    onUpdate(rule.id, weight, enabled);
    setDirty(false);
  };

  return (
    <div className="flex items-center gap-4 py-3 border-b border-[var(--border)] last:border-0">
      <div className="w-40 min-w-[10rem]">
        <p className="font-medium text-sm">{rule.display_name}</p>
        <p className="text-xs text-[var(--muted-foreground)] leading-tight">{rule.description}</p>
      </div>
      <div className="flex-1 flex items-center gap-2">
        <input
          type="range"
          min={0}
          max={1}
          step={0.05}
          value={weight}
          disabled={!enabled}
          onChange={(e) => handleWeightChange(Number(e.target.value))}
          className="flex-1 accent-[var(--primary)] disabled:opacity-40"
        />
        <span className="text-xs w-10 text-right tabular-nums">{weight.toFixed(2)}</span>
      </div>
      <button
        onClick={handleToggle}
        className={`text-xs px-2 py-1 rounded border transition-colors ${
          enabled
            ? "border-[var(--primary)] text-[var(--primary)]"
            : "border-[var(--border)] text-[var(--muted-foreground)]"
        }`}
      >
        {enabled ? "On" : "Off"}
      </button>
      {dirty && (
        <Button size="sm" onClick={handleSave}>
          Save
        </Button>
      )}
    </div>
  );
}

// ── Queue Item ────────────────────────────────────────────────────────────────

function QueueCard({
  item,
  onAccept,
  onReject,
  onReview,
}: {
  item: ValidationQueueItem;
  onAccept: (id: string) => void;
  onReject: (id: string) => void;
  onReview: (id: string) => void;
}) {
  const scoreColor =
    item.overall_score >= 70 ? "text-green-500" : item.overall_score >= 50 ? "text-amber-500" : "text-red-500";

  return (
    <Card>
      <CardContent className="pt-4">
        <div className="flex gap-4">
          {item.image_url && (
            <img
              src={item.image_url}
              alt="generated portrait"
              className="w-24 h-24 object-cover rounded flex-shrink-0"
            />
          )}
          <div className="flex-1 min-w-0">
            <p className="font-medium truncate">{item.figure_name ?? item.input_text}</p>
            <p className="text-xs text-[var(--muted-foreground)] mb-2">
              {new Date(item.created_at).toLocaleString()}
            </p>
            <div className="flex flex-wrap gap-2 mb-3">
              {item.categories.map((cat) => (
                <div key={cat.category} className="text-xs bg-[var(--muted)] rounded px-2 py-0.5">
                  <span className="capitalize">{cat.category.replace(/_/g, " ")}</span>
                  <span
                    className={`ml-1 font-semibold ${
                      cat.score >= 70 ? "text-green-500" : cat.score >= 50 ? "text-amber-500" : "text-red-500"
                    }`}
                  >
                    {Math.round(cat.score)}
                  </span>
                </div>
              ))}
            </div>
            <div className="flex items-center justify-between">
              <span className={`text-sm font-bold ${scoreColor}`}>
                Overall: {item.overall_score}
              </span>
              {item.human_review_status ? (
                <Badge variant={item.human_review_status === "accepted" ? "success" : "destructive"}>
                  {item.human_review_status}
                </Badge>
              ) : (
                <div className="flex gap-2 flex-wrap">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => onReject(item.request_id)}
                    className="text-red-500 border-red-500 hover:bg-red-50"
                  >
                    Reject
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => onAccept(item.request_id)}
                    className="bg-green-600 hover:bg-green-700 text-white"
                  >
                    Accept
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => onReview(item.request_id)}
                  >
                    Review
                  </Button>
                </div>
              )}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Tabs ──────────────────────────────────────────────────────────────────────

type Tab = "overview" | "rules" | "queue";

// ── Admin Page ────────────────────────────────────────────────────────────────

export function Admin() {
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [pendingThreshold, setPendingThreshold] = useState<number | null>(null);
  const { navigate } = useNavigation();

  const agents = useAgents();
  const llmStatus = useLLMStatus();
  const costs = useCostSummary();
  const rulesQuery = useValidationRules();
  const queueQuery = useValidationQueue();
  const updateRule = useUpdateValidationRule();
  const updateThreshold = useUpdatePassThreshold();
  const acceptMutation = useAcceptValidation();
  const rejectMutation = useRejectValidation();

  const threshold =
    pendingThreshold !== null ? pendingThreshold : (rulesQuery.data?.pass_threshold ?? 70);

  const handleThresholdChange = (v: number) => setPendingThreshold(v);

  const handleThresholdSave = () => {
    updateThreshold.mutate(threshold, {
      onSuccess: () => setPendingThreshold(null),
    });
  };

  const handleRuleUpdate = useCallback(
    (id: string, weight: number, enabled: boolean) => {
      updateRule.mutate({ id, weight, enabled });
    },
    [updateRule],
  );

  const handleAccept = useCallback(
    (requestId: string) => acceptMutation.mutate({ requestId }),
    [acceptMutation],
  );
  const handleReject = useCallback(
    (requestId: string) => rejectMutation.mutate({ requestId }),
    [rejectMutation],
  );
  const handleReview = useCallback(
    (requestId: string) => navigate(`/review/${requestId}`),
    [navigate],
  );

  const tabs: { id: Tab; label: string }[] = [
    { id: "overview", label: "Overview" },
    { id: "rules", label: "Validation Rules" },
    { id: "queue", label: `Review Queue${queueQuery.data ? ` (${queueQuery.data.total})` : ""}` },
  ];

  return (
    <div>
      <h2 className="text-3xl font-bold mb-6">Admin</h2>

      {/* Tab Bar */}
      <div className="flex gap-1 border-b border-[var(--border)] mb-6">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === t.id
                ? "border-b-2 border-[var(--primary)] text-[var(--primary)]"
                : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Overview Tab */}
      {activeTab === "overview" && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Agents</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {agents.data?.agents.map((agent) => (
                  <div key={agent.name} className="flex items-center justify-between">
                    <div>
                      <p className="font-medium">{agent.name}</p>
                      <p className="text-xs text-[var(--muted-foreground)]">{agent.description}</p>
                    </div>
                    <Badge variant="success">{agent.status}</Badge>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>LLM Providers</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {llmStatus.data &&
                  Object.entries(llmStatus.data.providers).map(([name, available]) => (
                    <div key={name} className="flex items-center justify-between">
                      <p className="font-medium">{name}</p>
                      <Badge variant={available ? "success" : "destructive"}>
                        {available ? "Available" : "Unavailable"}
                      </Badge>
                    </div>
                  ))}
              </div>
            </CardContent>
          </Card>

          <Card className="md:col-span-2">
            <CardHeader>
              <CardTitle>Cost Summary</CardTitle>
            </CardHeader>
            <CardContent>
              {costs.data && (
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <p className="text-sm text-[var(--muted-foreground)]">Total Cost</p>
                    <p className="text-2xl font-bold">${costs.data.total_cost.toFixed(4)}</p>
                  </div>
                  <div>
                    <p className="text-sm text-[var(--muted-foreground)]">Total Tokens</p>
                    <p className="text-2xl font-bold">{costs.data.total_tokens.toLocaleString()}</p>
                  </div>
                  <div>
                    <p className="text-sm text-[var(--muted-foreground)]">API Calls</p>
                    <p className="text-2xl font-bold">{costs.data.num_calls}</p>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* Validation Rules Tab */}
      {activeTab === "rules" && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Pass threshold gauge */}
          <Card>
            <CardHeader>
              <CardTitle>Pass Threshold</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col items-center gap-4">
              <SpeedGauge value={threshold} onChange={handleThresholdChange} />
              {pendingThreshold !== null && (
                <Button size="sm" onClick={handleThresholdSave} disabled={updateThreshold.isPending}>
                  {updateThreshold.isPending ? "Saving…" : "Save threshold"}
                </Button>
              )}
              <p className="text-xs text-center text-[var(--muted-foreground)]">
                Images scoring below this threshold fail validation and enter the review queue.
              </p>
            </CardContent>
          </Card>

          {/* Rule weights */}
          <Card className="md:col-span-2">
            <CardHeader>
              <CardTitle>Category Weights</CardTitle>
            </CardHeader>
            <CardContent>
              {rulesQuery.isLoading && (
                <p className="text-sm text-[var(--muted-foreground)]">Loading rules…</p>
              )}
              {rulesQuery.data?.rules.map((rule) => (
                <RuleRow key={rule.id} rule={rule} onUpdate={handleRuleUpdate} />
              ))}
              <p className="text-xs text-[var(--muted-foreground)] mt-3">
                Weights determine how much each category contributes to the overall score. Toggle a
                category off to exclude it from scoring.
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Review Queue Tab */}
      {activeTab === "queue" && (
        <div>
          {queueQuery.isLoading && (
            <p className="text-sm text-[var(--muted-foreground)]">Loading queue…</p>
          )}
          {queueQuery.data?.total === 0 && (
            <div className="text-center py-16 text-[var(--muted-foreground)]">
              <p className="text-lg font-medium">No items pending review</p>
              <p className="text-sm mt-1">
                All completed generations passed validation or have already been reviewed.
              </p>
            </div>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {queueQuery.data?.items.map((item) => (
              <QueueCard
                key={item.request_id}
                item={item}
                onAccept={handleAccept}
                onReject={handleReject}
                onReview={handleReview}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
