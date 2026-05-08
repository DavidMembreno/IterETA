import { useEffect, useState } from "react";
import axios from "axios";
import Splash from "./Splash.tsx";

const API = "http://192.168.1.151:8000";

//  Axios interceptor -- attaches token to every request
axios.interceptors.request.use((config) => {
  const token = localStorage.getItem("itereta_token");
  if (token) config.headers["X-Token"] = token;
  return config;
});

axios.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("itereta_token");
      localStorage.removeItem("itereta_username");
      window.location.reload();
    }
    return Promise.reject(err);
  }
);

const CUSTOM_INTERVAL_PREFIX = "custom_interval_";
const DEFAULT_SETTING_KEYS = ["oil_change_interval_miles", "tire_rotation_interval_miles", "brake_service_interval_miles", "maintenance_time_gap_days"];
const SETTING_LABELS: Record<string, string> = {
  oil_change_interval_miles: "Oil & Filter Change Interval (miles)",
  tire_rotation_interval_miles: "Tire Rotation Interval (miles)",
  brake_service_interval_miles: "Brake Service Interval (miles)",
  maintenance_time_gap_days: "No-Maintenance Reminder Gap (days)",
};
const MAINTENANCE_PRESETS = [
  "Oil & Filter Change", "Tire Rotation", "Tire Balance", "Wheel Alignment", "Tire Replacement",
  "Brake Pad Replacement", "Brake Rotor Replacement", "Brake Fluid Flush", "Brake Inspection",
  "Battery Inspection", "Battery Replacement", "Transmission Fluid Flush", "Coolant Flush",
  "Power Steering Fluid", "Differential Fluid", "Engine Air Filter", "Cabin Air Filter",
  "Spark Plug Replacement", "Windshield Wiper Replacement", "Other",
];

//  Types

interface Vehicle { id: number; nickname: string; make?: string; model?: string; year?: number; current_mileage?: number; }
interface Trip { id: number; vehicle_id: number; start_label: string; end_label?: string; start_time: string; end_time?: string; duration_minutes?: number; }
interface SafetyIncident { id: number; trip_id: number; severity: number; description?: string; created_at: string; }
interface MaintenanceRecord { id: number; vehicle_id: number; service_type: string; cost?: number; mileage?: number; service_date: string; notes?: string; }
interface ETAResult { route: string; trip_count: number; avg_duration_minutes: number; conservative_eta_minutes: number; confidence: string; note: string; }
interface Alert { level: "HIGH" | "MODERATE" | "LOW"; rule: string; message: string; }
interface AlertsResult { alert_count: number; alerts: Alert[]; }
interface ReliabilityResult { total_trips: number; completed_trips: number; completion_rate_pct: number; avg_duration_minutes?: number; recent_incidents_30d: number; avg_severity_30d?: number; }
interface KnownRoute { start_label: string; end_label: string; trip_count: number; }
interface Setting { key: string; value: string; description?: string; }

//  Helpers

const alertColor = (level: string, dark: boolean) => {
  if (level === "HIGH") return dark ? "bg-red-900 border-red-600 text-red-200" : "bg-red-100 border-red-400 text-red-800";
  if (level === "MODERATE") return dark ? "bg-yellow-900 border-yellow-600 text-yellow-200" : "bg-yellow-100 border-yellow-400 text-yellow-800";
  return dark ? "bg-blue-900 border-blue-600 text-blue-200" : "bg-blue-100 border-blue-400 text-blue-800";
};
const confidenceColor = (c: string) => c === "high" ? "text-green-500" : c === "moderate" ? "text-yellow-500" : "text-red-400";
const formatDate = (iso: string) => new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
const openInMaps = (dest: string) => window.open(`https://maps.google.com/?q=${encodeURIComponent(dest)}`, "_blank");
const humanizeKey = (key: string) => key.replace(CUSTOM_INTERVAL_PREFIX, "").replace(/_miles$/, "").replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());

type Tab = "dashboard" | "trips" | "safety" | "maintenance" | "eta" | "settings";

//  Auth Screen

