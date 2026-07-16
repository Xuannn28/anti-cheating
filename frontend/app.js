
const BACKEND_URL = "http://127.0.0.1:8000";
let activeSessionId = null;
let webcamInterval = null;
let pollInterval = null;
let mediaRecorder = null; // Our persistent MediaRecorder instance
let localStream = null;   // To keep track of our media stream globally

function toggleChat() {
    document.getElementById('chat-panel').classList.toggle('hidden');
}

// 1. Verify Candidate Name matching based on Access ID input
async function verifyCandidate() {
    const accessId = document.getElementById('access-id-input').value.trim();
    if (!accessId) return alert("Please specify an Access ID!");
    
    try {
    const response = await fetch(`${BACKEND_URL}/api/session/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ candidate_name: "John Doe" }) 
    });
    const data = await response.json();
    
    if (data.session_id) {
        activeSessionId = data.session_id;
        document.getElementById('candidate-profile').classList.remove('hidden');
        document.getElementById('active-session-label').innerText = `ID: ${activeSessionId}`;
    }
    } catch (err) {
    alert("Failed to reach FastAPI backend server. Ensure app.py is running!");
    }
}

// 2. Transition into the session workspace and turn on feeds (but do NOT track yet)
function enterWorkspace() {
    document.getElementById('access-gate').classList.add('hidden');
    document.getElementById('workspace').classList.remove('hidden');
    initializeHardwareFeeds();
    if (activeSessionId) {
        loadExamTopics(activeSessionId);
    } else {
        console.warn("No activeSessionId found when entering workspace, using fallbacks instead.");
        useFallbackTopics();
    }
}

// 3. Request Local Hardware permissions & turn them ON visually
async function initializeHardwareFeeds() {
    try {
    localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
    document.getElementById('webcam').srcObject = localStream;
    console.log("Hardware feeds are visually ON. Tracking is idle.");
    } catch (err) {
    console.error("Critical: Camera/Mic permissions missing or blocked: ", err);
    }
}

// 4. Start Recording: Trigger all active proctoring APIs and background syncing
function startRecording() {
    if (!localStream) {
    return alert("Cannot start tracking without active camera/mic feeds.");
    }
    
    console.log("Starting proctoring session API tracking...");
    
    // Start local Computer Vision eye-tracker processing loop (every 1000ms)
    startVisionProctorLoop(localStream);
    
    // Start Local Audio chunk recording loop (slices data every 15 seconds)
    startAudioProctorLoop(localStream);

    // Start server-side metric monitoring sync (every 3 seconds)
    pollInterval = setInterval(syncServerMetrics, 3000);
    
    // Toggle button states in UI
    document.getElementById('btn-start-record').disabled = true;
    document.getElementById('btn-end-record').disabled = false;
}

// 5. End Recording: Turn off active tracking APIs but keep the hardware feeds running visually
function endRecording() {
    console.log("Stopping proctoring session API tracking...");
    
    // Clear background eye-tracking snapshot intervals
    if (webcamInterval) {
    clearInterval(webcamInterval);
    webcamInterval = null;
    }
    
    // Clear the metrics syncing poll interval
    if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
    }

    // Stop the MediaRecorder from sending any more files
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
    try {
        mediaRecorder.stop();
        mediaRecorder = null;
    } catch (e) {
        console.debug("Error stopping MediaRecorder:", e);
    }
    }

    console.log("Tracking APIs stopped. Visual stream remains active.");
    
    // Toggle button states in UI
    document.getElementById('btn-end-record').disabled = true;
    document.getElementById('btn-submit-exam').disabled = false;
}

// Wraps the recording launch with UI state updates
function startRecordingAndUI() {
    // 1. Run the background loops
    startRecording();
    
    // 2. Adjust live badge to showing RED active tracking layout
    const badge = document.getElementById('tracking-status-badge');
    badge.innerText = "● LIVE TRACKING ACTIVE";
    badge.className = "bg-red-950/40 text-red-400 border border-red-900 px-4 py-1.5 rounded text-sm font-mono font-bold animate-pulse";
}

// Wraps the recording shutdown with UI state updates
function endRecordingAndUI() {
    // 1. Shut down the API processes
    endRecording();
    
    // 2. Adjust live badge to show idle feedback is still running
    const badge = document.getElementById('tracking-status-badge');
    badge.innerText = "● TRACKING COMPLETED";
    badge.className = "bg-slate-900 text-slate-400 border border-slate-700 px-4 py-1.5 rounded text-sm font-mono font-bold";
}

// 6. Capture & POST camera snapshot blocks dynamically to eye-tracker
function startVisionProctorLoop(stream) {
    const videoTrack = stream.getVideoTracks()[0];
    const imageCapture = new ImageCapture(videoTrack);
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');

    webcamInterval = setInterval(async () => {
    try {
        const bitmap = await imageCapture.grabFrame();
        canvas.width = bitmap.width;
        canvas.height = bitmap.height;
        ctx.drawImage(bitmap, 0, 0);

        canvas.toBlob(async (blob) => {
        if (!blob) return;
        const formData = new FormData();
        formData.append("file", blob, "frame.jpg");

        await fetch(`${BACKEND_URL}/api/proctor/eye-tracker?session_id=${activeSessionId}`, {
            method: "POST",
            body: formData
        });
        }, "image/jpeg", 0.7);

    } catch (e) {
        console.debug("Frame collection skipped: ", e);
    }
    }, 1000);
}

// 7. Gather Audio blobs using continuous timeslice streams
// 7. Gather Audio blobs using continuous timeslice streams
function startAudioProctorLoop(stream) {
  try {
    const audioTracks = stream.getAudioTracks();
    
    if (audioTracks.length === 0) {
      console.warn("No microphone track found in the stream.");
      return;
    }

    const audioOnlyStream = new MediaStream(audioTracks);
    const options = { mimeType: 'audio/webm;codecs=opus' };
    
    if (!MediaRecorder.isTypeSupported(options.mimeType)) {
      options.mimeType = 'audio/webm';
    }

    mediaRecorder = new MediaRecorder(audioOnlyStream, options);

    mediaRecorder.ondataavailable = async (e) => {
      // Prevent any potential default browser event bubble propagation
      if (e.preventDefault) e.preventDefault(); 

      if (e.data && e.data.size > 0) {
        console.log(`[Audio Loop] Chunk recorded: ${(e.data.size / 1024).toFixed(1)} KB. Sending...`);
        const blob = new Blob([e.data], { type: options.mimeType });
        const formData = new FormData();
        formData.append("file", blob, "chunk.webm");

        try {
          const response = await fetch(`${BACKEND_URL}/api/proctor/audio-tracker?session_id=${activeSessionId}`, {
            method: "POST",
            body: formData
          });
          
          if (!response.ok) {
            throw new Error(`HTTP status error: ${response.status}`);
          }
          
          const data = await response.json();
          console.log("[Audio Loop] Server response successfully received:", data);
          
        } catch (err) {
          console.error("[Audio Loop] Failed inside fetch pipeline:", err);
        }
      }
    };

    mediaRecorder.onerror = (err) => {
      console.error("MediaRecorder encountered a runtime error:", err);
    };

    mediaRecorder.start(15000); 
    console.log("MediaRecorder tracking loop initialized successfully!");

  } catch (err) {
    console.error("Failed to start MediaRecorder: ", err);
  }
}

// 8. Poll backend server to synchronize metrics on the user dashboard
async function syncServerMetrics() {
    try {
    const res = await fetch(`${BACKEND_URL}/api/session/${activeSessionId}/status`);
    const data = await res.json();
    
    if (data.metrics) {
        document.getElementById('gaze-flag-count').innerText = data.metrics.gaze_looking_away_events;
        document.getElementById('reading-flag-count').innerText = data.metrics.gaze_reading_events;
        document.getElementById('ai-flag-count').innerText = data.metrics.ai_generated_speech_events;
    }
    } catch (err) {
    console.warn("Unable to fetch backend sync stats.");
    }
}

// 9. Chatbot integration (Sends text to /api/session/chat)
async function sendChatMessage() {
    const input = document.getElementById('chat-input');
    const text = input.value.trim();
    if (!text) return;

    const chatMessages = document.getElementById('chat-messages');

    const userBubble = document.createElement('div');
    userBubble.className = "bg-sky-900/50 p-3 rounded-lg max-w-[80%] ml-auto border border-sky-800 text-slate-200 text-right";
    userBubble.innerText = text;
    chatMessages.appendChild(userBubble);
    input.value = "";
    chatMessages.scrollTop = chatMessages.scrollHeight;

    try {
    const response = await fetch(`${BACKEND_URL}/api/session/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_message: text })
    });
    const data = await response.json();

    const botBubble = document.createElement('div');
    botBubble.className = "bg-slate-900 p-3 rounded-lg max-w-[80%] border border-slate-800 text-slate-300";
    botBubble.innerText = data.reply || "I cannot retrieve any database matching instructions.";
    chatMessages.appendChild(botBubble);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    } catch (err) {
    console.error("Failed to fetch chat response.");
    }
}

