export const LOGIN_REQUEST_EVENT = "agora:request-login";

export interface LoginRequestDetail {
  returnTo?: string;
  onAuthenticated?: (() => void) | null;
}

export function requestLogin(
  returnTo?: string,
  onAuthenticated?: (() => void) | null,
) {
  if (typeof window === "undefined") return;

  const fallback = `${window.location.pathname}${window.location.search}${window.location.hash}`;
  window.dispatchEvent(
    new CustomEvent<LoginRequestDetail>(LOGIN_REQUEST_EVENT, {
      detail: {
        returnTo: returnTo ?? fallback,
        onAuthenticated: onAuthenticated ?? null,
      },
    }),
  );
}
