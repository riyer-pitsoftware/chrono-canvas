import { useState } from 'react';

interface LoginProps {
  onSuccess: () => void;
}

export function Login({ onSuccess }: LoginProps) {
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
      });
      const data = await res.json();
      if (res.ok && data.ok) {
        onSuccess();
      } else {
        setError(data.detail || 'Login failed');
      }
    } catch {
      setError('Connection error');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-950">
      <form
        onSubmit={handleSubmit}
        className="bg-zinc-900 border border-zinc-800 rounded-lg p-8 w-full max-w-sm shadow-xl"
      >
        <h1 className="text-2xl font-bold text-zinc-100 mb-1 text-center">
          ChronoCanvas
        </h1>
        <p className="text-zinc-500 text-sm text-center mb-6">Enter password to continue</p>

        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          autoFocus
          className="w-full px-3 py-2 bg-zinc-800 border border-zinc-700 rounded text-zinc-100 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-amber-500 focus:border-transparent mb-4"
        />

        {error && (
          <p className="text-red-400 text-sm mb-4">{error}</p>
        )}

        <button
          type="submit"
          disabled={loading || !password}
          className="w-full py-2 bg-amber-600 hover:bg-amber-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium rounded transition-colors"
        >
          {loading ? 'Signing in...' : 'Sign In'}
        </button>
      </form>
    </div>
  );
}
