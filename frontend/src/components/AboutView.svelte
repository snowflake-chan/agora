<script lang="ts">
  import {
    ArrowRight,
    Eye,
    GitMerge,
    GitPullRequest,
    MessageCircle,
    Scale,
    ShieldCheck,
    UsersRound,
    Vote,
  } from "@lucide/svelte";
  import { onMount } from "svelte";
  import { translator } from "../lib/i18n";

  let aboutRoot: HTMLElement;

  onMount(() => {
    const sections = aboutRoot.querySelectorAll<HTMLElement>("[data-reveal]");
    const reduceMotion = document.documentElement.dataset.motion === "reduced"
      || window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if (reduceMotion || !("IntersectionObserver" in window)) {
      sections.forEach((section) => section.classList.add("is-visible"));
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      },
      { rootMargin: "0px 0px -12% 0px", threshold: 0.08 },
    );

    sections.forEach((section) => {
      section.classList.add("reveal-ready");
      observer.observe(section);
    });

    return () => observer.disconnect();
  });
</script>

<main class="about-main" bind:this={aboutRoot}>
  <section class="about-hero" aria-labelledby="about-title">
    <div class="hero-copy">
      <p class="eyebrow">{$translator("about.eyebrow")}</p>
      <h1 id="about-title">{$translator("about.heroTitle")}</h1>
      <p class="hero-description">{$translator("about.heroDescription")}</p>

      <div class="hero-actions">
        <a class="about-action about-action-primary" href="/">
          {$translator("about.ctaExplore")}
          <ArrowRight aria-hidden="true" />
        </a>
        <a class="about-action about-action-secondary" href="/patches">
          {$translator("about.ctaChanges")}
        </a>
      </div>
    </div>

    <div class="hero-map" aria-label={$translator("about.loopLabel")}>
      <div class="map-brand">
        <img src="/favicon.svg" alt="" width="64" height="64" />
        <div>
          <strong>Agora</strong>
          <span>{$translator("about.loopLabel")}</span>
        </div>
      </div>

      <ol class="loop-list">
        <li>
          <span class="loop-icon loop-icon-discuss"><MessageCircle aria-hidden="true" /></span>
          <span class="loop-copy">
            <strong>{$translator("about.stepDiscuss")}</strong>
            <span>{$translator("about.stepDiscussDesc")}</span>
          </span>
          <span class="loop-index" aria-hidden="true">01</span>
        </li>
        <li>
          <span class="loop-icon loop-icon-propose"><GitPullRequest aria-hidden="true" /></span>
          <span class="loop-copy">
            <strong>{$translator("about.stepPropose")}</strong>
            <span>{$translator("about.stepProposeDesc")}</span>
          </span>
          <span class="loop-index" aria-hidden="true">02</span>
        </li>
        <li>
          <span class="loop-icon loop-icon-decide"><Vote aria-hidden="true" /></span>
          <span class="loop-copy">
            <strong>{$translator("about.stepDecide")}</strong>
            <span>{$translator("about.stepDecideDesc")}</span>
          </span>
          <span class="loop-index" aria-hidden="true">03</span>
        </li>
        <li>
          <span class="loop-icon loop-icon-ship"><GitMerge aria-hidden="true" /></span>
          <span class="loop-copy">
            <strong>{$translator("about.stepShip")}</strong>
            <span>{$translator("about.stepShipDesc")}</span>
          </span>
          <span class="loop-index" aria-hidden="true">04</span>
        </li>
      </ol>
    </div>
  </section>

  <section class="model-section" aria-labelledby="model-title" data-reveal>
    <div class="section-heading">
      <h2 id="model-title">{$translator("about.modelTitle")}</h2>
      <div class="section-copy">
        <p>{$translator("about.modelBodyPrimary")}</p>
        <p>{$translator("about.modelBodySecondary")}</p>
      </div>
    </div>

    <div class="principles-layout">
      <article class="principle-feature">
        <UsersRound aria-hidden="true" />
        <div>
          <h3>{$translator("about.agencyTitle")}</h3>
          <p>{$translator("about.agencyBody")}</p>
        </div>
      </article>
      <div class="principle-stack">
        <article>
          <Eye aria-hidden="true" />
          <div>
            <h3>{$translator("about.visibilityTitle")}</h3>
            <p>{$translator("about.visibilityBody")}</p>
          </div>
        </article>
        <article>
          <ShieldCheck aria-hidden="true" />
          <div>
            <h3>{$translator("about.accountabilityTitle")}</h3>
            <p>{$translator("about.accountabilityBody")}</p>
          </div>
        </article>
      </div>
    </div>
  </section>

  <section class="governance-section" aria-labelledby="governance-title" data-reveal>
    <div class="governance-heading">
      <p class="eyebrow">{$translator("about.governanceEyebrow")}</p>
      <h2 id="governance-title">{$translator("about.governanceTitle")}</h2>
      <p>{$translator("about.governanceBody")}</p>
    </div>

    <ol class="governance-path">
      <li>
        <span class="stage-icon"><GitPullRequest aria-hidden="true" /></span>
        <strong>{$translator("about.stageDraft")}</strong>
        <p>{$translator("about.stageDraftDesc")}</p>
      </li>
      <li>
        <span class="stage-icon"><Vote aria-hidden="true" /></span>
        <strong>{$translator("about.stageVoting")}</strong>
        <p>{$translator("about.stageVotingDesc")}</p>
      </li>
      <li>
        <span class="stage-icon"><Scale aria-hidden="true" /></span>
        <strong>{$translator("about.stageDecision")}</strong>
        <p>{$translator("about.stageDecisionDesc")}</p>
      </li>
      <li>
        <span class="stage-icon"><GitMerge aria-hidden="true" /></span>
        <strong>{$translator("about.stageMerge")}</strong>
        <p>{$translator("about.stageMergeDesc")}</p>
      </li>
    </ol>
  </section>

  <section class="values-section" aria-labelledby="values-title" data-reveal>
    <div>
      <h2 id="values-title">{$translator("about.valuesTitle")}</h2>
      <p class="values-description">{$translator("about.valuesBody")}</p>
    </div>

    <ol class="values-list">
      <li><span>01</span><strong>{$translator("about.valueIdentity")}</strong></li>
      <li><span>02</span><strong>{$translator("about.valueReasoning")}</strong></li>
      <li><span>03</span><strong>{$translator("about.valueRevision")}</strong></li>
      <li><span>04</span><strong>{$translator("about.valueOutcome")}</strong></li>
    </ol>
  </section>

  <section class="closing-section" aria-labelledby="closing-title" data-reveal>
    <img src="/favicon.svg" alt="" width="48" height="48" />
    <div class="closing-copy">
      <h2 id="closing-title">{$translator("about.closingTitle")}</h2>
      <p>{$translator("about.closingBody")}</p>
    </div>
    <div class="closing-actions">
      <a class="about-action about-action-primary" href="/">
        {$translator("about.closingCta")}
        <ArrowRight aria-hidden="true" />
      </a>
      <a
        class="source-link"
        href="https://github.com/snowflake-chan/agora"
        target="_blank"
        rel="noreferrer"
      >
        {$translator("about.sourceCta")}
      </a>
    </div>
  </section>
