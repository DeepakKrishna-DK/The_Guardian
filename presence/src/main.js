import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';

// ─────────────────────────────────────────────────────────────────────────────
// THREE.JS SCENE SETUP
// ─────────────────────────────────────────────────────────────────────────────
const canvas = document.getElementById('three-canvas');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.localClippingEnabled = true;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x020208);
scene.fog = new THREE.FogExp2(0x020208, 0.035);

const camera = new THREE.PerspectiveCamera(50, window.innerWidth / window.innerHeight, 0.1, 100);
camera.position.set(0, 1.25, 4.0);
camera.lookAt(0, 1.25, 0);

const clock = new THREE.Clock();
let frameCount = 0;
let lastFpsTime = 0;

// Bloom post-processing
const renderScene = new RenderPass(scene, camera);
const bloomPass = new UnrealBloomPass(new THREE.Vector2(window.innerWidth, window.innerHeight), 1.4, 0.4, 0.1);
bloomPass.threshold = 0.2;
bloomPass.strength = 0.65;
bloomPass.radius = 0.5;

const composer = new EffectComposer(renderer);
composer.addPass(renderScene);
composer.addPass(bloomPass);

// ─────────────────────────────────────────────────────────────────────────────
// HOLOGRAPHIC MATERIALS & ENVIRONMENT
// ─────────────────────────────────────────────────────────────────────────────
const clipPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), -0.2);

const hologramMat = new THREE.MeshBasicMaterial({
  color: 0x00f0ff,
  wireframe: true,
  transparent: true,
  opacity: 0.65,
  blending: THREE.AdditiveBlending,
  depthWrite: false,
  clippingPlanes: [clipPlane],
});

const hologramInnerMat = new THREE.MeshBasicMaterial({
  color: 0x020614,
  transparent: true,
  opacity: 0.95,
  depthWrite: true,
  clippingPlanes: [clipPlane],
});

// Starfield particles
const starCount = 3500;
const starGeo = new THREE.BufferGeometry();
const starPos = new Float32Array(starCount * 3);
const starColors = new Float32Array(starCount * 3);

