import { NavLink } from 'react-router-dom';
import { 
  LayoutDashboard, 
  CreditCard, 
  AlertTriangle, 
  Network, 
  Settings, 
  FlaskConical, 
  History,
  ShieldAlert
} from 'lucide-react';

const Sidebar = () => {
  const navItemClass = ({ isActive }: { isActive: boolean }) => 
    `flex items-center space-x-3 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
      isActive 
        ? "bg-primary/10 text-primary" 
        : "text-slate-600 hover:bg-gray-100 hover:text-slate-900"
    }`;

  return (
    <aside className="w-64 h-full bg-white border-r border-gray-200 flex flex-col shrink-0">
      <div className="h-16 flex items-center px-6 border-b border-gray-200 shrink-0">
        <ShieldAlert className="w-6 h-6 text-primary mr-2" />
        <span className="text-lg font-bold text-slate-800 tracking-tight">FraudOps</span>
      </div>

      <div className="flex-1 overflow-y-auto py-6 px-4 space-y-8">
        <div>
          <p className="px-3 text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Main</p>
          <nav className="space-y-1">
            <NavLink to="/dashboard" className={navItemClass}>
              <LayoutDashboard className="w-4 h-4" />
              <span>Command Center</span>
            </NavLink>
            <NavLink to="/transactions" className={navItemClass}>
              <CreditCard className="w-4 h-4" />
              <span>Transactions</span>
            </NavLink>
            <NavLink to="/cases" className={navItemClass}>
              <AlertTriangle className="w-4 h-4" />
              <span>Cases</span>
            </NavLink>
            <NavLink to="/network" className={navItemClass}>
              <Network className="w-4 h-4" />
              <span>Fraud Network</span>
            </NavLink>
          </nav>
        </div>

        <div>
          <p className="px-3 text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Management</p>
          <nav className="space-y-1">
            <NavLink to="/rules" className={navItemClass} end>
              <Settings className="w-4 h-4" />
              <span>Rules</span>
            </NavLink>
            <NavLink to="/rules/simulation" className={navItemClass}>
              <FlaskConical className="w-4 h-4" />
              <span>Rule Simulation</span>
            </NavLink>
          </nav>
        </div>

        <div>
          <p className="px-3 text-xs font-semibold text-gray-400 uppercase tracking-wider mb-2">Review</p>
          <nav className="space-y-1">
            <NavLink to="/review-history" className={navItemClass}>
              <History className="w-4 h-4" />
              <span>Review History</span>
            </NavLink>
          </nav>
        </div>
      </div>
      
      <div className="p-4 border-t border-gray-200 text-xs text-gray-400 text-center">
        Batch 2 Build
      </div>
    </aside>
  );
};

export default Sidebar;
