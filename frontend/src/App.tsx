import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
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

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        
        {/* Main Application Shell */}
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
      </Routes>
    </BrowserRouter>
  );
}

export default App;
