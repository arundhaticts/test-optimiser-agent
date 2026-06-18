# Test Optimiser Agent — Frontend (React)

This folder is the **web user interface** for the Test Optimiser agent. It is a small
single-page app: you fill in a form, click **Run Analysis**, approve three checkpoints, and
read the results. It does **no analysis itself** — all the thinking happens in the Python
backend (`../api.py` + the LangGraph agent). The frontend only **shows** data and **sends**
your decisions back.

This README assumes you have **never used React**. It explains the ideas you need, then walks
through every file.

---

## 1. React primer

1. **Component** — a function that returns a piece of UI. In this app every screen and widget
   is a component (e.g. `InputPanel`, `AuditLog`). A component is just a JavaScript/TypeScript
   function whose name starts with a capital letter and that returns "JSX".

2. **JSX** — HTML-like syntax inside the code. `return <button>Run</button>` produces a real
   button on the page. You can drop values in with curly braces: `<h1>{title}</h1>`. It looks
   like HTML but it's actually TypeScript.

3. **Props** — the inputs a component receives, like function arguments. A parent passes data
   *down* to a child: `<AuditLog entries={auditLog} />`. Inside `AuditLog`, `entries` is a prop.

4. **State** — data a component remembers and that, when changed, makes the screen re-draw.
   You create it with the `useState` hook:
   ```ts
   const [view, setView] = useState("input");   // `view` is the value, `setView` changes it
   ```
   Calling `setView("results")` tells React "this changed — re-draw". This is how the UI moves
   between screens.

5. **Hooks** — special functions starting with `use`. We use two:
   - `useState` — remember a value (above).
   - `useEffect` — run code *after* the screen draws, e.g. start a timer to poll the backend.
     `useEffect(fn, [x])` re-runs `fn` whenever `x` changes.

That's it. The whole app is components passing props down and lifting state up to one place
(`App.tsx`), which decides what to show.

---

## 2. The tech stack (and why)

- **React** — the UI library (components + state).
- **TypeScript** — JavaScript with types. The `.tsx` extension = "TypeScript + JSX". Types
  catch mistakes before the app runs (e.g. using a field that doesn't exist).
- **Vite** — the dev server + build tool. `npm run dev` starts a local server with instant
  hot-reload (you save a file, the browser updates). `npm run build` makes a production bundle.
- **axios** — a small library for making HTTP calls to the backend.
- **lucide-react** — the icon set (the little check / lock / warning icons).
- **Plain CSS** — all styling lives in one file, `src/index.css`. No Tailwind or UI library.

---

## 3. How to run it

```bash
# 1) start the backend first (from the repo root, in the Python venv)
uvicorn api:app --reload          # http://127.0.0.1:8000

# 2) start this frontend (from this folder)
npm install                       # one-time: downloads dependencies into node_modules/
npm run dev                       # http://localhost:5173  — open this in your browser
```

Other commands: `npm run build` (production bundle into `dist/`), `npm run preview` (serve the
built bundle), `npm run lint` (style/error check).

The backend URL (`http://127.0.0.1:8000`) is set once in `src/api.ts`. CORS (permission for the
browser to call a different port) is already enabled on the backend for `localhost:5173`.

---

## 4. The folder structure

```
frontend/
├── index.html                  the single HTML page the browser loads
├── package.json                dependencies + the npm scripts (dev/build/lint)
├── vite.config.ts              Vite settings (mostly defaults)
├── tsconfig*.json              TypeScript settings
├── node_modules/               installed dependencies (created by `npm install`; not committed)
├── dist/                       production build output (created by `npm run build`)
└── src/                        ← all our code lives here
    ├── main.tsx                entry point: mounts <App> into index.html
    ├── App.tsx                 the "brain": holds all state, decides which screen shows
    ├── api.ts                  every HTTP call to the backend (the ONLY file that knows URLs)
    ├── types.ts                TypeScript shapes for all the data (no logic, just types)
    ├── index.css               all styling
    └── components/             the UI pieces
        ├── InputPanel.tsx          the start form (suite path, goal, etc.)
        ├── AuditLog.tsx            the live "Progress" feed on the right
        ├── DegradedBanner.tsx      the "running with fallbacks" notice
        ├── hitl/                   the 3 human-in-the-loop approval cards
        │   ├── ApproveRemovals.tsx     checkpoint 1 — which tests to remove
        │   ├── ApproveRanking.tsx      checkpoint 2 — confirm smoke/regression/full tiers
        │   └── ApproveTests.tsx        checkpoint 3 — which generated tests to keep
        └── results/                the final results, shown as 4 tabs
            ├── ResultsTabs.tsx         the tab switcher
            ├── HealthScorecard.tsx     tab 1 — the six 0–10 dimension scores
            ├── CoverageMap.tsx         tab 2 — criteria coverage + gaps
            ├── RedundancyReport.tsx    tab 3 — duplicates / flaky / slow
            └── OptimisedPlan.tsx       tab 4 — current vs proposed plan
```

("HITL" = *human-in-the-loop* — the points where the agent pauses and asks you to approve.)

---

## 5. The big picture: how a run flows through the app

The app is a **state machine** with four screens, all controlled by `App.tsx`:

```
  input ──Run Analysis──► running ──checkpoint arrives──► hitl
    ▲                        ▲                              │
    │                        └──────you approve────────────┘  (repeats for the 3 checkpoints)
    │                                                          │
    └────────Run Another──── results ◄──run completes──────────┘
```

- **input** — the form (`InputPanel`).
- **running** — a spinner while the backend works (the backend blocks until the next pause).
- **hitl** — one of the three approval cards.
- **results** — the four result tabs.

`App.tsx` keeps a variable `view` (one of those four words). Whenever the backend replies,
`App.tsx` updates `view`, and React re-draws the matching screen.

**Important about the backend:** it is *synchronous*. When the frontend sends `POST /runs`, the
backend doesn't reply "started" — it actually runs the agent until the first checkpoint (or the
end) and *then* replies. So the spinner is the app simply waiting for that one HTTP response.

