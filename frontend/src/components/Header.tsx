import { Bell, Search, User, LogOut } from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { isAnyEndpointConfigured } from '../config/apiEndpoints';

const getPageTitle = (pathname: string) => {
  if (pathname.startsWith('/transactions')) return 'Transactions';
  if (pathname.startsWith('/cases')) return 'Cases';
  if (pathname.startsWith('/network')) return 'Fraud Network';
  if (pathname.startsWith('/rules/simulation')) return 'Rule Simulation';
  if (pathname.startsWith('/rules')) return 'Rules Management';
  if (pathname.startsWith('/review-history')) return 'Review History';
  return 'Command Center';
};

const Header = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const pageTitle = getPageTitle(location.pathname);
  const { reviewer, logout } = useAuth();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6 shrink-0">
      <div className="flex items-center">
        <h1 className="text-xl font-semibold text-slate-800">{pageTitle}</h1>
      </div>
      
      <div className="flex items-center space-x-6">
        <span title={isAnyEndpointConfigured() ? 'Configured backend endpoint available' : 'Using isolated frontend mock data'} className={`hidden rounded-full border px-2.5 py-1 text-xs font-medium md:inline-flex ${isAnyEndpointConfigured() ? 'border-green-200 bg-green-50 text-green-700' : 'border-slate-200 bg-slate-50 text-slate-600'}`}>
          {isAnyEndpointConfigured() ? 'Backend Connected' : 'Demo Data'}
        </span>
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input 
            type="text" 
            placeholder="Search cases, txns..." 
            className="pl-9 pr-4 py-1.5 bg-gray-50 border border-gray-200 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary w-64 transition-shadow"
          />
        </div>
        
        <button className="relative text-gray-500 hover:text-gray-700 transition-colors">
          <Bell className="w-5 h-5" />
          <span className="absolute 0 top-0 right-0 w-2 h-2 bg-red-500 rounded-full border border-white"></span>
        </button>
        
        <div className="flex items-center space-x-3 border-l border-gray-200 pl-6">
          <div className="text-right hidden md:block">
            <p className="text-sm font-medium text-slate-700 leading-none">{reviewer?.name || 'Reviewer'}</p>
            <p className="text-xs text-green-600 font-medium mt-1">● Online</p>
          </div>
          <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-primary">
            <User className="w-4 h-4" />
          </div>
          <button 
            onClick={handleLogout}
            className="ml-2 p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-md transition-colors"
            title="Sign Out"
          >
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </header>
  );
};

export default Header;
