# No-cost Muse Glimmer inference route research

**Checked:** October 29, 2026
**Purpose:** Find a Muse Glimmer route that can be used without spending money, then separate verified free use from hackathon bonus eligibility. This records public provider terms and model listings only; no account was created and no inference request was sent.

## Findings

| Route | Exact model and published cost | Money-safety evidence | Event fit and limitation | Assessment |
| --- | --- | --- | --- | --- |
| NVIDIA API Catalog (current app route) | `meta/muse-glimmer-30b`; NVIDIA's page offers a free prototype endpoint. | Trial/prototype use is rate-limited; our most recent health request timed out. Keep the existing no-paid-fallback behavior. | NVIDIA is not among the event listing's named inference partners, so do not claim the open-weight bonus without a rule or organizer confirming eligibility. | Keep as the current configured route; availability is unreliable. |
| Requesty Free (new candidate) | `nvidia/muse-glimmer-30b`; OpenAI-compatible base URL `https://router.requesty.ai/v1`; Requesty lists $0 and 200 requests/day for free models. | Requesty's pricing and terms say no payment method is required on the free plan. Do not buy credits, enable Auto Recharge, or switch to Pay-as-you-go. | The model page says it is served by NVIDIA, so this is a gateway to the same upstream provider, not a demonstrated fix for NVIDIA timeouts. Requesty is not one of the named hackathon partners. Its free-plan terms allow use of requests to train/improve its routing and related models; the catalog also marks this model/provider as retaining data and using it for training. Send public issue/source material only. | Strongest newly found $0 gateway candidate for a later, explicitly configured trial; not verified for the bonus and not proven more reliable. |
| Hugging Face Inference Providers | Muse Glimmer is listed through Together and DeepInfra, with published per-token prices. | Free users receive a small monthly credit allowance; calls draw down that allowance. It is a limited promotional allowance, not a permanently zero-priced endpoint. | Not established as a named event partner route; hosted provider choice and bonus eligibility still need rules confirmation. | Not a preferred no-money route. |
| OpenRouter | Muse Glimmer is listed at paid per-token rates; it is absent from the free-model set checked. | A `:free` catalog model does not make this exact Meta model free. | Not a named event partner. | Exclude for strict $0 use. |
| Fireworks (event partner) | Current Muse Glimmer catalog lists on-demand deployment; serverless is unsupported, with GPU-second billing. | The current co-host page offers $100 credits only to selected participants. Fireworks says use pauses at zero when Auto Reload is off and accounts without a payment method are suspended at depletion. Confirm this account's credit balance; do not add a payment method or enable reload. | Named event partner, but accepted rules still control whether this deployment qualifies for the open-weight bonus. | Best partner-hosted candidate if the event credit is actually active; otherwise it can spend money. |
| Modal (event partner) | Muse Glimmer on a dedicated endpoint; billed by usage. | Modal's GPU guide requires a valid payment method. | Named event partner; no-cost credit does not itself prove a hard no-charge ceiling. | Exclude under the user's no-money constraint unless verified account controls change. |
| Baseten (event partner) | Muse Glimmer can be deployed on hosted infrastructure; deployment consumes compute. | The current co-host page offers $100 credits and 2M TPM rate limits to select participants. Baseten also advertises starter credits, but this account's grant, payment-method requirement, and hard stop are unverified. | Named event partner; accepted rules and actual deployment type still need confirmation. | Worth checking only if event credits are active and billing can be safely bounded at zero. |
| Self-host from GitHub/Meta weights | Meta's official cookbook supports local runtimes such as llama.cpp and Ollama; the quantized Glimmer files are about 17–20 GB. | No provider bill, but requires suitable local hardware. | Participant hardware may satisfy the event's open-weight wording, subject to exact rules. | Not practical on the current machine; do not treat a GitHub repo as hosted free inference. |

## Recommendation

Keep NVIDIA as the current app route until there is a deliberate, no-cost change. Requesty is the best new candidate for an OpenAI-compatible, exact-model $0 route: it explicitly advertises 200 free requests/day without a payment method. However, it forwards to NVIDIA, so there is no evidence it will solve the observed timeouts. A future trial should use only public issue/source text, remain on Requesty's free plan, and stop at the free-tier limit.

Requesty is not shown as an event inference partner. The route may support the general Meta-model contribution, but it is not verified for the event's open-weight bonus. Continue to omit that bonus claim until the accepted rules or an organizer confirms the exact provider/model route.

## Primary sources checked

- [NVIDIA Muse Glimmer model page](https://build.nvidia.com/meta/muse-glimmer-30b) — free prototype endpoint and hosted deployment options.
- [Meta Muse Glimmer deployment docs](https://dev.meta.ai/docs/muse-glimmer/deploy) — supported self-host and hosted-provider paths, model requirements.
- [Meta's Muse Glimmer cookbook on GitHub](https://github.com/meta-models/meta-oss-cookbook) — first-party self-hosted runtimes; this is a local-inference route, not a free hosted API.
- [Requesty Muse Glimmer listing](https://www.requesty.ai/models/nvidia/muse-glimmer-30b) — model ID, upstream provider, price, data retention and training metadata.
- [Requesty free-model listing](https://www.requesty.ai/models/free) and [pricing](https://www.requesty.ai/pricing) — $0 models, 200 requests/day, no card requirement.
- [Requesty Terms of Service](https://www.requesty.ai/terms) — free-plan conditions and use of free-plan content.
- [Hugging Face Inference Providers pricing](https://huggingface.co/docs/inference-providers/pricing) and [supported models](https://huggingface.co/inference/models) — free-user allowance and Glimmer provider prices.
- [OpenRouter Muse Glimmer listing](https://openrouter.ai/meta/muse-glimmer-30b) and [free-model catalog](https://openrouter.ai/collections/free-models/) — paid Glimmer listing versus free catalog.
- [Cerebral Valley's current event listing](https://events.cerebralvalley.ai/e/meta-ai-developer-hackathon) — lists $100 in Baseten, Modal, and Fireworks credits for select participants, with 2M TPM listed for Baseten.
- [Fireworks Glimmer model page](https://fireworks.ai/models/fireworks/muse-glimmer-30b) and [credit depletion FAQ](https://docs.fireworks.ai/faq-new/billing-pricing/what-happens-when-i-finish-my-1-dollar-credit) — on-demand billing and credit safeguards.
- [Modal Glimmer model page](https://modal.com/library/meta/muse-glimmer-30b-bf16) and [GPU guide](https://modal.com/docs/guide/gpu) — dedicated inference and payment-method requirement for GPUs.
- [Baseten Glimmer model page](https://www.baseten.co/library/muse-glimmer-30b/) and [pricing](https://www.baseten.co/pricing/) — deployment and starter-credit information.
- [Meta Global AI Developer Hackathon page](https://dev.meta.ai/events/global-hackathon) and [Cerebral Valley's current event listing](https://events.cerebralvalley.ai/e/meta-ai-developer-hackathon) — event entry point and current named partners/credits. The full accepted Official Rules still need to be checked for the bonus.
