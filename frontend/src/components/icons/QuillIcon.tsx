import type { SVGProps } from "react";

export function QuillIcon({ className, ...props }: SVGProps<SVGSVGElement>) {
  return (
    <svg
      viewBox="0 0 64 64"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      {...props}
    >
      <path
        d="M54 4C34 10 16 28 10 46c-2.3 7-1.2 10.2 1 12 2 1.7 5.3 2.4 12-1 18-9 35-27 41-47"
        fill="currentColor"
        fillOpacity="0.08"
      />
      <path d="M54 4C34 10 16 28 10 46" />
      <path d="M10 46c-2 6-1 9 1 11s5 3 11 1" />
      <path d="M22 52l12 12" />
      <path d="M22 52c6-16 24-34 40-40" />
    </svg>
  );
}
