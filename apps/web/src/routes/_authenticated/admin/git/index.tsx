import { createFileRoute, redirect } from "@tanstack/react-router";
import { GitBranch } from "lucide-react";
import { useTranslation } from "react-i18next";
import { GitIdentitiesPanel } from "@/components/git/GitIdentitiesPanel";
import { Separator } from "@/components/ui/separator";
import { myPermissionsQueryOptions } from "@/lib/admin-api";
import { hasPermission } from "@/lib/permissions";

export const Route = createFileRoute("/_authenticated/admin/git/")({
	beforeLoad: async ({ context: { queryClient } }) => {
		const permissions = await queryClient
			.fetchQuery(myPermissionsQueryOptions)
			.catch(() => [] as string[]);
		if (!hasPermission(permissions, "git.identities:manage")) {
			throw redirect({ to: "/home" });
		}
	},
	component: GitSettingsPage,
});

function GitSettingsPage() {
	const { t } = useTranslation("admin");
	return (
		<div className="flex flex-col gap-6 p-6 max-w-3xl w-full mx-auto">
			<div>
				<div className="flex items-center gap-2">
					<GitBranch className="size-5 text-primary" />
					<h1 className="text-xl font-semibold">{t("git.title")}</h1>
				</div>
				<p className="mt-1 text-sm text-muted-foreground">
					{t("git.description")}
				</p>
			</div>
			<Separator />
			<GitIdentitiesPanel />
		</div>
	);
}
