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
  reason_code?: string;
  reason_params?: Record<string, number>;
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
    body: JSON.stringify({ recipient: userId, amount }),
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

export async function shortenPatchVote(
  patchId: string,
  remainingHours?: number,
): Promise<{ ok: boolean; action: "shortened" | "ended"; new_voting_ends_at?: string; outcome?: string }> {
  return req("/admin/patches/" + patchId + "/shorten-vote", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ remaining_hours: remainingHours ?? null }),
  });
}

// ── Staking API ──

export interface StakePool {
  type: string;
  name: string;
  description: string;
  base_apy: number;
  lock_days: number;
  risk_level: string;
  min_stake: number;
}

export interface StakeResult {
  ok: boolean;
  stake: {
    id: string;
    amount: number;
    pool_type: string;
    apy: number;
    locked_until: string | null;
    created_at: string;
  };
}

export interface UnstakeResult {
  ok: boolean;
  principal_returned: number;
  yield_earned: number;
  penalty: number;
  total_returned: number;
}

export interface ClaimYieldResult {
  ok: boolean;
  claimed: number;
}

export interface StakeItem {
  id: string;
  amount: number;
  pool_type: string;
  reference_id: string | null;
  locked_until: string | null;
  apy: number;
  pending_yield: number;
  is_active: boolean;
  created_at: string;
}

export interface StakingStats {
  total_staked: number;
  total_pending_yield: number;
  active_stakes: number;
}

export async function listPools(): Promise<{ pools: StakePool[] }> {
  return req("/tokens/staking/pools");
}

export async function stakeTokens(amount: number, poolType: string, referenceId?: string): Promise<StakeResult> {
  return req("/tokens/staking/stake", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ amount, pool_type: poolType, reference_id: referenceId ?? null }),
  });
}

export async function unstakeTokens(stakeId: string): Promise<UnstakeResult> {
  return req("/tokens/staking/unstake", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ stake_id: stakeId }),
  });
}

export async function claimYield(stakeId: string): Promise<ClaimYieldResult> {
  return req("/tokens/staking/claim-yield", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ stake_id: stakeId }),
  });
}

export async function listMyStakes(includeInactive = false): Promise<{ stakes: StakeItem[] }> {
  return req(`/tokens/staking/my-stakes?include_inactive=${includeInactive}`);
}

export async function getMyStakingStats(): Promise<StakingStats> {
  return req("/tokens/staking/my-stats");
}

export async function getUserStakingStats(userId: string): Promise<StakingStats> {
  return req(`/tokens/staking/user-stats/${userId}`);
}

// ── Achievement API ──

export interface AchievementItem {
  key: string;
  name: string;
  score: number;
  tier: number;
  tier_label: string;
  thresholds: number[];
}

export interface AchievementCategory {
  key: string;
  label: string;
  achievements: AchievementItem[];
}

export interface AchievementData {
  categories: AchievementCategory[];
}

export async function getUserAchievements(userId: string): Promise<AchievementData> {
  return req(`/tokens/achievements/user/${userId}`);
}

export async function syncMyAchievements(): Promise<{ ok: boolean; newly_earned: Array<{ key: string; name: string; category: string; tier: number; score: number }> }> {
  return req("/tokens/achievements/sync", { method: "POST" });
}

// ── Paid Q&A API ──

export interface PaidQuestionItem {
  id: string;
  from_user: { id: string; username: string; nickname: string | null } | null;
  to_user: { id: string; username: string; nickname: string | null };
  question_text: string;
  amount: number;
  is_anonymous: boolean;
  is_answered: boolean;
  answer_text: string | null;
  created_at: string;
  answered_at: string | null;
}

export interface QACounts {
  questions_received: number;
  questions_answered: number;
  questions_asked: number;
}

export async function askQuestion(toUserId: string, questionText: string, amount: number, isAnonymous = false): Promise<{ ok: boolean; question: { id: string; amount: number; is_anonymous: boolean; created_at: string } }> {
  return req("/tokens/qa/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ to_user_id: toUserId, question_text: questionText, amount, is_anonymous: isAnonymous }),
  });
}

export async function listUserQuestions(userId: string, page = 1, pageSize = 20): Promise<{ items: PaidQuestionItem[]; total: number; page: number; page_size: number }> {
  return req(`/tokens/qa/user/${userId}?page=${page}&page_size=${pageSize}`);
}

export async function getQACounts(userId: string): Promise<QACounts> {
  return req(`/tokens/qa/count/${userId}`);
}

export async function answerQuestion(questionId: string, answerText: string): Promise<{ ok: boolean; question: { id: string; is_answered: boolean; answered_at: string | null } }> {
  return req("/tokens/qa/answer", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question_id: questionId, answer_text: answerText }),
  });
}

// ── Fine API ──

export interface FineItem {
  id: string;
  user: { id: string; username: string };
  amount: number;
  reason: string;
  reference_type: string;
  reference_id: string | null;
  issued_by: { id: string; username: string } | null;
  status: string;
  issued_at: string;
  paid_at: string | null;
}

export async function getMyFines(page = 1, pageSize = 20): Promise<{ items: FineItem[]; total: number; page: number; page_size: number }> {
  return req(`/tokens/fines/my?page=${page}&page_size=${pageSize}`);
}

export async function payFine(fineId: string): Promise<{ ok: boolean; status: string }> {
  return req("/tokens/fines/pay", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fine_id: fineId }),
  });
}

export async function checkUnpaidFines(): Promise<{ has_unpaid_fines: boolean }> {
  return req("/tokens/fines/check");
}

export async function listFines(userId?: string, status?: string, page = 1, pageSize = 20): Promise<{ items: FineItem[]; total: number; page: number; page_size: number }> {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (userId) params.set("user_id", userId);
  if (status) params.set("status", status);
  return req(`/tokens/fines/list?${params}`);
}

export async function issueFine(userId: string, amount: number, reason: string, referenceType: string = "general", referenceId?: string): Promise<{ ok: boolean; fine: { id: string; user_id: string; amount: number; status: string } }> {
  return req("/tokens/fines/issue", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, amount, reason, reference_type: referenceType, reference_id: referenceId ?? null }),
  });
}

export async function cancelFine(fineId: string): Promise<{ ok: boolean; status: string }> {
  return req("/tokens/fines/cancel", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fine_id: fineId }),
  });
}
