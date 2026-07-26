# Frontend design system

The redesigned interface uses an editorial “knowledge in focus” identity: warm neutral
canvas, ink navigation, violet intelligence accent, restrained coral media accent,
layered translucent surfaces, strong typographic scale, and subtle orbital motifs.

CSS tokens define color, spacing rhythm, radii, shadows, surfaces, semantic states, and
motion curves. Light/dark themes share semantic tokens. The layout adapts at 1120, 900,
and 680 pixel breakpoints.

Core product surfaces are the command palette, collapsible navigation, bento overview,
mixed-source intake studio, searchable library, evidence-first research canvas,
synchronized video/transcript workspace, document inspector, and comparison/report
studio. Motion is disabled under `prefers-reduced-motion`. Controls have visible focus
states, labels, keyboard submission, and mobile navigation.

Source content is rendered as escaped React text. No raw HTML or unsafe Markdown is used.