---

## 6. Every file, explained

### `index.html`
The only HTML file. It contains an empty `<div id="root"></div>`. React fills that div with the
whole app. You'll rarely touch this.

### `src/main.tsx` — the entry point
Three lines of real work: import the global CSS, find `#root`, and render `<App />` into it.
This is the bridge from the HTML page to React.

### `src/types.ts` — the data shapes (no logic)
Pure TypeScript `interface` definitions describing every piece of JSON that moves between the
frontend and backend: the run request, the three checkpoint payloads, the decision shapes, and
the four output deliverables (scorecard, coverage map, redundancy report, optimised plan).
Think of it as the contract. If the backend's JSON shape changes, you update it here and
TypeScript shows you everywhere that needs fixing. **It produces no code at runtime** — types
vanish after compilation; they exist only to catch mistakes while you write.

### `src/api.ts` — talking to the backend
The **only** file that knows the backend URL and HTTP routes. It exposes four functions:
- `startRun(req)` → `POST /runs` (begin a run)
- `resumeRun(threadId, decision)` → `POST /runs/{id}/resume` (answer a checkpoint)
- `getRun(threadId)` → `GET /runs/{id}` (fetch the live audit log / errors)
- `checkHealth()` → `GET /health`

It also does an important job: **adapting the real backend shape to clean names.** The backend
calls the run id `run_id` and uses `status: "awaiting_approval"`; this file normalises those to
`threadId` and `status: "interrupted"` so the rest of the app stays tidy. It also turns network
errors into friendly messages. Keeping all of this in one file means no other component ever
deals with URLs or HTTP quirks.

### `src/App.tsx` — the brain / state machine
The top-level component. It holds **all** the important state with `useState`:
`view`, `threadId`, `checkpoint`, `hitlPayload`, `auditLog`, `toolErrors`, `outputs`, `busy`,
`error`. It defines the actions:
- `handleRun(req)` — called when you submit the form; calls `startRun`, then routes the result.
- `handleResume(decision)` — called when you approve a checkpoint; calls `resumeRun`.
- `applyResult(res)` — looks at the backend reply: if `interrupted`, show the right HITL card;
  if `completed`, show the results.
- a `useEffect` that, while a request is in flight, **polls** `getRun` every 2 seconds so the
  audit feed animates.

Then it simply renders the screen that matches `view`, passing the data down as props. Every
other component is "dumb": it receives props and reports clicks back up via callback props
(e.g. `onApprove`). All decisions live here.

### `src/components/InputPanel.tsx` — the start form
The first screen. Local `useState` for each field (suite path, project id, goal, coverage %,
risk areas, run mode). On submit it builds a `RunRequest` (converting the coverage % to a 0–1
number and splitting the comma-separated risk areas into a list) and calls the `onRun` prop.
The hero text at the top is just presentation.

