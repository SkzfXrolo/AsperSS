# Security Policy

## Reporting a Vulnerability

If you discover a security issue in Argus Projects, report it privately:

- Primary contact: `security@argusprojects.com` (TBD, provision mailbox)
- Temporary fallback: project maintainers via private channel
- Please do **not** open public GitHub issues for exploitable vulnerabilities.

Include, when possible:

- Affected component (`web_app`, scanner, plugin, infra)
- Reproduction steps (non-destructive)
- Impact assessment
- Suggested mitigation

## Disclosure Timeline

- **Acknowledgement:** within 72 hours
- **Triage and severity:** within 7 days
- **Fix target:**
  - Critical: 7 days
  - High: 14 days
  - Medium: 30 days
  - Low: 60-90 days
- **Public advisory:** after fix deployment and validation, coordinated with reporter

## Scope

In scope:

- `web_app` (Flask app, auth, API, templates, static JS)
- Scanner update and token flows
- Minecraft plugin API integrations
- Build/release artifacts and CI workflows

## Out of Scope

- Social engineering, phishing, physical access
- Denial-of-service using volumetric network attacks
- Vulnerabilities requiring compromised maintainer machine
- Third-party services outside Argus control (unless misconfigured by Argus)

## Safe Harbor

Good-faith security research is authorized if you:

- Avoid privacy violations and data exfiltration
- Avoid destructive actions (drop, overwrite, corruption)
- Stop once meaningful proof is obtained
- Report findings responsibly and privately

Argus will not pursue legal action against compliant good-faith researchers.

## Hall of Fame

Argus may acknowledge responsible reporters (with permission) in a future Hall of Fame section.
