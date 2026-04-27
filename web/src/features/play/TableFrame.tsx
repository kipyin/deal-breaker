import type { ReactNode } from "react";

type Props = {
  children: ReactNode;
  label?: string;
};

/** 16:9 arcade table chrome: pixel border, purple felt, CRT overlay, vignette. */
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
