# Stakeholder Q&A

**Why Copilot?** It aligns with the client's Microsoft direction and can support governed agents/actions, subject to licensing and security validation. The current MVP is not Copilot.

**Why not ChatGPT?** Product choice should follow approved data boundaries, integration, licensing, evaluation and governance—not brand preference. The provider boundary keeps the workflow testable.

**How is learner data protected?** The demo uses synthetic data, minimises fields, masks basic PII patterns locally and sends nothing externally. Production needs approved systems, access/retention controls and stronger de-identification.

**Will AI replace staff?** No. It prepares evidence and a draft; staff interpret, edit, approve and own release.

**How accurate is the report?** Calculations are tested against a golden dataset; themes are indicators. Report accuracy must be sampled against source evidence and stakeholder-reviewed.

**How are hallucinations prevented?** Local output is deterministic and built only from metrics/themes/evidence. Future prompts restrict sources and require insufficiency statements, but human verification remains necessary.

**How do we verify recommendations?** Each must connect to observed evidence; reviewers assess feasibility and define a measure for the next delivery.

**Can it connect directly to Qualtrics?** Not currently. The MVP accepts compatible CSV; a read-only approved API/connector is planned.

**Can reports be automatically sent?** No—and the MVP deliberately avoids that. Future distribution must sit after explicit approval.

**Can it support multiple courses?** The dataset can contain multiple courses, but the current aggregate view does not provide course filtering. That is a V2 requirement.

**Can it compare historical results?** Not safely yet. History is illustrative; question/scales/cohorts must be comparable before trend claims.

**What happens when AI is wrong?** Evidence remains visible; reviewers edit/reject the draft, record approval only after correction, and the team updates tests/rules.

**Can Learning Futures edit reports?** Yes, the full draft is editable before approval.

**How scalable is it?** Modules are replaceable and adequate for prototype datasets. Production scale, concurrency, identity, monitoring and retention are not yet validated.

**What is prototype versus future?** CSV, local validation/masking/analytics, reports, review and export work now. Live Qualtrics, Copilot, Power Platform, Power BI, authentication and distribution are future.