for (let i = 0; i < starCount; i++) {
  const r = 18 + Math.random() * 32;
  const theta = Math.random() * Math.PI * 2;
  const phi = Math.acos(Math.random() * 2 - 1);

  starPos[i * 3] = r * Math.sin(phi) * Math.cos(theta);
  starPos[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
  starPos[i * 3 + 2] = r * Math.cos(phi);

  const col = new THREE.Color();
  col.setHSL(0.55 + Math.random() * 0.15, 0.8, 0.5 + Math.random() * 0.3);
  starColors[i * 3] = col.r;
  starColors[i * 3 + 1] = col.g;
  starColors[i * 3 + 2] = col.b;
}
starGeo.setAttribute('position', new THREE.BufferAttribute(starPos, 3));
starGeo.setAttribute('color', new THREE.BufferAttribute(starColors, 3));

const starMat = new THREE.PointsMaterial({
  size: 0.12,
  vertexColors: true,
  transparent: true,
  opacity: 0.8,
  blending: THREE.AdditiveBlending,
});
const starField = new THREE.Points(starGeo, starMat);
scene.add(starField);

// Projector floor grid
const gridGeo = new THREE.PlaneGeometry(10, 10, 16, 16);
const gridMat = new THREE.MeshBasicMaterial({
  color: 0x0066ff,
  wireframe: true,
  transparent: true,
  opacity: 0.22,
  blending: THREE.AdditiveBlending,
});
const gridFloor = new THREE.Mesh(gridGeo, gridMat);
gridFloor.rotation.x = -Math.PI / 2;
gridFloor.position.y = -0.5;
scene.add(gridFloor);

// Glowing projector plate
const plateGeo = new THREE.PlaneGeometry(3.6, 3.6, 32, 32);
const plateMat = new THREE.MeshStandardMaterial({
  color: 0x111118,
  emissive: 0x0088ff,
  emissiveIntensity: 0.5,
  roughness: 0.2,
  metalness: 0.8,
});
const plate = new THREE.Mesh(plateGeo, plateMat);
plate.rotation.x = -Math.PI / 2;
plate.position.y = 0.0;
scene.add(plate);

// Volumetric scanline beam
const beamGeo = new THREE.CylinderGeometry(2.4, 1.4, 4.2, 32, 1, true);
const beamMat = new THREE.ShaderMaterial({
  uniforms: {
    uColor: { value: new THREE.Color(0x00aaff) },
    uTime: { value: 0 },
    uIntensity: { value: 1.0 },
  },
  vertexShader: `varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
  fragmentShader: `
    uniform vec3 uColor; uniform float uTime; uniform float uIntensity; varying vec2 vUv;
    void main() {
      float alpha = (1.0 - vUv.y) * 0.12 * uIntensity;
      float scanline = sin(vUv.y * 70.0 - uTime * 6.0) * 0.5 + 0.5;
      alpha *= 0.5 + scanline * 0.5;
      gl_FragColor = vec4(uColor, alpha);
    }
  `,
  transparent: true,
  blending: THREE.AdditiveBlending,
  depthWrite: false,
  side: THREE.DoubleSide,
});
const beam = new THREE.Mesh(beamGeo, beamMat);
beam.position.y = 2.1;
scene.add(beam);

// ─────────────────────────────────────────────────────────────────────────────
// 3D AVATAR GLTF LOADER
// ─────────────────────────────────────────────────────────────────────────────
const loader = new GLTFLoader();
let headMesh = null;
const holoGroup = new THREE.Group();
scene.add(holoGroup);

const initOverlay = document.getElementById('init-overlay');

loader.load('/models/half-body.glb', (gltf) => {
  const model = gltf.scene;

  model.traverse((child) => {
    if (child.isMesh) {
      const name = child.name.toLowerCase();
      if (name.includes('hair') || name.includes('teeth') || name.includes('eye') || name.includes('shirt') || name.includes('outfit')) {
        child.visible = false;
      } else if (name.includes('head') || name.includes('body') || name.includes('avatar') || name.includes('mesh')) {
        const geom = child.geometry;

        const inner = new THREE.Mesh(geom, hologramInnerMat);
        inner.morphTargetInfluences = child.morphTargetInfluences;
        inner.morphTargetDictionary = child.morphTargetDictionary;

        const outer = new THREE.Mesh(geom, hologramMat);
        outer.morphTargetInfluences = child.morphTargetInfluences;
        outer.morphTargetDictionary = child.morphTargetDictionary;

        child.parent.add(inner);
        child.parent.add(outer);
        child.visible = false;

        headMesh = outer;
      }
    }
  });

  model.scale.setScalar(6.5);
  model.position.set(0, -3.2, 0);
  holoGroup.add(model);

  if (initOverlay) initOverlay.style.display = 'none';
  window.__presenceLoaded = true;
});

// ─────────────────────────────────────────────────────────────────────────────
// WEB AUDIO API & DUAL-MODE LIP-SYNC ENGINE
// ─────────────────────────────────────────────────────────────────────────────
const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
const analyser = audioCtx.createAnalyser();
analyser.fftSize = 256;
const dataArray = new Uint8Array(analyser.frequencyBinCount);
let audioVolume = 0;

// Setup wave canvas oscilloscope
const waveCanvas = document.getElementById('wave-canvas');
const waveCtx = waveCanvas ? waveCanvas.getContext('2d') : null;
if (waveCanvas) {
  waveCanvas.width = 260;
  waveCanvas.height = 38;
}

function drawWaveform() {
  if (!waveCtx || !waveCanvas) return;
  analyser.getByteTimeDomainData(dataArray);

  waveCtx.clearRect(0, 0, waveCanvas.width, waveCanvas.height);
  waveCtx.lineWidth = 1.5;
  waveCtx.strokeStyle = guardianState === 'speaking' ? '#00f0ff' : (guardianState === 'listening' ? '#ff3344' : '#0066ff');
  waveCtx.beginPath();

  const sliceWidth = waveCanvas.width / dataArray.length;
  let x = 0;

  for (let i = 0; i < dataArray.length; i++) {
    const v = dataArray[i] / 128.0;
    const y = (v * waveCanvas.height) / 2;
    if (i === 0) waveCtx.moveTo(x, y);
    else waveCtx.lineTo(x, y);
    x += sliceWidth;
  }
  waveCtx.stroke();
}

// ─────────────────────────────────────────────────────────────────────────────
// STATE MACHINE & WEBSOCKET ENGINE
// ─────────────────────────────────────────────────────────────────────────────
let guardianState = 'idle';
const statePill = document.getElementById('status-badge');
const stateText = document.getElementById('state-text');
const transcriptTicker = document.getElementById('transcript-ticker');
const telemetryFps = document.getElementById('telemetry-fps');
const telemetryKs = document.getElementById('telemetry-ks');
const cognitiveFeed = document.getElementById('cognitive-feed');
const evidenceContainer = document.getElementById('evidence-container');
const approvalCard = document.getElementById('approval-card');
const approvalDesc = document.getElementById('approval-desc');
const approvalTarget = document.getElementById('approval-target');
let currentApprovalId = null;

export function setGuardianState(state) {
  guardianState = state;
  if (stateText) stateText.innerText = state.toUpperCase();

  if (statePill) {
    if (state === 'speaking') {
      statePill.style.borderColor = 'var(--cyan)';
      statePill.style.color = 'var(--cyan)';
    } else if (state === 'thinking' || state === 'researching') {
      statePill.style.borderColor = 'var(--purple)';
      statePill.style.color = 'var(--purple)';
    } else if (state === 'listening') {
      statePill.style.borderColor = 'var(--red)';
      statePill.style.color = 'var(--red)';
    } else {
      statePill.style.borderColor = 'var(--cyan)';
      statePill.style.color = 'var(--green)';
    }
  }
}

function addCognitiveEvent(title, detail) {
  if (!cognitiveFeed) return;
  const timeStr = new Date().toTimeString().split(' ')[0];
  const item = document.createElement('div');
  item.className = 'stream-item';
  item.innerHTML = `<div class="stream-time">${timeStr} // ${title}</div>${detail}`;
  cognitiveFeed.prepend(item);
}

function renderEvidence(sources) {
  if (!evidenceContainer || !sources || !sources.length) return;
  evidenceContainer.innerHTML = '';

  sources.forEach((s) => {
    const card = document.createElement('div');
    card.className = 'evidence-card';
    const badgeType = s.type === 'local_knowledge' ? 'badge-knowledge' : (s.type === 'web' ? 'badge-web' : 'badge-paper');
    const badgeText = s.type === 'local_knowledge' ? 'LOCAL KNOWLEDGE' : (s.type === 'web' ? 'WEB INTELLIGENCE' : 'SCHOLARLY PAPER');

    card.innerHTML = `
      <span class="evidence-badge ${badgeType}">${badgeText}</span>
      <div class="evidence-title">${s.title || s.identifier || 'Evidence Source'}</div>
      <div class="evidence-snippet">${s.snippet || s.content || ''}</div>
      ${s.url ? `<a href="${s.url}" target="_blank" class="evidence-link">➔ View Source Record</a>` : ''}
    `;
    evidenceContainer.appendChild(card);
  });
}

// Play speech audio chunk via Web Audio API, or fallback to SpeechSynthesis
async function playAudioChunk(audioB64, sentenceText) {
  if (audioCtx.state === 'suspended') await audioCtx.resume();

  if (audioB64 && audioB64.length > 50) {
    try {
      const binaryString = atob(audioB64);
      const len = binaryString.length;
      const bytes = new Uint8Array(len);
      for (let i = 0; i < len; i++) bytes[i] = binaryString.charCodeAt(i);

      audioCtx.decodeAudioData(bytes.buffer, (buffer) => {
        const source = audioCtx.createBufferSource();
        source.buffer = buffer;
        source.connect(analyser);
        source.connect(audioCtx.destination);
        source.start(0);
      });
      return;
    } catch (e) {
      console.warn('Audio decoding fallback:', e);
    }
  }

  // Fallback: Web Speech API synthesis with oscillator amplitude simulation
  if ('speechSynthesis' in window && sentenceText) {
    const utter = new SpeechSynthesisUtterance(sentenceText);
    utter.rate = 1.05;

    // Pulse a zero-gain oscillator into the analyser to animate mouthOpen
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    gain.gain.value = 0.8;
    osc.connect(gain);
    gain.connect(analyser);
    osc.start();

    utter.onend = () => {
      try { osc.stop(); } catch (_) {}
    };
    utter.onerror = () => {
      try { osc.stop(); } catch (_) {}
    };

    window.speechSynthesis.speak(utter);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// WEBSOCKET CONNECTION
// ─────────────────────────────────────────────────────────────────────────────
let ws = null;
const API_BASE = 'http://127.0.0.1:8000';
const WS_URL = 'ws://127.0.0.1:8000/ws/presence';

function connectWebSocket() {
  try {
    ws = new WebSocket(WS_URL);

    ws.onopen = () => {
      console.log('Connected to Guardian JARVIS Core via WebSocket');
      addCognitiveEvent('SYSTEM SYNCHRONIZED', 'Connected to Guardian Unified Core (Port 8000).');
    };

    ws.onmessage = async (event) => {
      try {
        const msg = JSON.parse(event.data);
        const evt = msg.event;

        if (evt === 'connected') {
          if (msg.kill_switch && telemetryKs) {
            telemetryKs.innerText = 'ACTIVE (LOCKED)';
            telemetryKs.style.color = 'var(--red)';
          }
        } else if (evt === 'thinking') {
          setGuardianState('thinking');
          if (transcriptTicker) transcriptTicker.innerText = msg.thought || 'Analyzing intent...';
          addCognitiveEvent('INTENT ANALYSIS', msg.thought || 'Processing conversation turn.');
        } else if (evt === 'researching') {
          setGuardianState('researching');
          if (transcriptTicker) transcriptTicker.innerText = msg.detail || 'Querying evidence sources...';
          addCognitiveEvent('EVIDENCE RETRIEVAL', msg.detail || 'Gathered sources.');
          if (msg.sources) renderEvidence(msg.sources);
        } else if (evt === 'speaking') {
          setGuardianState('speaking');
          if (transcriptTicker) transcriptTicker.innerText = msg.sentence || 'Guardian is speaking...';
          await playAudioChunk(msg.audio_b64, msg.sentence);
        } else if (evt === 'approval_required') {
          const prop = msg.proposal;
          if (prop && approvalCard) {
            currentApprovalId = prop.action_id;
            if (approvalDesc) approvalDesc.innerText = `Action: ${prop.action_type} (${prop.description})`;
            if (approvalTarget) approvalTarget.innerText = `Target: ${prop.target || 'General System'}`;
            approvalCard.style.display = 'block';
            addCognitiveEvent('LEVEL 3 GATE TRIGGERED', `Consequential action staged: ${prop.action_type}. Human authorization required.`);
          }
        } else if (evt === 'approval_result') {
          if (approvalCard) approvalCard.style.display = 'none';
          addCognitiveEvent('APPROVAL RECORDED', `Action ${msg.action_id} ${msg.approved ? 'AUTHORIZED' : 'DENIED'}.`);
        } else if (evt === 'kill_switch_activated') {
          setGuardianState('emergency_stop');
          if (window.speechSynthesis) window.speechSynthesis.cancel();
          if (telemetryKs) {
            telemetryKs.innerText = 'LOCKED';
            telemetryKs.style.color = 'var(--red)';
          }
          addCognitiveEvent('EMERGENCY STOP', 'Kill Switch engaged. All active operations locked.');
        } else if (evt === 'kill_switch_reset') {
          setGuardianState('idle');
          if (telemetryKs) {
            telemetryKs.innerText = 'DISARMED';
            telemetryKs.style.color = 'var(--green)';
          }
          addCognitiveEvent('EMERGENCY CLEARED', 'Kill Switch reset. Normal operations resumed.');
        } else if (evt === 'idle') {
          setGuardianState('idle');
          if (transcriptTicker) transcriptTicker.innerText = 'Ready. Speak or enter a command...';
        }
      } catch (err) {
        console.error('WebSocket dispatch error:', err);
      }
    };

    ws.onclose = () => {
      setTimeout(connectWebSocket, 2500);
    };
    ws.onerror = () => {
      try { ws.close(); } catch (_) {}
    };
  } catch (e) {
    setTimeout(connectWebSocket, 2500);
  }
}

connectWebSocket();

// ─────────────────────────────────────────────────────────────────────────────
// USER INTERACTION CONTROLS
// ─────────────────────────────────────────────────────────────────────────────

// Chat form submission
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');

function sendUserQuery(text) {
  if (!text.trim()) return;
  if (transcriptTicker) transcriptTicker.innerText = `User: "${text}"`;
  addCognitiveEvent('USER DIRECTIVE', text);

  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({
      type: 'user_message',
      text: text,
      use_knowledge: true,
      use_web: true,
      use_academic: false,
    }));
  } else {
    // REST fallback
    fetch(`${API_BASE}/conversation`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: text, use_knowledge: true, use_web: true }),
    }).catch((err) => console.error('REST fallback error:', err));
  }
}

