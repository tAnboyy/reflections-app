import { useState, useEffect } from 'react';

const API = '/api';

export default function ProfessorConfig() {
    const [modules, setModules] = useState([]);
    const [selectedModule, setSelectedModule] = useState('');
    const [newModuleName, setNewModuleName] = useState('');

    // Config fields
    const [topics, setTopics] = useState([]);
    const [topicInput, setTopicInput] = useState('');
    const [depth, setDepth] = useState('surface');
    const [style, setStyle] = useState('supportive');
    const [mustApp, setMustApp] = useState(false);
    const [saving, setSaving] = useState(false);
    const [status, setStatus] = useState('');

    useEffect(() => {
        fetchModules();
    }, []);

    const fetchModules = () => {
        fetch(`${API}/modules`).then((r) => r.json()).then(setModules).catch(() => { });
    };

    // Load existing config when module changes
    useEffect(() => {
        if (!selectedModule) return;
        fetch(`${API}/modules/${selectedModule}/config`)
            .then((r) => {
                if (!r.ok) throw new Error('none');
                return r.json();
            })
            .then((cfg) => {
                setTopics(cfg.required_topics || []);
                setDepth(cfg.expected_depth || 'surface');
                setStyle(cfg.probing_style || 'supportive');
                setMustApp(cfg.must_include_application || false);
            })
            .catch(() => {
                setTopics([]);
                setDepth('surface');
                setStyle('supportive');
                setMustApp(false);
            });
    }, [selectedModule]);

    const handleCreateModule = async () => {
        if (!newModuleName.trim()) return;
        const res = await fetch(`${API}/modules`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: newModuleName.trim() }),
        });
        const mod = await res.json();
        setModules((prev) => [...prev, mod]);
        setSelectedModule(mod.id);
        setNewModuleName('');
    };

    const addTopic = () => {
        const t = topicInput.trim();
        if (t && !topics.includes(t)) {
            console.log('Adding topic:', t, 'Current topics:', topics);
            setTopics((prev) => {
                const updated = [...prev, t];
                console.log('Updated topics:', updated);
                return updated;
            });
            setTopicInput('');
        }
    };

    const removeTopic = (t) => {
        console.log('Removing topic:', t);
        setTopics((prev) => prev.filter((x) => x !== t));
    };

    const handleTopicKeyDown = (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            addTopic();
        }
    };

    const handleSave = async () => {
        if (!selectedModule) return;
        console.log('Saving config with topics:', topics);
        setSaving(true);
        setStatus('');
        const payload = {
            required_topics: topics,
            expected_depth: depth,
            probing_style: style,
            must_include_application: mustApp,
        };
        console.log('Save payload:', payload);
        try {
            const res = await fetch(`${API}/modules/${selectedModule}/config`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            const data = await res.json().catch(() => null);
            if (!res.ok) {
                const msg = (data && data.detail) || 'Save failed';
                throw new Error(msg);
            }
            // Update local state from server's authoritative response
            if (data) {
                setTopics(data.required_topics || []);
                setDepth(data.expected_depth || depth);
                setStyle(data.probing_style || style);
                setMustApp(Boolean(data.must_include_application));
            }
            setStatus('✓ Saved');
        } catch (e) {
            setStatus('✗ ' + e.message);
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="page">
            <h1>Professor Module Configuration</h1>

            {/* Create new module */}
            <div className="card">
                <div className="form-group">
                    <label>Create New Module</label>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                        <input
                            type="text"
                            placeholder="e.g. Week 3 — Neural Networks"
                            value={newModuleName}
                            onChange={(e) => setNewModuleName(e.target.value)}
                        />
                        <button className="btn btn-outline" onClick={handleCreateModule}>Create</button>
                    </div>
                </div>
            </div>

            {/* Select module */}
            <div className="card">
                <div className="form-group">
                    <label>Select Module</label>
                    <select value={selectedModule} onChange={(e) => setSelectedModule(e.target.value)}>
                        <option value="">Choose…</option>
                        {modules.map((m) => (
                            <option key={m.id} value={m.id}>{m.name}</option>
                        ))}
                    </select>
                </div>

                {selectedModule && (
                    <>
                        <div className="form-group">
                            <label>Required Topics</label>
                            <div className="tag-input-wrapper">
                                {topics.map((t) => (
                                    <span key={t} className="tag">
                                        {t}
                                        <span className="remove" onClick={() => removeTopic(t)}>×</span>
                                    </span>
                                ))}
                                <input
                                    type="text"
                                    placeholder="Add topic + Enter"
                                    value={topicInput}
                                    onChange={(e) => setTopicInput(e.target.value)}
                                    onKeyDown={handleTopicKeyDown}
                                />
                            </div>
                        </div>

                        <div className="row">
                            <div className="form-group" style={{ flex: 1 }}>
                                <label>Expected Depth</label>
                                <select value={depth} onChange={(e) => setDepth(e.target.value)}>
                                    <option value="surface">Surface</option>
                                    <option value="applied">Applied</option>
                                    <option value="analytical">Analytical</option>
                                </select>
                            </div>
                            <div className="form-group" style={{ flex: 1 }}>
                                <label>Probing Style</label>
                                <select value={style} onChange={(e) => setStyle(e.target.value)}>
                                    <option value="supportive">Supportive</option>
                                    <option value="socratic">Socratic</option>
                                </select>
                            </div>
                        </div>

                        <div className="form-group">
                            <div className="checkbox-row">
                                <input
                                    type="checkbox"
                                    id="mustApp"
                                    checked={mustApp}
                                    onChange={(e) => setMustApp(e.target.checked)}
                                />
                                <label htmlFor="mustApp" style={{ textTransform: 'none', fontSize: '0.9rem', marginBottom: 0 }}>
                                    Must include application-based question
                                </label>
                            </div>
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                            <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
                                {saving ? 'Saving…' : 'Save Configuration'}
                            </button>
                            {status && <span style={{ fontSize: '0.85rem' }}>{status}</span>}
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}
