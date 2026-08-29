import React, { useCallback, useContext, useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { Check, X, Flag, EyeOff, ChevronLeft, ChevronRight, MessageSquare } from 'lucide-react'
import { Button, Input, Field, Badge, EmptyState, PageHeader, Kbd } from '../components/ui.jsx'
import { RoleContext } from '../App.jsx'

export default function Review() {
  const { user } = useContext(RoleContext)
  const [queue, setQueue] = useState([])
  const [idx, setIdx] = useState(0)
  const [loading, setLoading] = useState(true)
  const [override, setOverride] = useState({ open: false, score: '', notes: '' })
  const [blind, setBlind] = useState(true)
  const overrideInputRef = useRef(null)

  const load = async () => { setLoading(true); try { const items = await api.reviewQueue(); setQueue(items); setIdx(0) } finally { setLoading(false) } }
  useEffect(() => { load() }, [])

  const current = queue[idx]

  const submit = useCallback(async (action, finalScore, notes) => {
    if (!current) return
    await api.submitReview({ crop_id: current.crop_id, action, final_score: finalScore, notes: notes || '', reviewer_id: user?.id })
    setQueue(q => q.filter((_, i) => i !== idx))
    setIdx(i => Math.max(0, Math.min(i, queue.length - 2)))
    setOverride({ open: false, score: '', notes: '' })
  }, [current, idx, queue.length, user])

  const onApprove = () => current && submit('approve', current.aggregate.median, '')
  const onFlag = () => current && submit('flag', current.aggregate.median, 'Flagged by reviewer')
  const openOverride = () => { if (!current) return; setOverride({ open: true, score: String(current.aggregate.median), notes: '' }); setTimeout(() => overrideInputRef.current?.focus(), 30) }
  const submitOverride = () => { const s = Number(override.score); if (isNaN(s)) return; submit('override', s, override.notes) }

  useEffect(() => {
    const handler = (e) => {
      if (override.open) {
        if (e.key === 'Escape') { setOverride({ open: false, score: '', notes: '' }); e.preventDefault() }
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { submitOverride(); e.preventDefault() }
        return
      }
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)) return
      switch (e.key.toLowerCase()) {
        case 'enter': onApprove(); e.preventDefault(); break
        case 'o': openOverride(); e.preventDefault(); break
        case 'f': onFlag(); e.preventDefault(); break
        case 'j': case 'arrowright': setIdx(i => Math.min(i + 1, queue.length - 1)); e.preventDefault(); break
        case 'k': case 'arrowleft': setIdx(i => Math.max(i - 1, 0)); e.preventDefault(); break
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [override.open, queue.length, current, idx]) // eslint-disable-line

  if (loading) return <div><PageHeader step="Step 03 · Verify" title="Review" description="Loading…" /></div>

  if (queue.length === 0) return (
    <div><PageHeader step="Step 03 · Verify" title="Review" description="Blind-review flagged papers side-by-side with the AI's justification." actions={<button className="btn-ghost h-10 px-4 rounded-lg text-sm" onClick={load}>Refresh</button>} />
      <EmptyState title="Queue is clear" description="Nothing has been graded yet, or every answer has been reviewed." action={<button className="btn-primary h-10 px-5 rounded-lg text-sm" onClick={load}>Refresh queue</button>} /></div>
  )

  return (
    <div className="space-y-6">
      <PageHeader step="Step 03 · Verify" title="Review" description={`${queue.length} pending · sorted by AI uncertainty (highest variance first)`}
        actions={<>
          <button onClick={() => setBlind(!blind)} className={`h-10 px-4 rounded-lg text-sm flex items-center gap-2 border transition ${blind ? 'border-[#6b52c6] text-[#6b52c6] bg-[#f3f0ff]' : 'border-gray-300 text-gray-500 hover:border-[#6b52c6]'}`}><EyeOff className="w-4 h-4" /> {blind ? 'Blind: ON' : 'Blind: OFF'}</button>
          <div className="hidden md:flex items-center gap-3 text-[11px] text-gray-400">
            <span className="flex items-center gap-1"><Kbd>↵</Kbd> approve</span>
            <span className="flex items-center gap-1"><Kbd>O</Kbd> override</span>
            <span className="flex items-center gap-1"><Kbd>F</Kbd> flag</span>
            <span className="flex items-center gap-1"><Kbd>J</Kbd>/<Kbd>K</Kbd> nav</span>
          </div>
          <button className="btn-ghost h-9 w-9 rounded-lg flex items-center justify-center" onClick={load}>↻</button>
        </>}
      />

      <div className="flex items-center justify-between">
        <span className="text-[12px] text-gray-500">Item {idx + 1} of {queue.length}</span>
        <div className="flex gap-1">
          <button className="btn-ghost h-9 px-3 rounded-lg text-sm" onClick={() => setIdx(i => Math.max(0, i - 1))} disabled={idx === 0}><ChevronLeft className="w-4 h-4" /></button>
          <button className="btn-ghost h-9 px-3 rounded-lg text-sm" onClick={() => setIdx(i => Math.min(queue.length - 1, i + 1))} disabled={idx === queue.length - 1}><ChevronRight className="w-4 h-4" /></button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Paper panel */}
        <div className="lg:col-span-7 go-card p-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-gray-100 border border-gray-200 font-semibold text-sm flex items-center justify-center text-gray-600">{blind ? '?' : current.student_anon_id?.slice(0, 2)}</div>
              <div><div className="font-display text-[18px] text-gray-900">{blind ? 'Anonymous Student' : current.student_anon_id}</div><div className="text-[12px] text-gray-500">{current.question_id} · {current.rubric_title}</div></div>
            </div>
            <div className="flex items-center gap-2">
              {current.plagiarism_flagged && <Badge variant="danger">Similarity</Badge>}
              <span className="text-[11px] text-gray-400">#{current.crop_id}</span>
            </div>
          </div>
          <div className="mt-5 rounded-xl border border-gray-200 bg-gray-50 overflow-hidden p-3">
            <img src={api.cropImageUrl(current.crop_id)} alt="student answer" className="w-full h-auto max-h-[64vh] object-contain bg-white rounded border border-gray-200" />
          </div>
        </div>

        {/* AI grades */}
        <div className="lg:col-span-5 space-y-4">
          <div className="go-card p-5">
            <div className="text-[11px] uppercase tracking-widest text-gray-500 mb-3 font-medium">AI grade · {current.aggregate.n_passes} pass{current.aggregate.n_passes === 1 ? '' : 'es'}</div>
            <div className="grid grid-cols-4 gap-2">
              <ScoreBlock label="Median" value={current.aggregate.median} color="#6b52c6" />
              <ScoreBlock label="Max" value={current.aggregate.max_score} />
              <ScoreBlock label="Min" value={current.aggregate.min_score} />
              <ScoreBlock label="σ" value={current.aggregate.std_dev.toFixed(2)} color={current.aggregate.std_dev > 1 ? '#f59e0b' : '#22c55e'} />
            </div>
            {current.gradings.length > 1 && (
              <div className="mt-3 flex gap-1.5">{current.gradings.map(g => (
                <div key={g.id} title={`Pass ${g.pass_num}: ${g.score}/${g.max_score}`} className="flex-1 h-7 rounded border border-gray-200 bg-gray-50 flex items-center justify-center text-[13px] text-gray-700">
                  {g.score}{!g.critic_passed && <span className="ml-1 text-amber-500">!</span>}
                </div>
              ))}</div>
            )}
          </div>

          <div className="go-card p-5">
            <div className="text-[11px] uppercase tracking-widest text-gray-500 mb-2 font-medium">Per-criterion</div>
            <div className="space-y-2">
              {pickMedianGrading(current).per_criterion.map((c, i) => (
                <div key={i} className="p-3 rounded-lg border border-gray-200 bg-gray-50">
                  <div className="flex items-center justify-between text-[13px]"><span className="text-gray-800"><span className="text-gray-400 mr-2">#{i+1}</span>{c.name}</span><span className="text-[#6b52c6] font-semibold">{c.awarded}/{c.max}</span></div>
                  <p className="text-[11px] text-gray-500 mt-1 pl-5">{c.reasoning}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="go-card p-5">
            <div className="text-[11px] uppercase tracking-widest text-gray-500 mb-2 font-medium">Justification</div>
            <p className="text-[13px] text-gray-700 leading-relaxed">{pickMedianGrading(current).justification}</p>
            {pickMedianGrading(current).flags?.length > 0 && (
              <div className="mt-3 flex gap-1.5 flex-wrap">{pickMedianGrading(current).flags.map(f => <Badge key={f} variant="warning">{f}</Badge>)}</div>
            )}
          </div>

          {/* Actions */}
          <div className="go-card p-5 border-[#6b52c6]/20">
            {!override.open ? (
              <div className="flex flex-wrap items-center gap-2">
                <button className="btn-primary h-10 px-4 rounded-lg text-sm flex items-center gap-2" onClick={onApprove}><Check className="w-4 h-4" /> Approve {current.aggregate.median}</button>
                <button className="btn-ghost h-10 px-4 rounded-lg text-sm flex items-center gap-2" onClick={openOverride}><X className="w-4 h-4" /> Override</button>
                <button className="btn-ghost h-10 px-4 rounded-lg text-sm flex items-center gap-2 text-red-500 border-red-200 hover:bg-red-50" onClick={onFlag}><Flag className="w-4 h-4" /> Flag</button>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="grid grid-cols-3 gap-3">
                  <Field label={`Score (0 — ${current.gradings[0]?.max_score || 0})`}><Input ref={overrideInputRef} type="number" step="0.5" min="0" max={current.gradings[0]?.max_score || 0} value={override.score} onChange={e => setOverride({ ...override, score: e.target.value })} /></Field>
                  <div className="col-span-2"><Field label="Note (optional)"><Input value={override.notes} onChange={e => setOverride({ ...override, notes: e.target.value })} placeholder="Why you changed the score" /></Field></div>
                </div>
                <div className="flex gap-2 justify-end">
                  <button className="btn-ghost h-10 px-4 rounded-lg text-sm" onClick={() => setOverride({ open: false, score: '', notes: '' })}>Cancel</button>
                  <button className="btn-primary h-10 px-4 rounded-lg text-sm" onClick={submitOverride}>Save override</button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Transcript */}
      <details className="group">
        <summary className="list-none cursor-pointer go-card px-5 py-3 text-[13px] text-gray-500 hover:text-[#6b52c6] transition-colors">
          <span className="inline-flex items-center gap-2"><span className="text-gray-400 group-open:rotate-90 transition-transform">›</span> OCR transcript</span>
        </summary>
        <pre className="mt-2 p-4 go-card text-[13px] text-gray-700 whitespace-pre-wrap font-sans leading-relaxed">{current.gradings[0]?.transcript || '(no transcript captured)'}</pre>
      </details>
    </div>
  )
}

function pickMedianGrading(item) {
  const sorted = [...item.gradings].sort((a, b) => Math.abs(a.score - item.aggregate.median) - Math.abs(b.score - item.aggregate.median))
  return sorted[0] || item.gradings[0]
}

function ScoreBlock({ label, value, color }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2.5">
      <div className="text-[10px] uppercase tracking-widest text-gray-400 font-medium">{label}</div>
      <div className="font-display text-[20px] mt-0.5" style={{ color: color || '#111827' }}>{value}</div>
    </div>
  )
}
