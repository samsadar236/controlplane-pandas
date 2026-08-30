import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, Check, ClipboardList, GraduationCap, ScanEye, ShieldCheck, ShieldAlert, Menu } from 'lucide-react'

export default function Landing() {
  const navigate = useNavigate()
  const [loaded, setLoaded] = useState(false)

  useEffect(() => {
    const t = setTimeout(() => setLoaded(true), 100)
    return () => clearTimeout(t)
  }, [])

  const cardClass = "bg-surface rounded-xl p-8 border border-outline-variant shadow-card flex flex-col hover:-translate-y-1 transition-transform duration-300"

  return (
    <div className="bg-background text-on-background font-sans antialiased relative min-h-screen">
      <div className="absolute inset-0 z-0 bg-grid-pattern pointer-events-none" />

      <nav className="sticky top-2 mx-auto max-w-container-max-width w-[calc(100%-80px)] hidden md:flex justify-between items-center z-50 bg-surface/80 backdrop-blur-md rounded-full mt-2 px-6 py-2 shadow-nav border border-outline-variant/30">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-primary rounded flex items-center justify-center text-on-primary">
            <Check className="w-4 h-4" strokeWidth={3} />
          </div>
          <span className="font-headline-sm text-headline-sm font-bold text-primary">GradeOps</span>
        </div>
        <span className="text-sm text-on-surface-variant font-bold">ControlPlane.ai · Team Pandas</span>
      </nav>

      <div className="md:hidden flex justify-between items-center p-4 bg-surface/90 backdrop-blur-md sticky top-0 z-50 border-b border-outline-variant/30">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-primary rounded flex items-center justify-center text-on-primary">
            <Check className="w-4 h-4" strokeWidth={3} />
          </div>
          <span className="font-headline-sm text-headline-sm font-bold text-primary">GradeOps</span>
        </div>
        <Menu className="w-6 h-6 text-on-surface" />
      </div>

      <main className="relative z-10 w-full pt-8 md:pt-12 pb-16">
        <section className="max-w-container-max-width mx-auto px-4 md:px-10 flex flex-col items-center text-center">
          <h1 className={`font-headline-lg-mobile md:font-headline-lg text-headline-lg-mobile md:text-headline-lg text-on-surface mb-6 max-w-4xl mt-4 transition-all duration-700 ${loaded ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`}>
            Grade smarter, not harder.
          </h1>
          <p className={`font-body-lg text-body-lg text-on-surface-variant max-w-2xl mb-10 transition-all duration-700 delay-100 ${loaded ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`}>
            Elevate your grading process with AI-powered accuracy and unparalleled speed. Designed
            exclusively for educators to reclaim time without compromising on rigorous academic
            standards.
          </p>
          <div className={`flex flex-col sm:flex-row gap-4 justify-center w-full sm:w-auto transition-all duration-700 delay-200 ${loaded ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`}>
            <button
              onClick={() => navigate('/rubrics')}
              className="font-label-md text-label-md bg-primary text-on-primary px-8 py-4 rounded-full shadow-cta hover:bg-on-primary-fixed-variant transition-all duration-200 flex items-center justify-center gap-2 group"
            >
              Start Grading{' '}
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </button>
          </div>
        </section>

        <section className="max-w-container-max-width mx-auto px-4 md:px-10 mt-16">
          <div className="text-center mb-12">
            <h2 className="font-headline-md text-headline-md text-on-surface mb-4">
              The Complete Grading Architecture
            </h2>
            <p className="font-body-md text-body-md text-on-surface-variant max-w-2xl mx-auto">
              A seamless workflow from initial criteria to final review, governed by automated
              safety checks at every step.
            </p>
          </div>

          {/* Row 1 */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
            <div className={cardClass}>
              <div className="w-12 h-12 rounded-lg bg-surface-container-high flex items-center justify-center text-primary mb-6">
                <ClipboardList className="w-6 h-6" />
              </div>
              <h3 className="font-headline-sm text-headline-sm text-on-surface mb-3">Rubrics</h3>
              <p className="font-body-sm text-body-sm text-on-surface-variant flex-grow">
                The Foundation. Build, import, or generate comprehensive grading schemas that align
                perfectly with your curriculum objectives.
              </p>
            </div>

            <div className={cardClass}>
              <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center text-primary mb-6">
                <GraduationCap className="w-6 h-6" />
              </div>
              <h3 className="font-headline-sm text-headline-sm text-on-surface mb-3">Grading (AI Efficiency)</h3>
              <p className="font-body-sm text-body-sm text-on-surface-variant flex-grow">
                Our core engine analyzes submissions against your rubrics in seconds, providing
                initial scores and deeply contextual feedback for every criterion.
              </p>
            </div>

            <div className={cardClass}>
              <div className="w-12 h-12 rounded-lg bg-surface-container-high flex items-center justify-center text-tertiary mb-6">
                <ScanEye className="w-6 h-6" />
              </div>
              <h3 className="font-headline-sm text-headline-sm text-on-surface mb-3">Review</h3>
              <p className="font-body-sm text-body-sm text-on-surface-variant flex-grow">
                Human-in-the-loop validation. Easily adjust AI suggestions, add personal notes, and
                ensure every grade reflects your professional judgment.
              </p>
            </div>
          </div>

          {/* Row 2 — flexbox centered */}
          <div style={{display: 'flex', gap: '24px', justifyContent: 'center'}}>
            <div className={cardClass} style={{width: 'calc(33.333% - 8px)', minWidth: '260px'}}>
              <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center text-primary mb-6">
                <ShieldAlert className="w-6 h-6" />
              </div>
              <h3 className="font-headline-sm text-headline-sm text-on-surface mb-3">Responsible AI Gate</h3>
              <p className="font-body-sm text-body-sm text-on-surface-variant flex-grow">
                Every AI output passes through automated bias, PII, and grounding checks before it
                reaches a human. A policy-driven decision engine allows, flags, or blocks each
                result so unsafe or ungrounded grades never surface.
              </p>
            </div>

            <div className={cardClass} style={{width: 'calc(33.333% - 8px)', minWidth: '260px'}}>
              <div className="w-12 h-12 rounded-lg bg-surface-container-high flex items-center justify-center text-on-surface-variant mb-6">
                <ShieldCheck className="w-6 h-6" />
              </div>
              <h3 className="font-headline-sm text-headline-sm text-on-surface mb-3">Audit</h3>
              <p className="font-body-sm text-body-sm text-on-surface-variant flex-grow">
                Every automated suggestion, manual override, and feedback note is cryptographically
                logged. Maintain a perfect trail of how every grade was determined for institutional
                compliance.
              </p>
            </div>
          </div>
        </section>
      </main>
    </div>
  )
}