### `src/components/AuditLog.tsx` — the live progress feed
Receives `entries` (the audit log) as a prop and renders them newest-at-bottom. It **translates**
the raw backend events into plain English (e.g. `intake/normalised_suite` → "Read 23 tests
(pytest framework)") via a `humanise()` function, formats timestamps in your local timezone, and
auto-scrolls. Read-only.

### `src/components/DegradedBanner.tsx` — the fallback notice
If the run has any `tool_errors` (e.g. the LLM was rate-limited and the agent used a
deterministic fallback), this shows a calm blue, dismissible banner explaining which capability
degraded. If there are no errors it renders nothing.

### `src/components/hitl/` — the three approval cards
Each is shown when the backend pauses at that checkpoint. They receive the checkpoint `payload`
and an `onApprove` callback:
- **`ApproveRemovals.tsx`** (checkpoint 1) — a table of flaky/duplicate candidates with
  checkboxes. Pinned (risk-area) tests show a lock and a disabled checkbox so they can never be
  selected. "Approve Selected" sends the chosen ids; "Skip" sends an empty list.
- **`ApproveRanking.tsx`** (checkpoint 2) — three columns (smoke / regression / full) showing the
  proposed tiers and the projected coverage. "Approve Ranking" confirms them.
- **`ApproveTests.tsx`** (checkpoint 3) — each generated test with its code, the criterion it
  covers, and a valid/invalid badge; plus a "Could not generate" section for dropped ones.
  Checkboxes choose which to keep.

### `src/components/results/` — the four result tabs
Shown when the run completes. `ResultsTabs.tsx` is just a tab switcher (it keeps which tab is
active in `useState`) that renders one of:
- **`HealthScorecard.tsx`** — six cards, each a 0–10 score coloured red/amber/green (a `null`
  score shows a grey "Needs data" badge, never 0), with the reason and recommended action.
- **`CoverageMap.tsx`** — a table of criteria → covering tests (covered / gap), and gap cards.
  If you approved a generated test for a gap, it shows "gap · test drafted" and names that test.
- **`RedundancyReport.tsx`** — duplicate clusters, flaky tests (with a fail-rate bar), slow tests.
- **`OptimisedPlan.tsx`** — current suite vs the proposed plan (tiers, removals, generated) and a
  one-line summary.

### `src/index.css` — all the styling
One stylesheet for the whole app: the dark theme colours (CSS variables at the top), layout,
cards, badges, the tier colours, the score colours, etc. Change a `--variable` at the top to
re-theme everything.

---

## 7. Following the data, end to end (a worked example)

1. You fill the form and click **Run Analysis**. `InputPanel` calls `onRun(request)`.
2. `App.handleRun` sets `view = "running"` (spinner shows) and calls `api.startRun(request)`.
3. `api.ts` does `POST /runs`, waits for the backend to reach checkpoint 1, and returns a
   normalised result `{ status: "interrupted", checkpoint: "approve_removals", payload }`.
4. `App.applyResult` stores the payload and sets `view = "hitl"`. React draws `ApproveRemovals`
   with that payload.
5. You tick boxes and click **Approve Selected**. The card calls `onApprove([...ids])`.
6. `App.handleResume` sets the spinner again and calls `api.resumeRun(threadId, ids)`
   (`POST /runs/{id}/resume`). The backend runs to checkpoint 2 and replies.
7. Steps 4–6 repeat for `approve_ranking` and `approve_tests`.
8. After the last approval the backend replies `{ status: "completed", outputs }`. `App` sets
   `view = "results"` and renders `ResultsTabs` with the four deliverables.

Throughout, a background timer polls `GET /runs/{id}` so the **Progress** feed fills in.

---

## 8. How to make common changes

- **Change the backend URL** → `API_BASE` constant at the top of `src/api.ts`.
- **Re-theme / change colours** → the `:root { --... }` variables at the top of `src/index.css`.
- **Add a field to the run form** → add state + an input in `InputPanel.tsx`, add the field to
  `RunRequest` in `types.ts`, and include it in the body in `api.ts`.
- **Show a new piece of a deliverable** → the four files in `components/results/` render the
  outputs; add to the matching one (and the type in `types.ts` if it's a new field).
- **Change how an audit event reads** → the `humanise()` function in `AuditLog.tsx`.

> Rule of thumb: data and decisions live in `App.tsx`; HTTP lives in `api.ts`; shapes live in
> `types.ts`; everything else is a presentational component that takes props and renders.
