import { useState, useEffect } from 'react';

const API = '/api';

export default function ProfessorConfig() {
    const [modules, setModules] = useState([]);
    const [selectedModule, setSelectedModule] = useState('');
    const [newModuleName, setNewModuleName] = useState('');

    // Config fields
    const [topics, setTopics] = useState([]);
    const [topicInput, setTopicInput] = useState('');
    const [subTopics, setSubTopics] = useState([]);
    const [subTopicInput, setSubTopicInput] = useState('');
    const [depth, setDepth] = useState('surface');
    const [style, setStyle] = useState('supportive');
    const [mustApp, setMustApp] = useState(false);
    const [customNotes, setCustomNotes] = useState('');
    const [saving, setSaving] = useState(false);
    const [generating, setGenerating] = useState(false);
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
                setSubTopics(cfg.sub_topics || []);
                setDepth(cfg.expected_depth || 'surface');
                setStyle(cfg.probing_style || 'supportive');
                setMustApp(cfg.must_include_application || false);
                setCustomNotes(cfg.custom_notes || '');
            })
            .catch(() => {
                setTopics([]);
                setSubTopics([]);
                setDepth('surface');
                setStyle('supportive');
                setMustApp(false);
                setCustomNotes('');
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
            setTopics((prev) => [...prev, t]);
            setTopicInput('');
        }
    };

    const removeTopic = (t) => {
        setTopics((prev) => prev.filter((x) => x !== t));
    };

    const handleTopicKeyDown = (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            addTopic();
        }
    };

    const addSubTopic = () => {
        const t = subTopicInput.trim();
        if (t && !subTopics.includes(t)) {
            setSubTopics((prev) => [...prev, t]);
            setSubTopicInput('');
        }
    };

    const removeSubTopic = (t) => {
        setSubTopics((prev) => prev.filter((x) => x !== t));
    };

    const handleSubTopicKeyDown = (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            addSubTopic();
        }
    };

    const handleAutoGenerate = async () => {
        if (!topics.length) return;
        setGenerating(true);
        setStatus('');
        try {
            const res = await fetch(`${API}/modules/subtopics/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ main_topics: topics }),
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.detail || 'Generation failed');
            setSubTopics(data.sub_topics || []);
            setStatus('Sub-topics generated');
        } catch (e) {
            setStatus('✗ ' + e.message);
        } finally {
            setGenerating(false);
        }
    };

    const handleSave = async () => {
        if (!selectedModule) return;
        setSaving(true);
        setStatus('');
        const payload = {
            required_topics: topics,
            sub_topics: subTopics,
            expected_depth: depth,
            probing_style: style,
            must_include_application: mustApp,
            custom_notes: customNotes,
        };
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
            if (data) {
                setTopics(data.required_topics || []);
                setSubTopics(data.sub_topics || []);
                setDepth(data.expected_depth || depth);
                setStyle(data.probing_style || style);
                setMustApp(Boolean(data.must_include_application));
                setCustomNotes(data.custom_notes || '');
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
                            <label>Main Topics</label>
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

                        <div className="form-group">
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.4rem' }}>
                                <label style={{ marginBottom: 0 }}>Sub Topics</label>
                                <button
                                    className="btn btn-outline"
                                    style={{ fontSize: '0.75rem', padding: '0.2rem 0.6rem' }}
                                    onClick={handleAutoGenerate}
                                    disabled={!topics.length || generating}
                                >
                                    {generating ? 'Generating…' : 'Auto-generate'}
                                </button>
                            </div>
                            <div className="tag-input-wrapper">
                                {subTopics.map((t) => (
                                    <span key={t} className="tag">
                                        {t}
                                        <span className="remove" onClick={() => removeSubTopic(t)}>×</span>
                                    </span>
                                ))}
                                <input
                                    type="text"
                                    placeholder="Add sub-topic + Enter"
                                    value={subTopicInput}
                                    onChange={(e) => setSubTopicInput(e.target.value)}
                                    onKeyDown={handleSubTopicKeyDown}
                                />
                            </div>
                            <small style={{ color: 'var(--muted, #888)', fontSize: '0.8rem' }}>
                                Chat questions will follow these sub-topics in order.
                            </small>
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

                        <div className="form-group">
                            <label>Custom Notes for LLM</label>
                            <textarea
                                rows={4}
                                placeholder="e.g. Focus on the student's understanding of backpropagation before moving to other topics. Ensure they can explain the chain rule."
                                value={customNotes}
                                onChange={(e) => setCustomNotes(e.target.value)}
                                style={{ width: '100%', resize: 'vertical' }}
                            />
                            <small style={{ color: 'var(--muted, #888)', fontSize: '0.8rem' }}>
                                These instructions are given highest priority — the LLM will address them before other topics.
                            </small>
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
