import { BrowserRouter, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import DashboardLayout from './layouts/DashboardLayout';
import Dashboard from './pages/Dashboard';
import Transactions from './pages/Transactions';
import TransactionDetail from './pages/TransactionDetail';
import Cases from './pages/Cases';
import CaseDetail from './pages/CaseDetail';
import FraudNetwork from './pages/FraudNetwork';
import Rules from './pages/Rules';
import RuleSimulation from './pages/RuleSimulation';
import ReviewHistory from './pages/ReviewHistory';
import Login from './pages/Login';

const ProtectedRoute = () => {
  const { isAuthenticated, isLoading } = useAuth();
  
  if (isLoading) {
    return <div className="h-screen w-screen flex items-center justify-center bg-gray-50 text-slate-500 text-sm">Loading session...</div>;
  }
  
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  
  return <Outlet />;
};

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          
          {/* Main Application Shell */}
          <Route element={<ProtectedRoute />}>
            <Route element={<DashboardLayout />}>
              <Route path="/" element={<Navigate to="/dashboard" replace />} />
              <Route path="/dashboard" element={<Dashboard />} />
              
              <Route path="/transactions" element={<Transactions />} />
              <Route path="/transactions/:id" element={<TransactionDetail />} />
              
              <Route path="/cases" element={<Cases />} />
              <Route path="/cases/:id" element={<CaseDetail />} />
              
              <Route path="/network" element={<FraudNetwork />} />
              
              <Route path="/rules" element={<Rules />} />
              <Route path="/rules/simulation" element={<RuleSimulation />} />
              
              <Route path="/review-history" element={<ReviewHistory />} />
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
