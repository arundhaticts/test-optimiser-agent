import { useEffect, useRef } from "react";
import type { AuditEntry } from "../types";

const NUM = (v: unknown): number => (typeof v === "number" ? v : Number(v) || 0);

/** Turn a raw audit entry into a plain-English progress line for a non-technical reader. */
function humanise(e: AuditEntry): string {
  const d = e.details ?? {};
  const offline = d.method === "deterministic" || d.method === "deterministic-fallback";
  switch (`${e.node}:${e.event}`) {
    case "intake:normalised_suite": {
      const un = NUM(d.unparseable);
      return `Read ${NUM(d.parsed)} tests (${d.framework ?? "unknown"} framework)` +
        (un ? `, ${un} could not be parsed` : "");
    }
    case "intake:suite_unreadable":
      return "Could not read the test suite";
    case "coverage:analysed":
      return `Mapped ${NUM(d.criteria)} acceptance criteria — found ${NUM(d.gaps)} coverage gap${NUM(d.gaps) === 1 ? "" : "s"}`;
    case "redundancy:flagged":
      return `Flagged ${NUM(d.duplicate_clusters)} duplicate cluster(s), ${NUM(d.flaky)} flaky and ${NUM(d.slow)} slow test(s)`;
    case "retrieval:retrieved":
      return `Pulled ${NUM(d.hits)} item(s) of prior context`;
    case "scoring:scored":
      return `Scored ${NUM(d.dimensions)} health dimensions${offline ? " (offline fallback)" : " with the LLM"}`;
    case "hitl_removals:approved":
      return `Approved ${NUM(d.count)} removal(s)`;
    case "prioritisation:tiered":
      return `Tiered tests: ${NUM(d.smoke)} smoke, ${NUM(d.regression)} regression, ${NUM(d.full)} full`;
    case "revise:reverted_removal":
      return "Reverted a removal to protect the coverage floor";
    case "hitl_priority:approved":
      return "Approved the ranking";
    case "gap_generation:drafted":
      return `Drafted ${NUM(d.count)} test(s) for gaps${offline ? " (offline fallback)" : " with the LLM"}`;
    case "validation:validated":
      return `Validated ${NUM(d.valid)} of ${NUM(d.total)} generated test(s)`;
    case "hitl_generated:approved":
      return `Approved ${NUM(d.count)} generated test(s)`;
    case "assemble:assembled_plan":
      return "Assembled the optimised plan";
    case "report:rendered_outputs":
      return `Produced ${NUM(d.deliverables)} deliverables`;
    default:
      return e.event.replace(/_/g, " ");
  }
}

function rawDetails(d?: Record<string, unknown>): string {
  if (!d) return "";
  return Object.entries(d)
    .map(([k, v]) => `${k}=${typeof v === "object" ? JSON.stringify(v) : String(v)}`)
    .join("  ");
}

function fmtTime(ts?: string): string {
  if (!ts) return "";
  const d = new Date(ts);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function fmtFull(ts?: string): string {
  if (!ts) return "";
  const d = new Date(ts);
  return isNaN(d.getTime()) ? "" : d.toLocaleString();
}

export default function AuditLog({ entries }: { entries: AuditEntry[] }) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [entries.length]);

  const latestDate = (() => {
    const ts = entries[entries.length - 1]?.ts;
    if (!ts) return "";
    const d = new Date(ts);
    return isNaN(d.getTime()) ? "" : d.toLocaleDateString([], { day: "numeric", month: "short", year: "numeric" });
  })();

  return (
    <div className="audit">
      <h3 className="audit-title">
        Progress {latestDate && <span className="audit-date">{latestDate}</span>}
      </h3>
      <div className="audit-scroll">
        {entries.length === 0 ? (
          <p className="muted">Waiting for the agent to start…</p>
        ) : (
          <ul className="audit-feed">
            {entries.map((e, i) => (
              <li key={`${e.node}-${i}`} className="audit-row" title={rawDetails(e.details)}>
                <div className="audit-top">
                  <span className="audit-node">{e.node}</span>
                  <span className="audit-time" title={fmtFull(e.ts)}>{fmtTime(e.ts)}</span>
                </div>
                <span className="audit-msg">{humanise(e)}</span>
              </li>
            ))}
            <div ref={endRef} />
          </ul>
        )}
      </div>
    </div>
  );
}
