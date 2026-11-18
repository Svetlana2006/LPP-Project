import { useMemo, useState } from "react";

const INITIAL_SENDERS = [
  { id: "s-01", name: "Northstar Kitchen", supplyKg: 10, x: 3, y: 7 },
  { id: "s-02", name: "Olive & Grain", supplyKg: 10, x: 2, y: 7 },
  { id: "s-03", name: "Eastside Kitchen", supplyKg: 5, x: 0, y: 0 },
  { id: "s-04", name: "Market Café", supplyKg: 5, x: 2, y: 1 },
  { id: "s-05", name: "Green Table", supplyKg: 5, x: 4, y: 0 },
  { id: "s-06", name: "Corner Bakery", supplyKg: 5, x: 6, y: 1 },
  { id: "s-07", name: "River Deli", supplyKg: 5, x: 8, y: 2 },
];
const INITIAL_RECEIVERS = [
  { id: "r-01", name: "Harbor Food Bank", capacityKg: 10, x: 4, y: 7 },
  { id: "r-02", name: "Community Pantry", capacityKg: 10, x: 6, y: 9 },
  { id: "r-03", name: "Neighborhood Hub", capacityKg: 5, x: 9, y: 5 },
];
const numberFormat = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 2,
});

function formatKg(value) {
  return `${numberFormat.format(value ?? 0)} kg`;
}

function position(node) {
  return { x: node.x * 10, y: 100 - node.y * 10 };
}

