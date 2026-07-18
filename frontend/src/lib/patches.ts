import { API_BASE } from "./config";

export interface Patch {
  id: string;
  title: string;
  content: string;
  pr_number: number;
  status: string;
  author_id: string;
  author_username: string | null;
  voting_ends_at: string | null;
  for_count: number;
  against_count: number;
  abstain_count: number;
  created_at: string;
  updated_at: string;
}

export interface Vote {
  id: string;
  patch_id: string;
  voter_id: string;
  choice: string;
  voter_username: string | null;
  created_at: string;
}

export async function listPatches(
  page = 1,
  status?: string,
): Promise<Patch[]> {
  const params = new URLSearchParams({ page: String(page) });
  if (status) params.set("status", status);
  const res = await fetch(`${API_BASE}/patches?${params}`, { credentials: "include" });
  if (!res.ok) throw new Error("Failed to load patches");
  return res.json();
}

export async function getPatch(id: string): Promise<Patch> {
  const res = await fetch(`${API_BASE}/patches/${id}`, { credentials: "include" });
  if (!res.ok) throw new Error("Patch not found");
  return res.json();
}

export async function createPatch(data: {
  title: string;
  content: string;
  pr_number: number;
}): Promise<Patch> {
  const res = await fetch(`${API_BASE}/patches`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
    credentials: "include",
  });
  if (!res.ok) throw new Error((await res.json()).detail);
  return res.json();
}

export async function deletePatch(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/patches/${id}`, {
    method: "DELETE",
    credentials: "include",
  });
  if (!res.ok && res.status !== 204) throw new Error("删除失败");
}

export async function submitPatch(id: string): Promise<Patch> {
  const res = await fetch(`${API_BASE}/patches/${id}/submit`, {
    method: "POST",
    credentials: "include",
  });
  if (!res.ok) throw new Error((await res.json()).detail);
  return res.json();
}

export async function votePatch(
  patchId: string,
  choice: string,
): Promise<Vote> {
  const res = await fetch(`${API_BASE}/patches/${patchId}/vote`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ choice }),
    credentials: "include",
  });
  if (!res.ok) throw new Error((await res.json()).detail);
  return res.json();
}

export async function listVotes(patchId: string): Promise<Vote[]> {
  const res = await fetch(`${API_BASE}/patches/${patchId}/votes`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error("Failed to load votes");
  return res.json();
}
