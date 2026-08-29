import React, { useEffect, useState, useRef } from 'react'
import { api } from '../api'
import { Play, Pause, ChevronRight, FileUp, UploadCloud, X, Loader2, Sparkles, Zap, ShieldCheck } from 'lucide-react'
import { Button, Select, Field, Badge, EmptyState, PageHeader } from '../components/ui.jsx'


export default function Grading() {
  const [exams, setExams] = useState([])
  const [examId, setExamId] = useState(null)
  const [rubrics, setRubrics] = useState([])
  const [rubricId, setRubricId] = useState(null)
  const [files, setFiles] = useState([])
  const [batch, setBatch] = useState([])
  const [running, setRunning] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const fileRef = useRef(null)

  const refresh = async () => {
    const es = await api.listExams(); setExams(es)
    const eid = examId ?? es[0]?.id ?? null; setExamId(eid)
    if (eid) { const rs = await api.listRubrics(eid); setRubrics(rs); if (!rubricId && rs[0]) setRubricId(rs[0].id) }
  }
  useEffect(() => { refresh() }, []) // eslint-disable-line
  useEffect(() => { if (examId) api.listRubrics(examId).then(setRubrics) }, [examId])

  const handleFiles = (fileList) => {
    const picked = Array.from(fileList || [])
    if (!picked.length) return
    setFiles(f => [...f, ...picked])
  }

  const runBatch = async () => {
    if (!examId || !rubricId || !files.length) return
    setRunning(true)
    const fresh = files.map((f, i) => ({ id: `${Date.now()}_${i}`, name: f.name, file: f, status: 'queued', progress: 0 }))
    setBatch(prev => [...fresh, ...prev])
    for (let i = 0; i < fresh.length; i++) {
      const item = fresh[i]
      setBatch(b => b.map(x => x.id === item.id ? { ...x, status: 'grading' } : x))
      try {
        const res = await api.uploadPaper(examId, rubricId, item.file)
        setBatch(b => b.map(x => x.id === item.id ? { ...x, status: 'done', paperId: res.paper_id, anonId: res.student_anon_id, cropIds: res.crop_ids } : x))

      } catch (err) {
        setBatch(b => b.map(x => x.id === item.id ? { ...x, status: 'failed', error: err?.response?.data?.detail || err.message } : x))
      }
    }
    setRunning(false); setFiles([])
  }

  const handleDelete = async (paperId) => {
    if (!window.confirm('Delete this paper and all its grades?')) return
    try {
      await (api.deletePaper ? api.deletePaper(paperId) : fetch(`/papers/${paperId}`, { method: 'DELETE' }))
      setBatch(b => b.filter(x => x.paperId !== paperId))
    } catch (err) { alert(err?.response?.data?.detail || 'Failed to delete.') }
  }

  const removeUpload = (id) => setBatch(b => b.filter(x => x.id !== id))
  const rubric = rubrics.find(r => r.id === rubricId)
  const graded = batch.filter(b => b.status === 'done').length
  const failed = batch.filter(b => b.status === 'failed').length
  const pending = batch.filter(b => b.status === 'queued' || b.status === 'grading').length
  const anyDone = batch.some(b => b.status === 'done')

  return (
    <div className="space-y-6">
      <PageHeader step="Step 02 · Auto-grade" title="Grading" description="Upload scanned answer sheets. The AI extracts each answer, transcribes handwriting, and grades against the selected rubric."
        actions={<>
          <button onClick={runBatch} disabled={!rubricId || !files.length || running} className="btn-primary h-11 px-5 rounded-lg text-sm flex items-center gap-2">
            {running ? <><Pause className="w-4 h-4" /> Grading…</> : <><Play className="w-4 h-4" /> Run grading on {files.length || 0}</>}
          </button>
        </>}
      />

      {exams.length === 0 ? (
        <EmptyState title="Create an exam and a rubric first" description="Go to the Rubrics tab, create an exam, and add at least one rubric." />
      ) : (
        <>
          {/* Selectors */}
          <div className="go-card p-5">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <Field label="Exam"><Select value={examId || ''} onChange={e => setExamId(Number(e.target.value))}>{exams.map(e => <option key={e.id} value={e.id}>{e.title}</option>)}</Select></Field>
              <Field label="Rubric"><Select value={rubricId || ''} onChange={e => setRubricId(Number(e.target.value))}>{rubrics.length === 0 && <option value="">No rubrics</option>}{rubrics.map(r => <option key={r.id} value={r.id}>{r.title} ({r.version})</option>)}</Select></Field>
              <Field label="Answer sheets" hint="PDF or image. One student per file.">
                <label className="cursor-pointer"><input type="file" accept="application/pdf,image/*" multiple onChange={e => { handleFiles(e.target.files); e.target.value = '' }} className="sr-only" />
                  <span className="block w-full h-10 px-3 rounded-md border border-dashed border-gray-300 bg-gray-50 text-sm text-gray-500 flex items-center hover:border-[#6b52c6] hover:text-[#6b52c6] transition-colors">
                    {files.length > 0 ? `${files.length} file${files.length === 1 ? '' : 's'} selected` : 'Click to choose files'}
                  </span>
                </label>
              </Field>
            </div>
            {rubric && (
              <div className="mt-4 rounded-lg border border-gray-200 bg-gray-50 px-4 py-3">
                <div className="flex items-center gap-2 mb-1"><Badge variant="brand">{rubric.version}</Badge><span className="text-[13px] font-medium text-gray-900">{rubric.title}</span><span className="text-[11px] text-gray-400">· {rubric.max_marks} pts · {rubric.criteria.length} criteria</span></div>
                <p className="text-[12px] text-gray-500 whitespace-pre-line line-clamp-2">{rubric.question_text}</p>
              </div>
            )}
          </div>

          {/* Upload zone */}
          <div onDragOver={e => { e.preventDefault(); setDragOver(true) }} onDragLeave={() => setDragOver(false)} onDrop={e => { e.preventDefault(); setDragOver(false); handleFiles(e.dataTransfer.files) }}
            className={`go-card p-5 relative overflow-hidden transition-colors ${dragOver ? 'border-[#6b52c6] bg-[#f3f0ff]' : ''}`}>
            <div className="flex flex-col md:flex-row md:items-center gap-5">
              <div className="flex items-center gap-4 flex-1">
                <div className={`w-12 h-12 rounded-xl flex items-center justify-center border ${dragOver ? 'border-[#6b52c6] bg-[#f3f0ff] text-[#6b52c6]' : 'border-gray-200 bg-gray-50 text-gray-400'}`}><UploadCloud className="w-5 h-5" /></div>
                <div><div className="font-display text-[18px] text-gray-900">Drop answer sheets to auto-queue</div><div className="text-[12px] text-gray-500 mt-0.5">PDF or images · AI begins scoring after upload completes.</div></div>
              </div>
              <div className="flex items-center gap-2">
                <input ref={fileRef} type="file" accept="application/pdf,image/*" multiple hidden onChange={e => { handleFiles(e.target.files); e.target.value = '' }} />
                <button onClick={() => fileRef.current?.click()} className="btn-primary h-11 px-5 rounded-lg text-sm flex items-center gap-2"><FileUp className="w-4 h-4" /> Choose files</button>
              </div>
            </div>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="go-card p-5"><div className="flex items-center justify-between"><div className="text-[11px] uppercase tracking-[0.2em] text-gray-500">Graded</div><Sparkles className="w-4 h-4 text-[#6b52c6]" /></div><div className="font-display text-[36px] text-green-600 mt-2">{graded}</div></div>
            <div className="go-card p-5"><div className="flex items-center justify-between"><div className="text-[11px] uppercase tracking-[0.2em] text-gray-500">Pending</div><Zap className="w-4 h-4 text-[#6b52c6]" /></div><div className="font-display text-[36px] text-amber-500 mt-2">{pending}</div></div>
            <div className="go-card p-5"><div className="flex items-center justify-between"><div className="text-[11px] uppercase tracking-[0.2em] text-gray-500">Failed</div><ShieldCheck className="w-4 h-4 text-[#6b52c6]" /></div><div className="font-display text-[36px] text-red-500 mt-2">{failed}</div></div>
          </div>

          {/* Batch list */}
          {batch.length > 0 && (
            <div className="go-card overflow-hidden">
              <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between"><div className="font-semibold text-gray-900">Batch progress</div><div className="text-[12px] text-gray-400">{batch.length} total</div></div>
              <div className="divide-y divide-gray-100">
                {batch.map(item => (
                  <div key={item.id} className="px-5 py-3 flex items-center gap-3">
                    <div className={`w-9 h-9 rounded-lg border flex items-center justify-center ${item.status === 'done' ? 'border-green-200 bg-green-50 text-green-600' : item.status === 'failed' ? 'border-red-200 bg-red-50 text-red-500' : 'border-[#ddd6fe] bg-[#f3f0ff] text-[#6b52c6]'}`}>
                      {item.status === 'done' ? <Sparkles className="w-4 h-4" /> : item.status === 'failed' ? <X className="w-4 h-4" /> : <Loader2 className="w-4 h-4 animate-spin" />}
                    </div>
                    <span className="flex-1 text-[14px] truncate text-gray-800">{item.name}</span>
                    {item.status === 'queued' && <Badge>queued</Badge>}
                    {item.status === 'grading' && <Badge variant="warning">Grading…</Badge>}
                    {item.status === 'done' && (<><Badge variant="success">✓ {item.cropIds?.length || 0} answer{item.cropIds?.length === 1 ? '' : 's'}</Badge><span className="text-[11px] text-gray-400">{item.anonId}</span><button onClick={() => handleDelete(item.paperId)} className="text-[11px] text-red-500 hover:text-red-600 border border-red-200 px-2 py-1 rounded-md hover:bg-red-50 transition">Delete</button></>)}
                    {item.status === 'failed' && <Badge variant="danger" title={item.error}>Failed</Badge>}
                  </div>
                ))}
              </div>
            </div>
          )}

          {anyDone && <p className="mt-6 text-[13px] text-gray-500">Done. Open the <span className="text-[#6b52c6] font-medium">Review</span> tab to see grades and approve, override, or flag each answer.</p>}
        </>
      )}
    </div>
  )
}
