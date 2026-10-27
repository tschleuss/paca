import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { GitBranch, Plug, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
	type GitIdentity,
	type GitProvider,
	gitIdentitiesQueryOptions,
	gitProvidersQueryOptions,
} from "@/lib/git-api";
import { DeleteGitIdentityDialog } from "./DeleteGitIdentityDialog";
import { GitSetupDialog } from "./GitSetupDialog";
import { CopyChip, EmptyState, Section } from "./git-ui";

/**
 * The workspace's Git page. A newcomer sees what the feature does and the three
 * steps to get it working; each platform card says whether it is connected and
 * what to do next. A connected platform shows the bot's @handle to mention.
 */
export function GitIdentitiesPanel() {
	const { t } = useTranslation("admin");
	const providers = useQuery(gitProvidersQueryOptions);
	const identities = useQuery(gitIdentitiesQueryOptions);
	const [setup, setSetup] = useState<{
		provider: GitProvider;
		host: string;
	} | null>(null);
	const [removing, setRemoving] = useState<GitIdentity | null>(null);

	if (providers.isLoading || identities.isLoading) {
		return <Skeleton className="h-40 w-full" />;
	}
	if (providers.isError || identities.isError) {
		return (
			<p role="alert" className="text-sm text-destructive">
				{t("git.errors.generic")}
			</p>
		);
	}
	const list = providers.data ?? [];

	if (list.length === 0) {
		return (
			<EmptyState
				icon={Plug}
				title={t("git.noProviders.title")}
				description={t("git.noProviders.description")}
			>
				<Button render={<Link to="/admin/plugins" />} size="sm">
					{t("git.noProviders.action")}
				</Button>
			</EmptyState>
		);
	}

	const sharedFor = (providerId: string, host: string) =>
		(identities.data ?? []).find(
			(i) =>
				i.provider_id === providerId &&
				i.scope === "shared" &&
				i.host.toLowerCase() === host.toLowerCase(),
		);
	return (
		<div className="flex flex-col gap-6">
			<Section
				title={t("git.platforms.title")}
				description={t("git.platforms.description")}
			>
				<div className="flex flex-col gap-4">
					{list.map((provider) =>
						provider.hosts.map((host) => {
							const identity = sharedFor(provider.id, host);
							return (
								<Card key={`${provider.id}/${host}`}>
									<CardContent className="flex flex-col gap-4">
										<div className="flex items-start justify-between gap-3">
											<div className="flex min-w-0 items-center gap-3">
												<span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
													<GitBranch className="size-5" aria-hidden="true" />
												</span>
												<div className="min-w-0">
													<h3 className="truncate text-sm font-semibold">
														{provider.display_name}
													</h3>
													<p className="truncate text-xs text-muted-foreground">
														{host}
													</p>
												</div>
											</div>
											<Badge variant={identity ? "default" : "outline"}>
												{identity
													? t("git.status.connected")
													: t("git.status.notConnected")}
											</Badge>
										</div>

										{identity ? (
											<Connected
												identity={identity}
												onRemove={() => setRemoving(identity)}
											/>
										) : (
											<NotConnected
												provider={provider}
												host={host}
												onConnect={() => setSetup({ provider, host })}
											/>
										)}
									</CardContent>
								</Card>
							);
						}),
					)}
				</div>
			</Section>

			{setup ? (
				<GitSetupDialog
					provider={setup.provider}
					host={setup.host}
					open
					onOpenChange={(open) => {
						if (!open) setSetup(null);
					}}
				/>
			) : null}
			{removing ? (
				<DeleteGitIdentityDialog
					identity={removing}
					open
					onOpenChange={(open) => {
						if (!open) setRemoving(null);
					}}
				/>
			) : null}
		</div>
	);
}

function NotConnected({
	provider,
	host,
	onConnect,
}: {
	provider: GitProvider;
	host: string;
	onConnect: () => void;
}) {
	const { t } = useTranslation("admin");
	return (
		<div className="flex flex-col gap-3 rounded-lg bg-muted/40 p-4">
			<div>
				<p className="text-sm font-medium">
					{t("git.connect.title", { provider: provider.display_name })}
				</p>
				<p className="mt-0.5 text-sm text-muted-foreground">
					{t("git.connect.description", { host })}
				</p>
			</div>
			<div className="flex flex-wrap items-center gap-3">
				<Button type="button" size="sm" onClick={onConnect}>
					{t("git.setup.button", { provider: provider.display_name })}
				</Button>
				<span className="text-xs text-muted-foreground">
					{t("git.connect.time")}
				</span>
			</div>
		</div>
	);
}

function Connected({
	identity,
	onRemove,
}: {
	identity: GitIdentity;
	onRemove: () => void;
}) {
	const { t } = useTranslation("admin");
	const name = identity.display_name || identity.handle;
	return (
		<div className="flex flex-col gap-4">
			<div className="flex flex-wrap items-center justify-between gap-3 rounded-lg bg-muted/40 p-4">
				<div className="min-w-0">
					<p className="truncate text-sm font-medium">{name}</p>
					<p className="mt-0.5 text-sm text-muted-foreground">
						{t("git.connected.sharedNote")}
					</p>
				</div>
				{identity.handle ? (
					<div className="flex flex-col items-start gap-1">
						<span className="text-xs text-muted-foreground">
							{t("git.connected.mention")}
						</span>
						<CopyChip value={`@${identity.handle}`} />
					</div>
				) : null}
			</div>
			<div>
				<Button type="button" variant="outline" size="sm" onClick={onRemove}>
					<Trash2 className="size-4" />
					{t("git.delete.button")}
				</Button>
			</div>
		</div>
	);
}