// 10. Submit Exam and invoke /evaluate (Keeps visual stream up)
async function requestEvaluation() {
    try {
    const res = await fetch(`${BACKEND_URL}/api/session/${activeSessionId}/evaluate`, { method: "POST" });
    const data = await res.json();

    if (data.status === "success") {
        document.getElementById('eval-report').innerText = data.evaluation;
        document.getElementById('eval-report-container').classList.remove('hidden');
    } else {
        alert("Evaluation Error: " + data.message);
    }
    } catch (e) {
    alert("Server failed to evaluate the transcripts.");
    }
}

// Function to dynamically load and display the actual questions/topics
async function loadExamTopics(sessionId) {
  const container = document.getElementById("exam-questions-container");
  if (!container) return;

  try {
    // Replace with your actual backend endpoint that retrieves exam rules/questions
    const response = await fetch(`${BACKEND_URL}/api/session/${sessionId}/topics`);
    
    if (response.ok) {
      const data = await response.json(); // Expected format: { topics: [{ title: "...", description: "..." }] }
      
      container.innerHTML = ""; // Clear loader
      
      if (data.topics && data.topics.length > 0) {
        const topic = data.topics[0]; // Take the single assigned question
        const topicCard = `
          <div class="bg-slate-900 p-5 rounded border border-slate-800 space-y-2">
            <span class="text-sm font-bold text-sky-400 uppercase tracking-wider">${topic.title}</span>
            <p class="text-sm text-slate-300 pt-1">${topic.description}</p>
          </div>
        `;
        container.innerHTML = topicCard;
      } else {
        useFallbackTopics();
      }
    } else {
      // Fallback if endpoint doesn't exist yet
      useFallbackTopics();
    }
  } catch (err) {
    console.error("Failed to load custom exam topics:", err);
    useFallbackTopics();
  }
}

function useFallbackTopics() {
  const container = document.getElementById("exam-questions-container");
  container.innerHTML = `
    <div class="bg-slate-900 p-5 rounded border border-slate-800 space-y-2">
      <span class="text-sm font-bold text-sky-400 uppercase tracking-wider">Engineering Architecture</span>
      <p class="text-sm text-slate-300 pt-1">Explain Python's Global Interpreter Lock (GIL) and Generational Garbage Collection mechanisms. How do they affect performance?</p>
    </div>
  `;
}

// 11. Easter Egg: Trigger Antigravity module!
async function triggerAntigravity() {
    try {
    const res = await fetch(`${BACKEND_URL}/api/antigravity`);
    const data = await res.json();
    console.log("Antigravity response:", data);
    } catch (e) {
    console.error("Antigravity deployment failed.");
    }
}

document.addEventListener("DOMContentLoaded", () => {
  const chatInput = document.getElementById('chat-input');
  if (chatInput) {
    chatInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        sendChatMessage();
      }
    });
  }
});