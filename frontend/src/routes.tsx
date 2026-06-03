import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import AuthGuard from '@/components/AuthGuard';
import MainLayout from '@/components/Layout';
import Login from '@/pages/Login';
import Dashboard from '@/pages/Dashboard';
import Projects from '@/pages/Projects';
import ProjectDetail from '@/pages/Projects/ProjectDetail';
import Sessions from '@/pages/Sessions';
import Analysis from '@/pages/Analysis';

const AppRoutes: React.FC = () => {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route
        path="/"
        element={
          <AuthGuard>
            <MainLayout />
          </AuthGuard>
        }
      >
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="projects" element={<Projects />} />
        <Route path="projects/:projectId" element={<ProjectDetail />} />
        <Route path="sessions" element={<Sessions />} />
        <Route path="analysis" element={<Analysis />} />
        <Route path="settings" element={<div>系统设置页面开发中...</div>} />
      </Route>
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
};

export default AppRoutes;
