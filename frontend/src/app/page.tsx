"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api";

type Organization = {
  id: string;
  name: string;
  slug: string;
  role: string;
  monthly_token_limit: number;
  monthly_used_tokens: number;
  usage_month: string;
};
type User = { id: string; email: string };
type AuthResponse = { access_token: string; user: User; organizations: Organization[] };
type SummaryResult = {
  summary: string; provider: string; model: string; input_tokens: number;
  output_tokens: number; total_tokens: number; estimated_cost_usd: number;
  usage_used_tokens: number; usage_limit_tokens: number; remaining_tokens: number;
};
type Usage = {
  billing_month: string; used_tokens: number; limit_tokens: number;
  remaining_tokens: number; event_count: number; estimated_cost_usd: number;
};
type Mode = "login" | "register";

async function request<T>(path: string, token?: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers || {}),
    },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof data.detail === "string" ? data.detail : "The request could not be completed.";
    throw new Error(detail);
  }
  return data as T;
}

export default function Home() {
  const [mode, setMode] = useState<Mode>("register");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [organizationName, setOrganizationName] = useState("My AI Workspace");
  const [token, setToken] = useState("");
  const [user, setUser] = useState<User | null>(null);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [organizationId, setOrganizationId] = useState("");
  const [usage, setUsage] = useState<Usage | null>(null);
  const [inputText, setInputText] = useState("Our team shipped a new onboarding flow this week. Customers now complete setup in fewer steps, and support tickets about account configuration have decreased. Next, we will improve documentation and review activation metrics.");
  const [summary, setSummary] = useState<SummaryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [newOrgName, setNewOrgName] = useState("");
  const [creatingOrg, setCreatingOrg] = useState(false);

  const selectedOrg = useMemo(() => organizations.find((org) => org.id === organizationId) || organizations[0], [organizations, organizationId]);

  const loadWorkspace = useCallback(async (authToken: string) => {
    const [me, orgs] = await Promise.all([
      request<User>("/me", authToken),
      request<Organization[]>("/organizations", authToken),
    ]);
    setUser(me);
    setOrganizations(orgs);
    setOrganizationId((current) => orgs.some((org) => org.id === current) ? current : (orgs[0]?.id || ""));
  }, []);

  const loadUsage = useCallback(async () => {
    if (!token || !organizationId) return;
    try {
      const result = await request<Usage>(`/organizations/${organizationId}/usage`, token);
      setUsage(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load usage.");
    }
  }, [token, organizationId]);

  useEffect(() => {
    const saved = window.localStorage.getItem("saas-starter-token");
    if (!saved) return;
    setToken(saved);
    loadWorkspace(saved).catch(() => {
      window.localStorage.removeItem("saas-starter-token");
      setToken("");
    });
  }, [loadWorkspace]);

  useEffect(() => { void loadUsage(); }, [loadUsage]);

  async function handleAuth(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setLoading(true); setError(""); setSuccess("");
    try {
      const path = mode === "register" ? "/auth/register" : "/auth/login";
      const body = mode === "register"
        ? { email, password, organization_name: organizationName }
        : { email, password };
      const result = await request<AuthResponse>(path, undefined, { method: "POST", body: JSON.stringify(body) });
      window.localStorage.setItem("saas-starter-token", result.access_token);
      setToken(result.access_token); setUser(result.user); setOrganizations(result.organizations);
      setOrganizationId(result.organizations[0]?.id || "");
      setSuccess(mode === "register" ? "Workspace created. You're signed in." : "Welcome back.");
    } catch (err) { setError(err instanceof Error ? err.message : "Authentication failed."); }
    finally { setLoading(false); }
  }

  function signOut() {
    window.localStorage.removeItem("saas-starter-token");
    setToken(""); setUser(null); setOrganizations([]); setOrganizationId(""); setUsage(null); setSummary(null); setSuccess(""); setError("");
  }

  async function runSummary(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!selectedOrg) return;
    setLoading(true); setError(""); setSuccess(""); setSummary(null);
    try {
      const result = await request<SummaryResult>("/ai/summarize", token, {
        method: "POST",
        body: JSON.stringify({ organization_id: selectedOrg.id, input_text: inputText, max_output_tokens: 160 }),
      });
      setSummary(result); setSuccess("Summary generated and usage recorded.");
      const [orgs, freshUsage] = await Promise.all([
        request<Organization[]>("/organizations", token),
        request<Usage>(`/organizations/${selectedOrg.id}/usage`, token),
      ]);
      setOrganizations(orgs); setUsage(freshUsage);
    } catch (err) { setError(err instanceof Error ? err.message : "Could not generate summary."); }
    finally { setLoading(false); }
  }

  async function createOrganization(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setCreatingOrg(true); setError(""); setSuccess("");
    try {
      const org = await request<Organization>("/organizations", token, { method: "POST", body: JSON.stringify({ name: newOrgName }) });
      const next = [...organizations, org]; setOrganizations(next); setOrganizationId(org.id); setNewOrgName("");
      setSuccess("New workspace created.");
    } catch (err) { setError(err instanceof Error ? err.message : "Could not create workspace."); }
    finally { setCreatingOrg(false); }
  }

  const used = usage?.used_tokens ?? selectedOrg?.monthly_used_tokens ?? 0;
  const limit = usage?.limit_tokens ?? selectedOrg?.monthly_token_limit ?? 10000;
  const percent = Math.min(100, limit > 0 ? (used / limit) * 100 : 0);

  return (
    <main className="shell">
      <header className="topbar">
        <a className="brand" href="#top"><span className="brand-mark">N</span><span>novus<span className="brand-light"> / ai</span></span></a>
        <div className="top-actions"><span className="status-dot" /> <span className="environment-label">Starter workspace</span>{token && <button className="button button-quiet button-small" onClick={signOut}>Sign out</button>}</div>
      </header>

      {!token || !user ? (
        <section className="auth-layout" id="top">
          <div className="hero-copy">
            <div className="eyebrow"><span className="eyebrow-line" /> MULTI-TENANT AI SAAS FOUNDATION</div>
            <h1>Ship AI features.<br /><span>Know what they cost.</span></h1>
            <p className="hero-intro">A practical SaaS foundation for teams building AI products—with workspace boundaries, metered usage, and a clear view of every generation.</p>
            <div className="feature-stack">
              <div className="feature"><span className="feature-icon">◎</span><div><strong>Workspace isolation</strong><span>Every AI request is scoped to a member organization.</span></div></div>
              <div className="feature"><span className="feature-icon">↗</span><div><strong>Usage visibility</strong><span>Track tokens, estimated cost, and monthly limits.</span></div></div>
              <div className="feature"><span className="feature-icon">⌘</span><div><strong>Provider-ready</strong><span>Start with mock mode; connect a model when you're ready.</span></div></div>
            </div>
          </div>
          <div className="auth-card">
            <div className="card-kicker">GET STARTED</div>
            <h2>{mode === "register" ? "Create your workspace" : "Welcome back"}</h2>
            <p className="muted">{mode === "register" ? "Your first organization is provisioned automatically." : "Sign in to your AI workspace."}</p>
            <div className="tab-switch"><button className={mode === "register" ? "active" : ""} onClick={() => { setMode("register"); setError(""); }}>Create account</button><button className={mode === "login" ? "active" : ""} onClick={() => { setMode("login"); setError(""); }}>Sign in</button></div>
            <form onSubmit={handleAuth} className="form-stack">
              <label>Email address<input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" /></label>
              <label>Password<input type="password" autoComplete={mode === "register" ? "new-password" : "current-password"} required minLength={mode === "register" ? 10 : 1} value={password} onChange={(e) => setPassword(e.target.value)} placeholder={mode === "register" ? "At least 10 characters" : "Your password"} /></label>
              {mode === "register" && <label>Workspace name<input required minLength={2} maxLength={120} value={organizationName} onChange={(e) => setOrganizationName(e.target.value)} placeholder="Acme AI" /></label>}
              <button className="button button-primary button-full" disabled={loading}>{loading ? "Please wait…" : mode === "register" ? "Create account" : "Sign in"}<span>→</span></button>
            </form>
            {error && <div className="alert alert-error">{error}</div>}
            <p className="fine-print">Demo starter · Mock AI mode by default · Don't use production credentials here.</p>
          </div>
        </section>
      ) : (
        <section className="dashboard" id="top">
          <div className="dashboard-heading"><div><div className="eyebrow"><span className="eyebrow-line" /> WORKSPACE OVERVIEW</div><h1>Good to see you<span className="period">.</span></h1><p className="muted">A simple view of your team's AI usage and workspace.</p></div><div className="profile-chip"><div className="avatar">{user.email.slice(0, 1).toUpperCase()}</div><div><strong>{user.email}</strong><span>Workspace owner / member</span></div></div></div>
          {error && <div className="alert alert-error">{error}</div>}{success && <div className="alert alert-success">{success}</div>}
          <div className="workspace-control"><label htmlFor="org-select">ACTIVE WORKSPACE</label><select id="org-select" value={selectedOrg?.id || ""} onChange={(e) => setOrganizationId(e.target.value)}>{organizations.map((org) => <option key={org.id} value={org.id}>{org.name}</option>)}</select><span className="role-pill">{selectedOrg?.role || "member"}</span></div>
          <div className="metrics-grid">
            <article className="metric-card"><div className="metric-label">TOKENS USED</div><div className="metric-number">{used.toLocaleString()}<span> / {limit.toLocaleString()}</span></div><div className="meter"><div style={{ width: `${percent}%` }} /></div><div className="metric-foot">{Math.max(0, limit - used).toLocaleString()} tokens remaining this month</div></article>
            <article className="metric-card"><div className="metric-label">ESTIMATED AI COST</div><div className="metric-number">${(usage?.estimated_cost_usd ?? 0).toFixed(4)}</div><div className="metric-foot">Provider-reported tokens × configured price</div></article>
            <article className="metric-card"><div className="metric-label">GENERATIONS</div><div className="metric-number">{usage?.event_count ?? 0}</div><div className="metric-foot">Successful requests this billing month</div></article>
          </div>
          <div className="work-grid">
            <section className="panel"><div className="panel-heading"><div><div className="card-kicker">AI PLAYGROUND</div><h2>Summarize with AI</h2></div><span className="soft-tag">Usage metered</span></div><p className="muted">Submit text to your configured AI provider. The request is charged to the selected workspace's monthly token allowance.</p><form onSubmit={runSummary} className="form-stack"><label>Text to summarize<textarea required minLength={10} maxLength={30000} rows={7} value={inputText} onChange={(e) => setInputText(e.target.value)} placeholder="Paste text to summarize…" /></label><div className="input-meta"><span>{inputText.length.toLocaleString()} / 30,000 characters</span><span>Output cap: 160 tokens</span></div><button className="button button-primary" disabled={loading || !selectedOrg}>{loading ? "Generating…" : "Generate summary"}<span>✦</span></button></form>{summary && <div className="summary-result"><div className="result-head"><strong>Generated summary</strong><span className="soft-tag">{summary.provider} · {summary.model}</span></div><p>{summary.summary}</p><div className="result-stats"><span>{summary.input_tokens} input tokens</span><span>{summary.output_tokens} output tokens</span><span>${summary.estimated_cost_usd.toFixed(6)}</span></div></div>}</section>
            <aside className="side-column"><section className="panel"><div className="card-kicker">WORKSPACE MANAGEMENT</div><h2>Create another workspace</h2><p className="muted">Keep different customers, teams, or projects isolated.</p><form onSubmit={createOrganization} className="form-stack"><label>Workspace name<input required minLength={2} maxLength={120} value={newOrgName} onChange={(e) => setNewOrgName(e.target.value)} placeholder="Product team" /></label><button className="button button-secondary button-full" disabled={creatingOrg}>{creatingOrg ? "Creating…" : "Create workspace"}<span>＋</span></button></form></section><section className="trust-card"><div className="trust-mark">✓</div><div><strong>Tenant-scoped access</strong><p>Organization data is only returned after the API verifies your membership.</p></div></section><section className="trust-card"><div className="trust-mark">↗</div><div><strong>Quota enforced before generation</strong><p>Requests reserve tokens first. Failed provider calls release the reservation.</p></div></section></aside>
          </div>
          <footer className="dashboard-footer"><span>AI SaaS Starter Kit · v0.1.0</span><span>Mock provider costs $0 · Live provider prices are configurable estimates</span></footer>
        </section>
      )}
      <footer className="site-footer"><span>Built as a developer-first SaaS reference.</span><span>Auth · Multi-tenancy · Metering · AI</span></footer>
    </main>
  );
}
