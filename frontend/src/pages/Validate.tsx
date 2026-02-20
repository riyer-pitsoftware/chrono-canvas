import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { api } from "@/api/client";
import type { ValidationSummary } from "@/api/types";

export function Validate() {
  const [requestId, setRequestId] = useState("");
  const [results, setResults] = useState<ValidationSummary | null>(null);
  const [loading, setLoading] = useState(false);

  const handleValidate = async () => {
    if (!requestId.trim()) return;
    setLoading(true);
    try {
      const data = await api.get<ValidationSummary>(`/validation/${requestId}`);
      setResults(data);
    } catch {
      setResults(null);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2 className="text-3xl font-bold mb-6">Validation</h2>

      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Check Validation</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-3">
            <Input
              placeholder="Enter generation request ID..."
              value={requestId}
              onChange={(e) => setRequestId(e.target.value)}
              className="flex-1"
            />
            <Button onClick={handleValidate} disabled={loading}>
              {loading ? "Checking..." : "Check"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {results && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Results</CardTitle>
              <Badge variant={results.passed ? "success" : "destructive"}>
                Score: {results.overall_score.toFixed(1)}
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {results.results.map((r) => (
                <div key={r.id} className="flex items-center justify-between p-3 border border-[var(--border)] rounded-md">
                  <div>
                    <p className="font-medium">{r.category}: {r.rule_name}</p>
                    {r.details && <p className="text-sm text-[var(--muted-foreground)]">{r.details}</p>}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm">{r.score.toFixed(1)}</span>
                    <Badge variant={r.passed ? "success" : "destructive"}>
                      {r.passed ? "Pass" : "Fail"}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
