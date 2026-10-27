// spec: features/admin/git-setup.feature
// seed: tests/seed.spec.ts

import { expect, type Page, test } from "@playwright/test";
import { BASE_URL, signIn } from "../helpers/e2e-api";

const PROVIDER = {
	id: "com.example.git",
	display_name: "Example Git",
	hosts: ["git.example.test"],
	self_hosted_hosts: false,
	terms: {
		change_request: "pull request",
		change_request_plural: "pull requests",
		repository: "Repository",
	},
	capabilities: { multiple_identities: false, access_grants: false },
};

const IDENTITY = {
	id: "00000000-0000-4000-8000-0000000000b1",
	provider_id: PROVIDER.id,
	host: "git.example.test",
	kind: "app",
	scope: "shared",
	handle: "paca-bot",
	display_name: "Paca Bot",
	expires_at: null,
	created_at: "2026-10-01T00:00:00Z",
};

const ok = (data: unknown) => ({
	status: 200,
	contentType: "application/json",
	body: JSON.stringify({ success: true, data }),
});

interface Stub {
	identities: unknown[];
	calls: Array<{ method: string; path: string; body?: unknown }>;
}

async function stubGit(page: Page, stub: Stub) {
	await page.route("**/api/v1/git/providers", (route) =>
		route.fulfill(ok([PROVIDER])),
	);
	await page.route("**/api/v1/git/identities", (route) =>
		route.fulfill(ok(stub.identities)),
	);
	await page.route("**/api/v1/git/identities/*", (route) => {
		const request = route.request();
		if (request.method() === "DELETE") {
			stub.calls.push({
				method: "DELETE",
				path: new URL(request.url()).pathname,
			});
			stub.identities = [];
			return route.fulfill({ status: 204 });
		}
		return route.continue();
	});
	await page.route("**/__git_platform__**", (route) =>
		route.fulfill({
			status: 200,
			contentType: "text/html",
			body: "<h1>platform</h1>",
		}),
	);
}

const newStub = (over: Partial<Stub> = {}): Stub => ({
	identities: [],
	calls: [],
	...over,
});

const captureSetup = async (page: Page, stub: Stub) => {
	await page.route("**/api/v1/git/identities/setup", (route) => {
		const request = route.request();
		stub.calls.push({
			method: request.method(),
			path: "/setup",
			body: request.postDataJSON(),
		});
		return route.fulfill(
			ok({
				kind: "redirect",
				url: `${BASE_URL}/__git_platform__?step=setup`,
				state: "s1",
			}),
		);
	});
};

