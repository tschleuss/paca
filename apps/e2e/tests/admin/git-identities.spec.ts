// spec: features/admin/git-identities.feature
// seed: tests/seed.spec.ts
//
// Administration, Git. The e2e stack has no Git provider plugin, so the
// provider and identity endpoints are answered in the browser with page.route;
// access to the page is still decided by the real permissions of the user.

import { expect, type Page, test } from "@playwright/test";
import {
	authRequest,
	BASE_URL,
	cleanupGlobalRolesByPrefix,
	cleanupUsersByPrefix,
	createUserWithGlobalPermissions,
	newRunId,
	RESTRICTED_PASSWORD,
	signIn,
} from "../helpers/e2e-api";

const PREFIX = "E2E_GITADM_";
const RUN_ID = newRunId();
const name = (label: string) => `${PREFIX}${label}_${RUN_ID}`;

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

async function stubGit(
	page: Page,
	opts: { providers: unknown[]; identities: unknown[] },
) {
	await page.route("**/api/v1/git/providers", (route) =>
		route.fulfill(ok(opts.providers)),
	);
	await page.route("**/api/v1/git/identities", (route) =>
		route.fulfill(ok(opts.identities)),
	);
}

const openGitAdmin = async (page: Page) => {
	await page.goto(`${BASE_URL}/admin/git`);
	await expect(
		page.getByRole("heading", { name: "Git", exact: true }),
	).toBeVisible();
};

test.describe("Administration, Git", () => {
	test.beforeAll(async ({ request }) => {
		await authRequest(request);
		await cleanupUsersByPrefix(request, PREFIX);
		await cleanupGlobalRolesByPrefix(request, PREFIX);
	});

	test.beforeEach(async ({ request }) => {
		await authRequest(request);
	});

	test.afterAll(async ({ request }) => {
		await authRequest(request);
		await cleanupUsersByPrefix(request, PREFIX);
		await cleanupGlobalRolesByPrefix(request, PREFIX);
	});

	test.describe("What the page shows", () => {
		test("No provider plugin is installed", async ({ page }) => {
			await signIn(page);
			await stubGit(page, { providers: [], identities: [] });
			await openGitAdmin(page);

			await expect(page.getByText("No Git provider installed")).toBeVisible();
			await expect(
				page.getByRole("link", { name: "Manage plugins" }),
			).toHaveAttribute("href", "/admin/plugins");
		});

		test("A platform without an identity is not connected", async ({
			page,
		}) => {
			await signIn(page);
			await stubGit(page, { providers: [PROVIDER], identities: [] });
			await openGitAdmin(page);

			await expect(
				page.getByRole("heading", { name: "Example Git" }),
			).toBeVisible();
			await expect(page.getByText("Not connected")).toBeVisible();
			await expect(page.getByRole("button", { name: "Set up" })).toBeVisible();
		});

		test("A platform with an identity shows the bot to mention", async ({
			page,
		}) => {
			await signIn(page);
			await stubGit(page, { providers: [PROVIDER], identities: [IDENTITY] });
			await openGitAdmin(page);

			await expect(page.getByText("Connected", { exact: true })).toBeVisible();
			await expect(page.getByText("@paca-bot")).toBeVisible();
			await expect(page.getByRole("button", { name: "Remove" })).toBeVisible();
		});
	});

	test.describe("Who may open it", () => {
		test("A user without git.identities:manage is sent home", async ({
			page,
			request,
			playwright,
		}) => {
			const username = name("PLAIN");
			await createUserWithGlobalPermissions(request, playwright, {
				username,
				roleName: name("ROLE_PLAIN"),
				permissions: { "users:read": true },
			});
			await signIn(page, username, RESTRICTED_PASSWORD);
			await page.goto(`${BASE_URL}/admin/git`);

			await expect(page).toHaveURL(/\/home/);
			// The sidebar entries come from the user's permissions: open the sidebar
			// when it is collapsed (narrow screens) and wait for an entry the user
			// holds before asserting the Git entry is absent.
			if ((page.viewportSize()?.width ?? 1280) < 768) {
				await page
					.getByRole("button", { name: /toggle sidebar/i })
					.first()
					.click();
			}
			await expect(
				page.getByRole("link", { name: "Users", exact: true }),
			).toBeVisible();
			await expect(
				page.getByRole("link", { name: "Git", exact: true }),
			).toHaveCount(0);
		});

		test("A holder of git.identities:manage sees the entry and the page", async ({
			page,
			request,
			playwright,
		}) => {
			const username = name("MANAGER");
			await createUserWithGlobalPermissions(request, playwright, {
				username,
				roleName: name("ROLE_MANAGER"),
				permissions: { "git.identities:manage": true },
			});
			await signIn(page, username, RESTRICTED_PASSWORD);
			await stubGit(page, { providers: [PROVIDER], identities: [] });
			await openGitAdmin(page);

			await expect(
				page.getByRole("heading", { name: "Example Git" }),
			).toBeVisible();
		});
	});
});
