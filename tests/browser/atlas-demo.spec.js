import { expect, test } from "@playwright/test";

test("local showcase FAQ and appointment controls work without external services", async ({ page }) => {
  await page.goto("/atlas-studio-demo.html");

  await page.locator('[data-tab="faq"]').click();
  await page.locator("#faq-text").fill("Сколько стоит консультация?");
  await page.getByRole("button", { name: "Проверить ответ" }).click();
  await expect(page.locator("#output")).toContainText("FAQ: найден ответ");

  await page.locator('[data-tab="booking"]').click();
  const slot = page.getByRole("button", { name: "12:00" });
  await slot.click();
  await expect(page.locator("#output")).toContainText("Запись создана локально");
  await expect(page.getByRole("button", { name: /12:00 · занято/ })).toBeDisabled();
});
