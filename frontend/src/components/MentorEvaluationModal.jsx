import React, { useEffect, useMemo, useState } from 'react';
import { Check, ChevronLeft, ChevronRight, ClipboardCheck, UserRound } from 'lucide-react';
import { Modal } from './Modal';
import api from '../api/client';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useToast } from '../context/ToastContext';

const competencies = [
  ['problemDiscovery', 'Problem Discovery', 'Identifies the right problem, constraints, and business context.'],
  ['ownership', 'Ownership', 'Drives accountability, clarity, and delivery responsibility.'],
  ['solutionQuality', 'Solution Quality', 'Builds a practical and high-quality solution approach.'],
  ['communication', 'Communication', 'Explains decisions, tradeoffs, and progress clearly.'],
  ['leadershipDefense', 'Leadership Defense', 'Defends recommendations credibly under leader review.'],
];

const behaviors = [
  ['customerObsession', 'Customer Obsession', 'Shows strong customer focus in decisions and framing.'],
  ['biasForAction', 'Bias for Action', 'Moves quickly, resolves ambiguity, and advances the work.'],
  ['ownership', 'Ownership', 'Acts with accountability beyond narrow task boundaries.'],
  ['systemsThinking', 'Systems Thinking', 'Connects local decisions to broader platform effects.'],
  ['learningAgility', 'Learning Agility', 'Learns quickly, adapts, and improves based on feedback.'],
  ['executivePresence', 'Executive Presence', 'Communicates with confidence, clarity, and composure.'],
];

const scale = ['1 · Not yet ready', '2 · Developing', '3 · Meets expectations', '4 · Strong', '5 · Excellent / ready now'];
const steps = ['Candidate', 'Competencies', 'Behavior', 'Feedback', 'Recommendation'];
const recommendationLabels = {
  ready_now: 'Ready now',
  ready_with_coaching: 'Ready with coaching',
  not_yet_ready: 'Not yet ready',
};

function RatingRows({ items, scores, onChange }) {
  return (
    <div className="divide-y divide-slate-100">
      {items.map(([key, title, description]) => (
        <label key={key} className="grid gap-3 py-4 sm:grid-cols-[1fr_230px] sm:items-center">
          <span>
            <span className="block text-sm font-bold text-slate-800">{title}</span>
            <span className="mt-1 block text-xs text-slate-500">{description}</span>
          </span>
          <select
            value={scores[key] ?? ''}
            onChange={(event) => onChange(key, event.target.value ? Number(event.target.value) : '')}
            className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-800 focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-100"
          >
            <option value="">Select score</option>
            {scale.map((label, index) => <option key={label} value={index + 1}>{label}</option>)}
          </select>
        </label>
      ))}
    </div>
  );
}

