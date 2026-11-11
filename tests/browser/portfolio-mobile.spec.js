import { expect, test } from "@playwright/test";

for (const path of ["/", "/en.html", "/pulseboard.html", "/knowledge-assistant.html", "/atlas-studio-demo.html"]) {
  test(`mobile layout fits the viewport: ${path}`, async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.route("https://**", (route) => route.abort());
    await page.goto(path, { waitUntil: "domcontentloaded" });
    await expect(page.locator("h1").first()).toBeVisible();
    const size = await page.evaluate(() => ({
      viewport: document.documentElement.clientWidth,
      content: document.documentElement.scrollWidth,
    }));
    expect(size.content).toBeLessThanOrEqual(size.viewport);
  });
}

test("resume links and project details are accessible on mobile", async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 });
  await page.goto("/");
  const resume = page.locator("#resume");
  await expect(resume.getByRole("link", { name: /Резюме Python · PDF/ })).toHaveAttribute(
    "href", "/downloads/Leonid_Chekin_Resume_Python_AI_FinTech.pdf",
  );
  await expect(resume.getByRole("link", { name: /Русское резюме · DOCX/ })).toHaveAttribute(
    "href", "/downloads/Leonid_Chekin_Resume_Python_AI_FinTech.docx",
  );
  const projects = page.locator("details.more-projects");
  await projects.locator("summary").click();
  await expect(projects).toHaveAttribute("open", "");
  await expect(projects.getByRole("heading", { name: "Socialera" })).toBeVisible();
});
