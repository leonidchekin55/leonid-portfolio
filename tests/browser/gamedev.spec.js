import { expect, test } from "@playwright/test";

const games = ["fastfo-echo-range", "nuclear-sunset", "unity-coop", "pixel-2d-concept"];
for (const path of ["/", "/en.html"]) {
  test(`game projects are discoverable and clearly labeled on ${path}`, async ({ page }) => {
    await page.goto(path);
    const link = page.locator('header nav a[href="#gamedev"]');
    await expect(link).toHaveCount(1);
    await link.click();
    await expect(page).toHaveURL(/#gamedev$/);
    const section = page.locator("#gamedev");
    await expect(section.locator("article[data-game]")).toHaveCount(games.length);
    for (const game of games) {
      await expect(page.locator(`article[data-game="${game}"]`)).toHaveCount(1);
    }
    await expect(page.getByRole("heading", { name: "Nuclear Sunset", exact: true })).toHaveCount(1);
    await expect(page.getByRole("heading", { name: "FASTFO — Echo Range", exact: true })).toHaveCount(1);
    const demo = section.locator('[data-game="fastfo-echo-range"]');
    await expect(demo.locator('a[href="https://fastfo-echo-range.leonidchekin55.chatgpt.site/"]')).toHaveCount(1);
    await demo.locator("summary").click();
    await expect(demo.locator("details")).toHaveAttribute("open", "");
    await expect(demo.locator(".details")).toBeVisible();
    await expect(section.locator('[data-game="nuclear-sunset"] a, [data-game="unity-coop"] a, [data-game="pixel-2d-concept"] a')).toHaveCount(0);
  });

  test(`game navigation fits a narrow screen on ${path}`, async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 740 });
    await page.goto(path);
    const nav = page.locator("header nav");
    const fits = await nav.evaluate(el => el.scrollWidth <= el.clientWidth + 1);
    expect(fits).toBeTruthy();
    await nav.locator('a[href="#gamedev"]').click();
    await expect(page).toHaveURL(/#gamedev$/);
  });
}

for (const [home, report, alternate, lang] of [
  ["/", "gamedev-qa.html", "gamedev-qa-en.html", "ru"],
  ["/en.html", "gamedev-qa-en.html", "gamedev-qa.html", "en"],
]) {
  test(`QA evidence is accessible, localized and distinguishes observations from test plans (${lang})`, async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto(home);
    const game = page.locator('[data-game="fastfo-echo-range"]');
    await game.locator(`a[href="${report}"]`).click();
    await expect(page).toHaveURL(new RegExp(report.replace(".", "\\.") + "$"));
    await expect(page.locator("html")).toHaveAttribute("lang", lang);
    const rows = page.locator("table tbody tr");
    await expect(rows).toHaveCount(10);
    await expect(rows.filter({ hasText: lang === "ru" ? "Наблюдалось:" : "Observed:" })).toHaveCount(3);
    await expect(rows.filter({ hasText: lang === "ru" ? "Не проверено" : "Not run" })).toHaveCount(7);
    await expect(page.locator("#defect + p")).toContainText("HTTP 503");
    await expect(page.locator('a[href="pulseboard.html#demo-video"]')).toHaveCount(1);
    await page.locator(`header a[href="${alternate}"]`).click();
    await expect(page.locator("html")).toHaveAttribute("lang", lang === "ru" ? "en" : "ru");
  });
}