function App() {
  const [senders, setSenders] = useState(INITIAL_SENDERS);
  const [receivers, setReceivers] = useState(INITIAL_RECEIVERS);
  const [kind, setKind] = useState("restaurant");
  const [name, setName] = useState("");
  const [amount, setAmount] = useState("20");
  const [x, setX] = useState(5);
  const [y, setY] = useState(5);
  const [maxDistanceKm, setMaxDistanceKm] = useState(4);
  const [result, setResult] = useState(null);
  const [resultMode, setResultMode] = useState(null);
  const [busy, setBusy] = useState(false);
  const [busyMode, setBusyMode] = useState(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const totalSupply = useMemo(
    () => senders.reduce((sum, node) => sum + Number(node.supplyKg || 0), 0),
    [senders],
  );
  const totalCapacity = useMemo(
    () => receivers.reduce((sum, node) => sum + Number(node.capacityKg || 0), 0),
    [receivers],
  );

  function invalidateResults() {
    setResult(null);
    setResultMode(null);
    setError("");
    setNotice("");
  }

  function setNodes(setter, update) {
    setter(update);
    invalidateResults();
  }

  function handleGridClick(event) {
    const bounds = event.currentTarget.getBoundingClientRect();
    const gridX = Math.round(((event.clientX - bounds.left) / bounds.width) * 10);
    const gridY = Math.round(((bounds.bottom - event.clientY) / bounds.height) * 10);
    setX(Math.max(0, Math.min(10, gridX)));
    setY(Math.max(0, Math.min(10, gridY)));
    setNotice(`Placement selected at (${Math.max(0, Math.min(10, gridX))}, ${Math.max(0, Math.min(10, gridY))}).`);
  }

  function addNode(event) {
    event.preventDefault();
    const label = name.trim();
    const quantity = Number(amount);
    if (!label || !Number.isFinite(quantity) || quantity <= 0) {
      setError("Enter a name and a quantity greater than zero.");
      return;
    }

    const node = {
      id: `${kind === "restaurant" ? "s" : "r"}-${crypto.randomUUID()}`,
      name: label,
      x: Number(x),
      y: Number(y),
      ...(kind === "restaurant"
        ? { supplyKg: quantity }
        : { capacityKg: quantity }),
    };
    if (kind === "restaurant") {
      setNodes(setSenders, (current) => [...current, node]);
    } else {
      setNodes(setReceivers, (current) => [...current, node]);
    }
    setName("");
    setNotice(`${label} added to the grid.`);
  }

  function updateNode(kindToUpdate, id, field, value) {
    const setter = kindToUpdate === "restaurant" ? setSenders : setReceivers;
    const list = kindToUpdate === "restaurant" ? senders : receivers;
    const next = list.map((node) =>
      node.id === id ? { ...node, [field]: value } : node,
    );
    setNodes(setter, next);
  }

  function removeNode(kindToRemove, id) {
    const setter = kindToRemove === "restaurant" ? setSenders : setReceivers;
    const list = kindToRemove === "restaurant" ? senders : receivers;
    setNodes(
      setter,
      list.filter((node) => node.id !== id),
    );
  }

  async function runModel(mode) {
    setBusy(true);
    setBusyMode(mode);
    setError("");
    setNotice("");
    try {
      const response = await fetch("/api/solve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mode,
          maxDistanceKm,
          senders,
          receivers,
        }),
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || `The model request failed (${response.status}).`);
      }
      setResult(data);
      setResultMode(mode);
    } catch (requestError) {
      setResult(null);
      setResultMode(null);
      setError(requestError.message || "Unable to run the model.");
    } finally {
      setBusy(false);
      setBusyMode(null);
    }
  }

  function resetExample() {
    setSenders(INITIAL_SENDERS);
    setReceivers(INITIAL_RECEIVERS);
    setMaxDistanceKm(4);
    setName("");
    setX(5);
    setY(5);
    setAmount("20");
    setKind("restaurant");
    invalidateResults();
    setNotice("Example restored. Apply the LP to see its allocation.");
  }

  const activeLp = result?.lp?.allocations ?? [];
  const activeGreedy = result?.greedy?.allocations ?? [];

  return (
    <main className="app-shell">
      <header className="topbar">
        <a className="brand" href="#" aria-label="Foodloop home">
          <span className="brand-mark">f</span>
          <span>foodloop<span className="brand-light"> / lab</span></span>
        </a>
        <span className="topbar-note"><span className="status-dot" /> Interactive model demo</span>
      </header>

      <section className="intro">
        <div>
          <p className="eyebrow">FOOD RESCUE · ALLOCATION LAB</p>
          <h1>Make every handoff<br /><em>count.</em></h1>
          <p className="intro-copy">
            Place restaurants and NGOs on the grid, set supply and capacity, then
            watch the LP plan an allocation and compare it with a nearest-first greedy baseline.
          </p>
        </div>
        <div className="intro-badge">
          <span className="badge-icon">↗</span>
          <span>One shared<br />set of inputs</span>
        </div>
      </section>

      <div className="workspace">
        <aside className="control-panel">
          <div className="section-heading">
            <span className="step-number">01</span>
            <div><h2>Build your network</h2><p>Add points and set quantities</p></div>
          </div>

          <div className="network-totals">
            <div><span>RESTAURANT SUPPLY</span><strong>{formatKg(totalSupply)}</strong></div>
            <div><span>NGO CAPACITY</span><strong>{formatKg(totalCapacity)}</strong></div>
          </div>

          <form className="node-form" onSubmit={addNode}>
            <div className="segmented" role="group" aria-label="Point type">
              <button
                type="button"
                className={kind === "restaurant" ? "selected restaurant-tab" : ""}
                onClick={() => setKind("restaurant")}
              >Restaurant</button>
              <button
                type="button"
                className={kind === "ngo" ? "selected ngo-tab" : ""}
                onClick={() => setKind("ngo")}
              >NGO</button>
            </div>
            <label className="field-label" htmlFor="point-name">Name</label>
            <input id="point-name" value={name} onChange={(event) => setName(event.target.value)} placeholder={kind === "restaurant" ? "e.g. Sunrise Kitchen" : "e.g. City Food Bank"} maxLength={70} />
            <label className="field-label" htmlFor="point-amount">{kind === "restaurant" ? "Available supply (kg)" : "Receiving capacity (kg)"}</label>
            <input id="point-amount" type="number" min="0.01" step="any" value={amount} onChange={(event) => setAmount(event.target.value)} required />
            <div className="coordinate-fields">
              <label><span>X · 0—10</span><input aria-label="X coordinate" type="number" min="0" max="10" step="1" value={x} onChange={(event) => setX(Number(event.target.value))} /></label>
              <label><span>Y · 0—10</span><input aria-label="Y coordinate" type="number" min="0" max="10" step="1" value={y} onChange={(event) => setY(Number(event.target.value))} /></label>
            </div>
            <p className="form-hint">Click anywhere on the grid to choose a point.</p>
            <button className={`add-button ${kind === "ngo" ? "add-ngo" : ""}`} type="submit">
              <span>＋</span> Add {kind === "restaurant" ? "restaurant" : "NGO"}
            </button>
          </form>

          <div className="point-list">
            <PointList
              title="Restaurants"
              kind="restaurant"
              nodes={senders}
              quantityKey="supplyKg"
              quantityLabel="Supply"
              onUpdate={updateNode}
              onRemove={removeNode}
            />
            <PointList
              title="NGOs"
              kind="ngo"
              nodes={receivers}
              quantityKey="capacityKg"
              quantityLabel="Capacity"
              onUpdate={updateNode}
              onRemove={removeNode}
            />
          </div>
          <button type="button" className="reset-button" onClick={resetExample}>↺ Restore example data</button>
        </aside>

        <section className="map-panel" aria-label="Allocation grid and results">
          <div className="map-header">
            <div className="section-heading compact">
              <span className="step-number">02</span>
              <div><h2>Allocation grid</h2><p>Click to place · drag not required</p></div>
            </div>
            <div className="map-legend">
              <span><i className="legend-dot restaurant-dot" />Restaurant</span>
              <span><i className="legend-dot ngo-dot" />NGO</span>
            </div>
          </div>

          <div className="grid-wrap">
            <div className="axis-label axis-y">GRID Y</div>
            <div className="axis-label axis-x">GRID X</div>
            <svg className="allocation-grid" viewBox="0 0 100 100" role="img" aria-label="Clickable grid plotting restaurant and NGO locations" onClick={handleGridClick}>
              <rect x="0" y="0" width="100" height="100" className="grid-background" />
              {Array.from({ length: 11 }, (_, index) => (
                <g key={index}>
                  <line x1={index * 10} y1="0" x2={index * 10} y2="100" className="grid-line" />
                  <line x1="0" y1={index * 10} x2="100" y2={index * 10} className="grid-line" />
                </g>
              ))}
              {resultMode === "compare" && activeGreedy.map((allocation, index) => {
                const from = senders.find((node) => node.id === allocation.senderId);
                const to = receivers.find((node) => node.id === allocation.receiverId);
                if (!from || !to) return null;
                const start = position(from);
                const end = position(to);
                return <line key={`greedy-${index}`} x1={start.x} y1={start.y} x2={end.x} y2={end.y} className="allocation-line greedy-line" strokeWidth={lineWidth(allocation.amountKg)}><title>{`Greedy: ${allocation.senderName} → ${allocation.receiverName}: ${formatKg(allocation.amountKg)}`}</title></line>;
              })}
              {resultMode && activeLp.map((allocation, index) => {
                const from = senders.find((node) => node.id === allocation.senderId);
                const to = receivers.find((node) => node.id === allocation.receiverId);
                if (!from || !to) return null;
                const start = position(from);
                const end = position(to);
                return <line key={`lp-${index}`} x1={start.x} y1={start.y} x2={end.x} y2={end.y} className="allocation-line lp-line" strokeWidth={lineWidth(allocation.amountKg)}><title>{`LP: ${allocation.senderName} → ${allocation.receiverName}: ${formatKg(allocation.amountKg)}`}</title></line>;
              })}
              {senders.map((node) => <GridNode key={node.id} node={node} kind="restaurant" />)}
              {receivers.map((node) => <GridNode key={node.id} node={node} kind="ngo" />)}
            </svg>
            {(senders.length === 0 || receivers.length === 0) && (
              <div className="grid-empty-state">
                Add at least one restaurant and one NGO to see the network here.
              </div>
            )}
            <div className="grid-scale"><span>0 km</span><span>10 grid units</span></div>
          </div>

          <div className="distance-control">
            <div><span className="field-label">Maximum pair distance</span><p>Beyond this radius, a restaurant–NGO pair is unavailable.</p></div>
            <label className="range-value" htmlFor="distance-limit">{maxDistanceKm.toFixed(1)} <small>grid km</small></label>
            <input id="distance-limit" type="range" min="1" max="15" step="0.5" value={maxDistanceKm} onChange={(event) => { setMaxDistanceKm(Number(event.target.value)); invalidateResults(); }} />
            <div className="range-ends"><span>1</span><span>15</span></div>
          </div>

          <div className="model-actions">
            <button className="primary-action" type="button" disabled={busy || senders.length === 0 || receivers.length === 0} onClick={() => runModel("lp")}>
              {busy && busyMode === "lp" ? <span className="spinner" /> : <span className="action-icon">✳</span>}
              Apply LP model
            </button>
            <button className="secondary-action" type="button" disabled={busy || !result || resultMode === "compare" || senders.length === 0 || receivers.length === 0} onClick={() => runModel("compare")}>
              {busy && busyMode === "compare" ? <span className="spinner" /> : <span className="action-icon">⇄</span>}
              Compare results with greedy algorithm
            </button>
          </div>
          {error && <div className="message error-message" role="alert">{error}</div>}
          {notice && <div className="message notice-message" role="status">{notice}</div>}
          <p className="model-disclaimer">
            Scenario demo only. Grid distance is synthetic Euclidean distance (1 grid unit = 1 km), not a road route.
            Entered quantities are illustrative, not observed food surplus or NGO capacity.
          </p>

          {result && <Results result={result} mode={resultMode} />}
        </section>
      </div>
      <footer className="footer"><span>FOODLOOP · ALLOCATION LAB</span><span>Optimize the handoff, not the assumption.</span></footer>
    </main>
  );
}

