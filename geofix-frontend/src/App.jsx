import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronRight, Zap, CheckCircle, MessageSquare, Menu, X, Github, Twitter, Linkedin, Loader2, AlertCircle } from 'lucide-react';
import clsx from 'clsx';

function SpotlightCard({ children, delay = 0 }) {
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [opacity, setOpacity] = useState(0);

  const handleMouseMove = (e) => {
    if (!e.currentTarget) return;
    const rect = e.currentTarget.getBoundingClientRect();
    setPosition({ x: e.clientX - rect.left, y: e.clientY - rect.top });
  };

  const handleMouseEnter = () => setOpacity(1);
  const handleMouseLeave = () => setOpacity(0);

  return (
    <motion.div
      initial={{ opacity: 1, y: 0 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ delay }}
      className="relative rounded-3xl border border-white/10 bg-white/[0.02] overflow-hidden group"
      onMouseMove={handleMouseMove}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      <div
        className="pointer-events-none absolute -inset-px opacity-0 transition duration-300 group-hover:opacity-100"
        style={{
          background: `radial-gradient(600px circle at ${position.x}px ${position.y}px, rgba(255,133,93,0.15), transparent 40%)`,
        }}
      />
      <div className="relative p-10 h-full">
        {children}
      </div>
    </motion.div>
  );
}

function MouseFollowBackground() {
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });

  useEffect(() => {
    const handleMouseMove = (event) => {
      setMousePosition({
        x: event.clientX,
        y: event.clientY,
      });
    };

    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      <div className="absolute inset-0 bg-brand-dark" />

      {/* Orb 1 - Follows mouse with delay */}
      <motion.div
        animate={{
          x: mousePosition.x * 0.1,
          y: mousePosition.y * 0.1,
        }}
        transition={{ type: "spring", damping: 50, stiffness: 400 }}
        className="absolute top-[-10%] left-[-10%] w-[50vw] h-[50vw] rounded-full bg-brand-orange/10 blur-[100px] mix-blend-screen"
      />

      {/* Orb 2 - Inverse movement */}
      <motion.div
        animate={{
          x: mousePosition.x * -0.05,
          y: mousePosition.y * -0.05,
        }}
        transition={{ type: "spring", damping: 50, stiffness: 400 }}
        className="absolute bottom-[-10%] right-[-10%] w-[45vw] h-[45vw] rounded-full bg-brand-pink/10 blur-[120px] mix-blend-screen"
      />

      {/* Orb 3 - Static center pivot */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[60vw] h-[60vw] bg-brand-blue/5 blur-[150px] rounded-full mix-blend-screen" />
    </div>
  );
}

function SectionReveal({ children, delay = 0 }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-100px" }}
      transition={{ duration: 0.6, delay, ease: "easeOut" }}
    >
      {children}
    </motion.div>
  );
}

