import React, { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Landing from './pages/Landing';
import Cluster from './pages/Cluster';
import NodeManager from './pages/NodeManager';
import PodManager from './pages/PodManager';
import Dashboard from './pages/Dashboard';
import ThemeToggle from './components/ThemeToggle';
import NavBar from './components/NavBar';
import { ToastContainer } from 'react-toastify';
import 'react-toastify/dist/ReactToastify.css';
import './App.css';

function App() {
  const [theme, setTheme] = useState<'light' | 'dark'>('dark');

  useEffect(() => {
    // Check for system preference or stored preference
    const storedTheme = localStorage.getItem('theme') as 'light' | 'dark' | null;
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    
    if (storedTheme) {
      setTheme(storedTheme);
      document.documentElement.classList.toggle('dark', storedTheme === 'dark');
    } else {
      setTheme(prefersDark ? 'dark' : 'light');
      document.documentElement.classList.toggle('dark', prefersDark);
    }
  }, []);

  const toggleTheme = () => {
    const newTheme = theme === 'light' ? 'dark' : 'light';
    setTheme(newTheme);
    document.documentElement.classList.toggle('dark', newTheme === 'dark');
    localStorage.setItem('theme', newTheme);
  };

  return (
    <div className={`min-h-screen ${theme === 'dark' ? 'dark bg-gray-900 text-gray-100' : 'bg-gray-100 text-gray-900'} transition-colors duration-200`}>
      <BrowserRouter>
        <NavBar />
        <div className="fixed top-4 right-4 z-50">
          <ThemeToggle theme={theme} toggleTheme={toggleTheme} />
        </div>
        
        <div className="pt-16">
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/cluster" element={<Cluster />} />
            <Route path="/nodes" element={<NodeManager />} />
            <Route path="/pods" element={<Navigate to="/pod-manager" replace />} />
            <Route path="/pod-manager" element={<PodManager />} />
          </Routes>
        </div>
      </BrowserRouter>
      
      {/* Toast container for notifications */}
      <ToastContainer 
        position="bottom-right"
        autoClose={3000}
        hideProgressBar={false}
        newestOnTop
        closeOnClick
        rtl={false}
        pauseOnFocusLoss
        draggable
        pauseOnHover
        theme={theme}
      />
    </div>
  );
}

export default App; 