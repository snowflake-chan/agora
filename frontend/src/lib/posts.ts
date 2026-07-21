import type { User } from "./auth";
import { ApiError } from "./auth";

import { API_BASE } from "./config";
import type { VotingWindowKind } from "./governance";

export interface Post {
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

export interface Comment {
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
  if (!res.ok && res.status !== 204) throw new ApiError("POST_DELETE_FAILED");
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

export interface FeedItem {
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
}

export type FeedMode = "recommended" | "trending" | "following" | "latest";

export async function getFeed(
  page = 1,
  mode: FeedMode = "recommended",
): Promise<FeedItem[]> {
  const params = new URLSearchParams({
    page: String(page),
    mode,
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