function App() {
  const [isAuthOpen, setIsAuthOpen] = useState(false);
  const [authMode, setAuthMode] = useState('login');

  // Auth Form State
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const openAuth = (mode) => {
    setAuthMode(mode);
    setIsAuthOpen(true);
    setError(null);
    setEmail('');
    setPassword('');
  };

  const handleAuth = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      const endpoint = authMode === 'signup' ? '/api/auth/signup' : '/api/auth/login';
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email, password }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Authentication failed');
      }

      // Success - Redirect to app
      window.location.href = '/chat';
    } catch (err) {
      console.error("Auth error:", err);
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-brand-dark text-white selection:bg-brand-orange selection:text-black relative overflow-x-hidden">
      {/* <MouseFollowBackground /> */}
      <div className="absolute inset-0 bg-brand-dark" />

      {/* Navbar */}
      <nav className="fixed top-0 inset-x-0 z-50 bg-brand-dark/80 backdrop-blur-md border-b border-white/5">
        <div className="max-w-7xl mx-auto px-6 h-20 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <img src="/public/avatars/icon.png" alt="GeoFix" className="h-10 w-auto" />
            <span className="text-xl font-bold tracking-tight">GeoFix</span>
          </div>
          <div className="hidden md:flex items-center gap-8">
            <a href="https://twitter.com/geofix_ai" target="_blank" className="text-sm font-medium text-gray-400 hover:text-white transition-colors">Contact</a>
            <button onClick={() => openAuth('login')} className="text-sm font-medium text-white hover:text-brand-orange transition-colors">Sign In</button>
            <button onClick={() => openAuth('signup')} className="bg-white text-black px-5 py-2.5 rounded-full text-sm font-semibold hover:bg-brand-gray hover:text-white transition-all transform hover:scale-105">Start for free</button>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="relative pt-32 pb-20 px-6 flex flex-col items-center text-center overflow-hidden min-h-[90vh] justify-center">
        <motion.div
          initial={{ opacity: 1, y: 0 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: "easeOut" }}
          className="relative z-10 max-w-5xl mx-auto"
        >
          <div className="mb-6 flex justify-center">
            {/* INCREASED LOGO SIZE h-64 -> h-96, Reduced margin */}
            <img src="/public/img/logo_croped.png" alt="GeoFix Logo" className="h-[28rem] w-auto drop-shadow-2xl" />
          </div>

          <h1 className="text-6xl md:text-8xl font-extrabold tracking-tight mb-8 leading-[1.1]">
            Master Your <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-white via-brand-pink to-brand-orange">Geospatial Data</span>
          </h1>

          <p className="text-xl text-gray-400 max-w-2xl mx-auto mb-12 leading-relaxed">
            The advanced AI assistant for GIS professionals. Analyze, process, and visualize your data with the power of natural language.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <button onClick={() => openAuth('signup')} className="w-full sm:w-auto px-8 py-4 bg-white text-black text-lg font-bold rounded-full hover:bg-brand-orange transition-all transform hover:-translate-y-1 hover:shadow-lg flex items-center justify-center gap-2">
              Start for free <ChevronRight size={20} />
            </button>
            <button onClick={() => openAuth('login')} className="w-full sm:w-auto px-8 py-4 bg-white/5 border border-white/10 text-white text-lg font-semibold rounded-full hover:bg-white/10 transition-all backdrop-blur-sm">
              Launch Program
            </button>
          </div>
        </motion.div>
      </section>

      {/* Stats - Distinct Section */}
      <section className="py-24 border-y border-white/5 bg-white/[0.03] relative z-10 backdrop-blur-sm">
        <SectionReveal>
          <div className="max-w-7xl mx-auto px-6 grid grid-cols-2 md:grid-cols-4 gap-12 text-center">
            {[
              { label: "QC Tools", value: "8+" },
              { label: "Tests Passing", value: "93" },
              { label: "File Formats", value: "5" },
              { label: "Local & Private", value: "100%" },
            ].map((stat, i) => (
              <div key={i}>
                <div className="text-4xl md:text-5xl font-bold text-white mb-2">{stat.value}</div>
                <div className="text-sm font-medium text-brand-orange uppercase tracking-wider">{stat.label}</div>
              </div>
            ))}
          </div>
        </SectionReveal>
      </section>

      {/* Features - Distinct Section */}
      <section className="py-32 px-6 bg-brand-dark relative z-10">
        <div className="max-w-7xl mx-auto grid md:grid-cols-3 gap-8">
          {[
            { icon: Zap, title: "Real-time Error Detection", desc: "Automatically detect overlaps, self-intersections, and boundary violations with a single command." },
            { icon: CheckCircle, title: "Auto-Fix Engine", desc: "Repair invalid geometries and topology errors using intelligent algorithms like buffer(0) and make_valid." },
            { icon: MessageSquare, title: "Conversational GIS", desc: "Chat with GeoFix like a colleague. Ask questions, upload files, get explanations — all in natural language." },
          ].map((feature, i) => (
            <SpotlightCard key={i} delay={i * 0.1}>
              <div className="h-14 w-14 rounded-2xl bg-brand-orange/10 flex items-center justify-center text-brand-orange mb-6 group-hover:scale-110 transition-transform duration-300">
                <feature.icon size={28} />
              </div>
              <h3 className="text-2xl font-bold mb-4">{feature.title}</h3>
              <p className="text-gray-400 leading-relaxed">{feature.desc}</p>
            </SpotlightCard>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="py-20 px-6 border-t border-white/5 text-center relative z-10">
        <div className="max-w-3xl mx-auto">
          <h2 className="text-2xl font-bold text-white mb-2">Ammar Yasser Abdalazim</h2>
          <span className="text-brand-orange font-semibold tracking-wide uppercase text-sm mb-8 block">GIS Engineer & AI Developer</span>
          <p className="text-gray-400 mb-12 text-lg">
            Building tools that make geospatial data quality accessible to everyone. GeoFix combines deep GIS expertise with modern AI.
          </p>
          <div className="flex justify-center gap-6 mb-12">
            {[
              { icon: Linkedin, href: "https://www.linkedin.com/in/ammar-yasser-abdalazim-386236240" },
              { icon: Github, href: "https://github.com/AmmarYasser455" },
              { icon: Twitter, href: "https://x.com/Ammar12274191" },
            ].map((social, i) => (
              <a
                key={i}
                href={social.href}
                target="_blank"
                rel="noreferrer"
                className="p-3 rounded-full bg-white/5 hover:bg-white/10 hover:text-brand-orange transition-all"
              >
                <social.icon size={20} />
              </a>
            ))}
          </div>
          <div className="text-gray-600 text-sm">© 2026 GeoFix. All rights reserved.</div>
        </div>
      </footer>

      {/* Auth Modal */}
      <AnimatePresence>
        {isAuthOpen && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 z-[100] flex items-center justify-center bg-black/80 backdrop-blur-sm p-4"
            onClick={() => setIsAuthOpen(false)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.95, opacity: 0 }}
              className="bg-[#111] border border-white/10 rounded-3xl p-8 w-full max-w-md shadow-2xl relative"
              onClick={e => e.stopPropagation()}
            >
              <button onClick={() => setIsAuthOpen(false)} className="absolute top-4 right-4 text-gray-500 hover:text-white transition-colors"><X size={24} /></button>

              <h2 className="text-3xl font-bold mb-2">{authMode === 'signup' ? 'Create Account' : 'Welcome Back'}</h2>
              <p className="text-gray-400 mb-6">Enter your email to sign in to GeoFix</p>

              {error && (
                <div className="mb-6 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center gap-2">
                  <AlertCircle size={16} />
                  {error}
                </div>
              )}

              <form onSubmit={handleAuth} className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">Email</label>
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-brand-orange transition-colors"
                    disabled={isLoading}
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1">Password</label>
                  <input
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-brand-orange transition-colors"
                    disabled={isLoading}
                  />
                </div>

                <button
                  type="submit"
                  disabled={isLoading}
                  className="w-full bg-white text-black font-bold py-3.5 rounded-xl mt-4 hover:bg-brand-gray hover:text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
                >
                  {isLoading ? <img src="/public/animation/loading_icon.gif" className="h-6 w-auto" alt="Loading..." /> : (authMode === 'signup' ? 'Sign Up' : 'Sign In')}
                </button>
              </form>

              <div className="mt-8 text-center text-sm text-gray-500">
                {authMode === 'signup' ? "Already have an account?" : "Don't have an account?"}
                <button onClick={() => openAuth(authMode === 'signup' ? 'login' : 'signup')} className="text-brand-orange font-semibold ml-2 hover:underline">
                  {authMode === 'signup' ? 'Sign In' : 'Sign Up'}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default App;
