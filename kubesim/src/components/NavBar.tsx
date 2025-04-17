import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Button } from './ui/button';
import { Menu, X, ChevronDown, Server, Layers, PieChart, Home } from 'lucide-react';

const NavBar: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const location = useLocation();
  
  const isActive = (path: string) => {
    return location.pathname === path;
  };

  return (
    <nav className="bg-white dark:bg-gray-800 shadow-md">
      <div className="container mx-auto px-4">
        <div className="flex justify-between h-16">
          {/* Logo and brand */}
          <div className="flex items-center">
            <Link to="/" className="flex items-center">
              <img 
                src="/kubesim_logo.svg" 
                alt="KubeSim Logo" 
                className="h-10 w-10 mr-2 dark:invert"
              />
              <span className="text-xl font-bold dark:text-white">KubeSim</span>
            </Link>
          </div>

          {/* Desktop navigation */}
          <div className="hidden md:flex items-center space-x-2">
            <Link to="/">
              <Button 
                variant={isActive('/') ? "default" : "ghost"} 
                className="flex items-center"
              >
                <Home className="h-4 w-4 mr-2" />
                Dashboard
              </Button>
            </Link>
            <Link to="/cluster">
              <Button 
                variant={isActive('/cluster') ? "default" : "ghost"} 
                className="flex items-center"
              >
                <PieChart className="h-4 w-4 mr-2" />
                Cluster Overview
              </Button>
            </Link>
            <Link to="/nodes">
              <Button 
                variant={isActive('/nodes') ? "default" : "ghost"} 
                className="flex items-center"
              >
                <Server className="h-4 w-4 mr-2" />
                Manage Nodes
              </Button>
            </Link>
            <Link to="/pod-manager">
              <Button 
                variant={isActive('/pod-manager') ? "default" : "ghost"} 
                className="flex items-center"
              >
                <Layers className="h-4 w-4 mr-2" />
                Manage Pods
              </Button>
            </Link>
          </div>

          {/* Mobile menu button */}
          <div className="md:hidden flex items-center">
            <button
              onClick={() => setIsOpen(!isOpen)}
              className="inline-flex items-center justify-center p-2 rounded-md text-gray-400 hover:text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700 focus:outline-none"
              aria-expanded="false"
            >
              <span className="sr-only">Open main menu</span>
              {isOpen ? (
                <X className="block h-6 w-6" aria-hidden="true" />
              ) : (
                <Menu className="block h-6 w-6" aria-hidden="true" />
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile menu */}
      <div className={`md:hidden ${isOpen ? 'block' : 'hidden'}`}>
        <div className="px-2 pt-2 pb-3 space-y-1 sm:px-3">
          <Link to="/">
            <Button 
              variant={isActive('/') ? "default" : "ghost"} 
              className="w-full justify-start"
              onClick={() => setIsOpen(false)}
            >
              <Home className="h-4 w-4 mr-2" />
              Dashboard
            </Button>
          </Link>
          <Link to="/cluster">
            <Button 
              variant={isActive('/cluster') ? "default" : "ghost"} 
              className="w-full justify-start"
              onClick={() => setIsOpen(false)}
            >
              <PieChart className="h-4 w-4 mr-2" />
              Cluster Overview
            </Button>
          </Link>
          <Link to="/nodes">
            <Button 
              variant={isActive('/nodes') ? "default" : "ghost"} 
              className="w-full justify-start"
              onClick={() => setIsOpen(false)}
            >
              <Server className="h-4 w-4 mr-2" />
              Manage Nodes
            </Button>
          </Link>
          <Link to="/pod-manager">
            <Button 
              variant={isActive('/pod-manager') ? "default" : "ghost"} 
              className="w-full justify-start"
              onClick={() => setIsOpen(false)}
            >
              <Layers className="h-4 w-4 mr-2" />
              Manage Pods
            </Button>
          </Link>
        </div>
      </div>
    </nav>
  );
};

export default NavBar; 