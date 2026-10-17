# Updating the portfolio and resume

Project records live in [`content/portfolio.json`](../content/portfolio.json). A GitHub Action checks every four hours for new public repositories under your account and new pushes to public repositories, including external public repositories linked to project records. When it detects one, it opens a review issue with repository links and a JSON record to complete. The initial activity baseline is seeded from current public repositories, so old commits do not create a flood of issues.

To prepare an update from an issue:

1. Check the repository history and replace the JSON example with a complete, fact-checked record. Use `operation: "add"` and `collection: "new_projects"` for a new site card. For an existing entry use `operation: "update"` and select `new_projects` or `resume_projects` as the collection.
2. Leave the exact comment `/portfolio-update` on the issue. The workflow builds the site and PDF, runs the Python, HTML, and link checks, and opens a pull request with the source and generated files from a separate branch. If a pull request for that issue is already open, edit that pull request instead of requesting another one.
3. Review and merge the pull request. Only then do GitHub Actions regenerate the Russian and English pages, PDF resume, and connected Google Doc. Render deploys the merged `main` branch.

The workflow never publishes from an unreviewed issue. The repository itself cannot establish your role, project status, or results. Work in private repositories, local work, client work, or conversations outside public GitHub is not discoverable by the daily scan; add those updates through a verified issue or by editing `content/portfolio.json` directly in a pull request.

## New project record

Copy this object into the `new_projects` array and replace every example value:

```json
{
  "operation": "add",
  "collection": "new_projects",
  "project": {
    "slug": "lowercase-project-name",
    "title_ru": "Название проекта",
    "title_en": "Project name",
    "status_ru": "Клиентский проект · демо",
    "status_en": "Client project · demo",
    "role_ru": "Моя роль: Python-разработчик.",
    "role_en": "My role: Python developer.",
    "summary_ru": "Какую задачу решает проект и что вы сделали.",
    "summary_en": "The problem the project solves and what you delivered.",
    "tech": "Python / FastAPI / PostgreSQL",
    "links": [
      {
        "label_ru": "Демо",
        "label_en": "Demo",
        "url": "https://example.com"
      },
      {
        "label_ru": "Исходный код",
        "label_en": "Source code",
        "url": "https://github.com/username/repository"
      }
    ],
    "include_in_resume": true
  }
}
```

`slug` must be unique and use lowercase letters, numbers, and hyphens. Links must use HTTPS. Remove a link you do not have. Set `include_in_resume` to `false` for work that should appear on the site but not in the resume.

## One-time Google Doc connection

The site and downloadable PDF can refresh without Google credentials. To let GitHub Actions edit the Google Doc too:

1. Create a Google Cloud service account and enable the Google Docs API for its project.
2. Create a Workload Identity Federation pool and an OIDC provider for `https://token.actions.githubusercontent.com`. Map `google.subject = assertion.sub` and `attribute.repository = assertion.repository`, and restrict the provider condition to your repository and `refs/heads/main`.
3. Grant that repository identity the `Workload Identity User` role on the service account. Share the resume document with the service account email as an editor.
4. In GitHub repository **Settings → Secrets and variables → Actions → Variables**, add:
   - `GOOGLE_WORKLOAD_IDENTITY_PROVIDER` — the full provider resource name, such as `projects/PROJECT_NUMBER/locations/global/workloadIdentityPools/POOL_ID/providers/PROVIDER_ID`.
   - `GOOGLE_SERVICE_ACCOUNT_EMAIL` — the service account email.
   - `GOOGLE_RESUME_DOC_ID` — the value between `/document/d/` and `/edit` in the document URL.
5. Under **Settings → Actions → General → Workflow permissions**, allow read and write access if the workflow cannot push its generated files.
6. Run **Actions → Refresh portfolio and resume → Run workflow** once to confirm the connection.

Workload Identity Federation uses short-lived credentials, so no service-account JSON key needs to be stored in GitHub. If the settings are absent, the workflow still refreshes the site and PDF and reports that Google Doc sync was skipped.

## What refreshes automatically

- Russian and English project cards are generated inside the marked project section.
- The Russian PDF resume is built from the maintained profile and selected project records.
- The Google Doc receives the same resume text and links when its Actions connection is configured.
- The workflow pushes generated page and PDF changes; Render then deploys the site.
