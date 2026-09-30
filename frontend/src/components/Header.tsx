import { Bell, Search, User } from 'lucide-react';
import { useLocation } from 'react-router-dom';

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
  const pageTitle = getPageTitle(location.pathname);

  return (
    <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6 shrink-0">
      <div className="flex items-center">
        <h1 className="text-xl font-semibold text-slate-800">{pageTitle}</h1>
      </div>
      
      <div className="flex items-center space-x-6">
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
            <p className="text-sm font-medium text-slate-700 leading-none">Alex Reviewer</p>
            <p className="text-xs text-green-600 font-medium mt-1">● Online</p>
          </div>
          <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-primary">
            <User className="w-4 h-4" />
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;
