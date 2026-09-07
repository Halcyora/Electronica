import React, { useState, useEffect, useRef } from 'react';
import './Dashboard.css';

const API_BASE = 'http://localhost:8000';
const WS_BASE = 'ws://localhost:8000';

const Dashboard = () => {
  // State
  const [datasets, setDatasets] = useState({});
  const [selectedDataset, setSelectedDataset] = useState('mitdb');
  const [selectedRecord, setSelectedRecord] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [signalData, setSignalData] = useState([]);
  const [features, setFeatures] = useState({});
  const [inference, setInference] = useState(null);
  const [alerts, setAlerts] = useState([]);
  const [eventLog, setEventLog] = useState([]);

  const wsRef = useRef(null);
  const canvasRef = useRef(null);

  // Load available datasets
  useEffect(() => {
    fetch(`${API_BASE}/datasets`)
      .then(r => r.json())
      .then(data => {
        setDatasets(data);
        if (data.mitdb && data.mitdb.length > 0) {
          setSelectedRecord(data.mitdb[0]);
        }
      })
      .catch(err => console.error('Failed to load datasets:', err));
  }, []);

  // Update selected record when dataset changes
  useEffect(() => {
    if (datasets[selectedDataset]?.length > 0) {
      setSelectedRecord(datasets[selectedDataset][0]);
    }
  }, [selectedDataset, datasets]);

  // Start streaming
  const handleStartStream = async () => {
    if (!selectedRecord) {
      alert('Please select a record');
      return;
    }

    try {
      // Load signal
      const loadResp = await fetch(`${API_BASE}/load_signal`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          dataset: selectedDataset,
          record: selectedRecord,
          start_sec: 0,
          duration_sec: 60,
          speed_factor: 1.0,
          channels: [0],
        }),
      });

      if (!loadResp.ok) throw new Error('Failed to load signal');

      setSignalData([]);
      setAlerts([]);
      setIsStreaming(true);

      // Connect WebSocket
      wsRef.current = new WebSocket(`${WS_BASE}/ws/stream_signal`);

      wsRef.current.onopen = () => {
        console.log('WebSocket connected');
        wsRef.current.send(JSON.stringify({ batch_size: 20, speed_factor: 1.0 }));
      };

      wsRef.current.onmessage = async (event) => {
        const msg = JSON.parse(event.data);

        if (msg.status === 'end') {
          setIsStreaming(false);
          console.log('Stream ended');
          return;
        }

        if (msg.status === 'data' && msg.samples) {
          // Append samples
          setSignalData(prev => {
            const updated = [...prev, ...msg.samples];
            // Keep last 1000 samples for visualization
            return updated.slice(Math.max(0, updated.length - 1000));
          });

          // Extract features from latest batch (simple windowing)
          if (msg.samples.length >= 250) {
            try {
              const featResp = await fetch(`${API_BASE}/extract_features`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  ecg: msg.samples,
                  ppg: [],
                  imu: [],
                }),
              });

              if (featResp.ok) {
                const feat = await featResp.json();
                setFeatures(feat);

                // Run inference if ECG features available
                if (feat.ecg) {
                  const inferReq = [
                    feat.ecg.hr,
                    feat.ecg.hrv_sdnn,
                    feat.ecg.hrv_pnn50,
                    feat.ecg.hrv_rmssd,
                    feat.ecg.hr_mean_rr,
                    feat.ecg.arrhythmia_risk,
                  ];

                  const inferResp = await fetch(`${API_BASE}/infer`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                      features: inferReq,
                      model_type: 'ecg',
                    }),
                  });

                  if (inferResp.ok) {
                    const inf = await inferResp.json();
                    setInference(inf);

                    // Trigger alert if anomaly detected
                    if (inf.class_idx === 1 && inf.confidence > 0.6) {
                      const newAlert = {
                        timestamp: new Date().toISOString(),
                        type: 'Arrhythmia Risk',
                        severity: 'high',
                        confidence: inf.confidence,
                      };
                      setAlerts(prev => [newAlert, ...prev.slice(0, 4)]);
                      setEventLog(prev => [
                        {
                          timestamp: new Date().toLocaleString(),
                          event: `Anomaly detected: ${newAlert.type} (confidence: ${(inf.confidence * 100).toFixed(1)}%)`,
                        },
                        ...prev.slice(0, 9),
                      ]);
                    }
                  }
                }
              }
            } catch (err) {
              console.error('Feature extraction error:', err);
            }
          }

          // Request next batch
          if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ batch_size: 20, speed_factor: 1.0 }));
          }
        }
      };

      wsRef.current.onerror = err => {
        console.error('WebSocket error:', err);
        setIsStreaming(false);
      };
    } catch (err) {
      console.error('Error:', err);
      alert('Failed to start stream: ' + err.message);
    }
  };

  // Stop streaming
  const handleStopStream = () => {
    if (wsRef.current) {
      wsRef.current.close();
    }
    setIsStreaming(false);
  };

  // Draw waveform on canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || signalData.length === 0) return;

    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;

    // Clear
    ctx.fillStyle = '#f0f0f0';
    ctx.fillRect(0, 0, width, height);

    // Draw grid
    ctx.strokeStyle = '#ddd';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 10; i++) {
      const y = (height / 10) * i;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }

    // Draw signal
    ctx.strokeStyle = '#0066cc';
    ctx.lineWidth = 2;
    ctx.beginPath();

    const step = Math.max(1, Math.floor(signalData.length / width));
    const min = Math.min(...signalData);
    const max = Math.max(...signalData);
    const range = max - min || 1;

    for (let i = 0; i < signalData.length; i += step) {
      const x = (i / signalData.length) * width;
      const normalized = (signalData[i] - min) / range;
      const y = height - normalized * height;

      if (i === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    }

    ctx.stroke();
  }, [signalData]);

  return (
    <div className="dashboard">
      <header className="header">
        <h1>🫀 FractalPulse — Edge AI Health Monitoring</h1>
        <p>Real-time cardiac & respiratory anomaly detection (software-only prototype)</p>
      </header>

      <div className="container">
        {/* Control Panel */}
        <div className="panel control-panel">
          <h2>📊 Signal Replay</h2>

          <label>
            Dataset:
            <select value={selectedDataset} onChange={e => setSelectedDataset(e.target.value)}>
              {Object.keys(datasets).map(ds => (
                <option key={ds} value={ds}>
                  {ds}
                </option>
              ))}
            </select>
          </label>

          <label>
            Record:
            <select value={selectedRecord} onChange={e => setSelectedRecord(e.target.value)}>
              {(datasets[selectedDataset] || []).map(rec => (
                <option key={rec} value={rec}>
                  {rec}
                </option>
              ))}
            </select>
          </label>

          <div className="button-group">
            <button onClick={handleStartStream} disabled={isStreaming}>
              ▶ Start Stream
            </button>
            <button onClick={handleStopStream} disabled={!isStreaming}>
              ⏹ Stop Stream
            </button>
          </div>

          <p>Status: {isStreaming ? '🟢 Streaming...' : '⚪ Ready'}</p>
        </div>

        {/* Waveform Display */}
        <div className="panel waveform-panel">
          <h2>📈 ECG Signal</h2>
          <canvas ref={canvasRef} width={800} height={300} className="waveform-canvas"></canvas>
          <p>Samples: {signalData.length}</p>
        </div>

        {/* Features & Classification */}
        <div className="two-column">
          <div className="panel features-panel">
            <h2>🔍 Extracted Features</h2>
            <div className="features-list">
              {features.ecg ? (
                <>
                  <div>
                    <strong>Heart Rate:</strong> {features.ecg.hr.toFixed(1)} bpm
                  </div>
                  <div>
                    <strong>HRV (SDNN):</strong> {features.ecg.hrv_sdnn.toFixed(1)} ms
                  </div>
                  <div>
                    <strong>HRV (pNN50):</strong> {features.ecg.hrv_pnn50.toFixed(1)}%
                  </div>
                  <div>
                    <strong>HRV (RMSSD):</strong> {features.ecg.hrv_rmssd.toFixed(1)} ms
                  </div>
                  <div>
                    <strong>Beats Detected:</strong> {features.ecg.n_beats}
                  </div>
                </>
              ) : (
                <p>Waiting for signal...</p>
              )}
            </div>
          </div>

          <div className="panel classification-panel">
            <h2>🎯 Classification</h2>
            {inference ? (
              <>
                <div className="classification-result">
                  <div className="class-box">
                    <div className="class-name">{inference.class_name}</div>
                    <div className="confidence">
                      {(inference.confidence * 100).toFixed(1)}%
                    </div>
                  </div>
                </div>
                <div className="scores">
                  <div>Normal: {(inference.all_scores[0] * 100).toFixed(1)}%</div>
                  <div>Anomaly: {(inference.all_scores[1] * 100).toFixed(1)}%</div>
                </div>
              </>
            ) : (
              <p>Waiting for inference...</p>
            )}
          </div>
        </div>

        {/* Alerts */}
        <div className="panel alerts-panel">
          <h2>⚠️ Alerts</h2>
          {alerts.length > 0 ? (
            <div className="alerts-list">
              {alerts.map((alert, i) => (
                <div key={i} className={`alert alert-${alert.severity}`}>
                  <strong>{alert.type}</strong> — Confidence: {(alert.confidence * 100).toFixed(1)}%
                  <br />
                  <small>{new Date(alert.timestamp).toLocaleTimeString()}</small>
                </div>
              ))}
            </div>
          ) : (
            <p>No alerts</p>
          )}
        </div>

        {/* Event Log */}
        <div className="panel eventlog-panel">
          <h2>📝 Event Log</h2>
          <div className="eventlog-list">
            {eventLog.length > 0 ? (
              eventLog.map((entry, i) => (
                <div key={i} className="event-entry">
                  <span className="event-time">{entry.timestamp}</span>
                  <span className="event-text">{entry.event}</span>
                </div>
              ))
            ) : (
              <p>No events</p>
            )}
          </div>
        </div>
      </div>

      <footer className="footer">
        <p>🔒 Privacy-first, edge-only inference. No data sent to cloud.</p>
      </footer>
    </div>
  );
};

export default Dashboard;
