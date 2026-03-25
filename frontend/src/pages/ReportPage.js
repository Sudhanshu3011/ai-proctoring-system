// src/pages/ReportPage.js
// Shown after exam ends — violation summary + PDF download

import React, { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { reportAPI } from '../services/api';

const LEVEL_STYLE = {
  SAFE    : { bg:'#052e16', border:'#14532d', color:'#10b981' },
  WARNING : { bg:'#1c1003', border:'#78350f', color:'#f59e0b' },
  HIGH    : { bg:'#1a0505', border:'#7f1d1d', color:'#ef4444' },
  CRITICAL: { bg:'#1a0505', border:'#991b1b', color:'#dc2626' },
};

const MODULE_ICONS = {
  face:'👤', pose:'👁', object:'📱', audio:'🎙', browser:'🌐', unknown:'⚠'
};

export default function ReportPage() {
  const [sp]       = useSearchParams();
  const sessionId  = sp.get('session');
  const navigate   = useNavigate();

  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState('');
  const [generating, setGen]  = useState(false);

  useEffect(() => {
    if (!sessionId) { setError('No session ID provided'); setLoading(false); return; }
    reportAPI.get(sessionId)
      .then(r => setData(r.data))
      .catch(e => setError(e.response?.data?.detail || 'Failed to load report'))
      .finally(() => setLoading(false));
  }, [sessionId]);

  const handleDownload = async () => {
    setGen(true);
    try {
      // Trigger generation first
      await fetch(`/api/v1/reports/generate/${sessionId}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
      });
      // Then download
      window.open(reportAPI.download(sessionId), '_blank');
    } catch (e) {
      alert('Failed to generate PDF');
    } finally {
      setGen(false);
    }
  };

  if (loading) return (
    <div style={{ minHeight:'100vh', background:'var(--bg)', display:'flex',
      alignItems:'center', justifyContent:'center' }}>
      <div style={{ textAlign:'center' }}>
        <div style={{ width:40, height:40, border:'3px solid var(--border)',
          borderTopColor:'var(--accent)', borderRadius:'50%',
          animation:'spin 0.8s linear infinite', margin:'0 auto 16px' }}/>
        <style>{`@keyframes spin { to { transform:rotate(360deg) } }`}</style>
        <p style={{ color:'var(--muted)' }}>Loading report...</p>
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

  const level     = data?.risk_assessment?.risk_level || 'SAFE';
  const score     = data?.risk_assessment?.final_score || 0;
  const prob      = data?.risk_assessment?.cheat_probability || 0;
  const lvlStyle  = LEVEL_STYLE[level] || LEVEL_STYLE.SAFE;

  return (
    <div style={{ minHeight:'100vh', background:'var(--bg)' }}>
      {/* Navbar */}
      <nav style={{
        display:'flex', alignItems:'center', justifyContent:'space-between',
        padding:'14px 28px', borderBottom:'1px solid var(--border)',
        background:'var(--bg2)', position:'sticky', top:0, zIndex:10,
      }}>
        <div style={{ display:'flex', alignItems:'center', gap:'10px' }}>
          <span style={{ fontSize:'18px' }}>🔒</span>
          <span style={{ fontFamily:'Syne', fontWeight:700 }}>Exam Report</span>
        </div>
        <div style={{ display:'flex', gap:'10px' }}>
          <button className="btn-primary"
            style={{ padding:'8px 18px', fontSize:'12px' }}
            onClick={handleDownload} disabled={generating}>
            {generating ? 'Generating...' : '⬇ Download PDF'}
          </button>
          <button className="btn-ghost"
            style={{ padding:'8px 16px', fontSize:'12px' }}
            onClick={() => navigate('/dashboard')}>
            ← Dashboard
          </button>
        </div>
      </nav>

      <div style={{ maxWidth:'860px', margin:'0 auto', padding:'32px 24px' }}>

        {/* Header info */}
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
                  ? new Date(data.exam.started_at * 1000).toLocaleString()
                  : '—'}
              </div>
            </div>
          </div>
        </div>

        {/* Risk summary row */}
        <div style={{
          display:'grid', gridTemplateColumns:'repeat(4, 1fr)',
          gap:'12px', marginBottom:'20px',
        }}>
          {[
            { label:'Final Score',    value:`${score.toFixed(1)}`, unit:'/100' },
            { label:'Risk Level',     value: level,                unit:'' },
            { label:'Cheat Probability', value:`${(prob*100).toFixed(1)}`, unit:'%' },
            { label:'Total Violations',  value: data?.violations?.length || 0, unit:'' },
          ].map(({ label, value, unit }) => (
            <div key={label} className="card" style={{
              textAlign:'center', padding:'16px',
              borderColor: label === 'Risk Level' ? lvlStyle.border : 'var(--border)',
            }}>
              <div style={{
                fontFamily:'Syne', fontWeight:800, fontSize:'24px',
                color: label === 'Risk Level' ? lvlStyle.color : 'var(--text)',
              }}>
                {value}<span style={{ fontSize:'14px', opacity:0.6 }}>{unit}</span>
              </div>
              <div style={{ color:'var(--muted)', fontSize:'11px', marginTop:'4px' }}>{label}</div>
            </div>
          ))}
        </div>

        {/* Module breakdown */}
        {data?.module_stats && Object.keys(data.module_stats).length > 0 && (
          <div className="card" style={{ marginBottom:'20px' }}>
            <h3 style={{ fontFamily:'Syne', fontSize:'14px', marginBottom:'16px', color:'var(--muted)' }}>
              MODULE BREAKDOWN
            </h3>
            <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit, minmax(140px, 1fr))', gap:'10px' }}>
              {Object.entries(data.module_stats).map(([mod, stats]) => (
                <div key={mod} style={{
                  background:'var(--bg3)', borderRadius:'8px',
                  padding:'12px', border:'1px solid var(--border)',
                }}>
                  <div style={{ display:'flex', alignItems:'center', gap:'6px', marginBottom:'8px' }}>
                    <span>{MODULE_ICONS[mod] || '⚠'}</span>
                    <span style={{ fontFamily:'Syne', fontWeight:600, fontSize:'13px',
                      textTransform:'capitalize' }}>{mod}</span>
                  </div>
                  <div style={{ fontSize:'20px', fontFamily:'Syne', fontWeight:800, marginBottom:'2px' }}>
                    {stats.violation_count}
                  </div>
                  <div style={{ color:'var(--muted)', fontSize:'10px' }}>violations</div>
                  <div style={{ color:'var(--warn)', fontSize:'10px', marginTop:'2px' }}>
                    w: {stats.total_weight?.toFixed(0) || 0}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Violation timeline */}
        <div className="card">
          <h3 style={{ fontFamily:'Syne', fontSize:'14px', marginBottom:'16px', color:'var(--muted)' }}>
            VIOLATION TIMELINE ({data?.violations?.length || 0} events)
          </h3>
          {(!data?.violations || data.violations.length === 0) ? (
            <div style={{ color:'var(--safe)', fontSize:'13px', textAlign:'center', padding:'20px' }}>
              ✓ No violations recorded
            </div>
          ) : (
            <div style={{ display:'flex', flexDirection:'column', gap:'6px', maxHeight:400, overflowY:'auto' }}>
              {data.violations.map((v, i) => {
                const ts = v.timestamp
                  ? new Date(v.timestamp * 1000).toLocaleTimeString()
                  : '--';
                const wHigh = v.weight >= 30;
                return (
                  <div key={i} style={{
                    display:'grid', gridTemplateColumns:'90px 1fr 80px 60px',
                    gap:'10px', alignItems:'center',
                    padding:'8px 12px', borderRadius:'6px',
                    background: wHigh ? '#1a0505' : 'var(--bg3)',
                    border:`1px solid ${wHigh ? '#7f1d1d' : 'var(--border)'}`,
                    fontSize:'12px',
                  }}>
                    <span style={{ color:'var(--muted)', fontFamily:'DM Mono', fontSize:'11px' }}>{ts}</span>
                    <span style={{ color: wHigh ? '#f87171' : 'var(--text)', fontFamily:'Syne', fontWeight:600 }}>
                      {MODULE_ICONS[v.source_module] || '⚠'} {v.violation_type}
                    </span>
                    <span style={{ color:'var(--muted)', fontSize:'10px' }}>
                      conf {((v.confidence || 0) * 100).toFixed(0)}%
                    </span>
                    <span style={{
                      textAlign:'center', padding:'2px 8px', borderRadius:'10px',
                      background: wHigh ? '#450a0a' : '#0c1a2e',
                      color: wHigh ? '#f87171' : 'var(--accent)',
                      fontSize:'11px', fontWeight:700,
                    }}>
                      w:{v.weight}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}