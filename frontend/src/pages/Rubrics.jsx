import React, { useEffect, useState } from 'react'
import { api } from '../api'
import { Plus, Upload, Trash2, ChevronRight, Sparkles, Search } from 'lucide-react'
import { Button, Input, TextArea, Field, Badge, EmptyState, PageHeader } from '../components/ui.jsx'

const DEFAULT_INSTRUCTIONS = `Base all scoring strictly on evidence visible in the student's handwritten work. If evidence is missing, assign zero — do not guess, infer, or hallucinate.
Award credit for intermediate steps only if they are explicitly written by the student. Do not infer non-trivial reasoning from a correct final answer except for trivial algebraic simplifications.
If the student's solution does not match the question being asked, assign a score of 0.`

const SAMPLE_RUBRIC = {
  title: 'Linear equation — sample',
  question_text: 'Solve for x and show all steps:\n\n2x + 5 = 15',
  max_marks: 10,
  course_instructions: DEFAULT_INSTRUCTIONS,
  criteria: [
    { name: 'Isolate the variable term', points: 5, conditions: 'Student subtracts 5 from both sides to obtain 2x = 10.', accept_alternatives: 'Equivalent algebraic rearrangements that arrive at 2x = 10.', do_not_deduct_for: 'Minor handwriting or notation differences.' },
    { name: 'Solve for x', points: 5, conditions: 'Student divides both sides by 2 and obtains x = 5.', accept_alternatives: 'Equivalent forms such as x=5 or x = 5.0.', do_not_deduct_for: 'Minor notation differences.' },
  ],
}

