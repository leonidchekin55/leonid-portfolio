# Updating the portfolio and resume

Project records live in [`content/portfolio.json`](../content/portfolio.json). Add each new project once under `new_projects`, then commit and push that file to `main`. GitHub Actions will validate the entry, add it to both language versions, rebuild the Russian PDF resume, synchronize the Google Doc (after one-time setup below), and push the generated files. Render deploys the site from that push.

Only enter facts you can support. The generator does not infer your role, results, or technology from a project name.

## Add a project

Copy this object into the `new_projects` array and replace every example value:

```json
{
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
```

`slug` must be unique and use lowercase letters, numbers, and hyphens. Links must use HTTPS. Remove a link you do not have. Set `include_in_resume` to `false` for work that should appear on the site but not in the resume.

## One-time Google Doc connection

The site and downloadable PDF can refresh without Google credentials. To let GitHub Actions edit the Google Doc too:

1. Create a Google Cloud service account and enable the Google Docs API for its project.
2. Create a JSON key for that service account.
3. Share the resume document with the service account email as an editor.
4. In GitHub repository **Settings → Secrets and variables → Actions**, add the JSON key as secret `GOOGLE_SERVICE_ACCOUNT_JSON` and add `GOOGLE_RESUME_DOC_ID` as a repository variable. The document ID is the value between `/document/d/` and `/edit` in its URL.
5. Under **Settings → Actions → General → Workflow permissions**, allow read and write access if the workflow cannot push its generated files.
6. Run **Actions → Refresh portfolio and resume → Run workflow** once to confirm the connection.

Keep the service account key only in the GitHub Actions secret; never commit it to this repository. If the two settings are absent, the workflow still refreshes the site and PDF and reports that Google Doc sync was skipped.

## What refreshes automatically

- Russian and English project cards are generated inside the marked project section.
- The Russian PDF resume is built from the maintained profile and selected project records.
- The Google Doc receives the same resume text and links when its Actions connection is configured.
- The workflow pushes generated page and PDF changes; Render then deploys the site.
