const FOCUSABLE = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled])",
  "textarea:not([disabled])",
  "select:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

export function modal(node: HTMLElement, options: { onClose: () => void }) {
  const previousFocus = document.activeElement instanceof HTMLElement
    ? document.activeElement
    : null;
  const previousOverflow = document.body.style.overflow;

  function focusable() {
    return [...node.querySelectorAll<HTMLElement>(FOCUSABLE)]
      .filter((element) => !element.hidden && element.getClientRects().length > 0);
  }

  function handleKeydown(event: KeyboardEvent) {
    if (event.key === "Escape") {
      event.preventDefault();
      options.onClose();
      return;
    }
    if (event.key !== "Tab") return;

    const elements = focusable();
    if (!elements.length) {
      event.preventDefault();
      node.focus();
      return;
    }
    const first = elements[0];
    const last = elements[elements.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }

  document.body.style.overflow = "hidden";
  document.addEventListener("keydown", handleKeydown);
  requestAnimationFrame(() => {
    (node.querySelector<HTMLElement>("[data-autofocus]") ?? focusable()[0] ?? node).focus();
  });

  return {
    destroy() {
      document.removeEventListener("keydown", handleKeydown);
      document.body.style.overflow = previousOverflow;
      if (previousFocus?.isConnected) previousFocus.focus();
    },
  };
}