if (chatForm) {
  chatForm.addEventListener('submit', (e) => {
    e.preventDefault();
    if (chatInput && chatInput.value) {
      sendUserQuery(chatInput.value);
      chatInput.value = '';
    }
  });
}

// Quick Prompt Chips
document.querySelectorAll('.chip').forEach((chip) => {
  chip.addEventListener('click', () => {
    const q = chip.getAttribute('data-query');
    if (q) sendUserQuery(q);
  });
});

// Spatial Drawer Toggles
const leftPanel = document.getElementById('left-panel');
const rightPanel = document.getElementById('right-panel');
const toggleLeft = document.getElementById('toggle-left');
const toggleRight = document.getElementById('toggle-right');
const closeLeft = document.getElementById('close-left');
const closeRight = document.getElementById('close-right');

if (toggleLeft && leftPanel) {
  toggleLeft.addEventListener('click', () => leftPanel.classList.toggle('drawer-closed'));
}
if (closeLeft && leftPanel) {
  closeLeft.addEventListener('click', () => leftPanel.classList.add('drawer-closed'));
}

if (toggleRight && rightPanel) {
  toggleRight.addEventListener('click', () => rightPanel.classList.toggle('drawer-closed'));
}
if (closeRight && rightPanel) {
  closeRight.addEventListener('click', () => rightPanel.classList.add('drawer-closed'));
}

