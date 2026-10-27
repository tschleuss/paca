import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { mockProviders, mockIdentities, mockBegin, mockFollow, mockDelete } =
	vi.hoisted(() => ({
		mockProviders: vi.fn(),
		mockIdentities: vi.fn(),
		mockBegin: vi.fn(),
		mockFollow: vi.fn(),
		mockDelete: vi.fn(),
	}));

// The query options inside git-api call its own listGit* functions, which a
// module mock cannot replace, so the two list endpoints are mocked at the
// HTTP client instead.
vi.mock("@tanstack/react-router", async () => {
	const React = await import("react");
	return {
		Link: ({
			to,
			children,
			...rest
		}: {
			to: string;
			children?: React.ReactNode;
		}) => React.createElement("a", { href: to, ...rest }, children),
	};
});

vi.mock("@/lib/api-client", () => ({
	apiClient: {
		instance: {
			get: async (url: string) => {
				if (url === "/git/providers")
					return { data: { data: await mockProviders() } };
				if (url === "/git/identities")
					return { data: { data: await mockIdentities() } };
				throw new Error(`unexpected GET ${url}`);
			},
		},
	},
}));

vi.mock("@/lib/git-api", async (orig) => ({
	...(await orig<typeof import("@/lib/git-api")>()),
	beginGitSetup: mockBegin,
	followGitStep: mockFollow,
	deleteGitIdentity: mockDelete,
}));

import { GitIdentitiesPanel } from "./GitIdentitiesPanel";

const github = {
	id: "com.paca.github",
	display_name: "GitHub",
	hosts: ["github.com"],
	self_hosted_hosts: false,
	terms: {
		change_request: "Pull request",
		change_request_plural: "Pull requests",
		repository: "Repository",
	},
	capabilities: { multiple_identities: true },
};
const shared = {
	id: "i1",
	provider_id: "com.paca.github",
	host: "github.com",
	kind: "app",
	scope: "shared",
	handle: "paca-bot",
	display_name: "Paca",
	expires_at: null,
	created_at: "2026-01-01T00:00:00Z",
};

function renderPanel() {
	const client = new QueryClient({
		defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
	});
	return render(
		<QueryClientProvider client={client}>
			<GitIdentitiesPanel />
		</QueryClientProvider>,
	);
}

describe("GitIdentitiesPanel", () => {
	beforeEach(() => {
		vi.resetAllMocks();
		mockFollow.mockReturnValue(true);
	});

	it("tells the admin when no provider is installed", async () => {
		mockProviders.mockResolvedValue([]);
		mockIdentities.mockResolvedValue([]);
		renderPanel();
		expect(
			await screen.findByText(/no git provider installed/i),
		).toBeInTheDocument();
	});

	it("starts setup with the instance's return URL and hands the step to the browser", async () => {
		mockProviders.mockResolvedValue([github]);
		mockIdentities.mockResolvedValue([]);
		const step = {
			kind: "form_post",
			url: "https://github.com/settings/apps/new",
			fields: { manifest: "{}" },
			state: "s",
		};
		mockBegin.mockResolvedValue(step);
		const user = userEvent.setup();
		renderPanel();

		await user.click(await screen.findByRole("button", { name: "Set up" }));
		await user.type(screen.getByLabelText(/app name/i), "  Acme Paca ");
		await user.type(screen.getByLabelText(/organization/i), "acme");
		await user.click(
			screen.getByRole("button", { name: /continue to github\.com/i }),
		);

		await waitFor(() => expect(mockFollow).toHaveBeenCalledWith(step));
		expect(mockBegin).toHaveBeenCalledWith({
			provider_id: "com.paca.github",
			host: "github.com",
			return_url: `${window.location.origin}/admin/git`,
			params: { name: "Acme Paca", owner_org: "acme" },
		});
	});

	it("omits parameters the admin left empty", async () => {
		mockProviders.mockResolvedValue([github]);
		mockIdentities.mockResolvedValue([]);
		mockBegin.mockResolvedValue({ kind: "redirect", url: "u", state: "s" });
		const user = userEvent.setup();
		renderPanel();
		await user.click(await screen.findByRole("button", { name: "Set up" }));
		await user.click(
			screen.getByRole("button", { name: /continue to github\.com/i }),
		);
		await waitFor(() => expect(mockBegin).toHaveBeenCalled());
		expect(mockBegin.mock.calls[0][0].params).toEqual({});
	});

	it("shows why setup could not start", async () => {
		mockProviders.mockResolvedValue([github]);
		mockIdentities.mockResolvedValue([]);
		mockBegin.mockRejectedValue({
			response: { data: { error_code: "GIT_PUBLIC_URL_REQUIRED" } },
		});
		const user = userEvent.setup();
		renderPanel();
		await user.click(await screen.findByRole("button", { name: "Set up" }));
		await user.click(
			screen.getByRole("button", { name: /continue to github\.com/i }),
		);
		expect(await screen.findByRole("alert")).toHaveTextContent(/PUBLIC_URL/);
		expect(mockFollow).not.toHaveBeenCalled();
	});

	it("answers a token form in place", async () => {
		mockProviders.mockResolvedValue([github]);
		mockIdentities.mockResolvedValue([]);
		mockBegin.mockResolvedValue({
			kind: "token_form",
			prompt: "Paste a token with repo scope",
			state: "s",
			form: [
				{ name: "token", label: "Access token", secret: true, required: true },
			],
		});
		const user = userEvent.setup();
		renderPanel();
		await user.click(await screen.findByRole("button", { name: "Set up" }));
		await user.click(
			screen.getByRole("button", { name: /continue to github\.com/i }),
		);
		const field = await screen.findByLabelText("Access token");
		expect(field).toHaveAttribute("type", "password");
		expect(
			screen.getByText(/paste a token with repo scope/i),
		).toBeInTheDocument();
		expect(mockFollow).not.toHaveBeenCalled();
	});

	it("shows an existing identity and removes it after confirmation", async () => {
		mockProviders.mockResolvedValue([github]);
		mockIdentities.mockResolvedValue([shared]);
		mockDelete.mockResolvedValue(undefined);
		const user = userEvent.setup();
		renderPanel();

		expect(await screen.findByText("@paca-bot")).toBeInTheDocument();
		expect(
			screen.queryByRole("button", { name: "Set up" }),
		).not.toBeInTheDocument();
		await user.click(screen.getByRole("button", { name: "Remove" }));
		expect(mockDelete).not.toHaveBeenCalled();
		await user.click(
			await screen.findByRole("button", { name: "Remove identity" }),
		);
		await waitFor(() => expect(mockDelete).toHaveBeenCalledWith("i1"));
	});

	it("does not treat an agent's own identity as the host's shared one", async () => {
		mockProviders.mockResolvedValue([github]);
		mockIdentities.mockResolvedValue([{ ...shared, scope: "agent" }]);
		renderPanel();
		expect(
			await screen.findByRole("button", { name: "Set up" }),
		).toBeInTheDocument();
	});
});
