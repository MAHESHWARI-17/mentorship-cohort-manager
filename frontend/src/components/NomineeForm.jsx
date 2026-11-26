import React, { useState } from 'react';
import { Save, UserPlus } from 'lucide-react';
import { cities, timezonesByCountry } from '../data/cities';

const inputClass =
  'w-full px-3 py-2 text-xs rounded-xl border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-emerald-500 disabled:bg-slate-50 disabled:text-slate-400';
const labelClass = 'block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1';

/**
 * Nomination form for one mentor or trainee.
 * No cohort is involved: nominees go into a pool that an admin adds to cohorts.
 * `onSubmit(payload)` must return a promise; in create mode the form clears itself when it resolves.
 *
 * Edit mode: pass `initialValues` (an existing nominee) and optionally `onCancel`. The form is
 * pre-filled, keeps its values after saving, and the parent decides when to close it.
 */
export function NomineeForm({ kind, onSubmit, isPending = false, initialValues = null, onCancel = null }) {
  const isTrainee = kind === 'trainee';
  const isEdit = !!initialValues;
  const [name, setName] = useState(initialValues?.name || '');
  const [email, setEmail] = useState(initialValues?.email || '');
  const [employeeId, setEmployeeId] = useState(initialValues?.employeeId || '');
  const [location, setLocation] = useState(initialValues?.location || '');
  const [timezone, setTimezone] = useState(initialValues?.timezone || '');

  const selectedCity = cities.find(({ city, country }) => location === `${city}, ${country}`);
  // Older records may hold a location / time zone that is not in the current lists;
  // keep their value selectable so editing other fields never silently wipes it.
  const locationIsLegacy = !!location && !selectedCity;
  const timezoneOptions = selectedCity
    ? timezonesByCountry[selectedCity.country]
    : (timezone ? [{ value: timezone, label: timezone }] : []);

  const handleSubmit = async (event) => {
    event.preventDefault();
    const payload = {
      name: name.trim(),
      email: email.trim(),
      employeeId: employeeId.trim(),
      location: location || null,
      timezone: timezone || null,
    };
    try {
      await onSubmit(payload);
      if (isEdit) return;
      setName('');
      setEmail('');
      setEmployeeId('');
      setLocation('');
      setTimezone('');
    } catch {
      // the parent shows the error toast; keep the typed values so nothing is lost
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className={labelClass}>Full Name</label>
        <input required value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Jordan Scott" className={inputClass} />
      </div>
      <div>
        <label className={labelClass}>Email</label>
        <input required type="email" pattern="[^\s@]+@mphasis\.com" title="Use your @mphasis.com email address" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="jordan.scott@mphasis.com" className={inputClass} />
        <p className="mt-1 text-[11px] text-slate-500">Must end with @mphasis.com</p>
      </div>
      <div>
        <label className={labelClass}>Employee ID</label>
        <input required inputMode="numeric" pattern="[0-9]{7}" maxLength={7} title="Enter exactly 7 digits" value={employeeId} onChange={(e) => setEmployeeId(e.target.value.replace(/\D/g, '').slice(0, 7))} placeholder="1234567" className={inputClass} />
        <p className="mt-1 text-[11px] text-slate-500">Enter a unique 7-digit employee ID</p>
      </div>
      <div>
        <label className={labelClass}>Location{isTrainee ? '' : ' (optional)'}</label>
        <select
          required={isTrainee}
          value={location}
          onChange={(e) => {
            const value = e.target.value;
            setLocation(value);
            const match = cities.find(({ city, country }) => value === `${city}, ${country}`);
            setTimezone(match?.timezone || '');
          }}
          className={inputClass}
        >
          <option value="">Select a city</option>
          {locationIsLegacy && <option value={location}>{location}</option>}
          {['India', 'USA'].map((country) => (
            <optgroup key={country} label={country}>
              {cities.filter((c) => c.country === country).map(({ city }) => (
                <option key={city} value={`${city}, ${country}`}>{city}, {country}</option>
              ))}
            </optgroup>
          ))}
        </select>
      </div>
      <div>
        <label className={labelClass}>Time Zone{isTrainee ? '' : ' (optional)'}</label>
        <select
          required={isTrainee}
          value={timezone}
          onChange={(e) => setTimezone(e.target.value)}
          disabled={!selectedCity && !locationIsLegacy}
          className={inputClass}
        >
          <option value="">{selectedCity || locationIsLegacy ? 'Select a time zone' : 'Select a city first'}</option>
          {timezoneOptions.map(({ value, label }) => (
            <option key={value} value={value}>{label}</option>
          ))}
        </select>
      </div>
      <div className={isEdit ? 'flex flex-col-reverse gap-2 sm:flex-row sm:justify-end' : ''}>
        {isEdit && onCancel && (
          <button
            type="button"
            onClick={onCancel}
            disabled={isPending}
            className="py-2.5 px-4 rounded-xl text-xs font-bold text-slate-600 hover:bg-slate-100 disabled:opacity-50"
          >
            Cancel
          </button>
        )}
        <button
          type="submit"
          disabled={isPending}
          className={`${isEdit ? 'sm:w-auto' : 'w-full'} py-2.5 px-4 bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs rounded-xl shadow-sm flex items-center justify-center gap-1.5 disabled:opacity-50 transition-all`}
        >
          {isEdit ? <Save className="w-4 h-4" /> : <UserPlus className="w-4 h-4" />}
          <span>
            {isEdit
              ? (isPending ? 'Saving…' : 'Save changes')
              : (isPending ? 'Submitting…' : `Submit ${isTrainee ? 'Trainee' : 'Mentor'} Nomination`)}
          </span>
        </button>
      </div>
    </form>
  );
}
