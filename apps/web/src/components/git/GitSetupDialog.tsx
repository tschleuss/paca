import { useMutation, useQueryClient } from "@tanstack/react-query";
import { GitBranch, Loader2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogClose,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
	type BeginGitSetupPayload,
	beginGitSetup,
	completeGitSetup,
	followGitStep,
	GIT_ADMIN_PATH,
	type GitProvider,
	type GitSetupStep,
	gitErrorKey,
	gitIdentitiesKey,
} from "@/lib/git-api";

interface GitSetupDialogProps {
	provider: GitProvider;
	host: string;
	open: boolean;
	onOpenChange: (open: boolean) => void;
	/**
	 * Starts the setup; defaults to the workspace's shared identity. An agent's
	 * own identity passes its own endpoint.
	 */
	begin?: (payload: BeginGitSetupPayload) => Promise<GitSetupStep>;
	/** Where the browser returns when setup is finished (a same-origin path). */
	returnPath?: string;
	/** Query cache entry to refresh when a token form finishes in place. */
	invalidateKey?: readonly unknown[];
}

/**
 * Starts creating the shared bot identity for one provider host. The
 * provider decides what happens next: a redirect or a form post sends the
 * browser to the platform (which returns to /git/setup/callback), a token
 * form is answered right here. The optional name and organization are passed
 * through as provider parameters; a provider that has no use for them ignores
 * them.
 */
export function GitSetupDialog({
	provider,
	host,
	open,
	onOpenChange,
	begin = beginGitSetup,
	returnPath = GIT_ADMIN_PATH,
	invalidateKey = gitIdentitiesKey,
}: GitSetupDialogProps) {
	const { t } = useTranslation("admin");
	const queryClient = useQueryClient();
	const [name, setName] = useState("");
	const [org, setOrg] = useState("");
	const [isPublic, setIsPublic] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [tokenStep, setTokenStep] = useState<GitSetupStep | null>(null);
	const [tokenValues, setTokenValues] = useState<Record<string, string>>({});

	const start = useMutation({
		mutationFn: () => {
			const params: Record<string, string> = {};
			if (name.trim()) params.name = name.trim();
			if (org.trim()) params.owner_org = org.trim();
			if (isPublic) params.public = "true";
			return begin({
				provider_id: provider.id,
				host,
				return_url: `${window.location.origin}${returnPath}`,
				params,
			});
		},
		onSuccess: (step) => {
			if (step.kind === "token_form") {
				setTokenStep(step);
				return;
			}
			if (step.kind === "done") {
				void queryClient.invalidateQueries({ queryKey: invalidateKey });
				onOpenChange(false);
				return;
			}
			// Leaves the page; the platform returns to /git/setup/callback.
			if (!followGitStep(step)) setError(t("git.errors.generic"));
		},
		onError: (err: unknown) => {
			setError(t(`git.errors.${gitErrorKey(err)}` as never));
		},
	});

	const submitToken = useMutation({
		mutationFn: () => completeGitSetup(tokenStep?.state ?? "", tokenValues),
		onSuccess: () => {
			void queryClient.invalidateQueries({ queryKey: invalidateKey });
			onOpenChange(false);
		},
		onError: (err: unknown) => {
			setError(t(`git.errors.${gitErrorKey(err)}` as never));
		},
	});

	const busy = start.isPending || submitToken.isPending;
	const title = t("git.setup.dialogTitle", {
		provider: provider.display_name,
		host,
	});

	return (
		<Dialog
			open={open}
			onOpenChange={(next) => {
				if (!next) {
					setError(null);
					setTokenStep(null);
					setTokenValues({});
				}
				onOpenChange(next);
			}}
		>
			<DialogContent className="sm:max-w-md">
				<form
					className="flex flex-col gap-4"
					onSubmit={(e) => {
						e.preventDefault();
						setError(null);
						if (tokenStep) submitToken.mutate();
						else start.mutate();
					}}
				>
					<DialogHeader>
						<div className="mb-1 flex size-9 items-center justify-center rounded-lg bg-primary/10">
							<GitBranch className="size-4 text-primary" />
						</div>
						<DialogTitle>{title}</DialogTitle>
						<DialogDescription className="mt-1">
							{tokenStep?.prompt ??
								t("git.setup.dialogDescription", {
									host,
									changeRequests:
										provider.terms.change_request_plural.toLowerCase(),
								})}
						</DialogDescription>
					</DialogHeader>

					{tokenStep ? (
						(tokenStep.form ?? []).map((f) => (
							<div key={f.name} className="flex flex-col gap-1.5">
								<Label htmlFor={`git-setup-${f.name}`}>{f.label}</Label>
								<Input
									id={`git-setup-${f.name}`}
									type={f.secret ? "password" : "text"}
									autoComplete="off"
									required={f.required}
									value={tokenValues[f.name] ?? ""}
									onChange={(e) =>
										setTokenValues((v) => ({ ...v, [f.name]: e.target.value }))
									}
								/>
								{f.help ? (
									<p className="text-xs text-muted-foreground">{f.help}</p>
								) : null}
							</div>
						))
					) : (
						<>
							<div className="flex flex-col gap-1.5">
								<Label htmlFor="git-setup-name">{t("git.setup.name")}</Label>
								<Input
									id="git-setup-name"
									value={name}
									maxLength={34}
									placeholder="Paca"
									onChange={(e) => setName(e.target.value)}
								/>
								<p className="text-xs text-muted-foreground">
									{t("git.setup.nameHelp")}
								</p>
							</div>
							<div className="flex flex-col gap-1.5">
								<Label htmlFor="git-setup-org">{t("git.setup.org")}</Label>
								<Input
									id="git-setup-org"
									value={org}
									onChange={(e) => setOrg(e.target.value)}
								/>
								<p className="text-xs text-muted-foreground">
									{t("git.setup.orgHelp")}
								</p>
							</div>
							<div className="flex items-start gap-3">
								<Switch
									id="git-setup-public"
									checked={isPublic}
									onCheckedChange={setIsPublic}
								/>
								<div className="flex flex-col gap-1">
									<Label htmlFor="git-setup-public">
										{t("git.setup.public")}
									</Label>
									<p className="text-xs text-muted-foreground">
										{t("git.setup.publicHelp")}
									</p>
								</div>
							</div>
						</>
					)}

					{error ? (
						<div
							role="alert"
							className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive"
						>
							<span className="shrink-0">⚠</span>
							<span>{error}</span>
						</div>
					) : null}

					<DialogFooter>
						<DialogClose
							render={
								<Button type="button" variant="outline" disabled={busy} />
							}
						>
							{t("git.cancel")}
						</DialogClose>
						<Button type="submit" disabled={busy}>
							{busy ? <Loader2 className="size-4 animate-spin" /> : null}
							{tokenStep
								? t("git.setup.submitToken")
								: t("git.setup.start", { host })}
						</Button>
					</DialogFooter>
				</form>
			</DialogContent>
		</Dialog>
	);
}
