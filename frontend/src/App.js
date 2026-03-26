// src/App.js — FINAL with /report route
import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import LoginPage     from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import ExamPage      from './pages/ExamPage';
import EnrollPage    from './pages/EnrollPage';
import AdminPage     from './pages/AdminPage';
import ReportPage    from './pages/ReportPage';
import './index.css';

function Loader() {
  return (
    <div style={{ minHeight:'100vh', display:'flex', alignItems:'center',
      justifyContent:'center', background:'var(--bg)' }}>
      <div style={{ width:40, height:40, border:'3px solid var(--border)',
        borderTopColor:'var(--accent)', borderRadius:'50%',
        animation:'spin 0.8s linear infinite' }}/>
      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
    </div>
  );
}

function StudentRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <Loader />;
  if (!user)   return <Navigate to="/login" />;
  return children;
}

function AdminRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <Loader />;
  if (!user)             return <Navigate to="/login" />;
  if (user.role !== 'admin') return <Navigate to="/dashboard" />;
  return children;
}

function AppRoutes() {
  const { user, loading } = useAuth();
  if (loading) return <Loader />;
  return (
    <Routes>
      <Route path="/login" element={
        user
          ? <Navigate to={user.role === 'admin' ? '/admin' : '/dashboard'} />
          : <LoginPage />
      }/>
      <Route path="/dashboard" element={<StudentRoute><DashboardPage /></StudentRoute>}/>
      <Route path="/enroll"    element={<StudentRoute><EnrollPage /></StudentRoute>}/>
      <Route path="/exam/:id"  element={<StudentRoute><ExamPage /></StudentRoute>}/>
      <Route path="/report"    element={<StudentRoute><ReportPage /></StudentRoute>}/>
      <Route path="/admin"     element={<AdminRoute><AdminPage /></AdminRoute>}/>
      <Route path="*" element={
        <Navigate to={user ? (user.role==='admin' ? '/admin' : '/dashboard') : '/login'}/>
      }/>
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  );
}