export default function Rubrics() {
  const [exams, setExams] = useState([])
  const [examId, setExamId] = useState(null)
  const [rubrics, setRubrics] = useState([])
  const [editing, setEditing] = useState(null)
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [activeRubricId, setActiveRubricId] = useState(null)

  const refresh = async (eid) => {
    setLoading(true)
    try {
      const es = await api.listExams()
      setExams(es)
      const useExam = eid ?? examId ?? (es[0]?.id || null)
      setExamId(useExam)
      const rbs = useExam ? await api.listRubrics(useExam) : []
      setRubrics(rbs)
      if (rbs.length > 0 && !activeRubricId) setActiveRubricId(rbs[0].id)
    } finally { setLoading(false) }
  }
  useEffect(() => { refresh() }, []) // eslint-disable-line

  const createExam = async () => { const title = prompt('Name this exam'); if (!title) return; const e = await api.createExam({ title }); await refresh(e.id) }
  const startBlank = () => { if (!examId) { alert('Create an exam first.'); return }; setEditing({ _new: true, exam_id: examId, title: '', question_text: '', max_marks: 10, course_instructions: DEFAULT_INSTRUCTIONS, criteria: [{ name: '', points: 1, conditions: '', accept_alternatives: '', do_not_deduct_for: '' }] }) }
  const startSample = () => { if (!examId) { alert('Create an exam first.'); return }; setEditing({ _new: true, exam_id: examId, ...SAMPLE_RUBRIC }) }

  const deleteExam = async () => {
    if (!examId) return
    if (!window.confirm("Delete this exam and all rubrics?")) return
    try {
      const response = await fetch(`/api/exams/${examId}`, { method: 'DELETE' })
      if (response.ok) { const di = exams.findIndex(e => e.id === examId); const ue = exams.filter(e => e.id !== examId); setExams(ue); await refresh(ue.length > 0 ? ue[Math.max(0, di - 1)].id : null) }
      else alert("Failed to delete exam.")
    } catch (error) { console.error("Error deleting exam:", error) }
  }

  const save = async (r) => { const { _new, ...payload } = r; await api.createRubric(payload); setEditing(null); await refresh() }

  if (editing) return <RubricEditor initial={editing} onSave={save} onCancel={() => setEditing(null)} />

  const filteredExams = exams.filter(e => e.title.toLowerCase().includes(query.toLowerCase()))
  const activeRubric = rubrics.find(r => r.id === activeRubricId)

  return (
    <div>
      <PageHeader step="Step 01 · Define" title="Rubrics" description="Define grading criteria for each question. Criteria support alternatives and explicit do-not-deduct rules."
        actions={<>
          <button className="btn-ghost h-10 px-4 rounded-lg text-sm flex items-center gap-2" onClick={startSample}><Upload className="w-4 h-4" /> Load sample</button>
          <button onClick={createExam} className="btn-ghost h-10 px-4 rounded-lg text-sm flex items-center gap-2"><Plus className="w-4 h-4" /> New exam</button>
          <button onClick={startBlank} className="btn-primary h-10 px-4 rounded-lg text-sm flex items-center gap-2"><Plus className="w-4 h-4" /> New rubric</button>
        </>}
      />
      {loading ? <div className="go-card p-8 text-center text-gray-500">Loading…</div>
      : exams.length === 0 ? <EmptyState title="No exams yet" description="Create an exam first, then add one or more rubrics to it. Each question on the exam needs its own rubric." action={<button className="btn-primary h-10 px-5 rounded-lg text-sm" onClick={createExam}>Create your first exam</button>} />
      : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left: Exams */}
          <aside className="lg:col-span-3 go-card p-4">
            <div className="flex items-center gap-2 mb-3"><Search className="w-4 h-4 text-gray-400" /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search exams" className="w-full h-9 px-3 rounded-md text-sm outline-none bg-gray-50 border border-gray-200 text-gray-800 placeholder:text-gray-400 focus:border-[#6b52c6] focus:ring-2 focus:ring-[#6b52c6]/15" /></div>
            <div className="text-[11px] uppercase tracking-[0.18em] text-gray-400 px-2 py-2 font-medium">Exams</div>
            <div className="space-y-2">
              {filteredExams.map((e) => (
                <button key={e.id} onClick={() => { setExamId(e.id); refresh(e.id) }} className={`w-full text-left p-3 rounded-lg border transition ${examId === e.id ? 'border-[#6b52c6] bg-[#f3f0ff]' : 'border-gray-200 bg-white hover:border-gray-300'}`}>
                  <div className="flex items-center justify-between">
                    <div className="font-semibold text-[14px] text-gray-900">{e.title}</div>
                    {examId === e.id && <button onClick={(ev) => { ev.stopPropagation(); deleteExam() }} className="text-[10px] uppercase tracking-widest px-2 py-0.5 rounded-full text-red-500 border border-red-200 hover:bg-red-50">Delete</button>}
                  </div>
                  <div className="text-[12px] text-gray-400 mt-1">#{e.id}</div>
                </button>
              ))}
            </div>
          </aside>
          {/* Middle: Questions */}
          <section className="lg:col-span-3 go-card p-4">
            <div className="flex items-center justify-between mb-3 px-2">
              <div className="text-[11px] uppercase tracking-[0.18em] text-gray-400 font-medium">Questions</div>
              <button onClick={startBlank} className="text-[#6b52c6] hover:text-[#5843a8] text-sm flex items-center gap-1"><Plus className="w-3.5 h-3.5" /> Add</button>
            </div>
            {rubrics.length === 0 ? <div className="text-center py-10 text-sm text-gray-400">No rubrics yet.</div> : (
              <div className="space-y-2">
                {rubrics.map((r, i) => (
                  <button key={r.id} onClick={() => setActiveRubricId(r.id)} className={`w-full text-left p-3 rounded-lg border transition group ${activeRubricId === r.id ? 'border-[#6b52c6] bg-[#f3f0ff]' : 'border-gray-200 bg-white hover:border-gray-300'}`}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <div className="w-6 h-6 rounded-md bg-[#f3f0ff] border border-[#ddd6fe] text-[#6b52c6] text-xs flex items-center justify-center font-semibold">Q{i+1}</div>
                        <div className="text-[13px] font-medium truncate max-w-[180px] text-gray-900">{r.title}</div>
                      </div>
                      <ChevronRight className="w-4 h-4 text-gray-300 group-hover:text-[#6b52c6]" />
                    </div>
                    <div className="mt-1 text-[11px] text-gray-400">{r.criteria.length} criteria · {r.max_marks} marks</div>
                  </button>
                ))}
              </div>
            )}
          </section>
          {/* Right: Detail */}
          <section className="lg:col-span-6 go-card p-6">
            {!activeRubric ? <div className="text-center py-16 text-gray-400">Select a rubric to view details.</div> : (
              <>
                <div className="flex items-start justify-between gap-4">
                  <div><div className="text-[11px] uppercase tracking-[0.18em] text-[#6b52c6] font-medium">Rubric #{activeRubric.id}</div><div className="font-display text-[24px] text-gray-900 mt-1">{activeRubric.title}</div><Badge variant="brand" className="mt-2">{activeRubric.version}</Badge></div>
                  <div className="text-right"><div className="text-[11px] text-gray-400 uppercase tracking-widest">Total</div><div className="font-display text-[24px] text-[#6b52c6]">{activeRubric.max_marks}<span className="text-gray-400">pts</span></div></div>
                </div>
                <div className="mt-4 p-3 rounded-lg border border-gray-200 bg-gray-50"><div className="text-[11px] uppercase tracking-widest text-gray-400 mb-1 font-medium">Question</div><div className="text-[14px] text-gray-700 whitespace-pre-line">{activeRubric.question_text}</div></div>
                <div className="mt-5 space-y-2">
                  <div className="text-[11px] uppercase tracking-widest text-gray-400 mb-2 font-medium">Criteria ({activeRubric.criteria.length})</div>
                  {activeRubric.criteria.map((c, i) => (
                    <div key={i} className="p-3 rounded-xl border border-gray-200 bg-gray-50">
                      <div className="flex items-center justify-between text-[13px]">
                        <div className="flex items-center gap-2"><div className="w-6 h-6 rounded-md bg-[#f3f0ff] border border-[#ddd6fe] text-[#6b52c6] text-xs flex items-center justify-center font-semibold">#{i+1}</div><span className="font-medium text-gray-900">{c.name}</span></div>
                        <div className="text-[#6b52c6] font-semibold">{c.points} pts</div>
                      </div>
                      {c.conditions && <div className="mt-2 text-[12px] text-gray-600 pl-8">{c.conditions}</div>}
                      {c.accept_alternatives && <div className="mt-1 text-[12px] text-gray-400 pl-8">Accept also: {c.accept_alternatives}</div>}
                      {c.do_not_deduct_for && <div className="mt-1 text-[12px] text-gray-400 pl-8">Don't deduct: {c.do_not_deduct_for}</div>}
                    </div>
                  ))}
                </div>
              </>
            )}
          </section>
        </div>
      )}
    </div>
  )
}