// Level 3 Approval buttons
const btnApprove = document.getElementById('btn-approve-action');
const btnReject = document.getElementById('btn-reject-action');

if (btnApprove) {
  btnApprove.addEventListener('click', () => {
    if (currentApprovalId && ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'action_approval', action_id: currentApprovalId, approved: true }));
    }
    if (approvalCard) approvalCard.style.display = 'none';
  });
}

if (btnReject) {
  btnReject.addEventListener('click', () => {
    if (currentApprovalId && ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'action_approval', action_id: currentApprovalId, approved: false }));
    }
    if (approvalCard) approvalCard.style.display = 'none';
  });
}

// Emergency Kill Switch
const killSwitchBtn = document.getElementById('kill-switch-btn');
if (killSwitchBtn) {
  killSwitchBtn.addEventListener('click', () => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'emergency_stop' }));
    }
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// SPEECH RECOGNITION (Web Speech API)
// ─────────────────────────────────────────────────────────────────────────────
const micBtn = document.getElementById('mic-button');
let recognition = null;
let isRecording = false;

if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
  const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SpeechRec();
  recognition.continuous = false;
  recognition.interimResults = true;
  recognition.lang = 'en-US';

  recognition.onstart = () => {
    isRecording = true;
    if (micBtn) micBtn.classList.add('recording');
    setGuardianState('listening');
    if (transcriptTicker) transcriptTicker.innerText = 'Listening to your voice...';
  };

  recognition.onresult = (event) => {
    let interim = '';
    let final = '';
    for (let i = event.resultIndex; i < event.results.length; ++i) {
      if (event.results[i].isFinal) final += event.results[i][0].transcript;
      else interim += event.results[i][0].transcript;
    }
    if (transcriptTicker) {
      transcriptTicker.innerText = final || interim || 'Listening...';
    }
    if (final.trim()) {
      sendUserQuery(final.trim());
    }
  };

  recognition.onend = () => {
    isRecording = false;
    if (micBtn) micBtn.classList.remove('recording');
    if (guardianState === 'listening') setGuardianState('idle');
  };

  recognition.onerror = (e) => {
    isRecording = false;
    if (micBtn) micBtn.classList.remove('recording');
    console.warn('Speech recognition error:', e);
  };
}

