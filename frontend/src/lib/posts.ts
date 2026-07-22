import type { User } from "./auth";
import { ApiError } from "./auth";

import { API_BASE } from "./config";
import type { VotingWindowKind } from "./governance";
import type { ModerationFields } from "./moderation";

export interface Post extends ModerationFields {
  id: string;
  title: string;
  content: string;
  author_id: string;
  tags: string[] | null;
  author_username: string | null;
  reply_count: number;
  like_count: number;
  liked_by_me: boolean;
  created_at: string;
  updated_at: string;
  poll: Poll | null;
  revision_number: number;
}

export interface PollOption {
  id: string;
  text: string;
  vote_count: number;
}

export interface Poll {
  id: string;
  question: string;
  closes_at: string;
  is_closed: boolean;
  total_votes: number;
  selected_option_id?: string | null;
  options: PollOption[];
}

export interface PollCreateData {
  question: string;
  options: string[];
  duration_hours: number;
}

export interface Comment extends ModerationFields {
  id: string;
  content: string;
  author_id: string;
  parent_id: string;
  replying_id: string | null;
  author_username: string | null;
  replying_to_username: string | null;
  replying_to_content: string | null;
  reply_count: number;
  like_count: number;
  liked_by_me: boolean;
  created_at: string;
  updated_at: string | null;
  revision_number: number;
}

export interface ContentEditResult extends ModerationFields {
  id: string;
  type: "post" | "comment" | "guild_post";
  title: string | null;
  content: string;
  tags: string[] | null;
  author_id: string;
  parent_id: string | null;
  patch_id: string | null;
  guild_id: string | null;
  revision_number: number;
  created_at: string;
  updated_at: string;
}

export interface ContentRevision {
  id: string;
  content_id: string;
  version: number;
  title: string | null;
  content: string;
  tags: string[] | null;
  editor_id: string;
  edited_at: string;
}

export async function updateContent(
  id: string,
  data: {
    revision_number: number;
    title?: string;
    content?: string;
    tags?: string[] | null;
  },
): Promise<ContentEditResult> {
  const res = await fetch(`${API_BASE}/posts/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
    credentials: "include",
  });
  if (!res.ok) throw new ApiError((await res.json()).detail ?? "CONTENT_UPDATE_FAILED");
  return res.json();
}

export async function listContentHistory(id: string): Promise<ContentRevision[]> {
  const res = await fetch(`${API_BASE}/posts/${id}/history`, {
    credentials: "include",
  });
  if (!res.ok) throw new ApiError((await res.json()).detail ?? "CONTENT_HISTORY_LOAD_FAILED");
  return res.json();
}

export async function listPosts(page = 1): Promise<Post[]> {
  const res = await fetch(`${API_BASE}/posts?page=${page}`, { credentials: "include" });
  if (!res.ok) throw new Error("Failed to load posts");
  return res.json();
}

export async function getPost(id: string): Promise<Post> {
  const res = await fetch(`${API_BASE}/posts/${id}`, { credentials: "include" });
  if (!res.ok) throw new Error("Post not found");
  return res.json();
}

export async function createPost(data: {
  title: string;
  content: string;
  tags?: string[];
  poll?: PollCreateData;
}): Promise<Post> {
  const res = await fetch(`${API_BASE}/posts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
    credentials: "include",
  });
  if (!res.ok) throw new Error((await res.json()).detail);
  return res.json();
}

export async function listComments(postId: string): Promise<Comment[]> {
  const res = await fetch(`${API_BASE}/posts/${postId}/comments`, { credentials: "include" });
  if (!res.ok) throw new Error("Failed to load comments");
  return res.json();
}

export async function deleteContent(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/posts/${id}`, { method: "DELETE", credentials: "include" });
  if (!res.ok && res.status !== 204) {
    let detail = "POST_DELETE_FAILED";
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {}
    throw new ApiError(detail);
  }
}

export interface PostLikeState {
  like_count: number;
  liked_by_me: boolean;
}

async function setPostLike(id: string, liked: boolean): Promise<PostLikeState> {
  const res = await fetch(`${API_BASE}/posts/${id}/like`, {
    method: liked ? "PUT" : "DELETE",
    credentials: "include",
  });
  if (!res.ok) throw new ApiError(liked ? "POST_LIKE_FAILED" : "POST_UNLIKE_FAILED");
  return res.json();
}

export const likePost = (id: string) => setPostLike(id, true);
export const unlikePost = (id: string) => setPostLike(id, false);

export async function getPostLikeState(id: string): Promise<PostLikeState> {
  const res = await fetch(`${API_BASE}/posts/${id}/like`, { credentials: "include" });
  if (!res.ok) throw new ApiError("POST_LIKE_STATE_FAILED");
  return res.json();
}

export async function voteOnPoll(postId: string, optionId: string): Promise<Poll> {
  const res = await fetch(`${API_BASE}/posts/${postId}/poll/vote`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ option_id: optionId }),
    credentials: "include",
  });
  if (!res.ok) throw new ApiError((await res.json()).detail ?? "POLL_VOTE_FAILED");
  return res.json();
}

export interface FeedItem extends ModerationFields {
  id: string;
  type: "post" | "patch";
  title: string;
  content: string;
  author_id: string;
  author_username: string | null;
  created_at: string;
  tags: string[] | null;
  reply_count: number;
  like_count: number;
  pr_number: number | null;
  status: string | null;
  voting_started_at: string | null;
  voting_ends_at: string | null;
  voting_period_hours: number | null;
  voting_window_kind: VotingWindowKind | null;
  for_count: number;
  against_count: number;
  abstain_count: number;
  ranking_reason: string | null;
  poll: Poll | null;
  revision_number: number;
}

export type FeedMode = "recommended" | "trending" | "following" | "latest";

export async function getFeed(
  page = 1,
  mode: FeedMode = "recommended",
  rotationSeed = 0,
): Promise<FeedItem[]> {
  const params = new URLSearchParams({
    page: String(page),
    mode,
    rotation_seed: String(rotationSeed),
  });
  const res = await fetch(`${API_BASE}/posts/-/feed?${params}`, {
    credentials: "include",
  });
  if (!res.ok) throw new Error("Failed to load feed");
  return res.json();
}

export async function createComment(postId: string, data: { content: string; replying_id?: string }): Promise<Comment> {
  const res = await fetch(`${API_BASE}/posts/${postId}/comments`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
    credentials: "include",
  });
  if (!res.ok) throw new Error((await res.json()).detail);
  return res.json();
}
