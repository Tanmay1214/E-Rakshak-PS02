import { useState, useEffect } from 'react';
import { 
  fetchEvidenceMetadata, updateEvidenceMetadata, 
  fetchExaminer, updateExaminer, 
  fetchChainOfCustody, addChainOfCustodyEntry, deleteChainOfCustodyEntry 
} from '../services/api';
import { Plus, Trash2, Save, ChevronDown, ChevronUp } from 'lucide-react';
import LoadingSpinner from '../components/LoadingSpinner';
import type { EvidenceMetadata, ExaminerInfo, ChainOfCustodyEntry } from '../types/evidence';
import { formatTimestamp } from '../utils/formatters';

export default function CaseInfoPage() {
  const [loading, setLoading] = useState(true);
  const [saving1, setSaving1] = useState(false);
  const [saving2, setSaving2] = useState(false);
  const [saving3, setSaving3] = useState(false);
  
  const [expanded, setExpanded] = useState({
    evidence: true,
    examiner: true,
    chain: true
  });

  const [metadata, setMetadata] = useState<Partial<EvidenceMetadata>>({});
  const [examiner, setExaminer] = useState<Partial<ExaminerInfo>>({});
  const [chain, setChain] = useState<ChainOfCustodyEntry[]>([]);
  
  const [showAddEntry, setShowAddEntry] = useState(false);
  const [newEntry, setNewEntry] = useState({
    action: 'Evidence transferred',
    timestamp: new Date().toISOString().slice(0, 16),
    location: '',
    performed_by: '',
    received_by: '',
    evidence_condition: 'Sealed - Good',
    notes: ''
  });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [metaData, examData, chainData] = await Promise.all([
        fetchEvidenceMetadata().catch(() => ({})),
        fetchExaminer().catch(() => ({})),
        fetchChainOfCustody().catch(() => ({ entries: [] }))
      ]);
      setMetadata(metaData || {});
      setExaminer(examData || {});
      setChain(chainData?.entries || []);
      
      if (examData && 'name' in examData && examData.name) {
        setNewEntry(prev => ({ ...prev, performed_by: examData.name as string }));
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveMetadata = async () => {
    setSaving1(true);
    try {
      await updateEvidenceMetadata(metadata);
      alert('Evidence details saved');
    } catch (err) {
      alert('Error saving');
    } finally {
      setSaving1(false);
    }
  };

  const handleSaveExaminer = async () => {
    setSaving2(true);
    try {
      await updateExaminer(examiner);
      alert('Examiner info saved');
    } catch (err) {
      alert('Error saving');
    } finally {
      setSaving2(false);
    }
  };

  const handleAddChainEntry = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving3(true);
    try {
      await addChainOfCustodyEntry(newEntry);
      const chainData = await fetchChainOfCustody();
      setChain(chainData.entries || []);
      setShowAddEntry(false);
      setNewEntry(prev => ({
        ...prev,
        timestamp: new Date().toISOString().slice(0, 16),
        notes: '',
        location: '',
        received_by: ''
      }));
    } catch (err) {
      alert('Error adding entry');
    } finally {
      setSaving3(false);
    }
  };

  const handleDeleteEntry = async (id: string) => {
    if (!confirm('Delete this entry?')) return;
    try {
      await deleteChainOfCustodyEntry(id);
      setChain(chain.filter(c => c.id !== id));
    } catch (err) {
      alert('Error deleting');
    }
  };

  const toggleSection = (section: keyof typeof expanded) => {
    setExpanded(prev => ({ ...prev, [section]: !prev[section] }));
  };

  if (loading) {
    return <div className="flex justify-center p-12"><LoadingSpinner /></div>;
  }

  const inputClass = "w-full bg-[#1a1a2e] border border-[#333] text-white p-2.5 rounded-md focus:border-accent focus:outline-none transition-colors text-sm";
  const labelClass = "block text-xs uppercase text-text-secondary mb-1.5 font-medium";
  const sectionHeaderClass = "flex items-center justify-between p-4 bg-panel-alt cursor-pointer hover:bg-[#1f2937] transition-colors";
  
  return (
    <div className="max-w-5xl mx-auto space-y-6 pb-12">
      <h1 className="text-2xl font-bold text-white mb-6">Case Information</h1>

      {/* Evidence Details */}
      <div className="bg-panel rounded-lg border border-border overflow-hidden">
        <div className={sectionHeaderClass} onClick={() => toggleSection('evidence')}>
          <h2 className="text-lg font-semibold text-white">Evidence Details</h2>
          {expanded.evidence ? <ChevronUp className="w-5 h-5 text-text-secondary" /> : <ChevronDown className="w-5 h-5 text-text-secondary" />}
        </div>
        
        {expanded.evidence && (
          <div className="p-6 border-t border-border">
            <div className="grid grid-cols-2 gap-6 mb-6">
              <div>
                <label className={labelClass}>Evidence / Bag Tag Number</label>
                <input type="text" className={inputClass} value={metadata.evidence_bag_tag || ''} onChange={e => setMetadata({...metadata, evidence_bag_tag: e.target.value})} />
              </div>
              <div>
                <label className={labelClass}>Storage Location</label>
                <input type="text" className={inputClass} value={metadata.storage_location || ''} onChange={e => setMetadata({...metadata, storage_location: e.target.value})} />
              </div>
              <div>
                <label className={labelClass}>Seizure Date</label>
                <input type="date" className={inputClass} value={metadata.seizure_date || ''} onChange={e => setMetadata({...metadata, seizure_date: e.target.value})} />
              </div>
              <div>
                <label className={labelClass}>Seizure Location</label>
                <input type="text" className={inputClass} value={metadata.seizure_location || ''} onChange={e => setMetadata({...metadata, seizure_location: e.target.value})} />
              </div>
              <div>
                <label className={labelClass}>Seizure Authority</label>
                <input type="text" className={inputClass} value={metadata.seizure_authority || ''} onChange={e => setMetadata({...metadata, seizure_authority: e.target.value})} />
              </div>
              <div>
                <label className={labelClass}>Warrant Number</label>
                <input type="text" className={inputClass} value={metadata.warrant_number || ''} onChange={e => setMetadata({...metadata, warrant_number: e.target.value})} />
              </div>
              <div>
                <label className={labelClass}>Acquisition Tool</label>
                <input type="text" className={inputClass} value={metadata.acquisition_tool || ''} onChange={e => setMetadata({...metadata, acquisition_tool: e.target.value})} />
              </div>
              <div>
                <label className={labelClass}>Tool Version</label>
                <input type="text" className={inputClass} value={metadata.acquisition_tool_version || ''} onChange={e => setMetadata({...metadata, acquisition_tool_version: e.target.value})} />
              </div>
            </div>
            <div>
              <label className={labelClass}>Notes</label>
              <textarea className={`${inputClass} min-h-[80px] mb-4`} value={metadata.notes || ''} onChange={e => setMetadata({...metadata, notes: e.target.value})}></textarea>
            </div>
            <div className="flex justify-end">
              <button onClick={handleSaveMetadata} disabled={saving1} className="flex items-center gap-2 px-4 py-2 bg-accent hover:bg-accent/90 text-white rounded-md text-sm font-medium">
                {saving1 ? <LoadingSpinner /> : <Save className="w-4 h-4" />} Save Evidence Details
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Examiner Info */}
      <div className="bg-panel rounded-lg border border-border overflow-hidden">
        <div className={sectionHeaderClass} onClick={() => toggleSection('examiner')}>
          <h2 className="text-lg font-semibold text-white">Examiner Information</h2>
          {expanded.examiner ? <ChevronUp className="w-5 h-5 text-text-secondary" /> : <ChevronDown className="w-5 h-5 text-text-secondary" />}
        </div>
        
        {expanded.examiner && (
          <div className="p-6 border-t border-border">
            <div className="grid grid-cols-2 gap-6 mb-6">
              <div>
                <label className={labelClass}>Name</label>
                <input type="text" className={inputClass} value={examiner.name || ''} onChange={e => setExaminer({...examiner, name: e.target.value})} />
              </div>
              <div>
                <label className={labelClass}>Badge / ID Number</label>
                <input type="text" className={inputClass} value={examiner.badge_id || ''} onChange={e => setExaminer({...examiner, badge_id: e.target.value})} />
              </div>
              <div>
                <label className={labelClass}>Rank / Title</label>
                <input type="text" className={inputClass} value={examiner.rank_title || ''} onChange={e => setExaminer({...examiner, rank_title: e.target.value})} />
              </div>
              <div>
                <label className={labelClass}>Agency / Organization</label>
                <input type="text" className={inputClass} value={examiner.agency || ''} onChange={e => setExaminer({...examiner, agency: e.target.value})} />
              </div>
              <div>
                <label className={labelClass}>Email</label>
                <input type="email" className={inputClass} value={examiner.email || ''} onChange={e => setExaminer({...examiner, email: e.target.value})} />
              </div>
              <div>
                <label className={labelClass}>Phone</label>
                <input type="tel" className={inputClass} value={examiner.phone || ''} onChange={e => setExaminer({...examiner, phone: e.target.value})} />
              </div>
            </div>
            <div>
              <label className={labelClass}>Notes</label>
              <textarea className={`${inputClass} min-h-[80px] mb-4`} value={examiner.notes || ''} onChange={e => setExaminer({...examiner, notes: e.target.value})}></textarea>
            </div>
            <div className="flex justify-end">
              <button onClick={handleSaveExaminer} disabled={saving2} className="flex items-center gap-2 px-4 py-2 bg-accent hover:bg-accent/90 text-white rounded-md text-sm font-medium">
                {saving2 ? <LoadingSpinner /> : <Save className="w-4 h-4" />} Save Examiner Info
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Chain of Custody */}
      <div className="bg-panel rounded-lg border border-border overflow-hidden">
        <div className={sectionHeaderClass} onClick={() => toggleSection('chain')}>
          <h2 className="text-lg font-semibold text-white">Chain of Custody</h2>
          {expanded.chain ? <ChevronUp className="w-5 h-5 text-text-secondary" /> : <ChevronDown className="w-5 h-5 text-text-secondary" />}
        </div>
        
        {expanded.chain && (
          <div className="p-0 border-t border-border">
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="text-xs text-text-secondary uppercase bg-panel-alt border-b border-border">
                  <tr>
                    <th className="px-4 py-3">#</th>
                    <th className="px-4 py-3">Date/Time</th>
                    <th className="px-4 py-3">Action</th>
                    <th className="px-4 py-3">Performed By</th>
                    <th className="px-4 py-3">Received By</th>
                    <th className="px-4 py-3">Location</th>
                    <th className="px-4 py-3">Condition</th>
                    <th className="px-4 py-3">Notes</th>
                    <th className="px-4 py-3"></th>
                  </tr>
                </thead>
                <tbody>
                  {chain.map((entry, idx) => (
                    <tr key={entry.id || idx} className="border-b border-border hover:bg-[#1f2937] transition-colors">
                      <td className="px-4 py-3">{entry.entry_index || idx + 1}</td>
                      <td className="px-4 py-3 whitespace-nowrap">{formatTimestamp(entry.timestamp)}</td>
                      <td className="px-4 py-3">{entry.action}</td>
                      <td className="px-4 py-3">{entry.performed_by}</td>
                      <td className="px-4 py-3">{entry.received_by}</td>
                      <td className="px-4 py-3">{entry.location}</td>
                      <td className="px-4 py-3">
                        <span className="px-2 py-1 rounded-full text-xs bg-[#1a1a2e] border border-border">
                          {entry.evidence_condition}
                        </span>
                      </td>
                      <td className="px-4 py-3 max-w-[200px] truncate" title={entry.notes}>{entry.notes}</td>
                      <td className="px-4 py-3 text-right">
                        <button onClick={() => entry.id && handleDeleteEntry(entry.id)} className="text-danger hover:text-red-400 p-1">
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  ))}
                  {chain.length === 0 && (
                    <tr>
                      <td colSpan={9} className="px-4 py-8 text-center text-text-secondary">No chain of custody entries found</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <div className="p-4 border-t border-border">
              {!showAddEntry ? (
                <button onClick={() => setShowAddEntry(true)} className="flex items-center gap-2 text-sm text-accent hover:text-accent/80 font-medium">
                  <Plus className="w-4 h-4" /> Add Entry
                </button>
              ) : (
                <form onSubmit={handleAddChainEntry} className="bg-[#151923] p-4 rounded-lg border border-border mt-2">
                  <h3 className="text-sm font-semibold mb-4 text-white">New Chain of Custody Entry</h3>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-4 mb-4">
                    <div>
                      <label className={labelClass}>Action</label>
                      <select className={inputClass} value={newEntry.action} onChange={e => setNewEntry({...newEntry, action: e.target.value})}>
                        <option>Evidence seized</option>
                        <option>Evidence received for examination</option>
                        <option>Evidence transferred</option>
                        <option>Evidence stored</option>
                      </select>
                    </div>
                    <div>
                      <label className={labelClass}>Date / Time</label>
                      <input type="datetime-local" required className={inputClass} value={newEntry.timestamp} onChange={e => setNewEntry({...newEntry, timestamp: e.target.value})} />
                    </div>
                    <div>
                      <label className={labelClass}>Location</label>
                      <input type="text" className={inputClass} value={newEntry.location} onChange={e => setNewEntry({...newEntry, location: e.target.value})} />
                    </div>
                    <div>
                      <label className={labelClass}>Performed By</label>
                      <input type="text" className={inputClass} value={newEntry.performed_by} onChange={e => setNewEntry({...newEntry, performed_by: e.target.value})} />
                    </div>
                    <div>
                      <label className={labelClass}>Received By</label>
                      <input type="text" className={inputClass} value={newEntry.received_by} onChange={e => setNewEntry({...newEntry, received_by: e.target.value})} />
                    </div>
                    <div>
                      <label className={labelClass}>Evidence Condition</label>
                      <select className={inputClass} value={newEntry.evidence_condition} onChange={e => setNewEntry({...newEntry, evidence_condition: e.target.value})}>
                        <option>Sealed - Good</option>
                        <option>Sealed - Damaged</option>
                        <option>Unsealed</option>
                        <option>Unknown</option>
                      </select>
                    </div>
                  </div>
                  <div className="mb-4">
                    <label className={labelClass}>Notes</label>
                    <textarea className={`${inputClass} min-h-[60px]`} value={newEntry.notes} onChange={e => setNewEntry({...newEntry, notes: e.target.value})}></textarea>
                  </div>
                  <div className="flex justify-end gap-3">
                    <button type="button" onClick={() => setShowAddEntry(false)} className="px-4 py-2 text-sm text-text-secondary hover:text-white">Cancel</button>
                    <button type="submit" disabled={saving3} className="flex items-center gap-2 px-4 py-2 bg-accent hover:bg-accent/90 text-white rounded-md text-sm font-medium">
                      {saving3 ? <LoadingSpinner /> : <Plus className="w-4 h-4" />} Add Entry
                    </button>
                  </div>
                </form>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
