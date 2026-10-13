import * as THREE from 'three';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';

// ─────────────────────────────────────────────────────────────────────────────
// RENDERER & SCENE
// ─────────────────────────────────────────────────────────────────────────────
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
// Enable local clipping to hide hands
renderer.localClippingEnabled = true;
document.body.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x020005);
scene.fog = new THREE.FogExp2(0x020005, 0.04);

const camera = new THREE.PerspectiveCamera(50, window.innerWidth / window.innerHeight, 0.1, 100);
camera.position.set(0, 1.2, 4.0);
camera.lookAt(0, 1.2, 0);

const clock = new THREE.Clock();
let frameCount = 0;
let lastFpsTime = 0;
const fpsEl = document.getElementById('fps');
const loadingEl = document.getElementById('loading-msg');

// ─────────────────────────────────────────────────────────────────────────────
// POST-PROCESSING (GLOW / BLOOM)
// ─────────────────────────────────────────────────────────────────────────────
const renderScene = new RenderPass(scene, camera);
const bloomPass = new UnrealBloomPass(new THREE.Vector2(window.innerWidth, window.innerHeight), 1.5, 0.4, 0.1);
bloomPass.threshold = 0.2;
bloomPass.strength = 0.6;
bloomPass.radius = 0.5;

const composer = new EffectComposer(renderer);
composer.addPass(renderScene);
composer.addPass(bloomPass);

// ─────────────────────────────────────────────────────────────────────────────
// MATERIALS
// ─────────────────────────────────────────────────────────────────────────────
// Clipping plane: cut off everything below Y = 0.15 (local space of the model)
const clipPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), -0.2);

const hologramMat = new THREE.MeshBasicMaterial({
  color: 0x00ffff,
  wireframe: true,
  transparent: true,
  opacity: 0.6,
  blending: THREE.AdditiveBlending,
  depthWrite: false,
  clippingPlanes: [clipPlane]
});

const hologramInnerMat = new THREE.MeshBasicMaterial({
  color: 0x000000,
  transparent: true,
  opacity: 0.95,
  depthWrite: true,
  clippingPlanes: [clipPlane]
});

// ─────────────────────────────────────────────────────────────────────────────
// ENVIRONMENT: Galaxy Background
// ─────────────────────────────────────────────────────────────────────────────
const starCount = 4000;
const starGeo = new THREE.BufferGeometry();
const starPos = new Float32Array(starCount * 3);
const starColors = new Float32Array(starCount * 3);

for(let i=0; i < starCount; i++) {
  // Sphere distribution
  const r = 20 + Math.random() * 30;
  const theta = Math.random() * Math.PI * 2;
  const phi = Math.acos((Math.random() * 2) - 1);
  
  starPos[i*3] = r * Math.sin(phi) * Math.cos(theta);
  starPos[i*3+1] = r * Math.sin(phi) * Math.sin(theta);
  starPos[i*3+2] = r * Math.cos(phi);
  
  // RGB Galaxy colors
  const color = new THREE.Color();
  color.setHSL(Math.random(), 0.8, Math.random() * 0.5 + 0.5);
  starColors[i*3] = color.r;
  starColors[i*3+1] = color.g;
  starColors[i*3+2] = color.b;
}
starGeo.setAttribute('position', new THREE.BufferAttribute(starPos, 3));
starGeo.setAttribute('color', new THREE.BufferAttribute(starColors, 3));

const starMat = new THREE.PointsMaterial({
  size: 0.15,
  vertexColors: true,
  transparent: true,
  opacity: 0.8,
  blending: THREE.AdditiveBlending
});
const starField = new THREE.Points(starGeo, starMat);
scene.add(starField);

// ─────────────────────────────────────────────────────────────────────────────
// ENVIRONMENT: Projector Base
// ─────────────────────────────────────────────────────────────────────────────
// Bottom grid floor
const gridGeo = new THREE.PlaneGeometry(10, 10, 12, 12);
const gridMat = new THREE.MeshBasicMaterial({
  color: 0xaa00ff, wireframe: true, transparent: true, opacity: 0.2, blending: THREE.AdditiveBlending
});
const gridFloor = new THREE.Mesh(gridGeo, gridMat);
gridFloor.rotation.x = -Math.PI / 2;
gridFloor.position.y = -0.5;
scene.add(gridFloor);

