import React, { useState, useRef, useEffect } from 'react';
import Plot from 'react-plotly.js';

// --- Helper Components & Data ---

const Spinner = () => <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>;

// --- Example queries for cards (shortened descriptions, same length) ---
const EXAMPLES = [
  {
    label: "Descriptive",
    sub: "About schema/structure.",
    eg: "What tables are in the database?",
    tooltip: "e.g. What tables are in the database?"
  },
  {
    label: "Data Query",
    sub: "Get data or summaries.",
    eg: "Show me total sales by category",
    tooltip: "e.g. Show me total sales by category"
  },
  {
    label: "Destructive (Blocked)",
    sub: "Blocked for safety.",
    eg: "Delete all records",
    tooltip: "e.g. Delete all records"
  }
];

// --- Visualization Components (Plotly) ---
const DEEP_NAVY = '#1a2a6c';

function formatValue(val, isCurrency = false) {
  if (isCurrency && typeof val === 'number') {
    // Show as $437,231 (no decimals, no k suffix)
    return '$' + Math.round(val).toLocaleString();
  }
  if (typeof val === 'number') {
    return Math.round(val * 10) / 10;
  }
  return val;
}

const PlotlyBarChart = ({ data, xKey, yKey, xTitle, yTitle, isCurrency }) => (
  <Plot
    data={[
      {
        x: data.map(row => row[xKey]),
        y: data.map(row => row[yKey]),
        type: 'bar',
        marker: { color: DEEP_NAVY },
        text: data.map(row => formatValue(row[yKey], isCurrency)),
        textposition: 'auto',
        hovertemplate: isCurrency
          ? `%{x}<br>${yTitle}: %{text}<extra></extra>`
          : `%{x}<br>${yTitle}: %{y}<extra></extra>`,
      }
    ]}
    layout={{
      autosize: true,
      margin: { t: 40, l: 60, r: 20, b: 60 },
      xaxis: { title: xTitle, tickfont: { size: 14 } },
      yaxis: { title: yTitle, tickfont: { size: 14 } },
      plot_bgcolor: '#fff',
      paper_bgcolor: '#fff',
      font: { family: "'Manrope', sans-serif", color: DEEP_NAVY },
      showlegend: false,
      height: 340,
    }}
    useResizeHandler
    style={{ width: "100%", height: "100%" }}
    config={{ displayModeBar: false }}
  />
);

const PlotlyLineChart = ({ data, xKey, yKey, xTitle, yTitle, isCurrency }) => (
  <Plot
    data={[
      {
        x: data.map(row => row[xKey]),
        y: data.map(row => row[yKey]),
        type: 'scatter',
        mode: 'lines+markers',
        marker: { color: DEEP_NAVY },
        line: { color: DEEP_NAVY },
        text: data.map(row => formatValue(row[yKey], isCurrency)),
        textposition: 'top',
        hovertemplate: isCurrency
          ? `%{x}<br>${yTitle}: %{text}<extra></extra>`
          : `%{x}<br>${yTitle}: %{y}<extra></extra>`,
      }
    ]}
    layout={{
      autosize: true,
      margin: { t: 40, l: 60, r: 20, b: 60 },
      xaxis: { title: xTitle, tickfont: { size: 14 } },
      yaxis: { title: yTitle, tickfont: { size: 14 } },
      plot_bgcolor: '#fff',
      paper_bgcolor: '#fff',
      font: { family: "'Manrope', sans-serif", color: DEEP_NAVY },
      showlegend: false,
      height: 340,
    }}
    useResizeHandler
    style={{ width: "100%", height: "100%" }}
    config={{ displayModeBar: false }}
  />
);

const PlotlyPieChart = ({ data, nameKey, valueKey }) => (
  <Plot
    data={[
      {
        labels: data.map(row => row[nameKey]),
        values: data.map(row => row[valueKey]),
        type: 'pie',
        marker: { colors: ['#f40082', '#ff6600', '#00e5ff', '#1a2a6c', '#8884d8'] },
        textinfo: 'label+percent',
        insidetextorientation: 'radial',
      }
    ]}
    layout={{
      autosize: true,
      margin: { t: 40, l: 20, r: 20, b: 20 },
      legend: { orientation: 'h', y: -0.1 },
      font: { family: "'Manrope', sans-serif", color: '#1a2a6c' },
      height: 340,
    }}
    useResizeHandler
    style={{ width: "100%", height: "100%" }}
    config={{ displayModeBar: false }}
  />
);

