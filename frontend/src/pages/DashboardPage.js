// src/pages/DashboardPage.js
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { examAPI, authAPI } from '../services/api';

export default function DashboardPage() {
  const { user, logout }  = useAuth();
  const navigate          = useNavigate();
  const [exams,  setExams]   = useState([]);
  const [enroll, setEnroll]  = useState(null);  // enrollment status
  const [loading,setLoad]    = useState(true);

  useEffect(() => {
    Promise.all([examAPI.list(), authAPI.enrollStatus()])
      .then(([exRes, enRes]) => {
        setExams(exRes.data);
        setEnroll(enRes.data);
      })
      .catch(console.error)
      .finally(() => setLoad(false));
  }, []);

  const handleStart = async (examId) => {
    if (!enroll?.enrolled) {
      alert('Please enroll your face first before starting an exam.');
      navigate('/enroll');
      return;
    }
    try {
      const res = await examAPI.start(examId);
      navigate(`/exam/${examId}?session=${res.data.session_id}`);
    } catch (e) {
      alert(e.response?.data?.detail || 'Could not start exam');
    }
  };

  return (
    <div style={{ minHeight:'100vh', background:'var(--bg)' }}>
      {/* Navbar */}
      <nav style={{
        display:'flex', alignItems:'center', justifyContent:'space-between',
        padding:'16px 32px', borderBottom:'1px solid var(--border)',
        background:'var(--bg2)',
      }}>
        <div style={{ display:'flex', alignItems:'center', gap:'10px' }}>
          <span style={{ fontSize:'20px' }}>🔒</span>
          <span style={{ fontFamily:'Syne', fontWeight:700, fontSize:'16px' }}>
            ProctorAI
          </span>
        </div>
        <div style={{ display:'flex', alignItems:'center', gap:'16px' }}>
          <span style={{ color:'var(--muted)', fontSize:'12px' }}>
            {user?.full_name}
          </span>
          <button className="btn-ghost" onClick={() => navigate('/enroll')}
            style={{ fontSize:'12px', padding:'6px 14px' }}>
            Face Enrollment
          </button>
          <button className="btn-ghost" onClick={logout}
            style={{ fontSize:'12px', padding:'6px 14px' }}>
            Logout
          </button>
        </div>
      </nav>

      <div style={{ maxWidth:'900px', margin:'0 auto', padding:'40px 24px' }}>
        {/* Header */}
        <div style={{ marginBottom:'32px' }}>
          <h1 style={{ fontSize:'28px', marginBottom:'6px' }}>
            Welcome, {user?.full_name?.split(' ')[0]} 👋
          </h1>
          <p style={{ color:'var(--muted)' }}>
            Available exams are listed below.
          </p>
        </div>

        {/* Enrollment status banner */}
        {enroll && !enroll.enrolled && (
          <div style={{
            background:'#1c1003', border:'1px solid #78350f',
            borderRadius:'10px', padding:'14px 20px',
            display:'flex', alignItems:'center', justifyContent:'space-between',
            marginBottom:'24px',
          }}>
            <div>
              <div style={{ color:'var(--warn)', fontFamily:'Syne', fontWeight:600, fontSize:'13px' }}>
                ⚠ Face Enrollment Required
              </div>
              <div style={{ color:'var(--muted)', fontSize:'12px', marginTop:'2px' }}>
                You must enroll your face before starting any exam.
              </div>
            </div>
            <button className="btn-primary" style={{ fontSize:'12px', padding:'8px 16px' }}
              onClick={() => navigate('/enroll')}>
              Enroll Now →
            </button>
          </div>
        )}

        {enroll?.enrolled && (
          <div style={{
            background:'#052e16', border:'1px solid #14532d',
            borderRadius:'10px', padding:'12px 20px',
            marginBottom:'24px', color:'var(--safe)', fontSize:'12px',
          }}>
            ✓ Face enrolled — you can start exams
          </div>
        )}

        {/* Exam list */}
        <h2 style={{ fontSize:'16px', fontFamily:'Syne', marginBottom:'16px', color:'var(--muted)' }}>
          AVAILABLE EXAMS
        </h2>

        {loading ? (
          <div style={{ color:'var(--muted)', padding:'40px 0', textAlign:'center' }}>
            Loading exams...
          </div>
        ) : exams.length === 0 ? (
          <div className="card" style={{ textAlign:'center', padding:'40px', color:'var(--muted)' }}>
            No exams available right now.
          </div>
        ) : (
          <div style={{ display:'flex', flexDirection:'column', gap:'12px' }}>
            {exams.map(exam => (
              <div key={exam.id} className="card" style={{
                display:'flex', alignItems:'center',
                justifyContent:'space-between', gap:'20px',
              }}>
                <div style={{ flex:1 }}>
                  <div style={{ fontFamily:'Syne', fontWeight:700, fontSize:'16px', marginBottom:'4px' }}>
                    {exam.title}
                  </div>
                  <div style={{ color:'var(--muted)', fontSize:'12px', display:'flex', gap:'16px' }}>
                    <span>⏱ {exam.duration_minutes} minutes</span>
                    <span style={{
                      color: exam.status === 'active' ? 'var(--safe)' : 'var(--muted)'
                    }}>
                      ● {exam.status}
                    </span>
                  </div>
                </div>
                <button
                  className="btn-primary"
                  style={{ whiteSpace:'nowrap', padding:'10px 20px' }}
                  onClick={() => handleStart(exam.id)}
                >
                  Start Exam →
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}