// Glowing plate
const plateGeo = new THREE.PlaneGeometry(4.0, 4.0, 64, 64);
const plateMat = new THREE.MeshStandardMaterial({
  color: 0x222222, emissive: 0x0088ff, emissiveIntensity: 0.5,
  transparent: true, opacity: 0.9, roughness: 0.1, metalness: 0.9
});
plateMat.onBeforeCompile = (shader) => {
  shader.uniforms.uTime = { value: 0 };
  plateMat.userData.shader = shader;
  shader.vertexShader = `uniform float uTime;\n` + shader.vertexShader;
  shader.vertexShader = shader.vertexShader.replace(
    '#include <begin_vertex>',
    `#include <begin_vertex>\n float noise = sin(position.x * 8.0 + uTime) * cos(position.y * 8.0 + uTime) * 0.08;\n transformed.z += noise;`
  );
};
const plate = new THREE.Mesh(plateGeo, plateMat);
plate.rotation.x = -Math.PI / 2;
plate.position.y = 0.0;
scene.add(plate);

// Volumetric beam
const beamGeo = new THREE.CylinderGeometry(2.5, 1.5, 4, 32, 1, true);
const beamMat = new THREE.ShaderMaterial({
  uniforms: { uColor: { value: new THREE.Color(0x00aaff) }, uTime: { value: 0 }, uIntensity: { value: 1.0 } },
  vertexShader: `varying vec2 vUv; void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
  fragmentShader: `
    uniform vec3 uColor; uniform float uTime; uniform float uIntensity; varying vec2 vUv;
    void main() {
      float alpha = (1.0 - vUv.y) * 0.10 * uIntensity;
      float scanline = sin(vUv.y * 60.0 - uTime * 8.0) * 0.5 + 0.5;
      alpha *= 0.5 + scanline * 0.5;
      gl_FragColor = vec4(uColor, alpha);
    }
  `,
  transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide
});
const beam = new THREE.Mesh(beamGeo, beamMat);
beam.position.y = 2.0;
scene.add(beam);

// ─────────────────────────────────────────────────────────────────────────────
// GLTF LOADER (Holographic Head)
// ─────────────────────────────────────────────────────────────────────────────
const loader = new GLTFLoader();
let headMesh = null;
const holoGroup = new THREE.Group();
scene.add(holoGroup);

loader.load('/models/half-body.glb', (gltf) => {
  const model = gltf.scene;
  
  model.traverse((child) => {
    if (child.isMesh) {
      const name = child.name.toLowerCase();
      // Hide clothes, hair, teeth, eyes
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
  
  // SCALE UP ENORMOUSLY AND POSITION TO CENTER HEAD
  model.scale.setScalar(6.5);
  model.position.set(0, -3.2, 0); 
  holoGroup.add(model);
  
  if (loadingEl) loadingEl.style.display = 'none';
  window.__presenceLoaded = true;
});

// ─────────────────────────────────────────────────────────────────────────────
// STATE MACHINE, WEBSOCKET & RHYTHM
// ─────────────────────────────────────────────────────────────────────────────
let guardianState = 'idle';
let audioVolume = 0; // Driven by AnalyserNode

export function setGuardianState(state) {
  guardianState = state;
  const stateEl = document.getElementById('state');
  if (stateEl) stateEl.innerText = `State: ${state}`;
}

// Web Audio API Setup
const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
const analyser = audioCtx.createAnalyser();
analyser.fftSize = 256;
// Do NOT connect analyser to audioCtx.destination (keeps it muted in browser to avoid echo with Python backend)

const dataArray = new Uint8Array(analyser.frequencyBinCount);

// WebSocket Connection with Auto-Reconnect & Port Fallback
let ws = null;
const wsPorts = [8000, 8765];
let portIndex = 0;

function connectWebSocket() {
  const port = wsPorts[portIndex % wsPorts.length];
  try {
    ws = new WebSocket(`ws://localhost:${port}/ws/presence`);

    ws.onopen = () => {
      console.log(`Connected to Guardian Presence WebSocket on port ${port}`);
    };

    ws.onmessage = async (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.event === 'speaking') {
          setGuardianState('speaking');
          if (audioCtx.state === 'suspended') await audioCtx.resume();
          if (msg.audio_b64) {
            const binaryString = atob(msg.audio_b64);
            const len = binaryString.length;
            const bytes = new Uint8Array(len);
            for (let i = 0; i < len; i++) {
              bytes[i] = binaryString.charCodeAt(i);
            }
            audioCtx.decodeAudioData(bytes.buffer, (buffer) => {
              const source = audioCtx.createBufferSource();
              source.buffer = buffer;
              source.connect(analyser);
              source.start(0);
            });
          }
        } else if (msg.event === 'idle' || msg.event === 'transcribing' || msg.event === 'thinking') {
          setGuardianState(msg.event);
        }
      } catch (err) {
        console.error('WebSocket message error:', err);
      }
    };

    ws.onclose = () => {
      portIndex++;
      setTimeout(connectWebSocket, 2000);
    };

    ws.onerror = () => {
      try { ws.close(); } catch (_) {}
    };
  } catch (e) {
    portIndex++;
    setTimeout(connectWebSocket, 2000);
  }
}

