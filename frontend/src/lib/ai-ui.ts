export const WRITING_ASSIST_MIN_BODY_LENGTH = 12;
export const POLL_AI_MIN_TITLE_LENGTH = 8;
export const POLL_AI_MIN_BODY_LENGTH = 40;

export type AiInputReadiness = {
  ready: boolean;
  titleRemaining: number;
  bodyRemaining: number;
};

export type AiSignaturePart = string | number | boolean | null;

function remainingLength(value: string, minimum: number): number {
  return Math.max(0, minimum - value.trim().length);
}

export function getWritingAssistReadiness(body: string): AiInputReadiness {
  const bodyRemaining = remainingLength(body, WRITING_ASSIST_MIN_BODY_LENGTH);
  return {
    ready: bodyRemaining === 0,
    titleRemaining: 0,
    bodyRemaining,
  };
}

export function getPollAiReadiness(title: string, body: string): AiInputReadiness {
  const titleRemaining = remainingLength(title, POLL_AI_MIN_TITLE_LENGTH);
  const bodyRemaining = remainingLength(body, POLL_AI_MIN_BODY_LENGTH);
  return {
    ready: titleRemaining === 0 && bodyRemaining === 0,
    titleRemaining,
    bodyRemaining,
  };
}

export function createAiInputSignature(parts: readonly AiSignaturePart[]): string {
  return JSON.stringify(parts);
}

export function isCurrentAiResult(
  requestSequence: number,
  latestRequestSequence: number,
  requestedSignature: string,
  currentSignature: string,
): boolean {
  return requestSequence === latestRequestSequence && requestedSignature === currentSignature;
}
