// src/App.js — final with all routes including RoomScanPage
import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import ExamPage from './pages/ExamPage';
import EnrollPage from './pages/EnrollPage';
import AdminPage from './pages/AdminPage';
import ReportPage from './pages/ReportPage';
import RoomScanPage from './pages/RoomScanPage';
import './styles/global.css';

function Loader() {
  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center',
      justifyContent: 'center', background: '#fafafa'
    }}>
      <div style={{
        width: 32, height: 32, border: '3px solid #e4e4e7',
        borderTopColor: '#2563eb', borderRadius: '50%', animation: 'spin 0.8s linear infinite'
      }} />
      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
    </div>
  );
}

function StudentRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <Loader />;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

function AdminRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <Loader />;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== 'admin') return <Navigate to="/dashboard" replace />;
  return children;
}

function AppRoutes() {
  const { user, loading } = useAuth();
  if (loading) return <Loader />;

  return (
    <Routes>
      <Route path="/login" element={user ? <Navigate to={user.role === 'admin' ? '/admin' : '/dashboard'} replace /> : <LoginPage />} />
      <Route path="/dashboard" element={<StudentRoute><DashboardPage /></StudentRoute>} />
      <Route path="/enroll" element={<StudentRoute><EnrollPage /></StudentRoute>} />
      <Route path="/exam/:id" element={<StudentRoute><ExamPage /></StudentRoute>} />
      <Route path="/room-scan/:id" element={<StudentRoute><RoomScanPage /></StudentRoute>} />
      <Route path="/report" element={<StudentRoute><ReportPage /></StudentRoute>} />
      <Route path="/admin" element={<AdminRoute><AdminPage /></AdminRoute>} />
      <Route path="/" element={<Navigate to={user ? (user.role === 'admin' ? '/admin' : '/dashboard') : '/login'} replace />} />
      <Route path="*" element={<Navigate to="/" replace />} />
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