function lineWidth(amount) {
  return Math.min(2.4, 0.6 + Math.sqrt(amount) * 0.12);
}

function GridNode({ node, kind }) {
  const point = position(node);
  const isRestaurant = kind === "restaurant";
  const color = isRestaurant ? "#e7735e" : "#237b68";
  return (
    <g className={`grid-node ${isRestaurant ? "restaurant-node" : "ngo-node"}`} transform={`translate(${point.x} ${point.y})`} pointerEvents="none">
      <circle className="node-halo" r="4.8" fill="#fff" stroke={color} strokeWidth="1.5" />
      {isRestaurant
        ? <circle className="node-core" r="3.5" fill={color} />
        : <rect className="node-core ngo-core" x="-3.3" y="-3.3" width="6.6" height="6.6" rx="1.2" fill={color} />}
      <text className="node-type-mark" x="0" y="1.25">{isRestaurant ? "R" : "N"}</text>
      <text className="node-label" x="3.7" y="-3.5">{node.name.length > 17 ? `${node.name.slice(0, 16)}…` : node.name}</text>
      <title>{`${isRestaurant ? "Restaurant" : "NGO"}: ${node.name} (${node.x}, ${node.y})`}</title>
    </g>
  );
}

function PointList({ title, kind, nodes, quantityKey, quantityLabel, onUpdate, onRemove }) {
  const isRestaurant = kind === "restaurant";
  return (
    <section className="list-section">
      <h3><span className={`mini-dot ${isRestaurant ? "restaurant-dot" : "ngo-dot"}`} />{title}<span className="list-count">{nodes.length}</span></h3>
      {nodes.length === 0 ? <p className="empty-list">No {title.toLowerCase()} added yet.</p> : nodes.map((node) => (
        <div className="point-row" key={node.id}>
          <div className="point-row-top">
            <input className="point-name" aria-label={`${title} name`} value={node.name} onChange={(event) => onUpdate(kind, node.id, "name", event.target.value)} />
            <button className="remove-point" type="button" aria-label={`Remove ${node.name}`} onClick={() => onRemove(kind, node.id)}>×</button>
          </div>
          <div className="point-row-bottom">
            <label>{quantityLabel}<input aria-label={`${node.name} ${quantityLabel.toLowerCase()} in kilograms`} type="number" min="0" step="any" value={node[quantityKey]} onChange={(event) => onUpdate(kind, node.id, quantityKey, event.target.value === "" ? "" : Number(event.target.value))} /><span>kg</span></label>
            <span className="coordinates">({node.x}, {node.y})</span>
          </div>
        </div>
      ))}
    </section>
  );
}