function RubricEditor({ initial, onSave, onCancel }) {
  const [r, setR] = useState(initial)
  const [submitted, setSubmitted] = useState(false)
  const update = (patch) => setR({ ...r, ...patch })
  const updateCrit = (i, patch) => update({ criteria: r.criteria.map((c, idx) => idx === i ? { ...c, ...patch } : c) })
  const addCrit = () => update({ criteria: [...r.criteria, { name: '', points: 1, conditions: '', accept_alternatives: '', do_not_deduct_for: '' }] })
  const removeCrit = (i) => update({ criteria: r.criteria.filter((_, idx) => idx !== i) })
  const total = r.criteria.reduce((s, c) => s + (Number(c.points) || 0), 0)
  const mismatch = total !== Number(r.max_marks)
  const canSave = r.title.trim() && r.question_text.trim() && r.criteria.length > 0 && r.criteria.every(c => c.name.trim())
  const onSaveClick = () => { setSubmitted(true); if (canSave) onSave(r) }

  return (
    <div>
      <PageHeader step={initial._new ? 'Creating' : 'Editing'} title={initial._new ? 'New rubric' : 'Edit rubric'} description="Fine-grained criteria with explicit conditions, alternatives, and do-not-deduct rules."
        actions={<><button className="btn-ghost h-10 px-4 rounded-lg text-sm" onClick={onCancel}>Cancel</button><button className="btn-primary h-10 px-5 rounded-lg text-sm flex items-center gap-2" onClick={onSaveClick} disabled={!canSave}><Sparkles className="w-4 h-4" /> Save rubric</button></>}
      />
      {submitted && !canSave && <div className="mb-4 px-4 py-3 rounded-lg border border-red-200 bg-red-50 text-[13px] text-red-600">Fill in the rubric title, question text, and a name for every criterion.</div>}
      <div className="go-card mb-4"><div className="px-5 py-4 border-b border-gray-100 font-semibold text-gray-900">Basics</div><div className="px-5 py-4">
        <div className="grid grid-cols-3 gap-4 mb-4"><div className="col-span-2"><Field label="Title" required><Input value={r.title} onChange={e => update({ title: e.target.value })} placeholder="Short, descriptive name" invalid={submitted && !r.title.trim()} /></Field></div><Field label="Max marks"><Input type="number" min={0} value={r.max_marks} onChange={e => update({ max_marks: Number(e.target.value) || 0 })} /></Field></div>
        <Field label="Question text" required hint="Exactly as the question appears on the exam."><TextArea rows={3} value={r.question_text} onChange={e => update({ question_text: e.target.value })} invalid={submitted && !r.question_text.trim()} /></Field>
      </div></div>
      <div className="go-card mb-4"><div className="px-5 py-4 border-b border-gray-100"><div className="font-semibold text-gray-900">Grading instructions</div><div className="text-[12px] text-gray-400 mt-0.5">Anti-hallucination guardrails.</div></div><div className="px-5 py-4"><TextArea rows={5} value={r.course_instructions} onChange={e => update({ course_instructions: e.target.value })} /></div></div>
      <div className="go-card"><div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between"><div><div className="font-semibold text-gray-900">Criteria</div><div className={`text-[12px] mt-0.5 ${mismatch ? 'text-amber-600' : 'text-gray-400'}`}>{total} / {r.max_marks} pts{mismatch ? ' · mismatch' : ''}</div></div><button className="btn-ghost h-9 px-3 rounded-lg text-sm flex items-center gap-1" onClick={addCrit}><Plus className="w-4 h-4" /> Add</button></div>
        <div className="divide-y divide-gray-100">
          {r.criteria.map((c, i) => (
            <div key={i} className="px-5 py-4">
              <div className="flex items-center gap-3 mb-3">
                <span className="text-[#6b52c6] font-semibold text-sm">#{i+1}</span>
                <Input value={c.name} onChange={e => updateCrit(i, { name: e.target.value })} placeholder="Criterion name" invalid={submitted && !c.name.trim()} className="flex-1" />
                <Input type="number" min={0} step="0.5" value={c.points} onChange={e => updateCrit(i, { points: Number(e.target.value) || 0 })} className="w-20 text-center" />
                <span className="text-[11px] text-gray-400">pts</span>
                <button onClick={() => removeCrit(i)} disabled={r.criteria.length <= 1} className="w-9 h-9 rounded-md border border-gray-300 text-gray-400 hover:text-red-500 hover:border-red-400 transition flex items-center justify-center disabled:opacity-30"><Trash2 className="w-4 h-4" /></button>
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-3 pl-8">
                <Field label="Conditions"><TextArea rows={3} value={c.conditions} onChange={e => updateCrit(i, { conditions: e.target.value })} placeholder="What must the student show?" /></Field>
                <Field label="Accept also"><TextArea rows={3} value={c.accept_alternatives} onChange={e => updateCrit(i, { accept_alternatives: e.target.value })} placeholder="Equivalent forms" /></Field>
                <Field label="Do not deduct for"><TextArea rows={3} value={c.do_not_deduct_for} onChange={e => updateCrit(i, { do_not_deduct_for: e.target.value })} placeholder="Surface issues to ignore" /></Field>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}