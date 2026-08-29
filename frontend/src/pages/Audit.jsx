import React, { useEffect, useState } from 'react'
import { api } from '../api'
import { Download, Fingerprint, ShieldCheck, Clock, Search, Filter, Info, AlertTriangle, CheckCircle2 } from 'lucide-react'
import { Badge, PageHeader } from '../components/ui.jsx'

export default function Audit() {
  const [stats, setStats] = useState(null)
  const [entries, setEntries] = useState([])
  const [plag, setPlag] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')
  const [q, setQ] = useState('')

  const load = async () => {
    setLoading(true)
    try { const [s, e, p] = await Promise.all([api.stats(), api.audit(), api.plagiarism()]); setStats(s); setEntries(e); setPlag(p) }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  const pct = (n) => `${Math.round((n || 0) * 100)}%`

  const filteredEntries = entries.filter(e => {
    if (filter !== 'all') {
      const variant = actionVariant(e.action)
      if (filter === 'info' && variant !== 'neutral') return false
      if (filter === 'warn' && variant !== 'warning') return false
      if (filter === 'success' && variant !== 'success') return false
    }
    if (q) {
      const lower = q.toLowerCase()
      return (e.entity_type + e.action + JSON.stringify(e.after)).toLowerCase().includes(lower)
    }
    return true
  })

  return (
    <div className="space-y-6">
      <PageHeader step="Step 04 · Trust" title="Audit" description="Every keystroke, every AI decision, every override—timestamped and immutable. Ready for accreditation."
        actions={<>
          <button className="btn-ghost h-10 px-4 rounded-lg text-sm flex items-center gap-2"><Download className="w-4 h-4" /> Export CSV</button>
          <button className="btn-primary h-10 px-4 rounded-lg text-sm flex items-center gap-2" onClick={load}><Fingerprint className="w-4 h-4" /> Refresh</button>
        </>}
      />

      {/* Stats cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {[
            { l: 'Total answers', v: stats.total_crops, i: Clock },
            { l: 'Reviewed', v: stats.total_reviewed, i: CheckCircle2 },
            { l: 'Override rate', v: pct(stats.override_rate), i: AlertTriangle, accent: (stats.override_rate || 0) > 0.2 ? 'text-amber-600' : undefined },
            { l: 'Flag rate', v: pct(stats.flag_rate), i: Info },
            { l: 'Mean σ', v: (stats.mean_std_dev || 0).toFixed(2), i: ShieldCheck, accent: (stats.mean_std_dev || 0) > 1 ? 'text-amber-600' : 'text-green-600' },
            { l: 'Similarity pairs', v: stats.plagiarism_pairs, i: Fingerprint, accent: stats.plagiarism_pairs > 0 ? 'text-red-500' : undefined },
          ].map((s) => (
            <div key={s.l} className="go-card p-4">
              <div className="flex items-center justify-between"><div className="text-[10px] uppercase tracking-[0.2em] text-gray-500">{s.l}</div><s.i className="w-3.5 h-3.5 text-[#6b52c6]" /></div>
              <div className={`font-display text-[24px] mt-2 ${s.accent || 'text-[#6b52c6]'}`}>{s.v}</div>
            </div>
          ))}
        </div>
      )}

      {/* Search + Filter */}
      <div className="go-card p-4 flex flex-col md:flex-row items-stretch md:items-center gap-3">
        <div className="flex items-center gap-2 flex-1">
          <Search className="w-4 h-4 text-gray-400" />
          <input value={q} onChange={e => setQ(e.target.value)} placeholder="Search actions" className="w-full h-10 px-3 rounded-md text-sm outline-none bg-gray-50 border border-gray-200 text-gray-800 placeholder:text-gray-400 focus:border-[#6b52c6] focus:ring-2 focus:ring-[#6b52c6]/15" />
        </div>
        <div className="flex items-center gap-1 p-1 rounded-lg border border-gray-200 bg-gray-50">
          <Filter className="w-4 h-4 text-gray-400 ml-2 mr-1" />
          {['all', 'info', 'warn', 'success'].map(f => (
            <button key={f} onClick={() => setFilter(f)} className={`px-3 h-8 rounded-md text-xs uppercase tracking-widest transition ${filter === f ? 'bg-[#6b52c6] text-white font-semibold' : 'text-gray-500 hover:text-[#6b52c6]'}`}>{f}</button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Decision log */}
        <div className="go-card overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between"><div className="font-semibold text-gray-900">Decision log</div><div className="text-[12px] text-gray-400">{filteredEntries.length} events</div></div>
          <div className="max-h-[64vh] overflow-auto divide-y divide-gray-100">
            {loading ? <p className="px-5 py-6 text-sm text-gray-400">Loading…</p>
            : filteredEntries.length === 0 ? <p className="px-5 py-6 text-sm text-gray-400 text-center">No entries.</p>
            : filteredEntries.map(e => (
              <div key={e.id} className="px-5 py-4 flex items-center gap-4 hover:bg-gray-50 transition">
                <div className={`w-9 h-9 rounded-lg border flex items-center justify-center ${sevRing(e.action)}`}>
                  {actionIcon(e.action)}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[14px] text-gray-800"><span>{e.entity_type}#{e.entity_id}</span><span className="text-gray-400"> → </span><Badge variant={actionVariant(e.action)}>{e.action}</Badge></div>
                  <div className="text-[12px] text-gray-400 mt-0.5">r:{e.rubric_version || '—'} · p:{e.prompt_version || '—'} · {new Date(e.created_at).toLocaleTimeString()}</div>
                </div>
                <div className="text-[12px] text-gray-400 truncate max-w-[120px]" title={JSON.stringify(e.after)}>{summarizeDelta(e)}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Similarity flags */}
        <div className="go-card overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between"><div className="font-semibold text-gray-900">Similarity flags</div><div className="text-[12px] text-gray-400">{plag.length} pairs</div></div>
          <div className="max-h-[64vh] overflow-auto divide-y divide-gray-100">
            {loading ? <p className="px-5 py-6 text-sm text-gray-400">Loading…</p>
            : plag.length === 0 ? <p className="px-5 py-6 text-sm text-gray-400 text-center">No similarity pairs above threshold.</p>
            : plag.map(p => (
              <div key={`${p.crop_a_id}-${p.crop_b_id}`} className="px-5 py-4 flex items-center gap-4 hover:bg-gray-50 transition">
                <div className="flex-1"><span className="text-[14px] text-gray-800">#{p.crop_a_id}</span><span className="text-gray-400 mx-2">↔</span><span className="text-[14px] text-gray-800">#{p.crop_b_id}</span></div>
                <span className="text-red-500 font-semibold font-display text-[16px]">{(p.similarity * 100).toFixed(1)}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function actionVariant(action) {
  if (action === 'approve') return 'success'
  if (action === 'override') return 'warning'
  if (action === 'flag') return 'danger'
  return 'neutral'
}

function sevRing(action) {
  if (action === 'approve') return 'text-green-600 border-green-200 bg-green-50'
  if (action === 'override') return 'text-amber-600 border-amber-200 bg-amber-50'
  if (action === 'flag') return 'text-red-500 border-red-200 bg-red-50'
  return 'text-gray-500 border-gray-200 bg-gray-50'
}

function actionIcon(action) {
  if (action === 'approve') return <CheckCircle2 className="w-4 h-4" />
  if (action === 'override') return <AlertTriangle className="w-4 h-4" />
  if (action === 'flag') return <AlertTriangle className="w-4 h-4" />
  return <Info className="w-4 h-4" />
}

function summarizeDelta(e) {
  const a = e.after || {}
  if (a.final_score !== undefined) return `→ ${a.final_score}`
  if (a.median !== undefined) return `median ${a.median} · σ ${(a.std_dev || 0).toFixed(2)}`
  if (a.title) return a.title
  return '—'
}