function Results({ result, mode }) {
  const comparing = mode === "compare";
  const delta = result.differenceKg ?? 0;
  return (
    <section className="results-section" aria-live="polite">
      <div className="results-title">
        <div className="section-heading compact">
          <span className="step-number">03</span>
          <div><h2>{comparing ? "Side-by-side results" : "LP allocation"}</h2><p>{comparing ? "Same inputs · same eligibility radius" : "Two-stage optimization completed"}</p></div>
        </div>
        <span className="result-pill"><i />OPTIMAL</span>
      </div>
      <div className={`metric-grid ${comparing ? "comparison-metrics" : ""}`}>
        <Metric label="LP allocated" value={formatKg(result.lp.allocatedKg)} tone="lp-metric" />
        {comparing && <Metric label="Greedy allocated" value={formatKg(result.greedy.allocatedKg)} tone="greedy-metric" />}
        {comparing
          ? <Metric label={delta > 1e-7 ? "LP advantage" : "Allocation result"} value={Math.abs(delta) <= 1e-7 ? "Tie" : `+${formatKg(delta)}`} tone="delta-metric" />
          : <Metric label="LP distance cost" value={`${numberFormat.format(result.lp.kgKm)} kg-km`} tone="cost-metric" />}
      </div>
      {comparing && (
        <p className={`comparison-note ${delta > 1e-7 ? "positive-note" : "tie-note"}`}>
          {delta > 1e-7
            ? `For these inputs, the LP allocated ${formatKg(delta)} more than sender-ID greedy.`
            : "For these inputs, LP and greedy allocated the same total. A tie is a valid result."}
          {" "}The LP maximizes kilograms first; strict improvement is not guaranteed.
        </p>
      )}
      <div className="allocation-legend">
        <span><i className="line-key lp-key" />LP allocation</span>
        {comparing && <span><i className="line-key greedy-key" />Greedy allocation</span>}
        <span className="legend-spacer">Line width indicates kg assigned</span>
      </div>
      <div className="allocation-tables">
        <AllocationTable title="LP · stage 2" rows={result.lp.allocations} total={result.lp.allocatedKg} />
        {comparing && <AllocationTable title="Greedy · sender ID order" rows={result.greedy.allocations} total={result.greedy.allocatedKg} />}
      </div>
      <p className="result-footnote">The LP’s distance objective is grid-distance-weighted kg (kg-km); it is not a multi-stop vehicle route.</p>
    </section>
  );
}

function Metric({ label, value, tone }) {
  return <div className={`metric-card ${tone}`}><span>{label}</span><strong>{value}</strong></div>;
}

function AllocationTable({ title, rows, total }) {
  return (
    <div className="allocation-table-wrap">
      <div className="table-heading"><strong>{title}</strong><span>{formatKg(total)}</span></div>
      {rows.length === 0 ? <p className="no-allocations">No eligible allocation was possible.</p> : (
        <div className="allocation-rows">
          {rows.map((row, index) => (
            <div className="allocation-row" key={`${row.senderId}-${row.receiverId}-${index}`}>
              <div><strong>{row.senderName}</strong><span>to {row.receiverName}</span></div>
              <strong>{formatKg(row.amountKg)}</strong>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default App;