test.describe("Git setup", () => {
	test.describe("The setup dialog", () => {
		test("Connecting a platform asks for optional details", async ({
			page,
		}) => {
			await signIn(page);
			await stubGit(page, newStub());
			await page.goto(`${BASE_URL}/admin/git`);

			await page.getByRole("button", { name: "Set up" }).click();
			const dialog = page.getByRole("dialog");
			await expect(
				dialog.getByText("Set up Example Git on git.example.test"),
			).toBeVisible();
			await expect(dialog.getByLabel("App name (optional)")).toBeVisible();
			await expect(dialog.getByLabel("Organization (optional)")).toBeVisible();
			await expect(
				dialog.getByText("Allow installing on other accounts (public app)"),
			).toBeVisible();
		});

		test("Details are sent to the platform and the browser follows it", async ({
			page,
		}) => {
			const stub = newStub();
			await signIn(page);
			await stubGit(page, stub);
			await captureSetup(page, stub);
			await page.goto(`${BASE_URL}/admin/git`);

			await page.getByRole("button", { name: "Set up" }).click();
			const dialog = page.getByRole("dialog");
			await dialog.getByLabel("App name (optional)").fill("Acme Bot");
			await dialog.getByLabel("Organization (optional)").fill("acme");
			await dialog.getByRole("switch").click();
			await dialog
				.getByRole("button", { name: /Continue to git\.example\.test/ })
				.click();

			await expect(page).toHaveURL(/__git_platform__/);
			const call = stub.calls.find((c) => c.path === "/setup");
			expect(call?.method).toBe("POST");
			expect(call?.body).toMatchObject({
				provider_id: PROVIDER.id,
				host: "git.example.test",
				params: { name: "Acme Bot", owner_org: "acme", public: "true" },
			});
		});

		test("Cancel closes the dialog without calling the platform", async ({
			page,
		}) => {
			const stub = newStub();
			await signIn(page);
			await stubGit(page, stub);
			await captureSetup(page, stub);
			await page.goto(`${BASE_URL}/admin/git`);

			await page.getByRole("button", { name: "Set up" }).click();
			await page
				.getByRole("dialog")
				.getByRole("button", { name: "Cancel" })
				.click();
			await expect(page.getByRole("dialog")).toHaveCount(0);
			expect(stub.calls).toEqual([]);
		});

		test("Removing an identity asks for confirmation", async ({ page }) => {
			const stub = newStub({ identities: [IDENTITY] });
			await signIn(page);
			await stubGit(page, stub);
			await page.goto(`${BASE_URL}/admin/git`);

			await page.getByRole("button", { name: "Remove" }).click();
			const dialog = page.getByRole("alertdialog").or(page.getByRole("dialog"));
			await expect(dialog.getByText("Remove this identity?")).toBeVisible();
			await dialog.getByRole("button", { name: "Remove identity" }).click();
			await expect
				.poll(() => stub.calls.some((c) => c.method === "DELETE"))
				.toBe(true);
			expect(stub.calls[0].path).toContain(IDENTITY.id);
		});
	});

	test.describe("The callback page", () => {
		test("A callback without a state is invalid", async ({ page }) => {
			await signIn(page);
			await page.goto(`${BASE_URL}/git/setup/callback`);

			const alert = page.getByRole("alert");
			await expect(alert).toContainText("Setup could not be completed");
			await expect(alert).toContainText(
				"This setup link is invalid, expired or already used.",
			);
			await alert.getByRole("link", { name: "Back to Git settings" }).click();
			await expect(page).toHaveURL(/\/admin\/git/);
		});

		test("A state the API does not know fails with a message", async ({
			page,
		}) => {
			await signIn(page);
			await page.goto(`${BASE_URL}/git/setup/callback?state=unknown&code=abc`);
			await expect(page.getByRole("alert")).toContainText(
				"Setup could not be completed",
			);
		});

		test("A finished setup returns to Git settings", async ({ page }) => {
			const completions: unknown[] = [];
			await signIn(page);
			await page.route("**/api/v1/git/providers", (r) =>
				r.fulfill(ok([PROVIDER])),
			);
			await page.route("**/api/v1/git/identities", (r) =>
				r.fulfill(ok([IDENTITY])),
			);
			await page.route("**/api/v1/git/identities/setup/complete", (route) => {
				completions.push(route.request().postDataJSON());
				return route.fulfill(
					ok({
						identity: IDENTITY,
						next: null,
						return_url: `${BASE_URL}/admin/git`,
						done: true,
					}),
				);
			});
			await page.goto(
				`${BASE_URL}/git/setup/callback?state=abc123&code=1e5&extra=x`,
			);

			await expect(page).toHaveURL(/\/admin\/git$/);
			expect(completions).toEqual([
				{ state: "abc123", params: { code: "1e5", extra: "x" } },
			]);
		});

		test("A return url on another site is ignored", async ({ page }) => {
			await signIn(page);
			await page.route("**/api/v1/git/providers", (r) =>
				r.fulfill(ok([PROVIDER])),
			);
			await page.route("**/api/v1/git/identities", (r) =>
				r.fulfill(ok([IDENTITY])),
			);
			await page.route("**/api/v1/git/identities/setup/complete", (route) =>
				route.fulfill(
					ok({
						identity: IDENTITY,
						next: null,
						return_url: "https://evil.example.com/steal",
						done: true,
					}),
				),
			);
			await page.goto(`${BASE_URL}/git/setup/callback?state=abc&code=1`);
			await expect(page).toHaveURL(/\/admin\/git$/);
		});

		test("A setup that needs another step sends the browser on", async ({
			page,
		}) => {
			await signIn(page);
			await page.route("**/__git_platform__**", (route) =>
				route.fulfill({
					status: 200,
					contentType: "text/html",
					body: "<h1>platform</h1>",
				}),
			);
			await page.route("**/api/v1/git/identities/setup/complete", (route) =>
				route.fulfill(
					ok({
						identity: IDENTITY,
						next: {
							kind: "redirect",
							url: `${BASE_URL}/__git_platform__?step=2`,
							state: "s2",
						},
						return_url: `${BASE_URL}/admin/git`,
						done: false,
					}),
				),
			);
			await page.goto(`${BASE_URL}/git/setup/callback?state=abc&code=1`);
			await expect(page).toHaveURL(/__git_platform__\?step=2/);
		});

		test("A finished access grant returns to the project", async ({ page }) => {
			await signIn(page);
			const projectId = "00000000-0000-4000-8000-0000000000d1";
			const state = "grant-1";
			await page.addInitScript(
				([key, value]) => window.sessionStorage.setItem(key, value),
				[
					`paca.git.flow.${state}`,
					JSON.stringify({ kind: "access", projectId }),
				],
			);
			const completions: unknown[] = [];
			await page.route(`**/api/v1/projects/${projectId}**`, (route) =>
				route.abort(),
			);
			await page.route(
				`**/api/v1/projects/${projectId}/git/access/complete`,
				(route) => {
					completions.push(route.request().postDataJSON());
					return route.fulfill(
						ok({
							owner: "other-org",
							return_url: `${BASE_URL}/projects/${projectId}/settings#git`,
						}),
					);
				},
			);
			await page.goto(
				`${BASE_URL}/git/setup/callback?state=${state}&installation_id=77&setup_action=install`,
			);

			await expect.poll(() => completions.length).toBe(1);
			expect(completions[0]).toEqual({
				state,
				params: { installation_id: "77", setup_action: "install" },
			});
			await expect(page).toHaveURL(
				new RegExp(`/projects/${projectId}/settings`),
			);
		});
	});
});