function AuthScreen({ onAuth }: { onAuth: (username: string) => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    setError(""); setLoading(true);
    try {
      const res = await axios.post(`${API}/auth/${mode}`, { username, password });
      localStorage.setItem("itereta_token", res.data.token);
      localStorage.setItem("itereta_username", res.data.username);
      onAuth(res.data.username);
    } catch (e: any) {
      setError(e.response?.data?.detail ?? "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-red-700">IterETA</h1>
          <p className="text-gray-500 text-sm mt-1">Personal Transportation Reliability Platform</p>
        </div>

        <div className="bg-white border rounded-xl shadow-sm p-6 space-y-4">
          <div className="flex rounded-lg overflow-hidden border">
            <button
              onClick={() => { setMode("login"); setError(""); }}
              className={`flex-1 py-2 text-sm font-medium transition-colors ${mode === "login" ? "bg-red-600 text-white" : "text-gray-500 hover:bg-gray-50"}`}
            >
              Sign In
            </button>
            <button
              onClick={() => { setMode("register"); setError(""); }}
              className={`flex-1 py-2 text-sm font-medium transition-colors ${mode === "register" ? "bg-red-600 text-white" : "text-gray-500 hover:bg-gray-50"}`}
            >
              Create Account
            </button>
          </div>

          <input
            className="border rounded px-3 py-3 text-sm w-full"
            placeholder="Username"
            value={username}
            onChange={e => setUsername(e.target.value)}
            autoCapitalize="none"
            autoCorrect="off"
          />
          <input
            className="border rounded px-3 py-3 text-sm w-full"
            placeholder="Password"
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            onKeyDown={e => e.key === "Enter" && submit()}
          />

          {error && <p className="text-red-500 text-sm">{error}</p>}

          <button
            onClick={submit}
            disabled={loading}
            className="w-full bg-red-600 text-white rounded py-3 text-sm hover:bg-red-700 disabled:opacity-50"
          >
            {loading ? "Please wait..." : mode === "login" ? "Sign In" : "Create Account"}
          </button>
        </div>

        <p className="text-center text-xs text-gray-400 mt-4">
          Your data is private to your account.
        </p>
      </div>
    </div>
  );
}

// Main App

export default function App() {
  const [username, setUsername] = useState<string | null>(localStorage.getItem("itereta_username"));
  const [tab, setTab] = useState<Tab>("dashboard");
  const [dark, setDark] = useState(false);
  const [showSplash, setShowSplash] = useState(true);

  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [trips, setTrips] = useState<Trip[]>([]);
  const [safety, setSafety] = useState<SafetyIncident[]>([]);
  const [maintenance, setMaintenance] = useState<MaintenanceRecord[]>([]);
  const [alerts, setAlerts] = useState<AlertsResult | null>(null);
  const [reliability, setReliability] = useState<ReliabilityResult | null>(null);
  const [knownRoutes, setKnownRoutes] = useState<KnownRoute[]>([]);
  const [settings, setSettings] = useState<Setting[]>([]);

  const [showAddVehicle, setShowAddVehicle] = useState(false);
  const [vNickname, setVNickname] = useState(""); const [vMake, setVMake] = useState(""); const [vModel, setVModel] = useState(""); const [vYear, setVYear] = useState(""); const [vMileage, setVMileage] = useState("");
  const [mileageEditing, setMileageEditing] = useState<number | null>(null); const [mileageInput, setMileageInput] = useState("");
  const [tVehicleId, setTVehicleId] = useState(""); const [tStartLabel, setTStartLabel] = useState(""); const [tEndLabel, setTEndLabel] = useState("");
  const [activeTrip, setActiveTrip] = useState<Trip | null>(null);
  const [sTripId, setSTripId] = useState(""); const [sSeverity, setSSeverity] = useState(5); const [sDesc, setSDesc] = useState("");
  const [mVehicleId, setMVehicleId] = useState(""); const [mServiceType, setMServiceType] = useState(""); const [mServiceCustom, setMServiceCustom] = useState("");
  const [mCost, setMCost] = useState(""); const [mMileage, setMMileage] = useState(""); const [mNotes, setMNotes] = useState("");
  const [etaStart, setEtaStart] = useState(""); const [etaEnd, setEtaEnd] = useState("");
  const [etaResult, setEtaResult] = useState<ETAResult | null>(null); const [etaError, setEtaError] = useState("");
  const [settingEdits, setSettingEdits] = useState<Record<string, string>>({});
  const [newIntervalService, setNewIntervalService] = useState(""); const [newIntervalMiles, setNewIntervalMiles] = useState("");
  const [status, setStatus] = useState(""); const [seedStatus, setSeedStatus] = useState("");

  //  Dark mode
  const bg = dark ? "bg-gray-900 text-gray-100" : "bg-gray-50 text-gray-800";
  const card = dark ? "bg-gray-800 border-gray-700" : "bg-white border-gray-200";
  const input = dark ? "bg-gray-700 border-gray-600 text-gray-100 placeholder-gray-400" : "bg-white border-gray-300 text-gray-800";
  const navBg = dark ? "bg-gray-900 border-gray-700" : "bg-white border-gray-200";
  const subtext = dark ? "text-gray-400" : "text-gray-500";
  const activeTab = dark ? "border-red-400 text-red-400" : "border-red-600 text-red-700";
  const inactiveTab = dark ? "border-transparent text-gray-400 hover:text-gray-200" : "border-transparent text-gray-500 hover:text-gray-700";

  //restore active trip
  const restoreActiveTrip = (fetchedTrips: Trip[], fetchedVehicles: Vehicle[]) => {
  if (activeTrip) return; // already tracking one
  const vehicleIds = new Set(fetchedVehicles.map(v => v.id));
  const inProgress = fetchedTrips.find(
    t => !t.end_time && vehicleIds.has(t.vehicle_id)
  );
  if (inProgress) setActiveTrip(inProgress);
};
  //  Fetch
  const fetchAll = async () => {
    const [v, t, s, m, a, r, routes, sett] = await Promise.all([
      axios.get(`${API}/vehicles`), axios.get(`${API}/trips`), axios.get(`${API}/safety`),
      axios.get(`${API}/maintenance`), axios.get(`${API}/alerts`), axios.get(`${API}/analytics/reliability`),
      axios.get(`${API}/analytics/routes`), axios.get(`${API}/settings`),
    ]);
    setVehicles(v.data); setTrips(t.data); setSafety(s.data); setMaintenance(m.data);
    setAlerts(a.data); setReliability(r.data); setKnownRoutes(routes.data); setSettings(sett.data);
    restoreActiveTrip(t.data, v.data);
    const edits: Record<string, string> = {};
    sett.data.forEach((s: Setting) => { edits[s.key] = s.value; });
    setSettingEdits(edits);
  };

  useEffect(() => { if (username) fetchAll(); }, [username]);

  //  Actions
  const logout = async () => {
    try { await axios.post(`${API}/auth/logout`); } catch {}
    localStorage.removeItem("itereta_token");
    localStorage.removeItem("itereta_username");
    setUsername(null);
  };

  const createVehicle = async () => {
    if (!vNickname) return setStatus("Nickname is required.");
    await axios.post(`${API}/vehicles`, { nickname: vNickname, make: vMake || undefined, model: vModel || undefined, year: vYear ? parseInt(vYear) : undefined, current_mileage: vMileage ? parseInt(vMileage) : undefined });
    setVNickname(""); setVMake(""); setVModel(""); setVYear(""); setVMileage(""); setShowAddVehicle(false);
    setStatus("Vehicle added."); fetchAll();
  };

  const deleteVehicle = async (id: number) => { await axios.delete(`${API}/vehicles/${id}`); setStatus("Vehicle deleted."); fetchAll(); };

  const saveMileage = async (vehicleId: number) => {
    if (!mileageInput) return;
    await axios.patch(`${API}/vehicles/${vehicleId}/mileage`, { current_mileage: parseInt(mileageInput) });
    setMileageEditing(null); setMileageInput(""); setStatus("Mileage updated."); fetchAll();
  };

const startTrip = async () => {
  if (!tVehicleId || !tStartLabel || !tEndLabel) return setStatus("Select a vehicle and enter both locations.");
  const res = await axios.post(`${API}/trips/start`, { vehicle_id: parseInt(tVehicleId), start_label: tStartLabel });
  await fetchAll(); // fetch first, then override activeTrip with end_label intact
  setActiveTrip({ ...res.data, end_label: tEndLabel });
  setStatus(`Trip started.`);
};

  const endTrip = async () => {
  if (!activeTrip) return;
  const dest = activeTrip.end_label || tEndLabel;
  if (!dest) return setStatus("Enter a destination to end the trip.");
  await axios.post(`${API}/trips/${activeTrip.id}/end`, { end_label: dest });
  setActiveTrip(null);
  setTStartLabel(""); setTEndLabel(""); setTVehicleId("");
  setStatus("Trip ended and saved."); fetchAll();
};


  const createSafety = async () => {
    if (!sTripId) return setStatus("Select a trip.");
    await axios.post(`${API}/safety`, { trip_id: parseInt(sTripId), severity: sSeverity, description: sDesc || undefined });
    setSTripId(""); setSSeverity(5); setSDesc(""); setStatus("Safety incident logged."); fetchAll();
  };

  const createMaintenance = async () => {
    const service = mServiceType === "Other" ? mServiceCustom : mServiceType;
    if (!mVehicleId || !service) return setStatus("Select a vehicle and service type.");
    await axios.post(`${API}/maintenance`, { vehicle_id: parseInt(mVehicleId), service_type: service, cost: mCost ? parseFloat(mCost) : undefined, mileage: mMileage ? parseInt(mMileage) : undefined, notes: mNotes || undefined });
    setMVehicleId(""); setMServiceType(""); setMServiceCustom(""); setMCost(""); setMMileage(""); setMNotes(""); setStatus("Maintenance record saved."); fetchAll();
  };

  const fetchETA = async () => {
    setEtaError(""); setEtaResult(null);
    if (!etaStart || !etaEnd) return setEtaError("Enter both start and destination.");
    try { const res = await axios.get(`${API}/eta`, { params: { start_label: etaStart, end_label: etaEnd } }); setEtaResult(res.data); }
    catch { setEtaError(`No trip history found for "${etaStart} to ${etaEnd}".`); }
  };

  const saveSetting = async (key: string) => { await axios.put(`${API}/settings/${key}`, { value: settingEdits[key] }); setStatus("Setting saved."); fetchAll(); };

  const addCustomInterval = async () => {
    if (!newIntervalService || !newIntervalMiles) return setStatus("Enter a service type and interval.");
    await axios.post(`${API}/settings/custom-interval`, { service_type: newIntervalService, interval_miles: parseInt(newIntervalMiles) });
    setNewIntervalService(""); setNewIntervalMiles(""); setStatus(`Interval added.`); fetchAll();
  };

  const deleteCustomInterval = async (key: string) => { await axios.delete(`${API}/settings/custom-interval/${key}`); setStatus("Removed."); fetchAll(); };

  const seedOverdue = async () => {
    setSeedStatus("Seeding...");
    try { const res = await axios.post(`${API}/dev/seed-overdue`); setSeedStatus(`Done! Mileage set to ${res.data.new_mileage.toLocaleString()} on ${res.data.vehicle}. Check Dashboard.`); fetchAll(); }
    catch (e: any) { setSeedStatus(e.response?.data?.detail ?? "Failed. Add a vehicle first."); }
  };

  const clearTestData = async () => {
    const res = await axios.delete(`${API}/dev/clear-test-data`);
    setSeedStatus(`Cleared ${res.data.deleted_maintenance} maintenance + ${res.data.deleted_incidents} incident test records.`); fetchAll();
  };

  //  Derived
  const defaultSettings = settings.filter(s => DEFAULT_SETTING_KEYS.includes(s.key));
  const customSettings = settings.filter(s => s.key.startsWith(CUSTOM_INTERVAL_PREFIX));
  const maintenanceAlerts = alerts?.alerts.filter(a => a.rule.startsWith("mileage_") || a.rule.startsWith("no_record_") || a.rule === "maintenance_time_gap") ?? [];

  const tabs: { key: Tab; label: string }[] = [
    { key: "dashboard", label: "Dashboard" }, { key: "trips", label: "Trips" },
    { key: "safety", label: "Safety" }, { key: "maintenance", label: "Maintenance" },
    { key: "eta", label: "ETA" }, { key: "settings", label: "Settings" },
  ];


  if (showSplash) return <Splash onDone={() => setShowSplash(false)} />;

  //  Auth gate
  if (!username) return <AuthScreen onAuth={(u) => setUsername(u)} />;

  //  Render
  return (
    <div className={`min-h-screen ${bg} transition-colors duration-200`}>

      <header className="bg-red-700 text-white px-4 py-4 shadow flex justify-between items-center">
        <div>
          <h1 className="text-xl font-bold tracking-tight">IterETA</h1>
          <p className="text-red-200 text-xs">Signed in as <strong>{username}</strong></p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setDark(!dark)} className="text-xl p-2 rounded-full hover:bg-red-600 transition-colors">{dark ? "☀️" : "🌙"}</button>
          <button onClick={logout} className="text-xs text-red-200 hover:text-white px-2 py-1 rounded hover:bg-red-600 transition-colors">Sign out</button>
        </div>
      </header>

      <nav className={`${navBg} border-b flex px-2 pt-2 overflow-x-auto gap-1`}>
        {tabs.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`px-3 py-2 text-sm font-medium rounded-t border-b-2 transition-colors whitespace-nowrap ${tab === t.key ? activeTab : inactiveTab}`}>
            {t.label}
          </button>
        ))}
      </nav>

      {status && (
        <div className={`${dark ? "bg-green-900 border-green-700 text-green-300" : "bg-green-50 border-green-200 text-green-700"} border-b text-sm px-4 py-2 flex justify-between items-center`}>
          <span>{status}</span>
          <button onClick={() => setStatus("")} className="ml-4 text-lg leading-none opacity-60 hover:opacity-100">✕</button>
        </div>
      )}

      <main className="max-w-xl mx-auto px-4 py-6 space-y-6">

        {/* ── DASHBOARD ── */}
        {tab === "dashboard" && (
          <div className="space-y-6">
            {alerts && alerts.alert_count > 0 && (
              <section>
                <h2 className="text-base font-semibold mb-2">Active Alerts</h2>
                <div className="space-y-2">
                  {alerts.alerts.map((a, i) => (
                    <div key={i} className={`border rounded p-3 text-sm ${alertColor(a.level, dark)}`}>
                      <span className="font-bold mr-2">[{a.level}]</span>{a.message}
                    </div>
                  ))}
                </div>
              </section>
            )}
            {alerts && alerts.alert_count === 0 && (
              <div className={`${dark ? "bg-green-900 border-green-700 text-green-300" : "bg-green-50 border-green-200 text-green-700"} border rounded p-3 text-sm`}>No active alerts. All clear.</div>
            )}

            {reliability && (
              <section>
                <h2 className="text-base font-semibold mb-2">Reliability Summary</h2>
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { label: "Total Trips", value: reliability.total_trips },
                    { label: "Completed", value: reliability.completed_trips },
                    { label: "Completion Rate", value: `${reliability.completion_rate_pct}%` },
                    { label: "Avg Duration", value: reliability.avg_duration_minutes ? `${reliability.avg_duration_minutes} min` : "N/A" },
                    { label: "Incidents (30d)", value: reliability.recent_incidents_30d },
                    { label: "Avg Severity (30d)", value: reliability.avg_severity_30d ?? "N/A" },
                  ].map((stat) => (
                    <div key={stat.label} className={`${card} border rounded p-3 text-center shadow-sm`}>
                      <div className="text-xl font-bold text-red-500">{stat.value}</div>
                      <div className={`text-xs mt-1 ${subtext}`}>{stat.label}</div>
                    </div>
                  ))}
                </div>
              </section>
            )}

            <section>
              <h2 className="text-base font-semibold mb-2">Vehicles</h2>
              {vehicles.length === 0 ? <p className={`text-sm ${subtext}`}>No vehicles added yet.</p> : (
                <div className="space-y-2">
                  {vehicles.map((v) => (
                    <div key={v.id} className={`${card} border rounded p-3 shadow-sm`}>
                      <div className="flex justify-between items-start">
                        <div>
                          <span className="font-medium">{v.nickname}</span>
                          <span className={`text-sm ml-2 ${subtext}`}>{[v.year, v.make, v.model].filter(Boolean).join(" ")}</span>
                          <div className={`text-sm mt-0.5 ${subtext}`}>{v.current_mileage != null ? `${v.current_mileage.toLocaleString()} miles` : "No mileage recorded"}</div>
                        </div>
                        <button onClick={() => deleteVehicle(v.id)} className="text-xs text-red-400 hover:text-red-300 p-1">Remove</button>
                      </div>
                      {mileageEditing === v.id ? (
                        <div className="flex gap-2 mt-3">
                          <input type="number" className={`border rounded px-3 py-2 text-sm flex-1 ${input}`} placeholder="New mileage" value={mileageInput} onChange={e => setMileageInput(e.target.value)} />
                          <button onClick={() => saveMileage(v.id)} className="bg-red-600 text-white px-4 py-2 rounded text-sm hover:bg-red-700">Save</button>
                          <button onClick={() => setMileageEditing(null)} className={`px-2 text-sm ${subtext}`}>Cancel</button>
                        </div>
                      ) : (
                        <button onClick={() => { setMileageEditing(v.id); setMileageInput(v.current_mileage?.toString() ?? ""); }} className="mt-2 text-xs text-red-500 hover:underline py-1">Update mileage</button>
                      )}
                    </div>
                  ))}
                </div>
              )}
              <button onClick={() => setShowAddVehicle(!showAddVehicle)}
                className={`mt-3 w-full border border-dashed rounded py-3 text-sm text-red-500 transition-colors ${dark ? "border-red-700 hover:bg-gray-800" : "border-red-300 hover:bg-red-50"}`}>
                {showAddVehicle ? "Cancel" : "+ Add Vehicle"}
              </button>
              {showAddVehicle && (
                <div className="mt-3 space-y-2">
                  <input className={`border rounded px-3 py-3 text-sm w-full ${input}`} placeholder="Nickname *" value={vNickname} onChange={e => setVNickname(e.target.value)} />
                  <div className="grid grid-cols-2 gap-2">
                    <input className={`border rounded px-3 py-3 text-sm ${input}`} placeholder="Make" value={vMake} onChange={e => setVMake(e.target.value)} />
                    <input className={`border rounded px-3 py-3 text-sm ${input}`} placeholder="Model" value={vModel} onChange={e => setVModel(e.target.value)} />
                    <input className={`border rounded px-3 py-3 text-sm ${input}`} placeholder="Year" type="number" value={vYear} onChange={e => setVYear(e.target.value)} />
                    <input className={`border rounded px-3 py-3 text-sm ${input}`} placeholder="Current Mileage" type="number" value={vMileage} onChange={e => setVMileage(e.target.value)} />
                  </div>
                  <button onClick={createVehicle} className="w-full bg-red-600 text-white rounded py-3 text-sm hover:bg-red-700">Add Vehicle</button>
                </div>
              )}
            </section>

            <section>
              <h2 className="text-base font-semibold mb-2">Export Data</h2>
              <div className="flex gap-2 flex-wrap">
                {["trips", "safety", "maintenance"].map((type) => (
                  <a key={type} href={`${API}/export/${type}`} className={`${card} border rounded px-3 py-2 text-sm shadow-sm capitalize hover:opacity-80`}>Export {type} CSV</a>
                ))}
              </div>
            </section>
          </div>
        )}

        {/* ── TRIPS ── */}
        {tab === "trips" && (
          <div className="space-y-6">
            <section className={`${card} border rounded p-4 shadow-sm`}>
              <h2 className="text-base font-semibold mb-4">{activeTrip ? "Trip In Progress" : "Start a Trip"}</h2>
              {!activeTrip ? (
                <div className="space-y-3">
                  <select className={`border rounded px-3 py-3 text-sm w-full ${input}`} value={tVehicleId} onChange={e => setTVehicleId(e.target.value)}>
                    <option value="">Select vehicle...</option>
                    {vehicles.map(v => <option key={v.id} value={v.id}>{v.nickname}</option>)}
                  </select>
                  <input className={`border rounded px-3 py-3 text-sm w-full ${input}`} placeholder="Departing from (full address or place name)" value={tStartLabel} onChange={e => setTStartLabel(e.target.value)} />
                  <input className={`border rounded px-3 py-3 text-sm w-full ${input}`} placeholder="Destination (full address or place name)" value={tEndLabel} onChange={e => setTEndLabel(e.target.value)} />
                  <p className={`text-xs ${subtext}`}>Tip: use full addresses for accurate Maps navigation.</p>
                  <div className="flex gap-2">
                    <button onClick={startTrip} className="flex-1 bg-red-600 text-white rounded py-3 text-sm hover:bg-red-700">Start Trip</button>
                    {tEndLabel && <button onClick={() => openInMaps(tEndLabel)} className={`flex-1 ${card} border rounded py-3 text-sm hover:opacity-80`}>Open in Maps</button>}
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
<div className={`${dark ? "bg-red-900 border-red-700 text-red-200" : "bg-red-50 border-red-200 text-red-800"} border rounded p-3 text-sm`}>
    Trip #{activeTrip.id} in progress<br /><strong>{activeTrip.start_label}</strong> to <strong>{activeTrip.end_label ?? "destination not set"}</strong>
</div>
{!activeTrip.end_label && (
    <input
        className={`border rounded px-3 py-3 text-sm w-full ${input}`}
        placeholder="Where are you headed?"
        value={tEndLabel}
        onChange={e => setTEndLabel(e.target.value)}
    />
)}
<div className="flex gap-2">
    <button onClick={endTrip} className="flex-1 bg-green-600 text-white rounded py-3 text-sm hover:bg-green-700">End Trip</button>
    {(activeTrip.end_label || tEndLabel) && <button onClick={() => openInMaps(activeTrip.end_label || tEndLabel)} className={`flex-1 ${card} border rounded py-3 text-sm hover:opacity-80`}>Open in Maps</button>}
</div>
                </div>
              )}
            </section>
            <section>
              <h2 className="text-base font-semibold mb-2">Trip History</h2>
              {trips.length === 0 ? <p className={`text-sm ${subtext}`}>No trips recorded yet.</p> : (
                <div className="space-y-2">
                  {trips.map((t) => (
                    <div key={t.id} className={`${card} border rounded p-3 shadow-sm text-sm`}>
                      <div className="flex justify-between">
                        <span className="font-medium">{t.start_label} to {t.end_label ?? "In progress"}</span>
                        <span className={`text-xs ml-2 shrink-0 ${subtext}`}>{formatDate(t.start_time)}</span>
                      </div>
                      {t.duration_minutes && <div className={`mt-1 ${subtext}`}>{t.duration_minutes} min</div>}
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>
        )}

        {/* ── SAFETY ── */}
        {tab === "safety" && (
          <div className="space-y-6">
            <section className={`${card} border rounded p-4 shadow-sm`}>
              <h2 className="text-base font-semibold mb-4">Log Safety Incident</h2>
              <div className="space-y-3">
                <select className={`border rounded px-3 py-3 text-sm w-full ${input}`} value={sTripId} onChange={e => setSTripId(e.target.value)}>
                  <option value="">Select completed trip...</option>
                  {trips.filter(t => t.end_time).map(t => <option key={t.id} value={t.id}>#{t.id} — {t.start_label} to {t.end_label} ({formatDate(t.start_time)})</option>)}
                </select>
                <div>
                  <div className="flex justify-between text-sm mb-2">
                    <label className={subtext}>Severity</label>
                    <span className={`font-bold text-base ${sSeverity >= 7 ? "text-red-500" : sSeverity >= 4 ? "text-yellow-500" : "text-green-500"}`}>{sSeverity} / 10</span>
                  </div>
                  <input type="range" min={1} max={10} step={1} value={sSeverity} onChange={e => setSSeverity(parseInt(e.target.value))} className="w-full accent-red-600 h-2" style={{ touchAction: "none" }} />
                  <div className={`flex justify-between text-xs mt-1 ${subtext}`}><span>Minor</span><span>Moderate</span><span>Severe</span></div>
                </div>
                <input className={`border rounded px-3 py-3 text-sm w-full ${input}`} placeholder="Description (optional)" value={sDesc} onChange={e => setSDesc(e.target.value)} />
                <button onClick={createSafety} className="w-full bg-orange-500 text-white rounded py-3 text-sm hover:bg-orange-600">Log Incident</button>
              </div>
            </section>
            <section>
              <h2 className="text-base font-semibold mb-2">Incident History</h2>
              {safety.length === 0 ? <p className={`text-sm ${subtext}`}>No incidents logged.</p> : (
                <div className="space-y-2">
                  {safety.map((i) => (
                    <div key={i.id} className={`${card} border rounded p-3 shadow-sm text-sm flex justify-between items-start`}>
                      <div><span className="font-medium">Trip #{i.trip_id}</span>{i.description && <p className={`mt-1 ${subtext}`}>{i.description}</p>}</div>
                      <div className="text-right shrink-0 ml-2">
                        <span className={`font-bold ${i.severity >= 7 ? "text-red-500" : i.severity >= 4 ? "text-yellow-500" : "text-green-500"}`}>{i.severity}/10</span>
                        <div className={`text-xs mt-1 ${subtext}`}>{formatDate(i.created_at)}</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>
        )}

        {/* ── MAINTENANCE ── */}
        {tab === "maintenance" && (
          <div className="space-y-6">
            {maintenanceAlerts.length > 0 && (
              <section>
                <h2 className="text-base font-semibold mb-2">Maintenance Alerts</h2>
                <div className="space-y-2">
                  {maintenanceAlerts.map((a, i) => <div key={i} className={`border rounded p-3 text-sm ${alertColor(a.level, dark)}`}><span className="font-bold mr-2">[{a.level}]</span>{a.message}</div>)}
                </div>
              </section>
            )}
            <section className={`${card} border rounded p-4 shadow-sm`}>
              <h2 className="text-base font-semibold mb-4">Log Maintenance</h2>
              <div className="space-y-3">
                <select className={`border rounded px-3 py-3 text-sm w-full ${input}`} value={mVehicleId} onChange={e => setMVehicleId(e.target.value)}>
                  <option value="">Select vehicle...</option>
                  {vehicles.map(v => <option key={v.id} value={v.id}>{v.nickname}</option>)}
                </select>
                <select className={`border rounded px-3 py-3 text-sm w-full ${input}`} value={mServiceType} onChange={e => setMServiceType(e.target.value)}>
                  <option value="">Select service type...</option>
                  {MAINTENANCE_PRESETS.map(p => <option key={p} value={p}>{p}</option>)}
                </select>
                {mServiceType === "Other" && <input className={`border rounded px-3 py-3 text-sm w-full ${input}`} placeholder="Describe service..." value={mServiceCustom} onChange={e => setMServiceCustom(e.target.value)} />}
                <div className="grid grid-cols-2 gap-2">
                  <input className={`border rounded px-3 py-3 text-sm ${input}`} placeholder="Cost ($)" type="number" value={mCost} onChange={e => setMCost(e.target.value)} />
                  <input className={`border rounded px-3 py-3 text-sm ${input}`} placeholder="Mileage at service" type="number" value={mMileage} onChange={e => setMMileage(e.target.value)} />
                </div>
                <input className={`border rounded px-3 py-3 text-sm w-full ${input}`} placeholder="Notes (optional)" value={mNotes} onChange={e => setMNotes(e.target.value)} />
                <button onClick={createMaintenance} className="w-full bg-red-600 text-white rounded py-3 text-sm hover:bg-red-700">Save Record</button>
              </div>
            </section>
            <section>
              <h2 className="text-base font-semibold mb-2">Maintenance History</h2>
              {maintenance.length === 0 ? <p className={`text-sm ${subtext}`}>No records yet.</p> : (
                <div className="space-y-2">
                  {maintenance.map((r) => (
                    <div key={r.id} className={`${card} border rounded p-3 shadow-sm text-sm`}>
                      <div className="flex justify-between">
                        <span className="font-medium">{r.service_type}</span>
                        <span className={`text-xs ml-2 shrink-0 ${subtext}`}>{formatDate(r.service_date)}</span>
                      </div>
                      <div className={`mt-1 flex gap-3 flex-wrap ${subtext}`}>
                        {r.cost != null && <span>${r.cost}</span>}
                        {r.mileage != null && <span>{r.mileage.toLocaleString()} mi</span>}
                        {r.notes && <span>{r.notes}</span>}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          </div>
        )}

        {/* ── ETA ── */}
        {tab === "eta" && (
          <div className="space-y-6">
            <section className={`${card} border rounded p-4 shadow-sm`}>
              <h2 className="text-base font-semibold mb-1">ETA Lookup</h2>
              <p className={`text-sm mb-4 ${subtext}`}>Uses your past trip history to estimate travel time.</p>
              {knownRoutes.length > 0 && (
                <div className="mb-4">
                  <p className={`text-xs mb-2 ${subtext}`}>Past routes:</p>
                  <div className="flex flex-wrap gap-2">
                    {knownRoutes.map((r, i) => (
                      <button key={i} onClick={() => { setEtaStart(r.start_label); setEtaEnd(r.end_label); setEtaResult(null); setEtaError(""); }}
                        className={`${card} border rounded px-3 py-2 text-xs hover:opacity-80`}>
                        {r.start_label} to {r.end_label}<span className={`ml-1 ${subtext}`}>({r.trip_count})</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
              <div className="space-y-3">
                <input className={`border rounded px-3 py-3 text-sm w-full ${input}`} placeholder="Starting from" value={etaStart} onChange={e => setEtaStart(e.target.value)} />
                <input className={`border rounded px-3 py-3 text-sm w-full ${input}`} placeholder="Destination" value={etaEnd} onChange={e => setEtaEnd(e.target.value)} />
                <div className="flex gap-2">
                  <button onClick={fetchETA} className="flex-1 bg-red-600 text-white rounded py-3 text-sm hover:bg-red-700">Get ETA</button>
                  {etaEnd && <button onClick={() => openInMaps(etaEnd)} className={`flex-1 ${card} border rounded py-3 text-sm hover:opacity-80`}>Open in Maps</button>}
                </div>
              </div>
              {etaError && <div className={`mt-4 border rounded p-3 text-sm ${dark ? "bg-red-900 border-red-700 text-red-300" : "bg-red-50 border-red-200 text-red-700"}`}>{etaError}</div>}
              {etaResult && (
                <div className={`mt-4 border rounded p-4 space-y-3 ${dark ? "bg-gray-800 border-gray-700" : "bg-red-50 border-red-200"}`}>
                  <div className="font-semibold text-red-500">{etaResult.route}</div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className={`${card} rounded p-3 text-center border`}><div className="text-xl font-bold">{etaResult.avg_duration_minutes} min</div><div className={`text-xs ${subtext}`}>Average</div></div>
                    <div className={`${card} rounded p-3 text-center border`}><div className="text-xl font-bold text-red-500">{etaResult.conservative_eta_minutes} min</div><div className={`text-xs ${subtext}`}>Conservative ETA</div></div>
                  </div>
                  <div className="text-sm">Based on <strong>{etaResult.trip_count}</strong> past trip(s). Confidence: <span className={`font-medium ${confidenceColor(etaResult.confidence)}`}>{etaResult.confidence}</span></div>
                  <div className={`text-xs ${subtext}`}>{etaResult.note}</div>
                </div>
              )}
            </section>
          </div>
        )}

        {/* ── SETTINGS ── */}
        {tab === "settings" && (
          <div className="space-y-6">
            <section className={`${card} border rounded p-4 shadow-sm`}>
              <h2 className="text-base font-semibold mb-1">Default Service Intervals</h2>
              <p className={`text-sm mb-4 ${subtext}`}>Alerts fire when mileage since last service exceeds these thresholds.</p>
              <div className="space-y-4">
                {defaultSettings.map((s) => (
                  <div key={s.key}>
                    <label className="text-sm font-medium">{SETTING_LABELS[s.key] ?? s.key}</label>
                    <div className="flex gap-2 mt-1">
                      <input type="number" className={`border rounded px-3 py-3 text-sm flex-1 ${input}`} value={settingEdits[s.key] ?? s.value} onChange={e => setSettingEdits(prev => ({ ...prev, [s.key]: e.target.value }))} />
                      <button onClick={() => saveSetting(s.key)} className="bg-red-600 text-white px-4 py-3 rounded text-sm hover:bg-red-700">Save</button>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            <section className={`${card} border rounded p-4 shadow-sm`}>
              <h2 className="text-base font-semibold mb-1">Custom Service Intervals</h2>
              <p className={`text-sm mb-4 ${subtext}`}>Track any additional service type by mileage.</p>
              {customSettings.length > 0 && (
                <div className="space-y-3 mb-4">
                  {customSettings.map((s) => (
                    <div key={s.key} className="flex items-center gap-2">
                      <div className="flex-1"><div className="text-sm font-medium">{humanizeKey(s.key)}</div><div className={`text-xs ${subtext}`}>every {parseInt(s.value).toLocaleString()} miles</div></div>
                      <input type="number" className={`border rounded px-3 py-2 text-sm w-24 ${input}`} value={settingEdits[s.key] ?? s.value} onChange={e => setSettingEdits(prev => ({ ...prev, [s.key]: e.target.value }))} />
                      <button onClick={() => saveSetting(s.key)} className="bg-red-600 text-white px-3 py-2 rounded text-sm hover:bg-red-700">Save</button>
                      <button onClick={() => deleteCustomInterval(s.key)} className="text-red-400 hover:text-red-300 px-2 py-2 text-sm">✕</button>
                    </div>
                  ))}
                </div>
              )}
              <div className="space-y-2">
                <select className={`border rounded px-3 py-3 text-sm w-full ${input}`} value={newIntervalService} onChange={e => setNewIntervalService(e.target.value)}>
                  <option value="">Select service type to track...</option>
                  {MAINTENANCE_PRESETS.filter(p => p !== "Other").map(p => <option key={p} value={p}>{p}</option>)}
                </select>
                <div className="flex gap-2">
                  <input type="number" className={`border rounded px-3 py-3 text-sm flex-1 ${input}`} placeholder="Interval (miles)" value={newIntervalMiles} onChange={e => setNewIntervalMiles(e.target.value)} />
                  <button onClick={addCustomInterval} className="bg-red-600 text-white px-4 py-3 rounded text-sm hover:bg-red-700">Add</button>
                </div>
              </div>
            </section>

            <section className={`${card} border rounded p-4 shadow-sm`}>
              <h2 className="text-base font-semibold mb-1">Alert Preview</h2>
              <p className={`text-sm mb-4 ${subtext}`}>Seed backdated records to preview what alerts look like. Clear when done.</p>
              <div className="flex gap-2">
                <button onClick={seedOverdue} className="flex-1 bg-orange-500 text-white rounded py-3 text-sm hover:bg-orange-600">Simulate Overdue Services</button>
                <button onClick={clearTestData} className={`flex-1 ${card} border rounded py-3 text-sm hover:opacity-80`}>Clear Test Data</button>
              </div>
              {seedStatus && <p className={`text-sm mt-3 ${subtext}`}>{seedStatus}</p>}
            </section>
          </div>
        )}

      </main>
    </div>
  );
}