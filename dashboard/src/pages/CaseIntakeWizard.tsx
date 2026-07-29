import { useState } from 'react';
import { updateEvidenceMetadata, updateExaminer, addChainOfCustodyEntry } from '../services/api';
import { Check, Shield, ArrowRight, ArrowLeft } from 'lucide-react';
import LoadingSpinner from '../components/LoadingSpinner';

interface CaseIntakeWizardProps {
  caseId: string;
  exhibitId: string;
  onComplete: () => void;
}

export default function CaseIntakeWizard({ caseId, exhibitId, onComplete }: CaseIntakeWizardProps) {
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);

  const [step1Data, setStep1Data] = useState({
    evidence_bag_tag: '',
    seizure_date: '',
    seizure_location: '',
    seizure_authority: '',
    warrant_number: '',
    storage_location: '',
    acquisition_tool: 'E-RAKSHAK',
    acquisition_tool_version: 'v0.1.0',
    notes: ''
  });

  const [step2Data, setStep2Data] = useState({
    name: '',
    badge_id: '',
    rank_title: '',
    agency: '',
    email: '',
    phone: '',
    notes: ''
  });

  const [step3Data, setStep3Data] = useState({
    action: 'Evidence seized',
    timestamp: new Date().toISOString().slice(0, 16),
    location: '',
    evidence_condition: 'Sealed - Good',
    notes: ''
  });

  const handleSubmit = async () => {
    setLoading(true);
    try {
      await updateEvidenceMetadata(step1Data);
      await updateExaminer(step2Data);
      await addChainOfCustodyEntry({
        ...step3Data,
        performed_by: step2Data.name,
      });
      onComplete();
    } catch (err) {
      console.error(err);
      alert('Error submitting intake form');
    } finally {
      setLoading(false);
    }
  };

  const nextStep = (e: React.FormEvent) => {
    e.preventDefault();
    setStep(s => Math.min(s + 1, 3));
  };
  const prevStep = () => setStep(s => Math.max(s - 1, 1));

  const inputClass = "w-full bg-[#1a1a2e] border border-[#333] text-white p-2.5 rounded-md focus:border-accent focus:outline-none transition-colors";
  const labelClass = "block text-xs uppercase text-text-secondary mb-1.5 font-medium";

  return (
    <div className="min-h-screen bg-bg text-text-primary flex flex-col items-center py-12 px-4 overflow-y-auto">
      <div className="flex items-center gap-3 mb-10">
        <Shield className="w-10 h-10 text-accent" />
        <h1 className="text-3xl font-bold tracking-wider">E-RAKSHAK</h1>
      </div>

      <div className="w-full max-w-2xl bg-panel rounded-xl shadow-2xl border border-border overflow-hidden">
        {/* Progress Bar */}
        <div className="flex border-b border-border bg-panel-alt">
          {[1, 2, 3].map((num) => (
            <div key={num} className={`flex-1 flex flex-col items-center py-4 relative ${step === num ? 'bg-panel' : ''}`}>
              <div className={`w-8 h-8 rounded-full flex items-center justify-center mb-2 z-10 
                ${step > num ? 'bg-success text-white' : step === num ? 'bg-accent text-white' : 'bg-[#1a1a2e] text-text-secondary border border-border'}`}>
                {step > num ? <Check className="w-5 h-5" /> : num}
              </div>
              <span className={`text-xs font-semibold uppercase ${step === num ? 'text-accent' : 'text-text-secondary'}`}>
                {num === 1 ? 'Evidence Details' : num === 2 ? 'Examiner Info' : 'Chain of Custody'}
              </span>
            </div>
          ))}
        </div>

        <div className="p-8">
          <form onSubmit={step === 3 ? (e) => { e.preventDefault(); handleSubmit(); } : nextStep}>
            {step === 1 && (
              <div className="space-y-5 animate-in fade-in slide-in-from-right-4 duration-300">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className={labelClass}>Case ID</label>
                    <input type="text" className={`${inputClass} opacity-70 cursor-not-allowed`} value={caseId} readOnly />
                  </div>
                  <div>
                    <label className={labelClass}>Exhibit ID</label>
                    <input type="text" className={`${inputClass} opacity-70 cursor-not-allowed`} value={exhibitId} readOnly />
                  </div>
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className={labelClass}>Evidence / Bag Tag Number</label>
                    <input type="text" className={inputClass} value={step1Data.evidence_bag_tag} onChange={e => setStep1Data({...step1Data, evidence_bag_tag: e.target.value})} />
                  </div>
                  <div>
                    <label className={labelClass}>Storage Location</label>
                    <input type="text" className={inputClass} value={step1Data.storage_location} onChange={e => setStep1Data({...step1Data, storage_location: e.target.value})} />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className={labelClass}>Seizure Date</label>
                    <input type="date" className={inputClass} value={step1Data.seizure_date} onChange={e => setStep1Data({...step1Data, seizure_date: e.target.value})} />
                  </div>
                  <div>
                    <label className={labelClass}>Seizure Location</label>
                    <input type="text" className={inputClass} value={step1Data.seizure_location} onChange={e => setStep1Data({...step1Data, seizure_location: e.target.value})} />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className={labelClass}>Seizure Authority</label>
                    <input type="text" className={inputClass} value={step1Data.seizure_authority} onChange={e => setStep1Data({...step1Data, seizure_authority: e.target.value})} />
                  </div>
                  <div>
                    <label className={labelClass}>Warrant Number</label>
                    <input type="text" className={inputClass} value={step1Data.warrant_number} onChange={e => setStep1Data({...step1Data, warrant_number: e.target.value})} />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className={labelClass}>Acquisition Tool</label>
                    <input type="text" className={inputClass} value={step1Data.acquisition_tool} onChange={e => setStep1Data({...step1Data, acquisition_tool: e.target.value})} />
                  </div>
                  <div>
                    <label className={labelClass}>Tool Version</label>
                    <input type="text" className={inputClass} value={step1Data.acquisition_tool_version} onChange={e => setStep1Data({...step1Data, acquisition_tool_version: e.target.value})} />
                  </div>
                </div>

                <div>
                  <label className={labelClass}>Notes</label>
                  <textarea className={`${inputClass} min-h-[80px]`} value={step1Data.notes} onChange={e => setStep1Data({...step1Data, notes: e.target.value})}></textarea>
                </div>
              </div>
            )}

            {step === 2 && (
              <div className="space-y-5 animate-in fade-in slide-in-from-right-4 duration-300">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className={labelClass}>Name *</label>
                    <input type="text" required className={inputClass} value={step2Data.name} onChange={e => setStep2Data({...step2Data, name: e.target.value})} />
                  </div>
                  <div>
                    <label className={labelClass}>Badge / ID Number *</label>
                    <input type="text" required className={inputClass} value={step2Data.badge_id} onChange={e => setStep2Data({...step2Data, badge_id: e.target.value})} />
                  </div>
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className={labelClass}>Rank / Title</label>
                    <input type="text" className={inputClass} value={step2Data.rank_title} onChange={e => setStep2Data({...step2Data, rank_title: e.target.value})} />
                  </div>
                  <div>
                    <label className={labelClass}>Agency / Organization *</label>
                    <input type="text" required className={inputClass} value={step2Data.agency} onChange={e => setStep2Data({...step2Data, agency: e.target.value})} />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className={labelClass}>Email</label>
                    <input type="email" className={inputClass} value={step2Data.email} onChange={e => setStep2Data({...step2Data, email: e.target.value})} />
                  </div>
                  <div>
                    <label className={labelClass}>Phone</label>
                    <input type="tel" className={inputClass} value={step2Data.phone} onChange={e => setStep2Data({...step2Data, phone: e.target.value})} />
                  </div>
                </div>

                <div>
                  <label className={labelClass}>Notes</label>
                  <textarea className={`${inputClass} min-h-[80px]`} value={step2Data.notes} onChange={e => setStep2Data({...step2Data, notes: e.target.value})}></textarea>
                </div>
              </div>
            )}

            {step === 3 && (
              <div className="space-y-5 animate-in fade-in slide-in-from-right-4 duration-300">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className={labelClass}>Action</label>
                    <select className={inputClass} value={step3Data.action} onChange={e => setStep3Data({...step3Data, action: e.target.value})}>
                      <option>Evidence seized</option>
                      <option>Evidence received for examination</option>
                      <option>Evidence transferred</option>
                      <option>Evidence stored</option>
                    </select>
                  </div>
                  <div>
                    <label className={labelClass}>Date / Time</label>
                    <input type="datetime-local" required className={inputClass} value={step3Data.timestamp} onChange={e => setStep3Data({...step3Data, timestamp: e.target.value})} />
                  </div>
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className={labelClass}>Performed By</label>
                    <input type="text" className={`${inputClass} opacity-70`} value={step2Data.name} readOnly placeholder="Auto-filled from Step 2" />
                  </div>
                  <div>
                    <label className={labelClass}>Location</label>
                    <input type="text" className={inputClass} value={step3Data.location} onChange={e => setStep3Data({...step3Data, location: e.target.value})} />
                  </div>
                </div>

                <div>
                  <label className={labelClass}>Evidence Condition</label>
                  <select className={inputClass} value={step3Data.evidence_condition} onChange={e => setStep3Data({...step3Data, evidence_condition: e.target.value})}>
                    <option>Sealed - Good</option>
                    <option>Sealed - Damaged</option>
                    <option>Unsealed</option>
                    <option>Unknown</option>
                  </select>
                </div>

                <div>
                  <label className={labelClass}>Notes</label>
                  <textarea className={`${inputClass} min-h-[80px]`} value={step3Data.notes} onChange={e => setStep3Data({...step3Data, notes: e.target.value})}></textarea>
                </div>
              </div>
            )}

            <div className="mt-10 flex justify-between pt-6 border-t border-border">
              <button 
                type="button" 
                onClick={prevStep} 
                disabled={step === 1 || loading}
                className={`flex items-center gap-2 px-6 py-2.5 rounded-md font-medium transition-colors ${step === 1 ? 'opacity-0 pointer-events-none' : 'bg-panel-alt hover:bg-[#2a2a3e] text-white'}`}
              >
                <ArrowLeft className="w-4 h-4" /> Back
              </button>
              
              <button 
                type="submit" 
                disabled={loading}
                className="flex items-center gap-2 px-6 py-2.5 rounded-md font-medium bg-accent hover:bg-accent/90 text-white transition-colors"
              >
                {loading ? <LoadingSpinner /> : step === 3 ? 'Begin Examination' : 'Next Step'}
                {!loading && step !== 3 && <ArrowRight className="w-4 h-4" />}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
