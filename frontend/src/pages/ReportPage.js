// src/pages/ReportPage.js — FINAL
// Shows report after exam with PDF download

import React, { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { reportAPI } from '../services/api';

const LEVEL_STYLE = {
  SAFE    : { bg:'#052e16', border:'#14532d', color:'#10b981' },
  WARNING : { bg:'#1c1003', border:'#78350f', color:'#f59e0b' },
  HIGH    : { bg:'#1a0505', border:'#7f1d1d', color:'#ef4444' },
  CRITICAL: { bg:'#1a0505', border:'#991b1b', color:'#dc2626' },
};
const MODULE_ICONS = { face:'👤', pose:'👁', object:'📱', audio:'🎙', browser:'🌐' };

export default function ReportPage() {
  const [sp]      = useSearchParams();
  const sessionId = sp.get('session');
  const navigate  = useNavigate();

  const [data,      setData]    = useState(null);
  const [loading,   setLoading] = useState(true);
  const [error,     setError]   = useState('');
  const [dlLoading, setDlLoad]  = useState(false);

  useEffect(() => {
    if (!sessionId) { setError('No session ID'); setLoading(false); return; }
    reportAPI.get(sessionId)
      .then(r => setData(r.data))
      .catch(e => setError(e.response?.data?.detail || 'Failed to load report'))
      .finally(() => setLoading(false));
  }, [sessionId]);

  // const handleDownload = async () => {
  //   setDlLoad(true);
  //   try {
  //     // Generate first, then download
  //     const token = localStorage.getItem('token');
  //     await fetch(`/api/v1/reports/generate/${sessionId}`, {
  //       method: 'POST',
  //       headers: { Authorization: `Bearer ${token}` },
  //     });
  //     // Trigger download via link
  //     const link = document.createElement('a');
  //     link.href  = `/api/v1/reports/${sessionId}/download`;
  //     link.setAttribute('download', `report_${sessionId.slice(0,8)}.pdf`);
  //     // Append auth via fetch + blob (handles auth header)
  //     const res  = await fetch(link.href, {
  //       headers: { Authorization: `Bearer ${token}` },
  //     });
  //     const blob = await res.blob();
  //     const url  = URL.createObjectURL(blob);
  //     link.href  = url;
  //     document.body.appendChild(link);
  //     link.click();
  //     document.body.removeChild(link);
  //     URL.revokeObjectURL(url);
  //   } catch { alert('PDF generation failed. Try again.'); }
  //   finally  { setDlLoad(false); }
  // };

  const handleDownload = async () => {
    setDlLoad(true);
    try {
      const token = localStorage.getItem('token');

      // Step 1: Generate (safe to call even if already exists)
      await fetch(`/api/v1/reports/generate/${sessionId}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}` },
      });

      // Step 2: Fetch PDF as blob with auth header
      const response = await fetch(`/api/v1/reports/${sessionId}/download`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });

      if (!response.ok) {
        throw new Error(`Server returned ${response.status}`);
      }

      // Step 3: Force browser download
      const blob = await response.blob();
      const url  = window.URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.style.display = 'none';
      a.href          = url;
      a.download      = `ProctorAI_Report_${sessionId.slice(0, 8)}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);

    } catch (e) {
      alert(`PDF download failed: ${e.message}. Check if the exam session was completed.`);
    } finally {
      setDlLoad(false);
    }
  };

  if (loading) return (
    <div style={{ minHeight:'100vh', background:'var(--bg)', display:'flex',
      alignItems:'center', justifyContent:'center' }}>
      <div>
        <div style={{ width:40, height:40, border:'3px solid var(--border)',
          borderTopColor:'var(--accent)', borderRadius:'50%',
          animation:'spin 0.8s linear infinite', margin:'0 auto 16px' }}/>
        <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
        <p style={{ color:'var(--muted)', textAlign:'center' }}>Loading report...</p>
      </div>
    </div>
  );

  if (error) return (
    <div style={{ minHeight:'100vh', background:'var(--bg)', display:'flex',
      alignItems:'center', justifyContent:'center' }}>
      <div className="card" style={{ textAlign:'center', maxWidth:400 }}>
        <div style={{ fontSize:'32px', marginBottom:'12px' }}>⚠</div>
        <p style={{ color:'var(--high)' }}>{error}</p>
        <button className="btn-ghost" style={{ marginTop:'16px' }}
          onClick={() => navigate('/dashboard')}>← Dashboard</button>
      </div>
    </div>
  );

  const risk   = data?.risk_assessment || {};
  const level  = risk.risk_level || 'SAFE';
  const score  = risk.final_score || 0;
  const prob   = risk.cheat_probability || 0;
  const lvl    = LEVEL_STYLE[level] || LEVEL_STYLE.SAFE;
  const viols  = data?.violations || [];
  const mstats = data?.module_stats || {};

  return (
    <div style={{ minHeight:'100vh', background:'var(--bg)' }}>
      {/* Navbar */}
      <nav style={{
        display:'flex', alignItems:'center', justifyContent:'space-between',
        padding:'14px 28px', borderBottom:'1px solid var(--border)',
        background:'var(--bg2)', position:'sticky', top:0, zIndex:10,
      }}>
        <div style={{ display:'flex', alignItems:'center', gap:'10px' }}>
          <span>🔒</span>
          <span style={{ fontFamily:'Syne', fontWeight:700 }}>Exam Report</span>
        </div>
        <div style={{ display:'flex', gap:'10px' }}>
          <button className="btn-primary"
            style={{ padding:'8px 18px', fontSize:'12px' }}
            onClick={handleDownload} disabled={dlLoading}>
            {dlLoading ? 'Generating...' : '⬇ Download PDF'}
          </button>
          <button className="btn-ghost"
            style={{ padding:'8px 16px', fontSize:'12px' }}
            onClick={() => navigate('/dashboard')}>
            ← Dashboard
          </button>
        </div>
      </nav>

      <div style={{ maxWidth:'860px', margin:'0 auto', padding:'32px 24px' }}>

        {/* Candidate + exam info */}
        <div className="card" style={{ marginBottom:'20px' }}>
          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'20px' }}>
            <div>
              <div style={{ color:'var(--muted)', fontSize:'11px', marginBottom:'4px' }}>CANDIDATE</div>
              <div style={{ fontFamily:'Syne', fontWeight:700, fontSize:'16px' }}>
                {data?.candidate?.name}
              </div>
              <div style={{ color:'var(--muted)', fontSize:'12px' }}>{data?.candidate?.email}</div>
            </div>
            <div>
              <div style={{ color:'var(--muted)', fontSize:'11px', marginBottom:'4px' }}>EXAM</div>
              <div style={{ fontFamily:'Syne', fontWeight:700, fontSize:'16px' }}>
                {data?.exam?.title}
              </div>
              <div style={{ color:'var(--muted)', fontSize:'12px' }}>
                {data?.exam?.started_at
                  ? new Date(data.exam.started_at * 1000).toLocaleString() : '—'}
              </div>
            </div>
          </div>
        </div>

        {/* 4 metric cards */}
        <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:'12px', marginBottom:'20px' }}>
          {[
            { label:'Final Score',       value:`${score.toFixed(1)}`, unit:'/100', color: lvl.color },
            { label:'Risk Level',        value: level,                unit:'',     color: lvl.color },
            { label:'Cheat Probability', value:`${(prob*100).toFixed(1)}`, unit:'%',
              color: prob>0.75?'var(--critical)':prob>0.4?'var(--warn)':'var(--safe)' },
            { label:'Violations',        value: viols.length, unit:'', color:'var(--warn)' },
          ].map(({ label, value, unit, color }) => (
            <div key={label} className="card" style={{ textAlign:'center', padding:'16px' }}>
              <div style={{ fontFamily:'Syne', fontWeight:800, fontSize:'24px', color }}>
                {value}<span style={{ fontSize:'13px', opacity:0.6 }}>{unit}</span>
              </div>
              <div style={{ color:'var(--muted)', fontSize:'11px', marginTop:'4px' }}>{label}</div>
            </div>
          ))}
        </div>

        {/* Module breakdown */}
        {Object.keys(mstats).length > 0 && (
          <div className="card" style={{ marginBottom:'20px' }}>
            <h3 style={{ fontFamily:'Syne', fontSize:'13px', color:'var(--muted)', marginBottom:'14px' }}>
              MODULE BREAKDOWN
            </h3>
            <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit,minmax(130px,1fr))', gap:'10px' }}>
              {Object.entries(mstats).map(([mod, st]) => (
                <div key={mod} style={{
                  background:'var(--bg3)', borderRadius:'8px', padding:'12px',
                  border:'1px solid var(--border)',
                }}>
                  <div style={{ display:'flex', alignItems:'center', gap:'6px', marginBottom:'8px' }}>
                    <span>{MODULE_ICONS[mod] || '⚠'}</span>
                    <span style={{ fontFamily:'Syne', fontWeight:600, fontSize:'13px', textTransform:'capitalize' }}>
                      {mod}
                    </span>
                  </div>
                  <div style={{ fontSize:'22px', fontFamily:'Syne', fontWeight:800 }}>
                    {st.violation_count}
                  </div>
                  <div style={{ color:'var(--muted)', fontSize:'10px' }}>violations</div>
                  <div style={{ color:'var(--warn)', fontSize:'10px', marginTop:'2px' }}>
                    weight: {st.total_weight?.toFixed(0) || 0}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Violation timeline */}
        <div className="card">
          <h3 style={{ fontFamily:'Syne', fontSize:'13px', color:'var(--muted)', marginBottom:'14px' }}>
            VIOLATION TIMELINE ({viols.length} events)
          </h3>
          {viols.length === 0 ? (
            <div style={{ color:'var(--safe)', textAlign:'center', padding:'20px', fontSize:'13px' }}>
              ✓ No violations recorded
            </div>
          ) : (
            <div style={{ display:'flex', flexDirection:'column', gap:'6px', maxHeight:420, overflowY:'auto' }}>
              {viols.map((v, i) => {
                const ts    = v.timestamp ? new Date(v.timestamp*1000).toLocaleTimeString() : '--';
                const wHigh = (v.weight || 0) >= 30;
                return (
                  <div key={i} style={{
                    display:'grid', gridTemplateColumns:'90px 1fr 80px 56px',
                    gap:'10px', alignItems:'center',
                    padding:'8px 12px', borderRadius:'6px',
                    background: wHigh ? '#1a0505' : 'var(--bg3)',
                    border:`1px solid ${wHigh ? '#7f1d1d' : 'var(--border)'}`,
                    fontSize:'12px',
                  }}>
                    <span style={{ color:'var(--muted)', fontFamily:'DM Mono', fontSize:'10px' }}>{ts}</span>
                    <span style={{ color: wHigh ? '#f87171' : 'var(--text)', fontFamily:'Syne', fontWeight:600 }}>
                      {MODULE_ICONS[v.source_module] || '⚠'} {v.violation_type}
                    </span>
                    <span style={{ color:'var(--muted)', fontSize:'10px' }}>
                      {((v.confidence||0)*100).toFixed(0)}% conf
                    </span>
                    <span style={{
                      textAlign:'center', padding:'2px 8px', borderRadius:'10px', fontSize:'11px', fontWeight:700,
                      background: wHigh ? '#450a0a' : '#0c1a2e',
                      color: wHigh ? '#f87171' : 'var(--accent)',
                    }}>
                      w:{v.weight}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Disclaimer */}
        <p style={{ color:'var(--muted)', fontSize:'11px', textAlign:'center', marginTop:'20px', lineHeight:1.6 }}>
          This report was auto-generated by the AI Proctoring System.
          All detections should be reviewed by a human invigilator before any disciplinary action.
        </p>
      </div>
    </div>
  );
}