// Table and KPI remain unchanged
const ResultTable = ({ data }) => {
    if (!data || data.length === 0) return null;
    const headers = Object.keys(data[0]);
    // Heuristic: detect currency columns
    const isCurrencyCol = (col) =>
      col.toLowerCase().match(/amount|revenue|sales|price|cost|payment|charge|fee|balance/);

    return (
        <div className="overflow-x-auto">
            <table className="w-full text-left">
                <thead>
                    <tr className="bg-fs-blue/50">
                        {headers.map(header => <th key={header} className="p-3 uppercase tracking-wider text-sm">{header.replace(/_/g, ' ')}</th>)}
                    </tr>
                </thead>
                <tbody>
                    {data.map((row, index) => (
                        <tr key={index} className="border-b border-fs-blue/50 hover:bg-fs-blue/30">
                            {headers.map(header => (
                              <td key={header} className="p-3">
                                {isCurrencyCol(header) && typeof row[header] === 'number'
                                  ? '$' + Math.round(row[header]).toLocaleString()
                                  : (typeof row[header] === 'number'
                                      ? Math.round(row[header] * 10) / 10
                                      : row[header]
                                    )
                                }
                              </td>
                            ))}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    )
};


// --- Main App Component ---
function groupHistoryByBucket(history) {
  const today = new Date();
  const startOfToday = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const sevenDaysAgo = new Date(startOfToday);
  sevenDaysAgo.setDate(startOfToday.getDate() - 6);

  const buckets = {
    today: [],
    last7: [],
    older: [],
  };

  history.forEach((item, idx) => {
    const itemDate = new Date(item.timestamp);
    if (itemDate >= startOfToday) {
      buckets.today.push({ ...item, idx });
    } else if (itemDate >= sevenDaysAgo) {
      buckets.last7.push({ ...item, idx });
    } else {
      buckets.older.push({ ...item, idx });
    }
  });

  return [
    { label: "Today", items: buckets.today.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp)) },
    { label: "Last 7 Days", items: buckets.last7.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp)) },
    { label: "More than a week ago", items: buckets.older.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp)) }
  ].filter(bucket => bucket.items.length > 0);
}

