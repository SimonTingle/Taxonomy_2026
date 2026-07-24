import { useEffect, useMemo, useState } from "react";
import Papa from "papaparse";

const LOW_CONFIDENCE = 0.4;

const REQUIRED_COLUMNS = ["doc_type", "confidence", "department"];

function parseCsvText(text) {
  const { data, meta } = Papa.parse(text, { header: true, skipEmptyLines: true });
  const missing = REQUIRED_COLUMNS.filter((c) => !meta.fields?.includes(c));
  if (missing.length) {
    throw new Error(
      `This doesn't look like a classified output file (missing column${missing.length > 1 ? "s" : ""}: ${missing.join(", ")}). ` +
      `Upload the CSV produced by the classifier (out/classified.csv), not the raw SharePoint export.`
    );
  }
  return data;
}

export default function App() {
  const [rows, setRows] = useState([]);
  const [source, setSource] = useState("none");
  const [error, setError] = useState("");
  const [pathStructures, setPathStructures] = useState(null);

  // Filters
  const [q, setQ] = useState("");
  const [dept, setDept] = useState("All");
  const [docType, setDocType] = useState("All");
  const [lowOnly, setLowOnly] = useState(false);
  const [sortKey, setSortKey] = useState("confidence");
  const [sortDir, setSortDir] = useState("asc");

  // Try to auto-load generated outputs from /public on first render.
  useEffect(() => {
    fetch("/classified.csv")
      .then((r) => (r.ok ? r.text() : Promise.reject()))
      .then((text) => {
        setRows(parseCsvText(text));
        setSource("auto-loaded from public/classified.csv");
      })
      .catch(() => setSource("none"));

    fetch("/summary.json")
      .then((r) => (r.ok ? r.json() : Promise.reject()))
      .then((summary) => setPathStructures(summary.path_structures || null))
      .catch(() => setPathStructures(null));
  }, []);

  function onUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setError("");
    const reader = new FileReader();
    reader.onload = () => {
      try {
        setRows(parseCsvText(reader.result));
        setSource(`uploaded: ${file.name}`);
      } catch (err) {
        setError(err.message || "Could not parse that CSV.");
      }
    };
    reader.readAsText(file);
  }

  const departments = useMemo(
    () => ["All", ...unique(rows.map((r) => r.department))],
    [rows]
  );
  const docTypes = useMemo(
    () => ["All", ...unique(rows.map((r) => r.doc_type))],
    [rows]
  );

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    let out = rows.filter((r) => {
      if (dept !== "All" && r.department !== dept) return false;
      if (docType !== "All" && r.doc_type !== docType) return false;
      if (lowOnly && Number(r.confidence) >= LOW_CONFIDENCE) return false;
      if (needle) {
        const hay = `${r.resolved_filename || ""} ${r.FileRef || r.path || ""}`.toLowerCase();
        if (!hay.includes(needle)) return false;
      }
      return true;
    });
    out = [...out].sort((a, b) => {
      let av = a[sortKey], bv = b[sortKey];
      if (sortKey === "confidence" || sortKey === "depth") {
        av = Number(av); bv = Number(bv);
      }
      if (av < bv) return sortDir === "asc" ? -1 : 1;
      if (av > bv) return sortDir === "asc" ? 1 : -1;
      return 0;
    });
    return out;
  }, [rows, q, dept, docType, lowOnly, sortKey, sortDir]);

  const stats = useMemo(() => computeStats(rows), [rows]);

  function toggleSort(key) {
    if (sortKey === key) setSortDir(sortDir === "asc" ? "desc" : "asc");
    else { setSortKey(key); setSortDir("asc"); }
  }

  return (
    <div className="app">
      <header>
        <h1>Document Taxonomy Review</h1>
        <p className="src">Source: {source}</p>
      </header>

      {rows.length === 0 ? (
        <div className="empty">
          <p>
            No data loaded. Run the classifier, copy <code>out/classified.csv</code> into{" "}
            <code>web/public/</code>, or upload it here:
          </p>
          <input type="file" accept=".csv" onChange={onUpload} />
          {error && <p className="err">{error}</p>}
        </div>
      ) : (
        <>
          <section className="cards">
            <Card label="Total files" value={stats.total.toLocaleString()} />
            <Card label="Classified" value={`${stats.classifiedPct}%`} />
            <Card label="Distinct types" value={stats.distinctTypes} />
            <Card label="Low confidence" value={stats.lowCount.toLocaleString()} tone="warn" />
          </section>

          <PathStructuresPanel data={pathStructures} />

          <section className="controls">
            <input
              className="search"
              placeholder="Search filename or path…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
            <Select label="Department" value={dept} onChange={setDept} options={departments} />
            <Select label="Doc type" value={docType} onChange={setDocType} options={docTypes} />
            <label className="check">
              <input type="checkbox" checked={lowOnly} onChange={(e) => setLowOnly(e.target.checked)} />
              Low-confidence only
            </label>
            <label className="upload">
              Replace data
              <input type="file" accept=".csv" onChange={onUpload} />
            </label>
          </section>

          {error && <p className="err">{error}</p>}
          <p className="count">{filtered.length.toLocaleString()} of {rows.length.toLocaleString()} rows</p>

          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <Th label="File" k="resolved_filename" {...{ sortKey, sortDir, toggleSort }} />
                  <Th label="Department" k="department" {...{ sortKey, sortDir, toggleSort }} />
                  <Th label="Function" k="function" {...{ sortKey, sortDir, toggleSort }} />
                  <Th label="Doc type" k="doc_type" {...{ sortKey, sortDir, toggleSort }} />
                  <Th label="Conf." k="confidence" {...{ sortKey, sortDir, toggleSort }} />
                  <Th label="Method" k="method" {...{ sortKey, sortDir, toggleSort }} />
                </tr>
              </thead>
              <tbody>
                {filtered.slice(0, 2000).map((r, i) => {
                  const low = Number(r.confidence) < LOW_CONFIDENCE;
                  return (
                    <tr key={i} className={low ? "low" : ""}>
                      <td title={r.FileRef || r.path}>{r.resolved_filename}</td>
                      <td>{r.department}</td>
                      <td>{r.function}</td>
                      <td>{r.doc_type}</td>
                      <td><ConfBar value={Number(r.confidence)} /></td>
                      <td className="muted">{r.method}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {filtered.length > 2000 && (
              <p className="muted note">Showing first 2,000 rows — narrow the filters to see more.</p>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function unique(arr) {
  return [...new Set(arr.filter(Boolean))].sort();
}

function computeStats(rows) {
  const total = rows.length;
  if (!total) return { total: 0, classifiedPct: 0, distinctTypes: 0, lowCount: 0 };
  const classified = rows.filter((r) => !(r.doc_type || "").startsWith("unclassified")).length;
  const lowCount = rows.filter((r) => Number(r.confidence) < LOW_CONFIDENCE).length;
  const distinctTypes = new Set(rows.map((r) => r.doc_type)).size;
  return {
    total,
    classifiedPct: Math.round((1000 * classified) / total) / 10,
    distinctTypes,
    lowCount,
  };
}

function PathStructuresPanel({ data }) {
  if (!data) return null;
  const { top_folders: topFolders = [], depth_distribution: depthDist = {}, common_templates: templates = [] } = data;
  if (!topFolders.length && !templates.length) return null;

  const maxFolderCount = Math.max(1, ...topFolders.map(([, c]) => c));
  const maxTemplateCount = Math.max(1, ...templates.map(([, c]) => c));

  return (
    <section className="path-structures">
      <h2>Path structures found in the data</h2>
      <p className="muted subtitle">
        Real folder patterns from this export — use these to inform the department/function
        taxonomy in <code>rules.yaml</code> (or the auto-generated <code>proposed_rules.yaml</code>).
      </p>
      <div className="ps-grid">
        <div className="ps-col">
          <h3>Top-level folders</h3>
          <ul className="ps-bars">
            {topFolders.slice(0, 12).map(([name, count]) => (
              <li key={name}>
                <span className="ps-label" title={name}>{name || "(none)"}</span>
                <span className="ps-bar-track">
                  <span className="ps-bar-fill" style={{ width: `${(count / maxFolderCount) * 100}%` }} />
                </span>
                <span className="ps-count">{count.toLocaleString()}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="ps-col">
          <h3>Depth distribution</h3>
          <ul className="ps-bars">
            {Object.entries(depthDist).map(([depth, count]) => (
              <li key={depth}>
                <span className="ps-label">{depth} level{depth === "1" ? "" : "s"}</span>
                <span className="ps-bar-track">
                  <span
                    className="ps-bar-fill alt"
                    style={{ width: `${(count / Math.max(1, ...Object.values(depthDist))) * 100}%` }}
                  />
                </span>
                <span className="ps-count">{count.toLocaleString()}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="ps-col">
          <h3>Common path templates (top 3 levels)</h3>
          <ul className="ps-bars">
            {templates.slice(0, 10).map(([template, count]) => (
              <li key={template}>
                <span className="ps-label" title={template}>{template || "(root)"}</span>
                <span className="ps-bar-track">
                  <span className="ps-bar-fill alt2" style={{ width: `${(count / maxTemplateCount) * 100}%` }} />
                </span>
                <span className="ps-count">{count.toLocaleString()}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

function Card({ label, value, tone }) {
  return (
    <div className={`card ${tone || ""}`}>
      <div className="card-value">{value}</div>
      <div className="card-label">{label}</div>
    </div>
  );
}

function Select({ label, value, onChange, options }) {
  return (
    <label className="field">
      <span>{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((o) => (
          <option key={o} value={o}>{o}</option>
        ))}
      </select>
    </label>
  );
}

function Th({ label, k, sortKey, sortDir, toggleSort }) {
  const active = sortKey === k;
  return (
    <th onClick={() => toggleSort(k)} className={active ? "sorted" : ""}>
      {label}{active ? (sortDir === "asc" ? " ▲" : " ▼") : ""}
    </th>
  );
}

function ConfBar({ value }) {
  const pct = Math.round((value || 0) * 100);
  const hue = Math.round((value || 0) * 120); // red -> green
  return (
    <div className="conf">
      <div className="conf-track">
        <div className="conf-fill" style={{ width: `${pct}%`, background: `hsl(${hue} 70% 45%)` }} />
      </div>
      <span>{pct}%</span>
    </div>
  );
}
