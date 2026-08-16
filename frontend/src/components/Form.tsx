import type { ReactNode } from "react";

export function Field(props: {
  label: string;
  children: ReactNode;
  required?: boolean;
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-sm font-medium text-slate-700">
        {props.label}
        {props.required && <span className="ml-1 text-red-600">*</span>}
      </span>
      {props.children}
    </label>
  );
}

export const inputClass =
  "w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none";

export function SubmitButton(props: { children: ReactNode; disabled?: boolean }) {
  return (
    <button
      type="submit"
      disabled={props.disabled}
      className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
    >
      {props.children}
    </button>
  );
}

export function ErrorNote(props: { message: string | null }) {
  if (!props.message) return null;
  return (
    <p className="rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
      {props.message}
    </p>
  );
}

export function SuccessNote(props: { message: string | null }) {
  if (!props.message) return null;
  return (
    <p className="rounded border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">
      {props.message}
    </p>
  );
}