function App() {
  const [query, setQuery] = useState('');
  const [selectedIdx, setSelectedIdx] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [history, setHistory] = useState([]);
  const [dateFilter, setDateFilter] = useState("");
  const [showDatePicker, setShowDatePicker] = useState(false);
  const [search, setSearch] = useState("");
  const [showSearch, setShowSearch] = useState(false);
  const [isHome, setIsHome] = useState(true);
  const [pendingQuery, setPendingQuery] = useState(null);
  const [userChartType, setUserChartType] = useState(null);
  const textareaRef = useRef(null);
  const searchRef = useRef(null);
  const filterRef = useRef(null);

  // --- Close popovers on outside click ---
  useEffect(() => {
    function handleClickOutside(e) {
      if (showSearch && searchRef.current && !searchRef.current.contains(e.target)) {
        setShowSearch(false);
      }
      if (showDatePicker && filterRef.current && !filterRef.current.contains(e.target)) {
        setShowDatePicker(false);
      }
    }
    if (showSearch || showDatePicker) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [showSearch, showDatePicker]);

  // --- Define handleTextareaKeyDown before JSX usage ---
  const handleTextareaKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!isLoading && query.trim()) {
        document.getElementById('query-form').dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
      }
    }
  };

  // Show the latest or selected history item
  const current = (!isHome && selectedIdx !== null && history[selectedIdx])
    ? history[selectedIdx]
    : (!isHome && selectedIdx === null && history.length > 0 && !pendingQuery)
      ? history[history.length - 1]
      : null;

  // --- Helper to determine intent for current item ---
  function getCurrentIntent(item) {
    if (!item) return null;
    if (item.sql === "BLOCKED" || (item.error && item.error.toLowerCase().includes("blocked"))) return "destructive_request";
    if (item.sql === "N/A" && (!item.data || item.data.length === 0)) return "descriptive_question";
    return "data_query";
  }

  // --- UI logic for centering and loading spinner ---
  const isCentered = isHome || pendingQuery || isLoading;

  // Prevent infinite loading: Only set isLoading to true when submitting, and always set to false in finally
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    setIsLoading(true);
    setError('');
    setPendingQuery(query); // Mark that a query is pending

    try {
      const backendUrl = 'http://127.0.0.1:8000/get-insight';
      const response = await fetch(backendUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: query }),
      });

      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
      const data = await response.json();

      setHistory(prev => [
        ...prev,
        {
          question: query,
          sql: data.sql,
          data: data.data,
          narrative: data.narrative,
          bullets: data.bullets,
          chartType: data.chartType,
          error: data.error,
          timestamp: new Date().toISOString(),
        }
      ]);
      setSelectedIdx(history.length);
      setQuery('');
      setIsHome(false); // Ensure home is false after submit
    } catch (err) {
      setError('Failed to get a response from the backend. Please ensure it is running and accessible.');
    } finally {
      setIsLoading(false); // Always set loading to false
      setPendingQuery(null); // Clear pending state
    }
  };

  // Auto-expand textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = textareaRef.current.scrollHeight + "px";
    }
  }, [query]);

  // When a suggestion card is clicked, run its example and exit home mode
  const handleCardClick = (example) => {
    setIsHome(false);        // Set home to false immediately
    setSelectedIdx(null);    // Clear any previous selection immediately
    setQuery(example.eg);
    setPendingQuery(example.eg); // Mark pending query for loading state
    setTimeout(() => {
      document.getElementById('query-form').dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
    }, 0);
  };

  // New chat resets state and returns to home
  const handleNewChat = () => {
    setIsHome(true);
    setQuery('');
    setSelectedIdx(null);
    setPendingQuery(null);
  };

  // Filtered and grouped history by search and date
  const filteredHistory = history.filter(item => {
    const dateMatch = !dateFilter || new Date(item.timestamp).toISOString().slice(0, 10) === dateFilter;
    const searchMatch = !search || item.question.toLowerCase().includes(search.toLowerCase());
    return dateMatch && searchMatch;
  });
  const groupedHistory = groupHistoryByBucket(filteredHistory);

  // --- Chart type selector (move to top-level so it's always defined) ---
  const chartTypes = [
    { value: 'bar', label: 'Bar' },
    { value: 'line', label: 'Line' },
    { value: 'pie', label: 'Pie' },
    { value: 'table', label: 'Table' },
    { value: 'kpi', label: 'KPI' }
  ];

  // --- Visualization rendering with Plotly (use axisTitles from backend) ---
  const renderVisualization = (item) => {
    if (!item || !item.data || item.data.length === 0) return <p className="text-center text-gray-400 text-base">No data returned from the query.</p>;
    const chartType = userChartType || item.chartType;
    const keys = Object.keys(item.data[0]);
    // Always use axisTitles from backend if present, and pass to Plotly
    const x = (item.axisTitles && item.axisTitles.x) ? item.axisTitles.x : (keys[0] ? keys[0].replace(/_/g, ' ') : 'X');
    const y = (item.axisTitles && item.axisTitles.y) ? item.axisTitles.y : (keys[1] ? keys[1].replace(/_/g, ' ') : 'Y');
    const isCurrency = y.toLowerCase().match(/amount|revenue|sales|price|cost|payment|charge|fee|balance/) ||
      (keys[1] && keys[1].toLowerCase().match(/amount|revenue|sales|price|cost|payment|charge|fee|balance/));

    switch(chartType) {
      case 'kpi': return <KpiCard data={item.data} />;
      case 'bar':
        if (keys.length >= 2) return <PlotlyBarChart data={item.data} xKey={keys[0]} yKey={keys[1]} xTitle={x} yTitle={y} isCurrency={isCurrency} />;
        return <ResultTable data={item.data} />;
      case 'line':
        if (keys.length >= 2) return <PlotlyLineChart data={item.data} xKey={keys[0]} yKey={keys[1]} xTitle={x} yTitle={y} isCurrency={isCurrency} />;
        return <ResultTable data={item.data} />;
      case 'pie':
        if (keys.length >= 2) return <PlotlyPieChart data={item.data} nameKey={keys[0]} valueKey={keys[1]} />;
        return <ResultTable data={item.data} />;
      case 'table':
      default:
        // Pass formatted data to table
        return <ResultTable data={item.data} />;
    }
  };

  // --- UI ---
  const hasResults = !isHome && !!(history.length && (selectedIdx !== null || history.length > 0)) && !pendingQuery;

  return (
    <div className="bg-fs-bg min-h-screen flex flex-row font-sans text-base" style={{ fontFamily: "'Manrope', sans-serif", fontSize: 16 }}>
      {/* --- Sidebar: Recent Questions (LEFT, grouped by bucket) --- */}
      <aside className="w-96 min-h-screen bg-[#f3f4f6] border-r border-fs-border shadow-soft flex flex-col py-10 px-4">
        {/* Recent Chats Heading Row */}
        <div className="flex items-center mb-2 gap-2">
          <h2 className="text-[20px] font-semibold text-fs-primary uppercase tracking-wider flex-1 text-left">Recent Chats</h2>
          <div className="flex items-center gap-2 relative">
            {/* Filter button with calendar popover */}
            <div className="relative" ref={filterRef}>
              <button
                className="bg-[#f3f4f6] border border-fs-border rounded-full px-3 py-1 text-xs text-fs-primary hover:bg-[#e5e7eb] transition-all duration-200"
                onClick={() => setShowDatePicker(v => !v)}
                type="button"
                style={{ minWidth: 32, minHeight: 32 }}
                title="Filter by date"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="inline w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <rect x="3" y="5" width="18" height="16" rx="2" strokeWidth="2" stroke="currentColor" fill="none"/>
                  <path d="M16 3v4M8 3v4M3 9h18" strokeWidth="2" stroke="currentColor" fill="none"/>
                </svg>
              </button>
              {showDatePicker && (
                <div className="absolute right-0 mt-2 z-20 bg-white border border-fs-border rounded shadow-lg p-2">
                  <input
                    type="date"
                    value={dateFilter}
                    onChange={e => { setDateFilter(e.target.value); setShowDatePicker(false); }}
                    className="px-2 py-1 rounded border border-fs-border bg-white text-xs text-fs-primary focus:outline-none focus:ring-1 focus:ring-fs-primary"
                    style={{ width: 120, minWidth: 80 }}
                    autoFocus
                  />
                  {dateFilter && (
                    <button
                      className="ml-2 text-xs text-fs-muted hover:text-fs-primary"
                      onClick={() => setDateFilter("")}
                      type="button"
                      title="Clear filter"
                    >✕</button>
                  )}
                </div>
              )}
            </div>
            {/* Search button with animated input */}
            <div className="relative" ref={searchRef}>
              <button
                className={`bg-[#f3f4f6] border border-fs-border rounded-full px-3 py-1 text-xs text-fs-primary hover:bg-[#e5e7eb] transition-all duration-200 ${showSearch ? "ring-2 ring-fs-primary" : ""}`}
                type="button"
                style={{ minWidth: 32, minHeight: 32, zIndex: 10 }}
                title="Search"
                onClick={() => setShowSearch(v => !v)}
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="inline w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <circle cx="11" cy="11" r="7" strokeWidth="2" stroke="currentColor" fill="none"/>
                  <line x1="21" y1="21" x2="16.65" y2="16.65" strokeWidth="2" stroke="currentColor"/>
                </svg>
              </button>
              <div className={`absolute right-0 mt-2 transition-all duration-300 ${showSearch ? "opacity-100 scale-100" : "opacity-0 scale-95 pointer-events-none"}`}>
                <input
                  id="recent-search-input"
                  type="text"
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  placeholder="Search your recent chats..."
                  className="bg-white border border-fs-border rounded px-2 py-1 text-xs text-fs-primary focus:outline-none focus:ring-1 focus:ring-fs-primary transition-all duration-200 w-48"
                  style={{ minWidth: 120 }}
                  autoFocus={showSearch}
                />
              </div>
            </div>
          </div>
        </div>
        {/* New Chat Option (minimal, subtle) */}
        <button
          className="mb-4 mt-2 mx-auto w-fit bg-[#e5e7eb] text-fs-primary rounded-full py-1 px-4 text-sm font-normal shadow-none hover:bg-[#d1d5db] transition-all duration-200"
          onClick={handleNewChat}
        >
          + New Chat
        </button>
        {/* Recent Chats Buckets */}
        <div className="flex flex-col gap-6">
          {groupedHistory.length === 0 && (
            <div className="text-fs-muted text-sm">No questions yet.</div>
          )}
          {groupedHistory.map(bucket => (
            <div key={bucket.label}>
              <div className="text-sm text-fs-muted font-semibold mb-2 uppercase tracking-wider">{bucket.label}</div>
              <div className="flex flex-col gap-2">
                {bucket.items.map(item => (
                  <button
                    key={item.timestamp}
                    className={`text-left border border-fs-border rounded-xl px-4 py-3 transition-all duration-200
                      ${selectedIdx === item.idx ? 'bg-gray-200 border-gray-400' : 'bg-white'}
                      hover:bg-gray-100
                    `}
                    onClick={() => { setSelectedIdx(item.idx); setIsHome(false); }}
                  >
                    <div className="font-semibold text-fs-primary truncate text-base">{item.question}</div>
                    {item.narrative && (
                      <div className="text-xs text-fs-muted mt-1">{item.narrative.slice(0, 60)}{item.narrative.length > 60 ? '...' : ''}</div>
                    )}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </aside>

      {/* --- Main Console --- */}
      <main className={`flex-1 flex flex-col items-center ${hasResults ? "justify-start" : "justify-center"} py-12 px-8 transition-all duration-300`}>
        {/* Heading always at the top */}
        <div className="w-full max-w-4xl flex flex-col items-center">
          <h1 className="text-[36px] font-medium text-fs-primary mb-0 tracking-tight leading-tight text-center" style={{ fontFamily: "'Manrope', sans-serif" }}>
            GenAI Powered Data Query Tool
          </h1>
        </div>
        {/* Vertically center example cards and question box together when home or loading */}
        {isCentered ? (
          <div className="flex flex-col items-center justify-center flex-1 w-full" style={{ minHeight: 400 }}>
            {/* Example cards on top */}
            <div className="flex gap-2 w-full max-w-2xl mx-auto justify-center mb-2">
              {EXAMPLES.map((ex, i) => (
                <button
                  key={ex.label}
                  className="flex-1 flex flex-col items-start justify-center min-w-0 px-3 py-2 rounded-lg border border-fs-border bg-[#f3f4f6] shadow-none hover:bg-[#e5e7eb] transition-all duration-200"
                  onClick={() => handleCardClick(ex)}
                  type="button"
                  style={{ fontFamily: "'Manrope', sans-serif", minWidth: 0, maxWidth: "none", textAlign: "left" }}
                >
                  <span
                    className="text-xs text-fs-primary mb-0.5 w-full"
                    style={{
                      fontWeight: 200,
                      letterSpacing: 0,
                      textAlign: "left",
                      display: "block"
                    }}
                  >
                    {ex.label}
                  </span>
                  <span className="text-xs text-fs-muted w-full" style={{ textAlign: "left", display: "block" }}>
                    {ex.sub}
                    <span className="ml-1 text-xs text-fs-muted">eg: {ex.eg}</span>
                  </span>
                </button>
              ))}
            </div>
            {/* Minimal gap between example cards and question box */}
            <form
              id="query-form"
              onSubmit={handleSubmit}
              className="w-full max-w-4xl mb-0 flex flex-col items-center"
              autoComplete="off"
            >
              <div
                className="w-full relative flex flex-col items-stretch justify-center rounded-2xl"
                style={{
                  minHeight: 44,
                  background: "#e0e4ea",
                  transition: "min-height 0.2s",
                  // Maintain shape after query is executed
                }}
              >
                {/* Upper section: textarea */}
                <div className="flex w-full items-end px-2 pt-1 pb-1 relative">
                  <textarea
                    ref={textareaRef}
                    value={query}
                    onChange={e => setQuery(e.target.value)}
                    onKeyDown={handleTextareaKeyDown}
                    placeholder=""
                    rows={1}
                    className="flex-1 resize-none bg-transparent border-none outline-none text-base text-fs-primary placeholder-fs-muted focus:ring-0 focus:outline-none"
                    disabled={isLoading}
                    style={{
                      fontFamily: "'Manrope', sans-serif",
                      fontSize: 16,
                      minHeight: 32,
                      maxHeight: 200,
                      overflowY: 'hidden',
                      paddingTop: 7,
                      paddingBottom: 0,
                      paddingLeft: 10,
                      paddingRight: 10,
                      lineHeight: '32px',
                      resize: 'none',
                      boxSizing: 'border-box',
                      width: '100%',
                      transition: "min-height 0.2s"
                    }}
                    onInput={e => {
                      e.target.style.height = "32px";
                      e.target.style.height = Math.min(e.target.scrollHeight, 200) + "px";
                    }}
                  />
                  {!query && (
                    <span
                      className="absolute left-2 right-2 text-fs-muted pointer-events-none select-none"
                      style={{
                        top: 12,
                        bottom: 0,
                        height: 32,
                        display: 'flex',
                        alignItems: 'center',
                        fontSize: 16,
                        fontFamily: "'Manrope', sans-serif",
                        color: '#6b7280',
                        opacity: 0.8,
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        paddingLeft: 10,
                        paddingRight: 10
                      }}
                    >
                      Ask a question about your data to get started
                    </span>
                  )}
                </div>
                {/* Lower section: Ask button only */}
                <div className="flex w-full items-center justify-end px-2 pb-1">
                  <button
                    type="submit"
                    className="bg-fs-primary hover:bg-fs-blue text-white rounded-full px-4 py-1 text-sm font-medium transition-all duration-200 shadow-soft disabled:opacity-60 flex items-center justify-center h-7"
                    disabled={isLoading || !query.trim()}
                    style={{ fontFamily: "'Manrope', sans-serif", minWidth: 48, fontSize: 14 }}
                  >
                    {isLoading ? <Spinner /> : "Ask"}
                  </button>
                </div>
              </div>
            </form>
            {/* Loading spinner if pendingQuery */}
            {pendingQuery && (
              <div className="mt-6 flex items-center gap-2 text-fs-muted text-base">
                <Spinner />
                <span>Getting your answer...</span>
              </div>
            )}
          </div>
        ) : (
          <>
            {/* Question box and results when not home and not loading */}
            <form
              id="query-form"
              onSubmit={handleSubmit}
              className={`w-full max-w-4xl ${hasResults ? "mb-4" : "mb-0"} flex flex-col items-center`}
              autoComplete="off"
            >
              <div className="w-full relative flex flex-col items-stretch justify-center rounded-2xl" style={{ minHeight: 60, background: "#e0e4ea" }}>
                {/* Upper section: textarea */}
                <div className="flex w-full items-end px-2 pt-1 pb-1 relative">
                  <textarea
                    ref={textareaRef}
                    value={query}
                    onChange={e => setQuery(e.target.value)}
                    onKeyDown={handleTextareaKeyDown}
                    placeholder=""
                    rows={1}
                    className="flex-1 resize-none bg-transparent border-none outline-none text-base text-fs-primary placeholder-fs-muted focus:ring-0 focus:outline-none"
                    disabled={isLoading}
                    style={{
                      fontFamily: "'Manrope', sans-serif",
                      fontSize: 16,
                      minHeight: 32,
                      maxHeight: 200,
                      overflowY: 'hidden',
                      paddingTop: 7,
                      paddingBottom: 0,
                      paddingLeft: 10,
                      paddingRight: 10,
                      lineHeight: '32px',
                      resize: 'none',
                      boxSizing: 'border-box',
                      width: '100%',
                      transition: "min-height 0.2s"
                    }}
                    onInput={e => {
                      e.target.style.height = "32px";
                      e.target.style.height = Math.min(e.target.scrollHeight, 200) + "px";
                    }}
                  />
                  {!query && (
                    <span
                      className="absolute left-2 right-2 text-fs-muted pointer-events-none select-none"
                      style={{
                        top: 12,
                        bottom: 0,
                        height: 32,
                        display: 'flex',
                        alignItems: 'center',
                        fontSize: 16,
                        fontFamily: "'Manrope', sans-serif",
                        color: '#6b7280',
                        opacity: 0.8,
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        paddingLeft: 10,
                        paddingRight: 10
                      }}
                    >
                      Ask a question about your data to get started
                    </span>
                  )}
                </div>
                {/* Lower section: Ask button only */}
                <div className="flex w-full items-center justify-end px-2 pb-1">
                  <button
                    type="submit"
                    className="bg-fs-primary hover:bg-fs-blue text-white rounded-full px-4 py-1 text-sm font-medium transition-all duration-200 shadow-soft disabled:opacity-60 flex items-center justify-center h-7"
                    disabled={isLoading || !query.trim()}
                    style={{ fontFamily: "'Manrope', sans-serif", minWidth: 48, fontSize: 14 }}
                  >
                    {isLoading ? <Spinner /> : "Ask"}
                  </button>
                </div>
              </div>
            </form>
            {/* Main Result Console (no box, just whitespace) */}
            <div className="w-full max-w-4xl mb-8">
              {current ? (
                <>
                  {/* Query section right-aligned */}
                  <div className="mb-8 flex justify-end">
                    <div
                      className="bg-gray-100 px-6 py-4 max-w-2xl ml-40 text-fs-primary text-base break-words shadow-soft"
                      style={{
                        minWidth: "200px",
                        borderRadius: "1.25rem",
                        marginLeft: "3rem",
                        wordBreak: "break-word"
                      }}
                    >
                      {current.question}
                    </div>
                  </div>
                  {/* AI Insight */}
                  <div className="mb-8">
                    <h3 className="text-[20px] font-semibold text-fs-primary tracking-wider uppercase mb-5 text-left" style={{ fontFamily: "'Manrope', sans-serif" }}>AI INSIGHT</h3>
                    <div className="bg-gray-100 p-6 rounded-2xl text-fs-primary text-base shadow-soft">
                      <p>{current.narrative}</p>
                      {current.bullets && current.bullets.length > 0 && (
                        <ul className="list-disc ml-6 mt-2 text-fs-orange">
                          {current.bullets.map((b, i) => <li key={i}>{b}</li>)}
                        </ul>
                      )}
                    </div>
                  </div>
                  {/* Visualization: Only show for data_query */}
                  {getCurrentIntent(current) === "data_query" && (
                    <div className="mb-8">
                      <h3 className="text-[20px] font-semibold text-fs-primary tracking-wider uppercase mb-5 text-left" style={{ fontFamily: "'Manrope', sans-serif" }}>VISUALIZATION</h3>
                      <div className="flex items-center mb-4">
                        <span className="mr-2 text-fs-muted text-sm">Chart Type:</span>
                        <select
                          value={userChartType || (current && current.chartType) || 'table'}
                          onChange={e => setUserChartType(e.target.value)}
                          className="border border-fs-border rounded px-2 py-1 text-sm text-fs-primary bg-white focus:outline-none focus:ring-1 focus:ring-fs-primary"
                          style={{ minWidth: 100 }}
                        >
                          {chartTypes.map(opt => (
                            <option key={opt.value} value={opt.value}>{opt.label}</option>
                          ))}
                        </select>
                        {userChartType && (
                          <button
                            className="ml-2 text-xs text-fs-muted hover:text-fs-primary"
                            onClick={() => setUserChartType(null)}
                            type="button"
                            title="Reset to AI suggestion"
                          >Reset</button>
                        )}
                      </div>
                      <div className="bg-gray-100 p-6 rounded-2xl shadow-soft">
                        {current.error ? (
                          <div className="text-red-400 text-xs">{current.error}</div>
                        ) : renderVisualization(current)}
                      </div>
                    </div>
                  )}
                  {/* Generated SQL: Only show for data_query */}
                  {getCurrentIntent(current) === "data_query" && (
                    <div className="mb-8">
                      <h3 className="text-[20px] font-semibold text-fs-primary tracking-wider uppercase mb-5 text-left" style={{ fontFamily: "'Manrope', sans-serif" }}>GENERATED SQL QUERY</h3>
                      <pre className="bg-gray-100 p-6 rounded-2xl font-mono text-xs whitespace-pre-wrap shadow-soft" style={{ color: "#000" }}>
                        <code>{current.sql || '...'}</code>
                      </pre>
                    </div>
                  )}
                </>
              ) : null}
            </div>
          </>
        )}
        {/* Error */}
        {error && (
          <div className="bg-red-100 border border-red-300 text-red-700 p-4 rounded-xl mb-4 w-full max-w-4xl">
            <p className="font-bold">An Error Occurred</p>
            <p className="text-sm">{error}</p>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;