if (micBtn) {
  micBtn.addEventListener('click', () => {
    if (!recognition) {
      alert('Web Speech API is not supported in this browser. Please type commands directly.');
      return;
    }
    if (isRecording) {
      recognition.stop();
    } else {
      recognition.start();
    }
  });
}

// Spacebar push-to-talk
window.addEventListener('keydown', (e) => {
  if (e.code === 'Space' && e.target === document.body && recognition && !isRecording) {
    e.preventDefault();
    recognition.start();
  } else if (e.code === 'Escape') {
    // Barge-in: Halt speech playback immediately
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    setGuardianState('idle');
    if (transcriptTicker) transcriptTicker.innerText = 'Interrupted.';
  }
});

// Load Model Slots Matrix into Right Panel
async function loadSlotsMatrix() {
  const matrixContainer = document.getElementById('slot-matrix');
  if (!matrixContainer) return;
  try {
    const res = await fetch(`${API_BASE}/models/slots`);
    if (!res.ok) return;
    const data = await res.json();
    const slots = data.slots || [];
    matrixContainer.innerHTML = '';

    slots.forEach((s) => {
      const row = document.createElement('div');
      row.className = 'slot-row';
      row.innerHTML = `
        <span class="slot-num">#${s.slot_number}</span>
        <span class="slot-id">${s.id}</span>
        <span class="slot-task">${s.task}</span>
      `;
      matrixContainer.appendChild(row);
    });
  } catch (_) {}
}
loadSlotsMatrix();