connectWebSocket();

// ─────────────────────────────────────────────────────────────────────────────
// ANIMATION LOOP
// ─────────────────────────────────────────────────────────────────────────────
function animate() {
  requestAnimationFrame(animate);
  const t = clock.getElapsedTime();
  
  // Rotate starfield slowly
  starField.rotation.y = t * 0.02;
  starField.rotation.x = t * 0.01;

  if (plateMat.userData.shader) {
    plateMat.userData.shader.uniforms.uTime.value = t;
  }
  beamMat.uniforms.uTime.value = t;
  
  holoGroup.position.y = Math.sin(t * 1.5) * 0.05;
  
  // Read audio frequency data
  analyser.getByteFrequencyData(dataArray);
  
  // Calculate RMS (Root Mean Square) for volume
  let sum = 0;
  for (let i = 0; i < dataArray.length; i++) {
    sum += (dataArray[i] / 255.0) ** 2;
  }
  const rms = Math.sqrt(sum / dataArray.length);
  // Scale it up significantly to make it responsive (0.0 to 1.0)
  audioVolume = Math.min(1.0, rms * 3.5);
  
  if (guardianState === 'speaking') {
    // Cycle RGB colors rapidly when speaking
    const hue = (t * 0.5) % 1.0;
    hologramMat.color.setHSL(hue, 1.0, 0.6);
    beamMat.uniforms.uColor.value.setHSL(hue, 1.0, 0.4);
    
    // Pulse bloom intensely (reduced from previous values)
    bloomPass.strength = 0.8 + (audioVolume * 1.0);
    beamMat.uniforms.uIntensity.value = 1.0 + (audioVolume * 0.5);
    
    // Open mouth based on volume
    if (headMesh && headMesh.morphTargetDictionary && headMesh.morphTargetDictionary['mouthOpen']) {
      const idx = headMesh.morphTargetDictionary['mouthOpen'];
      headMesh.morphTargetInfluences[idx] = audioVolume * 0.9;
    }
  } else {
    // Other states
    audioVolume = 0;
    
    let hue = 0.5; // default cyan
    if (guardianState === 'transcribing') hue = 0.8; // purple/pink
    else if (guardianState === 'thinking') hue = 0.1; // orange
    else hue = 0.5 + Math.sin(t * 0.2) * 0.1; // Shifts between cyan and deep blue (idle)
    
    hologramMat.color.setHSL(hue, 1.0, 0.5);
    beamMat.uniforms.uColor.value.setHSL(hue, 1.0, 0.5);
    
    bloomPass.strength = 0.6 + Math.sin(t * 2.0) * 0.15;
    beamMat.uniforms.uIntensity.value = 1.0;
    
    if (headMesh && guardianState === 'idle') {
      holoGroup.rotation.y = Math.sin(t * 0.5) * 0.15;
      holoGroup.rotation.x = Math.sin(t * 0.7) * 0.05;
      
      // Close mouth
      if (headMesh.morphTargetDictionary && headMesh.morphTargetDictionary['mouthOpen']) {
        const idx = headMesh.morphTargetDictionary['mouthOpen'];
        headMesh.morphTargetInfluences[idx] *= 0.8; // lerp to 0
      }
    }
  }

  frameCount++;
  if (t - lastFpsTime >= 1.0) {
    if (fpsEl) fpsEl.innerText = `FPS: ${frameCount}`;
    frameCount = 0;
    lastFpsTime = t;
  }

  // Use composer for Bloom instead of renderer
  composer.render();
}
animate();

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
  composer.setSize(window.innerWidth, window.innerHeight);
});
