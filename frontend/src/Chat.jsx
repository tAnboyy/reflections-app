import { useState, useEffect, useRef } from 'react';

const API = '/api';

export default function Chat() {
    const [phase, setPhase] = useState('setup'); // setup | chatting | ended
    const [modules, setModules] = useState([]);
    const [moduleId, setModuleId] = useState('');
    const [studentId, setStudentId] = useState('student-1');
    const [sessionId, setSessionId] = useState(null);
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [seconds, setSeconds] = useState(600); // 10 min
    const [evaluation, setEvaluation] = useState(null);
    const bottomRef = useRef(null);

    // Fetch modules on mount
    useEffect(() => {
        fetch(`${API}/modules`)
            .then((r) => r.json())
            .then(setModules)
            .catch(() => { });
    }, []);

    // Timer
    useEffect(() => {
        if (phase !== 'chatting') return;
        if (seconds <= 0) {
            handleEnd();
            return;
        }
        const id = setInterval(() => setSeconds((s) => s - 1), 1000);
        return () => clearInterval(id);
    }, [phase, seconds]);

    // Auto-scroll
    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages]);

    const fmt = (s) => {
        const m = Math.floor(s / 60);
        const sec = s % 60;
        return `${m}:${sec.toString().padStart(2, '0')}`;
    };

    // ── Start Session ──────────────────────────────────────────────
    const handleStart = async () => {
        if (!moduleId) return;
        setLoading(true);
        try {
            const res = await fetch(`${API}/chat/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ student_id: studentId, module_id: moduleId }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Failed');
            setSessionId(data.session_id);
            setMessages([{ role: 'assistant', content: data.greeting }]);
            setPhase('chatting');
        } catch (e) {
            alert(e.message);
        } finally {
            setLoading(false);
        }
    };

    // ── Send Message ───────────────────────────────────────────────
    const handleSend = async () => {
        if (!input.trim() || loading) return;
        const userMsg = input.trim();
        setInput('');
        setMessages((prev) => [...prev, { role: 'user', content: userMsg }]);
        setLoading(true);
        try {
            const res = await fetch(`${API}/chat/message`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: sessionId, message: userMsg, time_remaining: seconds }),
            });
            const data = await res.json();
            setMessages((prev) => [...prev, { role: 'assistant', content: data.reply }]);
        } catch {
            setMessages((prev) => [...prev, { role: 'assistant', content: '⚠ Error reaching server.' }]);
        } finally {
            setLoading(false);
        }
    };

    // ── End Session ────────────────────────────────────────────────
    const handleEnd = async () => {
        if (!sessionId) return;
        setPhase('ended');
        try {
            const res = await fetch(`${API}/chat/end`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: sessionId }),
            });
            const data = await res.json();
            setEvaluation(data.evaluation);
        } catch {
            /* silent */
        }
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    // ── Setup screen ───────────────────────────────────────────────
    if (phase === 'setup') {
        return (
            <div className="setup-screen">
                <h2>Start a Reflection Session</h2>
                <div className="form-group">
                    <label>Student ID</label>
                    <input type="text" value={studentId} onChange={(e) => setStudentId(e.target.value)} />
                </div>
                <div className="form-group">
                    <label>Module</label>
                    <select value={moduleId} onChange={(e) => setModuleId(e.target.value)}>
                        <option value="">Select a module…</option>
                        {modules.map((m) => (
                            <option key={m.id} value={m.id}>{m.name}</option>
                        ))}
                    </select>
                </div>
                <button className="btn btn-primary" onClick={handleStart} disabled={!moduleId || loading}>
                    {loading ? 'Starting…' : 'Begin Session'}
                </button>
            </div>
        );
    }

    // ── Ended screen ───────────────────────────────────────────────
    if (phase === 'ended') {
        return (
            <div className="page">
                <h1>Session Complete</h1>
                {evaluation ? (
                    <div className="card">
                        <p><strong>Depth Score:</strong> {evaluation.reflection_depth_score}</p>
                        <p><strong>Confidence:</strong> {evaluation.confidence_level}/5</p>
                        <p><strong>Engagement:</strong> {evaluation.engagement_score}</p>
                        <p><strong>Topics Covered:</strong> {evaluation.topics_covered?.join(', ') || 'n/a'}</p>
                        <p><strong>Missing Topics:</strong> {evaluation.missing_topics?.join(', ') || 'none'}</p>
                        <p><strong>Misconceptions:</strong> {evaluation.misconceptions?.join(', ') || 'none'}</p>
                    </div>
                ) : (
                    <p className="empty">Evaluating transcript…</p>
                )}
                <button className="btn btn-outline" onClick={() => { setPhase('setup'); setMessages([]); setSeconds(600); setEvaluation(null); }}>
                    New Session
                </button>
            </div>
        );
    }

    // ── Chat screen ────────────────────────────────────────────────
    return (
        <div className="chat-container">
            <div className="chat-header">
                <span style={{ fontWeight: 600 }}>Reflection Session</span>
                <span className={`timer ${seconds <= 60 ? 'warning' : ''}`}>{fmt(seconds)}</span>
                <button className="btn btn-danger" onClick={handleEnd}>End Session</button>
            </div>

            <div className="messages">
                {messages.map((m, i) => (
                    <div key={i} className={`message ${m.role}`}>{m.content}</div>
                ))}
                {loading && <div className="message assistant" style={{ opacity: 0.5 }}>Thinking…</div>}
                <div ref={bottomRef} />
            </div>

            <div className="chat-input">
                <input
                    type="text"
                    placeholder="Type your reflection…"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    disabled={loading}
                />
                <button className="btn btn-primary" onClick={handleSend} disabled={loading || !input.trim()}>
                    Send
                </button>
            </div>
        </div>
    );
}
