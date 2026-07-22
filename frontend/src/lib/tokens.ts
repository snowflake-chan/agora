import { API_BASE } from "./config";
import { ApiError } from "./auth";

export interface TokenBalance {
  balance: number;
  total_earned: number;
  total_spent: number;
}

export interface TokenTransaction {
  id: string;
  amount: number;
  type: "earn" | "spend" | "receive";
  source: string;
  reference_id: string | null;
  balance_after: number;
  created_at: string;
}

export interface TransactionList {
  items: TokenTransaction[];
  total: number;
  page: number;
  page_size: number;
}

export interface TipResult {
  ok: boolean;
  balance_after: number;
}

export interface DailyLoginResult {
  reward: number;
  streak: number;
  already_claimed: boolean;
  balance: number;
}

export type BoostTier = "low" | "mid" | "high";

export interface BoostResult {
  ok: boolean;
  tier: BoostTier;
  weight: number;
  expires_at: string;
  balance_after: number;
}

export interface TokenSupply {
  circulating_supply: number;
  total_issued: number;
  total_burned: number;
}

export type TokenParamKey =
  | "like_reward"
  | "vote_reward"
  | "proposal_pass_reward"
  | "daily_login_base"
  | "proposal_deposit"
  | "boost_price_low"
  | "boost_price_mid"
  | "boost_price_high"
  | "guild_create_fee"
  | "daily_user_cap";

export type TokenParams = Record<TokenParamKey, number>;

export interface TokenParamHistoryItem {
  key: TokenParamKey;
  old_value: number;
  new_value: number;
  changed_by: string | null;
  changed_at: string;
}

export interface MonetaryMetrics {
  inflation_7d: number;
  inflation_30d: number;
  velocity: number;
  active_users: number;
  status: "healthy" | "inflating" | "deflating";
  target_lower: number;
  target_upper: number;
}

export interface SupplySnapshot {
  date: string;
  circulating_supply: number;
  total_issued: number;
  total_burned: number;
  active_users: number;
  transaction_count_24h: number;
}

export interface PolicyAdjustment {
  adjusted: boolean;
  reason: string;
  adjustments: Record<string, number>;
  dry_run?: boolean;
}

async function req(path: string, options?: RequestInit) {
  const res = await fetch(`${API_BASE}${path}`, { credentials: "include", ...options });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(err.detail || res.statusText);
  }
  if (res.status === 204) return null;
  return res.json();
}

// ── User-facing token endpoints ──

export async function getBalance(): Promise<TokenBalance> {
  return req("/tokens/balance");
}

export async function listTransactions(page = 1, page_size = 20): Promise<TransactionList> {
  const params = new URLSearchParams({ page: String(page), page_size: String(page_size) });
  return req(`/tokens/transactions?${params}`);
}

export async function sendTip(postId: string, amount: number): Promise<TipResult> {
  return req("/tokens/tip", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ post_id: postId, amount }),
  });
}

export async function claimDailyLogin(): Promise<DailyLoginResult> {
  return req("/tokens/daily-login", { method: "POST" });
}

export async function boostPost(postId: string, tier: BoostTier): Promise<BoostResult> {
  return req(`/posts/${postId}/boost`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tier }),
  });
}

// ── Admin token economy endpoints ──

export async function getTokenSupply(): Promise<TokenSupply> {
  return req("/admin/tokens/supply");
}

export async function getTokenParams(): Promise<TokenParams> {
  // The admin panel needs a full map; fall back to defaults when an endpoint
  // value is missing so the UI never renders NaN.
  const defaults: TokenParams = {
    like_reward: 2,
    vote_reward: 2,
    proposal_pass_reward: 100,
    daily_login_base: 3,
    proposal_deposit: 50,
    boost_price_low: 10,
    boost_price_mid: 30,
    boost_price_high: 50,
    guild_create_fee: 200,
    daily_user_cap: 200,
  };
  const params = (await req("/admin/tokens/params")) as Partial<TokenParams>;
  return { ...defaults, ...params };
}

export async function updateTokenParams(updates: Partial<TokenParams>): Promise<{ ok: boolean; params: TokenParams }> {
  return req("/admin/tokens/params", {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
}

export async function mintTokens(userId: string, amount: number): Promise<{ ok: boolean }> {
  return req("/admin/tokens/mint", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, amount }),
  });
}

export async function getTokenParamHistory(): Promise<{ items: TokenParamHistoryItem[] }> {
  return req("/admin/tokens/params/history");
}

export async function getMonetaryMetrics(): Promise<MonetaryMetrics> {
  return req("/admin/tokens/monetary");
}

export async function getSupplyHistory(days = 90): Promise<SupplySnapshot[]> {
  return req(`/admin/tokens/supply/history?days=${days}`);
}

export async function applyPolicyAdjustment(dryRun = true): Promise<PolicyAdjustment> {
  return req("/admin/tokens/apply-policy", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dry_run: dryRun }),
  });
}
