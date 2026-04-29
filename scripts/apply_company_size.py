#!/usr/bin/env python3
"""
One-shot script: stamp companySize onto entries in inspiration.json where we
have confident data. Entries not in the map are left untouched (no companySize key).

Run from project root:
    python3 scripts/apply_company_size.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JSON_PATH = ROOT / "data" / "inspiration.json"
JS_PATH   = ROOT / "data" / "inspiration.js"

# Keys are entry IDs from inspiration.json; values are "Startup" | "MidMarket" | "Enterprise"
CLASSIFICATIONS = {
    # ───── ENTERPRISE ─────
    "stripe-figma":                                         "Enterprise",
    "shopify-shopify-com":                                  "Enterprise",
    "shopify-winter-2024-shopify-com":                      "Enterprise",
    "shopify-editions-summer-25-shopify-com":               "Enterprise",
    "coinbase-coinbase-com":                                "Enterprise",
    "figma-figma-com":                                      "Enterprise",
    "robinhood-robinhood-com":                              "Enterprise",
    "roblox-corp-roblox-com":                               "Enterprise",
    "whatsapp-whatsapp-com":                                "Enterprise",
    "webex-cisco-webex-com":                                "Enterprise",
    "hashicorp-hashicorp-com":                              "Enterprise",
    "culture-amp-cultureamp-com":                           "Enterprise",
    "sprout-social-sproutsocial-com":                       "Enterprise",
    "monday-com-monday-com":                                "Enterprise",
    "zendesk-zendesk-com":                                  "Enterprise",
    "gong-gong-io":                                         "Enterprise",
    "gong-webstacks-figma":                                 "Enterprise",
    "patreon-patreon-com":                                  "Enterprise",
    "cash-app-cash-app":                                    "Enterprise",
    "checkout-com-checkout-com":                            "Enterprise",
    "databricks-databricks-com":                            "Enterprise",
    "revolut-revolut-com":                                  "Enterprise",
    "docusign-brand-brand-docusign-com":                    "Enterprise",
    "airtable-figma":                                       "Enterprise",
    "okta-figma":                                           "Enterprise",
    "lattice-figma":                                        "Enterprise",
    "handshake-figma":                                      "Enterprise",
    "zapier-figma":                                         "Enterprise",
    "palantir-figma":                                       "Enterprise",
    "braze-figma":                                          "Enterprise",
    "miro-figma":                                           "Enterprise",
    "paypal-figma":                                         "Enterprise",
    "paypal-business-figma":                                "Enterprise",
    "mongodb-figma":                                        "Enterprise",
    "wiz-figma":                                            "Enterprise",
    "cloudflare-workers-figma":                             "Enterprise",
    "siriusxm-media-siriusxmmedia-com":                     "Enterprise",
    "tripadvisor-brandswetravelwith-tripadvisor-com":        "Enterprise",
    "block-block-xyz":                                      "Enterprise",
    "retool-retool-com":                                    "Enterprise",
    "retool-rebranded-oct-2024-retool-com":                 "Enterprise",
    "calendly-figma":                                       "Enterprise",
    "launchdarkly-launchdarkly-com":                        "Enterprise",
    "clickup-clickup-com":                                  "Enterprise",
    "wise-wise-com":                                        "Enterprise",
    "wise-business-figma":                                  "Enterprise",
    "justworks-figma":                                      "Enterprise",
    "deel-deel-com":                                        "Enterprise",
    "scale-scale-com":                                      "Enterprise",
    "bird-figma":                                           "Enterprise",
    "hinge-hinge-co":                                       "Enterprise",
    "ramp-ramp-com":                                        "Enterprise",
    "ramp-travel-ramp-com":                                 "Enterprise",
    "qonto-qonto-com":                                      "Enterprise",
    "mixpanel-mixpanel-com":                                "Enterprise",
    "oura-ouraring-com":                                    "Enterprise",
    "nuro-nuro-ai":                                         "Enterprise",
    "lowe-s-innovation-lab-lowesinnovationlabs-com":         "Enterprise",
    "drata-drata-com":                                      "Enterprise",
    "apollo-apollo-io":                                     "Enterprise",
    "vanta-figma":                                          "Enterprise",
    "cloudbees-cloudbees-com":                              "Enterprise",
    "deezer-figma":                                         "Enterprise",
    "vercel-vercel-com":                                    "Enterprise",
    "replit-replit-com":                                    "Enterprise",
    "linktree-figma":                                       "Enterprise",
    "ada-figma":                                            "Enterprise",
    "runway-runwayml-com":                                  "Enterprise",
    "mercury-mercury-com":                                  "Enterprise",
    "spendesk-spendesk-com":                                "Enterprise",
    "stash-stash-com":                                      "Enterprise",
    "mural-figma":                                          "Enterprise",
    "jasper-jasper-ai":                                     "Enterprise",
    "framer-framer-com":                                    "Enterprise",
    "customer-io-customer-io":                              "Enterprise",
    "windsurf-windsurf-com":                                "Enterprise",
    "dovetail-dovetail-com":                                "Enterprise",
    "watershed-watershed-com":                              "Enterprise",
    "front-figma":                                          "Enterprise",
    "mistral-mistral-ai":                                   "Enterprise",
    "cursor-figma":                                         "Enterprise",
    "intercom-intercom-com":                                "Enterprise",
    "hotjar-hotjar-com":                                    "Enterprise",
    "greenhouse-greenhouse-com":                            "Enterprise",
    "evernote-evernote-com":                                "Enterprise",
    "carta-carta-com":                                      "Enterprise",
    "angellist-angellist-com":                              "Enterprise",
    "zoox-figma":                                           "Enterprise",
    "going-figma":                                          "Enterprise",
    "cohere-figma":                                         "Enterprise",
    # ───── MIDMARKET ─────
    "linear-linear-app":                                    "MidMarket",
    "incident-io-incident-io":                              "MidMarket",
    "superhuman-figma":                                     "MidMarket",
    "sprig-sprig-com":                                      "MidMarket",
    "lyssna-lyssna-com":                                    "MidMarket",
    "openphone-openphone-com":                              "MidMarket",
    "whimsical-whimsical-com":                              "MidMarket",
    "gitbook-gitbook-com":                                  "MidMarket",
    "harvest-getharvest-com":                               "MidMarket",
    "warp-warp-dev":                                        "MidMarket",
    "sana-labs-figma":                                      "MidMarket",
    "cresta-cresta-com":                                    "MidMarket",
    "clearbit-clearbit-com":                                "MidMarket",
    "v7-labs-v7labs-com":                                   "MidMarket",
    "v7-figma":                                             "MidMarket",
    "arc-search-arc-net":                                   "MidMarket",
    "eppo-geteppo-com":                                     "MidMarket",
    "user-interviews-userinterviews-com":                   "MidMarket",
    "pipe-technologies-pipe-com":                           "MidMarket",
    "airtasker-figma":                                      "MidMarket",
    "clay-figma":                                           "MidMarket",
    "toggl-figma":                                          "MidMarket",
    "zeroheight-figma":                                     "MidMarket",
    "bolt-bolt-com":                                        "MidMarket",
    "otter-ai-otter-ai":                                    "MidMarket",
    "public-figma":                                         "MidMarket",
    "better-stack-betterstack-com":                         "MidMarket",
    "clerk-clerk-com":                                      "MidMarket",
    "neon-neon-tech":                                       "MidMarket",
    "perplexity-perplexity-ai":                             "MidMarket",
    "langchain-langchain-com":                              "MidMarket",
    "sanity-figma":                                         "MidMarket",
    # ───── STARTUP ─────
    "era-era-app":                                          "Startup",
    "david-ai-withdavid-ai":                                "Startup",
    "peec-ai-peec-ai":                                      "Startup",
    "solidroad-solidroad-com":                              "Startup",
    "radial-meetradial-com":                                "Startup",
    "quin-heyquin-io":                                      "Startup",
    "multi-multi-app":                                      "Startup",
    "wist-wist-chat":                                       "Startup",
    "giga-ai-giga-ai":                                      "Startup",
    "heynds-heynds-com":                                    "Startup",
    "wrangle-wrangle-ai":                                   "Startup",
    "gradient-labs-figma":                                  "Startup",
    "factory-ai-figma":                                     "Startup",
    "relume-relume-io":                                     "Startup",
    "outseta-figma":                                        "Startup",
    "legora-figma":                                         "Startup",
    "reducto-figma":                                        "Startup",
    "speakeasy-figma":                                      "Startup",
    "cartesia-figma":                                       "Startup",
    "cartesia-sonic-cartesia-ai":                           "Startup",
    "basedash-figma":                                       "Startup",
    "mymind-mymind-com":                                    "Startup",
    "tailwind-tailwindui-com":                              "Startup",
    "folk-folk-app":                                        "Startup",
    "raycast-raycast-com":                                  "Startup",
    "liveblock-liveblocks-io":                              "Startup",
    "strut-strut-so":                                       "Startup",
    "normative-figma":                                      "Startup",
    "duna-figma":                                           "Startup",
    "deepnote-figma":                                       "Startup",
}


def main():
    data = json.loads(JSON_PATH.read_text())

    applied = 0
    skipped_id = []
    for entry in data["entries"]:
        eid = entry["id"]
        if eid in CLASSIFICATIONS:
            entry["companySize"] = [CLASSIFICATIONS[eid]]
            applied += 1

    # Validate: every id in CLASSIFICATIONS should exist in entries
    entry_ids = {e["id"] for e in data["entries"]}
    for eid in CLASSIFICATIONS:
        if eid not in entry_ids:
            skipped_id.append(eid)

    # Write JSON
    JSON_PATH.write_text(json.dumps(data, indent=2))

    # Regenerate inspiration.js shim
    js = "// Auto-generated. Same data as inspiration.json, exposed as window.INSPIRATION_DATA.\n"
    js += "window.INSPIRATION_DATA = " + json.dumps(data, indent=2) + ";\n"
    JS_PATH.write_text(js)

    print(f"Applied companySize to {applied} entries.")
    if skipped_id:
        print(f"WARNING — {len(skipped_id)} IDs in map not found in JSON (may need update):")
        for sid in skipped_id:
            print(f"  {sid}")
    else:
        print("All IDs matched.")


if __name__ == "__main__":
    main()
