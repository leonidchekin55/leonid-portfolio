import { expect, test } from "@playwright/test";

for (const [path, resumePdf] of [
  ["/", "/downloads/Leonid_Chekin_Resume_Python_AI_FinTech.pdf"],
  ["/en.html", "/downloads/Leonid_Chekin_Resume_English_ATS.pdf"],
]) {
  test(`public resume is accessible on ${path}`, async ({ page, request }) => {
    await page.goto(path);
    const resume = page.locator("#resume");
    await expect(resume.locator('a[href^="https://docs.google.com/document/"]')).toHaveCount(0);
    await expect(resume.locator(`a[href="${resumePdf}"]`)).toHaveCount(1);
    const response = await request.get(resumePdf);
    expect(response.ok()).toBeTruthy();
    expect(response.headers()["content-type"]).toContain("application/pdf");
  });
}
