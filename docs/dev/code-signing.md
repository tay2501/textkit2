# Code Signing

## Code signing policy

Free code signing is provided by [SignPath.io](https://about.signpath.io/),
certificate by [SignPath Foundation](https://signpath.org/).

- **Committers and reviewers**: [Repository collaborators](https://github.com/tay2501/textkit2/graphs/contributors)
- **Approvers**: Repository owner ([tay2501](https://github.com/tay2501))
- **Signed artifacts**: `press.exe` inside `press-windows-x64.zip` attached to
  [GitHub Releases](https://github.com/tay2501/textkit2/releases)

### Privacy policy

This program will not transfer any information to other networked systems.
press performs **no network I/O** — all transforms run locally on clipboard,
stdin, or file input. The only files it writes are its own configuration,
dictionary, log, and hold-state files under `%APPDATA%\press\`.

---

## Release signing pipeline (maintainer notes)

The release workflow (`.github/workflows/release.yml`) contains a
`sign-windows-exe` job that submits the built executable to SignPath via
[`signpath/github-action-submit-signing-request@v2`](https://github.com/SignPath/github-action-submit-signing-request).

The job is **skipped automatically** until the SignPath Foundation
application is approved and the repository is configured. No workflow change
is needed at activation time.

### Activation checklist (after SignPath approval)

1. **Repository variables** (`Settings → Secrets and variables → Actions → Variables`):

   | Variable | Value |
   |---|---|
   | `SIGNPATH_ORGANIZATION_ID` | SignPath organization ID (from the SignPath dashboard URL) |
   | `SIGNPATH_PROJECT_SLUG` | SignPath project slug (e.g. `textkit2`) |
   | `SIGNPATH_SIGNING_POLICY_SLUG` | `release-signing` (or the policy slug configured in SignPath) |

2. **Repository secret**:

   | Secret | Value |
   |---|---|
   | `SIGNPATH_API_TOKEN` | API token of the SignPath CI user |

3. **SignPath project setup** — register this repository as the trusted build
   system (GitHub connector) and create an artifact configuration matching the
   uploaded GitHub artifact (a ZIP produced by `actions/upload-artifact`
   containing `press-windows-x64.zip`):

   ```xml
   <?xml version="1.0" encoding="utf-8"?>
   <artifact-configuration xmlns="http://signpath.io/artifact-configuration/v1">
     <zip-file>
       <zip-file path="press-windows-x64.zip">
         <directory path="press">
           <pe-file path="press.exe">
             <authenticode-sign/>
           </pe-file>
         </directory>
       </zip-file>
     </zip-file>
   </artifact-configuration>
   ```

4. Push a release tag. The `sign-windows-exe` job now runs, and
   `create-release` attaches the **signed** `press-windows-x64.zip`
   (checksums in `SHA256SUMS.txt` are computed from the signed artifact).

### SignPath Foundation eligibility (verified 2026-07-09)

- OSI-approved license (MIT) ✅ / actively maintained ✅ / released artifacts ✅
- All team members use MFA on GitHub (organization requirement)
- "Code signing policy" is published on the project home page (README) and
  this page — required wording per [signpath.org/terms](https://signpath.org/terms.html)