</main>

<style>
  :global(body) {
    padding-bottom: 6rem;
  }

  .about-main {
    --about-max: 78rem;
    overflow: hidden;
    padding-bottom: 0;
    padding-inline: 1.5rem;
  }

  .about-hero,
  .model-section,
  .governance-section,
  .values-section,
  .closing-section {
    width: min(100%, var(--about-max));
    margin-inline: auto;
  }

  .about-hero {
    display: grid;
    min-height: calc(100dvh - 7rem);
    grid-template-columns: minmax(0, 1.08fr) minmax(22rem, 0.92fr);
    align-items: center;
    gap: 6rem;
    padding-block: 5.5rem 6rem;
  }

  .hero-copy {
    max-width: 45rem;
  }

  .eyebrow {
    margin: 0 0 1.25rem;
    color: var(--vercel-text-tertiary);
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }

  h1,
  h2,
  h3,
  p {
    margin-top: 0;
    letter-spacing: 0;
  }

  h1 {
    max-width: 44rem;
    margin-bottom: 1.75rem;
    font-size: 5rem;
    font-weight: 500;
    line-height: 0.98;
  }

  .hero-description {
    max-width: 38rem;
    margin-bottom: 2.25rem;
    color: var(--vercel-text-secondary);
    font-size: 1.125rem;
    line-height: 1.75;
  }

  .hero-actions,
  .closing-actions {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 0.75rem;
  }

  .about-action {
    display: inline-flex;
    min-height: 2.75rem;
    align-items: center;
    justify-content: center;
    gap: 0.6rem;
    padding: 0.7rem 1rem;
    border: 1px solid transparent;
    border-radius: var(--vercel-radius-sm);
    font-size: 0.875rem;
    font-weight: 600;
    line-height: 1.2;
    transition: background 160ms ease, border-color 160ms ease, color 160ms ease, transform 160ms ease;
  }

  .about-action :global(svg) {
    width: 1rem;
    height: 1rem;
  }

  .about-action:hover {
    transform: translateY(-1px);
  }

  .about-action:focus-visible,
  .source-link:focus-visible {
    outline: 2px solid var(--vercel-ring);
    outline-offset: 3px;
  }

  .about-action-primary {
    color: var(--vercel-accent-foreground);
    background: var(--vercel-accent);
    border-color: var(--vercel-accent);
  }

  .about-action-primary:hover {
    color: var(--vercel-accent-foreground);
    background: var(--vercel-accent-hover);
    border-color: var(--vercel-accent-hover);
  }

  .about-action-secondary {
    color: var(--vercel-text);
    background: transparent;
    border-color: var(--vercel-border-hover);
  }

  .about-action-secondary:hover {
    color: var(--vercel-text);
    background: var(--vercel-hover);
  }

  .hero-map {
    position: relative;
    border: 1px solid var(--vercel-border);
    border-radius: var(--vercel-radius-lg);
    background: color-mix(in srgb, var(--vercel-card) 72%, transparent);
    box-shadow: 0 1.5rem 5rem color-mix(in srgb, var(--vercel-shadow) 45%, transparent);
    overflow: hidden;
  }

  .map-brand {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 1.5rem;
    border-bottom: 1px solid var(--vercel-border);
  }

  .map-brand img {
    width: 3.5rem;
    height: 3.5rem;
  }

  .map-brand div {
    display: grid;
    gap: 0.2rem;
  }

  .map-brand strong {
    color: var(--vercel-text);
    font-size: 1.05rem;
  }

  .map-brand span,
  .loop-copy span {
    color: var(--vercel-text-tertiary);
    font-size: 0.75rem;
    line-height: 1.45;
  }

  .loop-list {
    margin: 0;
    padding: 0.5rem 1.5rem;
    list-style: none;
  }

  .loop-list li {
    position: relative;
    display: grid;
    grid-template-columns: 2.5rem minmax(0, 1fr) auto;
    align-items: center;
    gap: 1rem;
    min-height: 5.5rem;
    border-bottom: 1px solid var(--vercel-border);
  }

  .loop-list li:last-child {
    border-bottom: 0;
  }

  .loop-icon,
  .stage-icon {
    display: grid;
    width: 2.5rem;
    height: 2.5rem;
    place-items: center;
    border: 1px solid var(--vercel-border);
    border-radius: var(--vercel-radius-sm);
    background: var(--vercel-surface-muted);
  }

  .loop-icon :global(svg),
  .stage-icon :global(svg) {
    width: 1.1rem;
    height: 1.1rem;
  }

  .loop-icon-discuss {
    color: var(--vercel-info);
  }

  .loop-icon-propose {
    color: var(--vercel-warning);
  }

  .loop-icon-decide {
    color: var(--vercel-success);
  }

  .loop-icon-ship {
    color: var(--vercel-text);
  }

  .loop-copy {
    display: grid;
    gap: 0.3rem;
  }

  .loop-copy strong {
    color: var(--vercel-text);
    font-size: 0.875rem;
  }

  .loop-index {
    color: var(--vercel-text-tertiary);
    font-family: "JetBrains Mono", monospace;
    font-size: 0.6875rem;
  }

  .model-section,
  .governance-section,
  .values-section {
    padding-block: 8rem;
    border-top: 1px solid var(--vercel-border);
  }

  .section-heading {
    display: grid;
    grid-template-columns: minmax(0, 1.15fr) minmax(18rem, 0.85fr);
    gap: 5rem;
    align-items: start;
    margin-bottom: 5rem;
  }

  h2 {
    margin-bottom: 0;
    font-size: 3.5rem;
    font-weight: 500;
    line-height: 1.06;
  }

  .section-copy {
    display: grid;
    gap: 1rem;
    padding-top: 0.5rem;
  }

  .section-copy p,
  .governance-heading > p:last-child,
  .values-description,
  .closing-copy p {
    margin-bottom: 0;
    color: var(--vercel-text-secondary);
    font-size: 1rem;
    line-height: 1.75;
  }

  .principles-layout {
    display: grid;
    grid-template-columns: minmax(0, 1.2fr) minmax(18rem, 0.8fr);
    gap: 4rem;
  }

  .principle-feature,
  .principle-stack article {
    display: grid;
    align-content: space-between;
    gap: 3rem;
    padding-top: 1.5rem;
    border-top: 1px solid var(--vercel-border-hover);
  }

  .principle-feature {
    min-height: 22rem;
  }

  .principle-feature :global(svg),
  .principle-stack :global(svg) {
    width: 1.5rem;
    height: 1.5rem;
    color: var(--vercel-text-tertiary);
  }

  .principle-feature h3,
  .principle-stack h3 {
    margin-bottom: 0.75rem;
    font-size: 1.5rem;
    font-weight: 500;
    line-height: 1.2;
  }

  .principle-feature p,
  .principle-stack p {
    max-width: 34rem;
    margin-bottom: 0;
    color: var(--vercel-text-secondary);
    line-height: 1.7;
  }

  .principle-stack {
    display: grid;
    gap: 3.5rem;
  }

  .principle-stack article {
    min-height: 9rem;
    grid-template-columns: 2rem minmax(0, 1fr);
    gap: 1.25rem;
  }

  .governance-section {
    display: grid;
    gap: 5rem;
  }

  .governance-heading {
    max-width: 48rem;
  }

  .governance-heading h2 {
    margin-bottom: 1.5rem;
  }

  .governance-heading > p:last-child {
    max-width: 40rem;
  }

  .governance-path {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    margin: 0;
    padding: 0;
    border-top: 1px solid var(--vercel-border-hover);
    list-style: none;
  }

  .governance-path li {
    min-height: 17rem;
    padding: 1.5rem 1.5rem 0 0;
    border-right: 1px solid var(--vercel-border);
  }

  .governance-path li + li {
    padding-left: 1.5rem;
  }

  .governance-path li:last-child {
    border-right: 0;
  }

  .governance-path .stage-icon {
    margin-bottom: 4rem;
    color: var(--vercel-text-secondary);
  }

  .governance-path strong {
    display: block;
    margin-bottom: 0.75rem;
    color: var(--vercel-text);
    font-size: 1rem;
  }

  .governance-path p {
    margin-bottom: 0;
    color: var(--vercel-text-tertiary);
    font-size: 0.8125rem;
    line-height: 1.6;
  }

  .values-section {
    display: grid;
    grid-template-columns: minmax(0, 0.9fr) minmax(22rem, 1.1fr);
    gap: 6rem;
  }

  .values-section h2 {
    margin-bottom: 1.5rem;
  }

  .values-description {
    max-width: 33rem;
  }

  .values-list {
    margin: 0;
    padding: 0;
    border-top: 1px solid var(--vercel-border-hover);
    list-style: none;
  }

  .values-list li {
    display: grid;
    min-height: 5rem;
    grid-template-columns: 3rem minmax(0, 1fr);
    align-items: center;
    border-bottom: 1px solid var(--vercel-border);
  }

  .values-list span {
    color: var(--vercel-text-tertiary);
    font-family: "JetBrains Mono", monospace;
    font-size: 0.6875rem;
  }

  .values-list strong {
    color: var(--vercel-text);
    font-size: 1rem;
    font-weight: 500;
  }

  .closing-section {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: center;
    gap: 2rem;
    padding-block: 4rem 7rem;
    border-top: 1px solid var(--vercel-border);
  }

  .closing-section > img {
    width: 3rem;
    height: 3rem;
  }

  .closing-copy h2 {
    margin-bottom: 0.5rem;
    font-size: 1.75rem;
  }

  .closing-copy p {
    font-size: 0.875rem;
  }

  .closing-actions {
    justify-content: flex-end;
  }

  .source-link {
    padding: 0.5rem;
    color: var(--vercel-text-secondary);
    font-size: 0.8125rem;
    font-weight: 500;
  }

  .source-link:hover {
    color: var(--vercel-text);
  }

  [data-reveal].reveal-ready {
    opacity: 0;
    transform: translateY(2rem);
    transition: opacity 650ms var(--apple-ease-soft), transform 650ms var(--apple-ease-soft);
  }

  [data-reveal].reveal-ready.is-visible {
    opacity: 1;
    transform: translateY(0);
  }

  @media (max-width: 64rem) {
    .about-hero {
      grid-template-columns: minmax(0, 1fr) minmax(20rem, 0.9fr);
      gap: 3.5rem;
    }

    h1 {
      font-size: 4rem;
    }

    h2 {
      font-size: 3rem;
    }

    .model-section,
    .governance-section,
    .values-section {
      padding-block: 6.5rem;
    }

    .section-heading,
    .values-section {
      gap: 3rem;
    }

    .governance-path .stage-icon {
      margin-bottom: 3rem;
    }
  }

  @media (max-width: 48rem) {
    .about-main {
      padding-inline: 1rem;
    }

    .about-hero {
      min-height: auto;
      grid-template-columns: 1fr;
      gap: 4rem;
      padding-block: 4.5rem 5rem;
    }

    h1 {
      font-size: 3.5rem;
      line-height: 1.02;
    }

    .hero-description {
      font-size: 1rem;
    }

    .hero-map {
      width: 100%;
      max-width: 32rem;
    }

    .section-heading,
    .principles-layout,
    .values-section {
      grid-template-columns: 1fr;
    }

    .section-heading {
      gap: 2rem;
      margin-bottom: 4rem;
    }

    h2 {
      font-size: 2.5rem;
    }

    .principle-feature {
      min-height: 16rem;
    }

    .governance-path {
      grid-template-columns: 1fr 1fr;
    }

    .governance-path li {
      min-height: 14rem;
      padding: 1.5rem 1.5rem 1.5rem 0;
      border-bottom: 1px solid var(--vercel-border);
    }

    .governance-path li:nth-child(2) {
      border-right: 0;
    }

    .governance-path li:nth-child(n + 3) {
      padding-top: 2rem;
      border-bottom: 0;
    }

    .governance-path .stage-icon {
      margin-bottom: 2rem;
    }

    .closing-section {
      grid-template-columns: auto minmax(0, 1fr);
    }

    .closing-actions {
      grid-column: 1 / -1;
      justify-content: flex-start;
    }
  }

  @media (max-width: 30rem) {
    h1 {
      font-size: 3rem;
    }

    h2 {
      font-size: 2.125rem;
    }

    .hero-actions,
    .closing-actions {
      align-items: stretch;
      flex-direction: column;
    }

    .about-action,
    .source-link {
      width: 100%;
      box-sizing: border-box;
      text-align: center;
    }

    .map-brand,
    .loop-list {
      padding-inline: 1rem;
    }

    .loop-list li {
      grid-template-columns: 2.5rem minmax(0, 1fr);
    }

    .loop-index {
      display: none;
    }

    .model-section,
    .governance-section,
    .values-section {
      padding-block: 5rem;
    }

    .principles-layout {
      gap: 3rem;
    }

    .governance-path {
      grid-template-columns: 1fr;
    }

    .governance-path li,
    .governance-path li + li,
    .governance-path li:nth-child(n + 3) {
      min-height: auto;
      padding: 1.5rem 0 2rem;
      border-right: 0;
      border-bottom: 1px solid var(--vercel-border);
    }

    .governance-path li:last-child {
      border-bottom: 0;
    }

    .closing-section {
      align-items: start;
      padding-bottom: 4rem;
    }
  }
</style>
