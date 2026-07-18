import { writable } from "svelte/store";

export const mainView = writable<"posts" | "patches">("posts");
