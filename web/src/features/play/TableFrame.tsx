import type { ReactNode } from "react";

type Props = {
  children: ReactNode;
  label?: string;
};

/** Arcade table chrome: felt, scanlines, vignette; layout is responsive (not fixed 16:9). */
export function TableFrame({ children, label = "Prototype play table" }: Props) {
  return (
    <section className="play-table" aria-label={label}>
      <div className="table-frame-outer">
        <div className="table-frame">
          <div className="table-frame__scanlines" aria-hidden />
          <div className="table-frame__vignette" aria-hidden />
          <div className="table-frame__content">{children}</div>
        </div>
      </div>
    </section>
  );
}