// ─────────────────────────────────────────────────────────────────────────────
// ANIMATION & RENDERING LOOP
// ─────────────────────────────────────────────────────────────────────────────
function animate() {
  requestAnimationFrame(animate);
  const t = clock.getElapsedTime();

  // Slow orbital rotation of stars
  starField.rotation.y = t * 0.015;
  starField.rotation.x = t * 0.008;

  // Pulse volumetric beam
  beamMat.uniforms.uTime.value = t;

  // Floating bob animation for hologram head
  holoGroup.position.y = Math.sin(t * 1.6) * 0.04;

  // Process audio frequency data
  analyser.getByteFrequencyData(dataArray);
  let sum = 0;
  for (let i = 0; i < dataArray.length; i++) {
    sum += (dataArray[i] / 255.0) ** 2;
  }
  const rms = Math.sqrt(sum / dataArray.length);
  audioVolume = Math.min(1.0, rms * 4.2);

  // Dynamic shader and morph responsiveness
  if (guardianState === 'speaking') {
    const hue = (t * 0.4) % 1.0;
    hologramMat.color.setHSL(hue, 1.0, 0.6);
    beamMat.uniforms.uColor.value.setHSL(hue, 1.0, 0.45);
    bloomPass.strength = 0.75 + audioVolume * 0.9;

    // Real-time lip sync blendshape animation
    if (headMesh && headMesh.morphTargetDictionary && headMesh.morphTargetDictionary['mouthOpen']) {
      const idx = headMesh.morphTargetDictionary['mouthOpen'];
      headMesh.morphTargetInfluences[idx] = audioVolume * 0.95;
    }
  } else {
    let hue = 0.52; // Default cyan
    if (guardianState === 'listening') hue = 0.95; // Red/Pink
    else if (guardianState === 'thinking') hue = 0.75; // Purple
    else if (guardianState === 'researching') hue = 0.12; // Gold

    hologramMat.color.setHSL(hue, 1.0, 0.52);
    beamMat.uniforms.uColor.value.setHSL(hue, 1.0, 0.45);
    bloomPass.strength = 0.6 + Math.sin(t * 2.0) * 0.12;

    if (headMesh) {
      holoGroup.rotation.y = Math.sin(t * 0.6) * 0.12;
      holoGroup.rotation.x = Math.sin(t * 0.8) * 0.04;

      // Close mouth smoothly
      if (headMesh.morphTargetDictionary && headMesh.morphTargetDictionary['mouthOpen']) {
        const idx = headMesh.morphTargetDictionary['mouthOpen'];
        headMesh.morphTargetInfluences[idx] *= 0.82;
      }
    }
  }

  // Draw audio oscilloscope
  drawWaveform();

  // Measure FPS
  frameCount++;
  if (t - lastFpsTime >= 1.0) {
    if (telemetryFps) telemetryFps.innerText = `${frameCount}`;
    frameCount = 0;
    lastFpsTime = t;
  }

  composer.render();
}

animate();

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
  composer.setSize(window.innerWidth, window.innerHeight);
});
