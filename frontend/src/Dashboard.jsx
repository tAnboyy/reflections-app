import { useState, useEffect } from 'react';

const API = '/api';

function scoreCls(v, max = 1) {
    const pct = v / max;
    if (pct >= 0.7) return 'score high';
    if (pct >= 0.4) return 'score mid';
    return 'score low';
}

export default function Dashboard() {
    const [modules, setModules] = useState([]);
    const [moduleId, setModuleId] = useState('');
    const [rows, setRows] = useState([]);

    useEffect(() => {
        fetch(`${API}/modules`).then((r) => r.json()).then(setModules).catch(() => { });
    }, []);

    useEffect(() => {
        if (!moduleId) { setRows([]); return; }
        fetch(`${API}/analytics/${moduleId}`)
            .then((r) => r.json())
            .then(setRows)
            .catch(() => setRows([]));
    }, [moduleId]);

    return (
        <div className="page">
            <h1>Analytics Dashboard</h1>

            <div className="form-group" style={{ maxWidth: 360 }}>
                <label>Module</label>
                <select value={moduleId} onChange={(e) => setModuleId(e.target.value)}>
                    <option value="">Select module…</option>
                    {modules.map((m) => (
                        <option key={m.id} value={m.id}>{m.name}</option>
                    ))}
                </select>
            </div>

            {moduleId && rows.length === 0 && (
                <p className="empty">No analytics data yet for this module.</p>
            )}

            {rows.length > 0 && (
                <>
                    <div className="card" style={{ overflowX: 'auto' }}>
                        <table>
                            <thead>
                                <tr>
                                    <th>Student</th>
                                    <th>Depth</th>
                                    <th>Confidence</th>
                                    <th>Engagement</th>
                                    <th>Missing Topics</th>
                                    <th>Misconceptions</th>
                                    <th>Date</th>
                                </tr>
                            </thead>
                            <tbody>
                                {rows.map((r) => (
                                    <tr key={r.conversation_id}>
                                        <td>{r.student_anonymized_id}</td>
                                        <td><span className={scoreCls(r.reflection_depth_score)}>{r.reflection_depth_score.toFixed(2)}</span></td>
                                        <td><span className={scoreCls(r.confidence_level, 5)}>{r.confidence_level}/5</span></td>
                                        <td><span className={scoreCls(r.engagement_score)}>{r.engagement_score.toFixed(2)}</span></td>
                                        <td>{r.missing_topics.length ? r.missing_topics.map((t) => <span key={t} className="tag">{t}</span>) : '—'}</td>
                                        <td>{r.misconceptions.length ? r.misconceptions.map((t, i) => <span key={i} className="tag">{t}</span>) : '—'}</td>
                                        <td style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>{new Date(r.created_at).toLocaleDateString()}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>

                    {/* Simple bar chart — reflection depth per student */}
                    <div className="card">
                        <h3 style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
                            Reflection Depth by Student
                        </h3>
                        <div className="bar-chart">
                            {rows.map((r) => (
                                <div key={r.conversation_id} className="bar-col">
                                    <div className="bar" style={{ height: `${r.reflection_depth_score * 100}%` }} />
                                    <span className="bar-label">{r.student_anonymized_id}</span>
                                </div>
                            ))}
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}
