import type { LucideIcon } from "lucide-react";
import { Check, Copy } from "lucide-react";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { cn } from "@/lib/utils";

/** A snippet the user is meant to type or paste somewhere else, with a copy button. */
export function CopyChip({
	value,
	label,
	className,
}: {
	value: string;
	/** What the button copies, for screen readers. */
	label?: string;
	className?: string;
}) {
	const { t } = useTranslation("admin");
	const [copied, setCopied] = useState(false);
	const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
	useEffect(
		() => () => {
			if (timer.current) clearTimeout(timer.current);
		},
		[],
	);
	return (
		<span
			className={cn(
				"inline-flex max-w-full items-center gap-1 rounded-md border border-border/60 bg-muted/50 py-0.5 pl-2 pr-0.5 font-mono text-xs",
				className,
			)}
		>
			<span className="truncate">{value}</span>
			<button
				type="button"
				aria-label={`${t("git.copy")}: ${label ?? value}`}
				title={copied ? t("git.copied") : t("git.copy")}
				className="rounded p-1 text-muted-foreground transition-colors hover:bg-background hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring"
				onClick={() => {
					void navigator.clipboard?.writeText(value);
					setCopied(true);
					if (timer.current) clearTimeout(timer.current);
					timer.current = setTimeout(() => setCopied(false), 1500);
				}}
			>
				{copied ? <Check className="size-3" /> : <Copy className="size-3" />}
			</button>
		</span>
	);
}

/** A titled block of a settings page. */
export function Section({
	title,
	description,
	action,
	children,
	id,
}: {
	title: string;
	description?: ReactNode;
	action?: ReactNode;
	children: ReactNode;
	id?: string;
}) {
	return (
		<section
			aria-labelledby={id ? `${id}-title` : undefined}
			className="flex flex-col gap-3"
		>
			<div className="flex items-start justify-between gap-3">
				<div className="min-w-0">
					<h2
						id={id ? `${id}-title` : undefined}
						className="text-base font-semibold"
					>
						{title}
					</h2>
					{description ? (
						<p className="mt-0.5 text-sm text-muted-foreground">
							{description}
						</p>
					) : null}
				</div>
				{action ? <div className="shrink-0">{action}</div> : null}
			</div>
			{children}
		</section>
	);
}

/** The "nothing here yet" block: what this is, what to do, and the way to do it. */
export function EmptyState({
	icon: Icon,
	title,
	description,
	children,
}: {
	icon: LucideIcon;
	title: string;
	description: ReactNode;
	children?: ReactNode;
}) {
	return (
		<div className="flex flex-col items-center gap-3 rounded-xl border border-dashed border-border bg-muted/20 px-6 py-8 text-center">
			<span className="flex size-10 items-center justify-center rounded-full bg-primary/10 text-primary">
				<Icon className="size-5" aria-hidden="true" />
			</span>
			<div className="max-w-md">
				<p className="text-sm font-semibold">{title}</p>
				<p className="mt-1 text-sm text-muted-foreground">{description}</p>
			</div>
			{children}
		</div>
	);
}
