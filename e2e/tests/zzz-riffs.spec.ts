import { expect, test, type Page } from "@playwright/test";
import fs from "node:fs";
import path from "node:path";

// Riffs y aprendizaje de la canción que dejan z-canciones y zz-acompanamiento (misma base).
// El worker real no participa: se lo simula contra la API con un resultado de separación grabado.
test.describe.configure({ mode: "serial" });

const CAPTURAS = path.resolve(
  import.meta.dirname,
  "../../docs/fases/fase-5/capturas",
);
const TOKEN_UI = process.env.E2E_API_TOKEN ?? "e2e-token-de-prueba";
const TOKEN_WORKER =
  process.env.E2E_WORKER_TOKEN ?? "e2e-worker-token-de-prueba";
const TITULO = "Canción de prueba";
const headersUi = { Authorization: `Bearer ${TOKEN_UI}` };
const headersWorker = { Authorization: `Bearer ${TOKEN_WORKER}` };

// A3 (cuerda 3, traste 2), D4 en la cuerda 2 con baja confianza, y un tercer acorde largo.
const NOTAS = [
  { t: 0, dur: 1, string: 3, fret: 2, confidence: 0.9 },
  { t: 1, dur: 1, string: 2, fret: 0, confidence: 0.4 },
  { t: 2, dur: 2, string: 2, fret: 3, confidence: 0.8 },
];

const capturar = (page: Page, nombre: string) =>
  page.screenshot({ path: path.join(CAPTURAS, `${nombre}.png`) });

// El riff queda debajo del panel de acompañamiento: se captura el bloque, no la ventana.
const capturarRiff = (page: Page, nombre: string) =>
  page
    .getByRole("region", { name: "Riff" })
    .screenshot({ path: path.join(CAPTURAS, `${nombre}.png`) });

test.beforeAll(() => {
  fs.mkdirSync(CAPTURAS, { recursive: true });
});

async function abrirCancion(page: Page) {
  await page.goto("/explorar");
  await page.getByRole("link", { name: TITULO }).click();
  await expect(
    page.getByRole("heading", { name: TITULO, exact: true }),
  ).toBeVisible();
}

const riff = (page: Page) => page.getByRole("region", { name: "Riff" });

test("1. el worker (simulado) entrega la separación con un riff", async ({
  request,
}) => {
  const claim = await request.post("/api/v1/jobs/claim", {
    data: { worker_id: "e2e" },
    headers: headersWorker,
  });
  expect(claim.status(), "tiene que haber una separación en cola").toBe(200);
  const job = await claim.json();
  expect(job.job_type).toBe("separation");
  expect(job.fingering_preferences).toEqual({ positions: {}, zones: {} });

  const riffs = { intro: { bpm: job.chart.bpm, events: NOTAS } };
  const result = await request.post(`/api/v1/jobs/${job.job_id}/result`, {
    data: { worker_id: "e2e", riffs },
    headers: headersWorker,
  });
  expect(result.status(), await result.text()).toBe(200);
});

test("2. la sección muestra el riff con tab, mástil y la leyenda de baja confianza", async ({
  page,
}) => {
  await abrirCancion(page);
  const bloque = riff(page);
  await expect(bloque.getByRole("img", { name: /Tablatura/ })).toBeVisible();
  await expect(bloque.getByRole("img", { name: /Mástil/ })).toBeVisible();
  await expect(
    bloque.locator('[data-role="note"][data-confidence="low"]'),
  ).toHaveCount(1);
  await expect(bloque.getByText(/poco seguro/i)).toBeVisible();
  await expect(page.getByText("Riff editado por vos")).toHaveCount(0);
  await capturarRiff(page, "riff-con-baja-confianza");
});

test("3. corregir la cuerda de una nota guarda el riff y aprende la digitación", async ({
  page,
  request,
}) => {
  const antes = await request.get("/api/v1/preferences/fingering", {
    headers: headersUi,
  });
  expect(await antes.json()).toEqual({ positions: {}, zones: {} });

  await abrirCancion(page);
  await page.getByRole("button", { name: "Editar tab" }).click();
  const editor = page.getByRole("region", { name: /Editar riff/ });
  await editor
    .getByRole("button", { name: "Tiempo 0, cuerda 3, traste 2" })
    .click();
  const controles = editor.getByRole("group", { name: "Nota elegida" });
  await controles
    .locator("label", { hasText: /^Cuerda/ })
    .locator("select")
    .selectOption("4"); // misma altura: cuerda 4, traste 7
  await editor.screenshot({ path: path.join(CAPTURAS, "riff-editando.png") });
  await editor.getByRole("button", { name: "Guardar" }).click();

  await expect(page.getByText("Riff editado por vos")).toBeVisible();
  await expect(
    riff(page).getByRole("img", { name: /Tablatura/ }),
  ).toBeVisible();

  const despues = await request.get("/api/v1/preferences/fingering", {
    headers: headersUi,
  });
  const aprendido = await despues.json();
  expect(aprendido.positions["57"]).toHaveProperty(["4,7"]);
  await page.reload();
  await expect(page.getByText("Riff editado por vos")).toBeVisible();
  await capturarRiff(page, "riff-editado");
});

test("4. elegir otra forma de un acorde y guardar la aprende", async ({
  page,
  request,
}) => {
  const antes = await request.get("/api/v1/preferences/chord-shapes", {
    headers: headersUi,
  });
  expect(await antes.json()).toEqual({});

  await abrirCancion(page);
  await page.getByRole("button", { name: "Editar sección" }).click();
  await page.getByRole("button", { name: /Elegir forma del acorde 1/ }).click();
  const formas = page.getByRole("group", { name: "Formas del acorde 1" });
  const otra = formas.getByRole("button", { pressed: false }).first();
  await expect(otra).toBeVisible();
  await capturar(page, "acorde-formas");
  await otra.click();
  await page.getByRole("button", { name: "Guardar" }).click();
  await expect(page.getByText("Editado por vos")).toBeVisible();

  const despues = await request.get("/api/v1/preferences/chord-shapes", {
    headers: headersUi,
  });
  const aprendido = await despues.json();
  expect(Object.keys(aprendido).length).toBeGreaterThan(0);
  expect(JSON.stringify(aprendido)).toContain("Em");
});

test("5. la canción con riff no tiene scroll horizontal a 375 px", async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 800 });
  await abrirCancion(page);
  await expect(
    riff(page).getByRole("img", { name: /Tablatura/ }),
  ).toBeVisible();
  const ancho = await page.evaluate(() => document.documentElement.scrollWidth);
  expect(ancho, "scrollWidth con riff").toBeLessThanOrEqual(375);
  await capturarRiff(page, "riff-375px");

  await page.getByRole("button", { name: "Editar tab" }).click();
  await expect(page.getByRole("region", { name: /Editar riff/ })).toBeVisible();
  const anchoEditor = await page.evaluate(
    () => document.documentElement.scrollWidth,
  );
  expect(anchoEditor, "scrollWidth editando el riff").toBeLessThanOrEqual(375);
  await page
    .getByRole("region", { name: /Editar riff/ })
    .screenshot({ path: path.join(CAPTURAS, "riff-editor-375px.png") });
});
