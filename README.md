# NFIP Claim Automation

Automates NFIP flood insurance claim processing for Fountain Group Adjusters.

## What it does

- Parses loss notices (NOL) in 4 PDF formats and 2 XML schemas
- Generates Adjuster's Preliminary Report PDF (FEMA form + photo report merged)
- Generates Prelim XML and Final XML in NFIP `<AdjusterData>` format
- Auto-uploads all documents to the Venue claims portal
- Runs on a DigitalOcean droplet, accessible from any browser including phone

## Stack

- **Backend:** Python / Flask
- **AI parsing:** Claude Sonnet (extract) → Claude Haiku (verify)
- **PDF generation:** ReportLab
- **Portal automation:** Playwright
- **File storage:** Dropbox

## Cost

~$0.023 per claim in API costs (Sonnet + Haiku).

## Supported NOL formats

- NFIP Direct (PDF)
- Selective (PDF)
- National General (PDF)
- ASI / Progressive (PDF)
- Wright National (XML)
- NFIP Direct (XML)

## Project structure

```
nfip-automation/
├── app/
│   ├── parsers/        # NOL parsers for each format
│   ├── generators/     # PDF and XML generators
│   ├── portal/         # Venue portal Playwright automation
│   └── api/            # Flask routes
├── docs/
│   └── specs/          # Design specs
├── config/             # Adjuster config (FCN, signature, credentials)
└── tests/
```