export function MentorEvaluationModal({ isOpen, onClose, trainee, cohortId, evaluation, attendance }) {
  const [step, setStep] = useState(0);
  const [competencyScores, setCompetencyScores] = useState({});
  const [behaviorScores, setBehaviorScores] = useState({});
  const [strengths, setStrengths] = useState('');
  const [growthAreas, setGrowthAreas] = useState('');
  const [recommendation, setRecommendation] = useState('');
  const { showToast } = useToast();
  const queryClient = useQueryClient();

  useEffect(() => {
    if (!isOpen) return;
    setStep(0);
    setCompetencyScores(evaluation?.competencyScores || {});
    setBehaviorScores(evaluation?.behaviorScores || {});
    setStrengths(evaluation?.strengths || '');
    setGrowthAreas(evaluation?.growthAreas || '');
    setRecommendation(evaluation?.recommendation || '');
  }, [isOpen, evaluation]);

  const scoreSummary = useMemo(() => {
    const competencyValues = Object.values(competencyScores).filter((value) => typeof value === 'number');
    const behaviorValues = Object.values(behaviorScores).filter((value) => typeof value === 'number');
    const competencyAverage = competencyValues.length ? competencyValues.reduce((a, b) => a + b, 0) / competencyValues.length : 1;
    const behaviorAverage = behaviorValues.length ? behaviorValues.reduce((a, b) => a + b, 0) / behaviorValues.length : 1;
    const competencyPoints = ((competencyAverage - 1) / 4) * 60;
    const behaviorPoints = ((behaviorAverage - 1) / 4) * 30;
    const attendancePoints = (attendance?.attendanceRate || 0) * 0.1;
    return { competencyAverage, behaviorAverage, competencyPoints, behaviorPoints, attendancePoints, total: competencyPoints + behaviorPoints + attendancePoints };
  }, [competencyScores, behaviorScores, attendance]);

  const saveMutation = useMutation({
    mutationFn: async () => {
      const response = await api.put(`/mentor/trainees/${trainee.id}/evaluation`, {
        competencyScores,
        behaviorScores,
        strengths,
        growthAreas,
        recommendation,
      }, { params: cohortId ? { cohort_id: cohortId } : {} });
      return response.data;
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['traineeDetail', trainee.id] });
      await queryClient.invalidateQueries({ queryKey: ['adminLeadershipEvaluations', cohortId] });
      showToast('Leadership evaluation saved');
      onClose();
    },
    onError: (error) => showToast(error.response?.data?.detail || 'Could not save evaluation', 'error'),
  });

  const sectionReady = () => {
    if (step === 1) return competencies.every(([key]) => competencyScores[key]);
    if (step === 2) return behaviors.every(([key]) => behaviorScores[key]);
    if (step === 3) return strengths.trim() && growthAreas.trim();
    if (step === 4) return !!recommendation;
    return true;
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={`Leadership Evaluation · ${trainee?.name || 'Trainee'}`} maxWidth="max-w-4xl">
      <div className="space-y-5">
        <div className="grid grid-cols-5 gap-2">
          {steps.map((label, index) => (
            <button key={label} type="button" onClick={() => index <= step && setStep(index)} className={`rounded-xl border px-2 py-2 text-[11px] font-bold sm:text-xs ${step === index ? 'border-emerald-600 bg-emerald-50 text-emerald-800' : index < step ? 'border-emerald-200 bg-emerald-50/50 text-emerald-700' : 'border-slate-200 bg-slate-50 text-slate-500'}`}>
              <span className="mr-1">{index < step ? '✓' : index + 1}</span>{label}
            </button>
          ))}
        </div>

        {step === 0 && (
          <section className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
            <div className="flex items-center gap-2 text-sm font-bold text-slate-800"><UserRound className="h-4 w-4 text-emerald-700" /> Candidate</div>
            <p className="mt-3 text-lg font-bold text-slate-900">{trainee?.name}</p>
            <p className="text-sm text-slate-600">{trainee?.employeeId} · {trainee?.email}</p>
            <p className="mt-1 text-sm text-slate-500">{trainee?.cohort?.name || 'Selected cohort'}</p>
            <div className="mt-4 rounded-xl border border-blue-100 bg-blue-50 p-3 text-xs leading-relaxed text-blue-900">
              Rate the trainee on the five core competencies and six leadership behaviors, then record feedback and a recommendation. You can reopen and update this evaluation later.
            </div>
          </section>
        )}

        {step === 1 && <section><h4 className="text-base font-bold text-slate-900">Core Competencies</h4><p className="mt-1 text-xs text-slate-500">Rate each dimension from 1 (needs support) to 5 (excellent / ready now).</p><RatingRows items={competencies} scores={competencyScores} onChange={(key, value) => setCompetencyScores((prev) => ({ ...prev, [key]: value }))} /></section>}
        {step === 2 && <section><h4 className="text-base font-bold text-slate-900">Leadership Behaviors</h4><p className="mt-1 text-xs text-slate-500">Rate the behaviors you observed using the same 1–5 scale.</p><RatingRows items={behaviors} scores={behaviorScores} onChange={(key, value) => setBehaviorScores((prev) => ({ ...prev, [key]: value }))} /></section>}
        {step === 3 && (
          <section className="space-y-4">
            <h4 className="text-base font-bold text-slate-900">Written Feedback</h4>
            <label className="block text-sm font-semibold text-slate-700">Strengths<textarea value={strengths} onChange={(event) => setStrengths(event.target.value)} rows={4} maxLength={5000} placeholder="What stood out positively?" className="mt-2 w-full rounded-xl border border-slate-200 p-3 text-sm focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-100" /></label>
            <label className="block text-sm font-semibold text-slate-700">Growth Areas<textarea value={growthAreas} onChange={(event) => setGrowthAreas(event.target.value)} rows={4} maxLength={5000} placeholder="Where should the employee improve next?" className="mt-2 w-full rounded-xl border border-slate-200 p-3 text-sm focus:border-emerald-500 focus:outline-none focus:ring-2 focus:ring-emerald-100" /></label>
          </section>
        )}
        {step === 4 && (
          <section className="space-y-5">
            <div>
              <h4 className="text-base font-bold text-slate-900">Recommendation</h4>
              <p className="mt-1 text-xs text-slate-500">Choose the outcome that best reflects readiness after reviewing scores and feedback.</p>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              {Object.entries(recommendationLabels).map(([value, label]) => (
                <button key={value} type="button" onClick={() => setRecommendation(value)} className={`rounded-xl border p-4 text-left text-sm font-bold ${recommendation === value ? 'border-emerald-500 bg-emerald-50 text-emerald-900 ring-2 ring-emerald-100' : 'border-slate-200 text-slate-700 hover:border-slate-300'}`}>
                  <span className="mr-2 inline-flex h-5 w-5 items-center justify-center rounded-full bg-slate-100">{recommendation === value ? <Check className="h-3.5 w-3.5 text-emerald-700" /> : '•'}</span>{label}
                </button>
              ))}
            </div>
            <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
              <div className="mb-3 flex items-center gap-2 text-sm font-bold text-slate-800"><ClipboardCheck className="h-4 w-4 text-emerald-700" /> Score Summary · out of 100</div>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <div className="rounded-xl bg-white p-3"><p className="text-[11px] text-slate-500">Competency avg</p><p className="mt-1 font-bold">{scoreSummary.competencyAverage.toFixed(2)} / 5</p><p className="text-xs text-emerald-700">{scoreSummary.competencyPoints.toFixed(1)} / 60</p></div>
                <div className="rounded-xl bg-white p-3"><p className="text-[11px] text-slate-500">Behavior avg</p><p className="mt-1 font-bold">{scoreSummary.behaviorAverage.toFixed(2)} / 5</p><p className="text-xs text-emerald-700">{scoreSummary.behaviorPoints.toFixed(1)} / 30</p></div>
                <div className="rounded-xl bg-white p-3"><p className="text-[11px] text-slate-500">Attendance</p><p className="mt-1 font-bold">{attendance?.attendanceRate || 0}%</p><p className="text-xs text-emerald-700">{scoreSummary.attendancePoints.toFixed(1)} / 10</p></div>
                <div className="rounded-xl bg-emerald-100 p-3"><p className="text-[11px] text-emerald-800">Total score</p><p className="mt-1 text-lg font-black text-emerald-900">{scoreSummary.total.toFixed(1)} / 100</p><p className="text-[10px] text-emerald-800">Attendance from completed sessions</p></div>
              </div>
              <p className="mt-3 text-[11px] leading-relaxed text-slate-500">Formula: competency points = (average − 1) ÷ 4 × 60; behavior points = (average − 1) ÷ 4 × 30; attendance points = attendance rate × 10%. The three parts add to 100 points.</p>
            </div>
          </section>
        )}

        <div className="flex items-center justify-between border-t border-slate-100 pt-4">
          <button type="button" onClick={() => setStep((current) => Math.max(0, current - 1))} disabled={step === 0 || saveMutation.isPending} className="inline-flex items-center gap-1 rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-bold text-slate-700 disabled:opacity-40"><ChevronLeft className="h-4 w-4" /> Back</button>
          {step < steps.length - 1 ? (
            <button type="button" onClick={() => setStep((current) => current + 1)} disabled={!sectionReady()} className="inline-flex items-center gap-1 rounded-xl bg-slate-900 px-5 py-2.5 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-40">Next <ChevronRight className="h-4 w-4" /></button>
          ) : (
            <button type="button" onClick={() => saveMutation.mutate()} disabled={!sectionReady() || saveMutation.isPending} className="inline-flex items-center gap-2 rounded-xl bg-emerald-700 px-5 py-2.5 text-sm font-bold text-white disabled:opacity-50">{saveMutation.isPending ? 'Saving…' : evaluation ? 'Update Evaluation' : 'Submit Evaluation'}</button>
          )}
        </div>
      </div>
    </Modal>
  );
}
