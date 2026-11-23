// Tiny Tailwind component set (no Solid-2-compatible component library is stable yet).
import type { JSX } from "@solidjs/web";
import { omit, type ParentComponent } from "solid-js";

type Variant = "primary" | "secondary";

const buttonVariants: Record<Variant, string> = {
  primary: "bg-stone-900 text-white hover:bg-stone-700 disabled:bg-stone-400",
  secondary: "bg-white text-stone-900 ring-1 ring-stone-300 hover:bg-stone-100 disabled:text-stone-400",
};

export function Button(props: JSX.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  const rest = omit(props, "variant", "class");
  return (
    <button
      {...rest}
      class={[
        "inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed",
        buttonVariants[props.variant ?? "primary"],
        props.class,
      ]}
    />
  );
}

export const Card: ParentComponent<{ class?: string }> = (props) => (
  <section class={["rounded-2xl bg-white p-5 shadow-sm ring-1 ring-stone-200", props.class]}>{props.children}</section>
);

export const CardTitle: ParentComponent = (props) => (
  <h2 class="mb-3 text-base font-semibold text-stone-800">{props.children}</h2>
);

type Tone = "neutral" | "success" | "warning" | "danger" | "info";

const tones: Record<Tone, string> = {
  neutral: "bg-stone-100 text-stone-700",
  success: "bg-emerald-50 text-emerald-700",
  warning: "bg-amber-50 text-amber-800",
  danger: "bg-red-50 text-red-700",
  info: "bg-sky-50 text-sky-700",
};

export const Badge: ParentComponent<{ tone?: Tone }> = (props) => (
  <span class={["inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium", tones[props.tone ?? "neutral"]]}>
    {props.children}
  </span>
);

export const Spinner = (props: { class?: string }) => (
  <span
    class={["inline-block size-4 animate-spin rounded-full border-2 border-current border-r-transparent", props.class]}
    role="status"
    aria-label="იტვირთება"
  />
);
