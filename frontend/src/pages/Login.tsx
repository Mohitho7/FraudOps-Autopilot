import React, { useState } from 'react';
import { ShieldAlert, Loader2, AlertCircle, Eye, EyeOff } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const Login = () => {
  const navigate = useNavigate();
  const { login } = useAuth();
  
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Form validation
  const [touched, setTouched] = useState({ email: false, password: false });
  const emailError = touched.email && !email.trim() ? 'Email is required' : null;
  const passwordError = touched.password && !password.trim() ? 'Password is required' : null;
  const isFormValid = email.trim() !== '' && password.trim() !== '';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setTouched({ email: true, password: true });
    
    if (!isFormValid) return;
    
    setIsSubmitting(true);
    setError(null);

    try {
      await login(email, password);
      navigate('/dashboard');
    } catch (err) {
      if (err instanceof TypeError && err.message === 'Failed to fetch') {
        setError('Unable to connect to the server. Please try again.');
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('An unexpected error occurred. Please try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex flex-col justify-center py-12 sm:px-6 lg:px-8">
      {/* Background pattern */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-primary/5 rounded-full blur-3xl" />
        <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-primary/5 rounded-full blur-3xl" />
      </div>

      <div className="sm:mx-auto sm:w-full sm:max-w-md relative z-10">
        <div className="flex justify-center">
          <div className="w-16 h-16 rounded-2xl bg-primary/20 border border-primary/30 flex items-center justify-center shadow-lg shadow-primary/10">
            <ShieldAlert className="w-9 h-9 text-primary" />
          </div>
        </div>
        <h1 className="mt-6 text-center text-3xl font-extrabold text-white tracking-tight">
          FraudOps Autopilot
        </h1>
        <p className="mt-2 text-center text-sm text-slate-400">
          Reviewer Login
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md relative z-10">
        <div className="bg-white/5 backdrop-blur-xl py-8 px-4 shadow-2xl sm:rounded-xl sm:px-10 border border-white/10">
          <form className="space-y-6" onSubmit={handleSubmit} noValidate>
            {/* Error Alert */}
            {error && (
              <div 
                className="flex items-start gap-3 p-4 bg-red-500/10 border border-red-500/20 rounded-lg"
                role="alert"
                id="login-error"
              >
                <AlertCircle className="w-5 h-5 text-red-400 mt-0.5 shrink-0" />
                <p className="text-sm text-red-300">{error}</p>
              </div>
            )}

            {/* Email field */}
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-slate-300">
                Email address
              </label>
              <div className="mt-1">
                <input
                  id="email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  onBlur={() => setTouched((t) => ({ ...t, email: true }))}
                  disabled={isSubmitting}
                  placeholder="alex@fraudops.dev"
                  aria-invalid={!!emailError}
                  aria-describedby={emailError ? 'email-error' : undefined}
                  className={`appearance-none block w-full px-3 py-2.5 bg-white/5 border rounded-lg shadow-sm placeholder-slate-500 text-white focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary sm:text-sm transition-all disabled:opacity-50 ${
                    emailError ? 'border-red-500/50' : 'border-white/10'
                  }`}
                />
                {emailError && (
                  <p id="email-error" className="mt-1 text-xs text-red-400">{emailError}</p>
                )}
              </div>
            </div>

            {/* Password field */}
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-slate-300">
                Password
              </label>
              <div className="mt-1 relative">
                <input
                  id="password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onBlur={() => setTouched((t) => ({ ...t, password: true }))}
                  disabled={isSubmitting}
                  placeholder="••••••••"
                  aria-invalid={!!passwordError}
                  aria-describedby={passwordError ? 'password-error' : undefined}
                  className={`appearance-none block w-full px-3 py-2.5 pr-10 bg-white/5 border rounded-lg shadow-sm placeholder-slate-500 text-white focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary sm:text-sm transition-all disabled:opacity-50 ${
                    passwordError ? 'border-red-500/50' : 'border-white/10'
                  }`}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-300 transition-colors"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
                {passwordError && (
                  <p id="password-error" className="mt-1 text-xs text-red-400">{passwordError}</p>
                )}
              </div>
            </div>

            {/* Submit button */}
            <div>
              <button
                id="login-submit"
                type="submit"
                disabled={isSubmitting}
                className="w-full flex justify-center items-center gap-2 py-2.5 px-4 border border-transparent rounded-lg shadow-lg text-sm font-semibold text-white bg-primary hover:bg-primary-hover focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary focus:ring-offset-slate-900 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Signing in...
                  </>
                ) : (
                  'Sign In'
                )}
              </button>
            </div>
          </form>
          
          {/* Demo hint */}
          <div className="mt-6">
            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-white/10" />
              </div>
              <div className="relative flex justify-center text-xs">
                <span className="px-2 bg-transparent text-slate-500">
                  Mock Authentication
                </span>
              </div>
            </div>
            <p className="mt-3 text-center text-xs text-slate-500">
              Demo: alex@fraudops.dev / reviewer123
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Login;
