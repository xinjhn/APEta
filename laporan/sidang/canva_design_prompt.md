# Canva Design Prompt — Sidang TA Deck Restyle

Paste-ready prompt for Canva AI / Magic Design, also usable as the styling brief when restyling the imported .pptx.

---

Design a 16:9 presentation template for an undergraduate thesis defense (sidang tugas akhir) in computer science at Politeknik Negeri Bandung. Topic: an empirical benchmark comparing REST API vs GraphQL performance. Audience: academic examiners. All slide text is in Bahasa Indonesia — keep it verbatim, never paraphrase or translate.

STYLE: minimalist academic "lab report" aesthetic — editorial, typography-driven, zero decoration. Think research journal meets IBM design language. Elegance comes from restraint, whitespace, and a strict grid — not ornament.

COLORS (exact):
- Background: #FAF9F6 (warm off-white)
- Primary text: #1C1B1A (near-black)
- Muted labels, captions, sources: #6B675F
- Hairline rules and dividers: #D8D4CC
- Data accents ONLY: #3B6FB5 blue = REST, #C2255C magenta = GraphQL. These two colors are semantic (they identify the protocols in every chart) — never use them decoratively, and never swap them.

TYPOGRAPHY: IBM Plex Sans — headlines semibold 32–40pt, body 14–16pt. IBM Plex Mono for small uppercase kickers and labels, 10–11pt with wide letter-spacing. Everything left-aligned except the title slide. Strong size contrast between headline and body; no more than 3 text sizes per slide.

LAYOUT SYSTEM (every content slide):
1. Small mono uppercase kicker, top-left (section name · chapter reference)
2. One full-width bold statement headline — the slide's single takeaway, max 2 lines
3. Content zone: one chart, one table, or max 5 short bullets — never more than one content block type per slide
4. Thin footer: caption/source note left in muted gray, page number right

SLIDE MASTERS NEEDED:
1. Title slide (centered, generous vertical whitespace)
2. Section divider (kicker + one large statement, mostly empty)
3. Statement + full-width chart
4. Two-column comparison (REST left/blue, GraphQL right/magenta)
5. Table slide (hairline rules only, no filled cells)
6. Verbatim blockquote slide (for research questions and hypotheses quoted word-for-word)
7. Appendix navigation slide

AVOID: gradients, drop shadows, stock photos, icons, decorative shapes or blobs, accent bars or stripes, rounded cards, filled boxes behind text, centered body text, more than one accent color per slide, cropped or recolored chart images.

---

## Notes

- Palette and fonts above are extracted from `Sidang_TA_APE_JeihanIlham_v2.pptx` (theme + slide XML) — exact.
- REST blue / GraphQL magenta hexes are approximated from the rendered charts (colors are baked into the chart images); close enough for template harmony.
- IBM Plex Sans and IBM Plex Mono should be in Canva's font library; if missing on your plan, closest pairs: Inter or Archivo (sans) + Space Mono (mono).
- Chart images must be placed as-is — any Canva recolor/filter would corrupt the REST-vs-GraphQL color semantics across ~15 result slides.
