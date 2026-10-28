# Citeproof Editorial Interface Design

**Status:** Approved direction; written spec for review  
**Product:** Citeproof, a local-first Python issue investigation workbench  
**Framework constraint:** Keep Streamlit and use `streamlit-shadcn-ui` selectively.

## Goal

Make the current investigation flow feel calm, precise, and premium while keeping source evidence and uncertainty easy to inspect. The interface should make the core sequence obvious: choose an issue, investigate it, inspect each agent’s citations, then review the cross-check and small evaluation.

## Visual direction

Use an editorial evidence-workbench style: warm ivory surfaces, deep ink text, and a restrained muted-brass accent. Use a distinctive serif treatment for the product title and a clean sans-serif for controls and explanations. Render source paths, line references, and quoted code in a legible monospace style. Keep the page airy and ordered, with thin separators and a small number of purposeful cards rather than decorative panels.

Use the existing Streamlit theme and Shadcn components where they improve hierarchy. Keep native Streamlit inputs and status controls to preserve reliable state and accessible labels. Avoid remote font or image dependencies and avoid animation so the demo remains stable offline and during a live run.

## Page structure

1. **Compact identity header:** Citeproof name, one-line purpose, and a quiet “two independent investigators” status mark.
2. **Issue brief:** Curated case selection and repository context are easy to scan; issue title and report remain the primary input.
3. **Run action and progress:** One clear primary action. Provider, model, privacy, and cost notes remain available in a compact disclosure. Live tool activity stays visible while requests run.
4. **Evidence review:** Two equally weighted investigator panels show claims, explanations, checked citations, and rejected quotes with their reasons.
5. **Cross-check and evaluation:** Present verified overlap separately from diagnosis correctness. Keep localization metrics labeled as changed-file proxies and preserve incomplete-run warnings.

## Interaction and accessibility

- Preserve all current functionality, including curated/manual input, pinned-checkout enforcement, cached demo loading, run reports, and explicit incomplete states.
- Use clear labels, visible keyboard focus, readable contrast, and layouts that stack cleanly on narrow screens.
- Give long issue text and file paths safe wrapping; keep code excerpts horizontally manageable.
- Avoid implying that citation validity, agent agreement, or a localization hit proves a diagnosis.

## Implementation boundary

Limit the UI pass to Streamlit theme/layout/presentation code and its focused documentation. Do not change model prompts, repository tools, citation rules, scoring, provider configuration, or evaluation labels as part of the visual refresh.

## Acceptance checks

- The curated and manual issue flows still render and retain their existing behavior.
- Cached Click #3449 can be loaded without an inference call.
- Investigator progress, verified and rejected citations, cross-check status, and evaluation caveats remain visible.
- The app renders without Streamlit exceptions at desktop and narrow viewport widths.
- The page reads as a cohesive editorial workbench rather than a default Streamlit dashboard.
