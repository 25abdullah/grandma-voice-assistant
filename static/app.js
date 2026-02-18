let ws = null;
let audioContext = null;
let mediaStream = null;
let sourceNode = null;
let processorNode = null;
let isRecording = false;

// Audio visualization variables
let micAnalyser = null;
let isListening = false;
let audioLevel = 0;
let isSpeaking = false;
let isAISpeaking = false;
let aiAudioLevel = 0;

const connectBtn = document.getElementById('connectBtn');
const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const statusText = document.getElementById('connectionStatus');
const errorMessage = document.getElementById('errorMessage');
const sessionIdDisplay = document.getElementById('sessionIdDisplay');
const userTranscription = document.getElementById('transcriptionText');
const aiResponse = document.getElementById('aiResponseText');


let isFirstAIToken = true;  
// VAD status element (we'll add this to the status area)
let vadStatusElement = null;

function showError(message) {
    if (errorMessage) {
        errorMessage.textContent = message;
        errorMessage.classList.add('show');
        setTimeout(() => {
            errorMessage.classList.remove('show');
        }, 5000);
    }
}

function updateSessionId(sessionId) {
    if (sessionIdDisplay) {
        if (sessionId && sessionId !== 'None' && sessionId !== 'null') {
            // Show shortened version for display
            const shortId = sessionId.length > 12 ? sessionId.substring(0, 12) + '...' : sessionId;
            sessionIdDisplay.textContent = shortId;
            sessionIdDisplay.title = sessionId; // Full ID on hover
        } else {
            sessionIdDisplay.textContent = 'None';
            sessionIdDisplay.title = '';
        }
    }
}



function updateStatus(connected, recording = false) {
    if (statusText && !isRecording && !isAISpeaking && !isSpeaking) {
        if (recording) {
            statusText.textContent = 'Recording...';
        } else if (connected) {
            statusText.textContent = 'Connected';
        } else {
            statusText.textContent = 'Disconnected';
        }
    } else if (statusText && recording) {
        statusText.textContent = 'Ready';
    }
}

async function connect() {
        const wsUrl = 'ws://127.0.0.1:8000/ws'; 
        console.log('Connecting to WebSocket:', wsUrl);
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            console.log('WebSocket connected');
            updateStatus(true);
            connectBtn.disabled = true;
            startBtn.disabled = false;
        };

        ws.onmessage = async (event) => {
            if (event.data instanceof Blob) {
                 audioQueue.push(event.data);
                 playNextAudio()
                 return ;
            }
            try {
                 const data = JSON.parse(event.data);
                 if (data.type === 'transcription') {
                    userTranscription.textContent = data.text;
                 }
                 else if (data.type === 'token') {
                     if (isFirstAIToken) {
                aiResponse.textContent = ''
                isFirstAIToken = false;
            }
                aiResponse.textContent += data.text;
                //need to also stream the voice 
                 }
                 else if (data.type === 'done') {
                    startBtn.disabled = false;
                    stopBtn.disabled = true; 
                    isFirstAIToken = true;
                 }


            } catch {

            }

        }}


function playNextAudio() {
    if (isPlayingAudio || audioQueue.length === 0) {
        return;
    }
    isPlayingAudio = true;
    isAISpeaking = true;
    muteMicrophone();
    
    const firstBlob = audioQueue.shift();
    const audioUrl = URL.createObjectURL(firstBlob);
    const audio = new Audio(audioUrl);
    audio.play();
    
    audio.onended = () => {
        URL.revokeObjectURL(audioUrl);
        isPlayingAudio = false;
        if (audioQueue.length === 0) {
            isAISpeaking = false;
            unmuteMicrophone();
        }
        playNextAudio();
    }
}







function updateStatusText() {
    // Update status based on current state - AI speaking takes priority
    if (isAISpeaking) {
        if (statusText) statusText.textContent = 'AI is speaking...';
    } else if (isSpeaking) {
        if (statusText) statusText.textContent = 'You are speaking...';
    } else {
        // User is not speaking and AI is not speaking
        // Status will be set by VAD status or processing state
    }
}

function updateVADStatus(data) {
    // Don't update status if paused or AI is speaking
    if (isAISpeaking) {
        return;
    }
    
    // Update status based on VAD state
    if (data.status === 'speech_started') {
        isSpeaking = true;
        if (statusText) statusText.textContent = 'You are speaking...';
    } else if (data.status === 'speech_active') {
        isSpeaking = true;
        if (statusText) statusText.textContent = 'You are speaking...';
    } else if (data.status === 'silence') {
        isSpeaking = false;
        // Only update to listening if not processing
        if (statusText && !statusText.textContent.includes('Processing')) {
            statusText.textContent = 'Listening...';
        }
    } else if (data.status === 'segment_complete') {
        isSpeaking = false;
        if (statusText) statusText.textContent = 'Processing...';
    } else if (data.status === 'idle') {
        isSpeaking = false;
        if (statusText) statusText.textContent = 'Ready';
    }
}

function showTurnOver(data) {
    // Turn indicator removed - do nothing
}

function hideTurnOver() {
    // Turn indicator removed - do nothing
}

function updateTranscription(data) {
    // Transcription UI removed - silently handle
    // This function is kept for compatibility but does nothing
}

function clearTranscription() {
    // Transcription UI removed - silently handle
}

let claudeResponseBuffer = '';
let audioQueue = [];
let isPlayingAudio = false;
let playbackAudioContext = null;
let audioGainNode = null;

// Initialize Web Audio API for audio playback
async function initAudioPlayback() {
    if (!playbackAudioContext) {
        playbackAudioContext = new (window.AudioContext || window.webkitAudioContext)();
        audioGainNode = playbackAudioContext.createGain();
        audioGainNode.connect(playbackAudioContext.destination);
    }
    
    // Resume audio context if it's suspended (required by some browsers)
    if (playbackAudioContext.state === 'suspended') {
        await playbackAudioContext.resume();
    }
}

async function playAudioChunk(audioData, sampleRate) {
    await initAudioPlayback();
    
    try {
        // Decode base64 to ArrayBuffer
        const binaryString = atob(audioData);
        const len = binaryString.length;
        const bytes = new Uint8Array(len);
        for (let i = 0; i < len; i++) {
            bytes[i] = binaryString.charCodeAt(i);
        }
        
        // Convert to Float32Array
        const float32Array = new Float32Array(bytes.buffer);
        
        // Create audio buffer
        const audioBuffer = playbackAudioContext.createBuffer(1, float32Array.length, sampleRate);
        audioBuffer.getChannelData(0).set(float32Array);
        
        // Create source and play
        const source = playbackAudioContext.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(audioGainNode);
        
        return new Promise((resolve) => {
            source.onended = resolve;
            source.start(0);
        });
    } catch (error) {
        console.error('Error playing audio:', error);
    }
}

function muteMicrophone() {
    if (mediaStream) {
        mediaStream.getAudioTracks().forEach(track => {
            track.enabled = false;
        });
        console.log('Microphone muted');
    }
}

function unmuteMicrophone() {
    if (mediaStream) {
        mediaStream.getAudioTracks().forEach(track => {
            track.enabled = true;
        });
        console.log('Microphone unmuted');
    }
}

async function processAudioQueue() {
    if (isPlayingAudio || audioQueue.length === 0) {
        return;
    }
    
    isPlayingAudio = true;
    isAISpeaking = true;
    
    // Update status immediately when AI starts speaking
    updateStatusText();
    
    if (audioStatus) audioStatus.classList.add('show');
    if (claudeText) claudeText.classList.add('playing');
    
    // Mute microphone when audio playback starts
    muteMicrophone();
    
    while (audioQueue.length > 0) {
        const audioChunk = audioQueue.shift();
        if (audioStatus) {
            audioStatus.textContent = `Playing: "${audioChunk.text.substring(0, 50)}${audioChunk.text.length > 50 ? '...' : ''}"`;
        }
        await playAudioChunk(audioChunk.audio, audioChunk.sample_rate);
    }
    
    isPlayingAudio = false;
    isAISpeaking = false;
    
    // Update status when AI finishes speaking
    updateStatusText();
    
    if (audioStatus) audioStatus.classList.remove('show');
    if (claudeText) claudeText.classList.remove('playing');
    
    // Unmute microphone when audio playback finishes
    unmuteMicrophone();
}









function updateClaudeResponse(data) {
    // Claude response UI removed - silently handle
    // This function is kept for compatibility but does nothing
    if (data.done) {
        claudeResponseBuffer = '';
    } else if (data.text) {
        claudeResponseBuffer += data.text;
    }
}

function handleAudioChunk(data) {
    // Add audio chunk to queue
    audioQueue.push({
        audio: data.audio,
        sample_rate: data.sample_rate,
        text: data.text
    });
    
    console.log('Received audio chunk for:', data.text);
    
    // Automatically start processing queue if not already playing
    if (!isPlayingAudio) {
        processAudioQueue();
    }
}

function clearClaudeResponse() {
    claudeResponseBuffer = '';
    if (claudeText) {
        claudeText.textContent = 'Waiting for Claude response...';
        claudeText.classList.add('empty');
        claudeText.classList.remove('streaming', 'playing');
    }
    if (audioStatus) audioStatus.classList.remove('show');
    audioQueue = [];
    isPlayingAudio = false;
    // Ensure microphone is unmuted when clearing
    unmuteMicrophone();
}

async function startRecording() {
      const humanInput = document.getElementById('transcriptionText');
      humanInput.textContent = 'Waiting...'
      aiResponse.textContent = 'Waiting...'
       isFirstAIToken = true;
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ 
            audio: {
                sampleRate: 16000,
                channelCount: 1,
                echoCancellation: true,
                noiseSuppression: true
            } 
        });
        
        // Create MediaRecorder
        mediaRecorder = new MediaRecorder(stream);
        mediaStream = stream;
        audioChunks = [];
        
        // Setup audio context and analyzer for visualization
        audioContext = new AudioContext();
        sourceNode = audioContext.createMediaStreamSource(mediaStream);
        micAnalyser = audioContext.createAnalyser();
        micAnalyser.fftSize = 512;
        sourceNode.connect(micAnalyser);
        isListening = true;
        isSpeaking = true;
        
        // Collect audio chunks
        mediaRecorder.ondataavailable = (event) => {
            audioChunks.push(event.data);
        };
        
        mediaRecorder.onstop = async () => {
            statusText.textContent = 'Processing...';
            isSpeaking = false;
            const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
            const arrayBuffer = await audioBlob.arrayBuffer();
            ws.send(arrayBuffer);
        };
        
        mediaRecorder.start();
        isRecording = true;
        statusText.textContent = 'Recording...';
        startBtn.disabled = true;
        stopBtn.disabled = false;
        
    } catch (error) {
        console.error('Recording error:', error);
    }
}

function stopRecording() {
    isRecording = false;
    isListening = false;
    isSpeaking = false;
    isAISpeaking = false;
    audioLevel = 0;
    
    // Unmute microphone before stopping (in case it was muted during playback)
    unmuteMicrophone();
    
    if (processorNode) {
        processorNode.disconnect();
        processorNode = null;
    }
    if (micAnalyser) {
        micAnalyser = null;
    }
    if (sourceNode) {
        sourceNode.disconnect();
        sourceNode = null;
    }
    if (mediaStream) {
        mediaStream.getTracks().forEach(track => track.stop());
        mediaStream = null;
    }
    if (audioContext) {
        audioContext.close();
        audioContext = null;
    }
    
    // Update status to connection state
    updateStatus(ws && ws.readyState === WebSocket.OPEN, false);
    updateSessionId(null); // Clear session ID when stopping
    
    startBtn.disabled = false;
    stopBtn.disabled = true;
}



function resumeRecording() {
    if (!isRecording) {
        return;
    }

    isListening = true;
    
    // Reconnect processor to resume audio processing
    if (processorNode && sourceNode) {
        sourceNode.connect(processorNode);
        processorNode.connect(audioContext.destination);
    }
    
    // Update UI
    if (statusText) statusText.textContent = 'Ready';
    startBtn.disabled = true;
    
    console.log('Recording resumed');
}



// p5.js setup and draw functions
function setup() {
    createCanvas(windowWidth, windowHeight);
    angleMode(RADIANS);
}

function windowResized() {
    resizeCanvas(windowWidth, windowHeight);
}

function draw() {
    // Dark gradient background
    for(let i = 0; i <= height; i++) {
        let inter = map(i, 0, height, 0, 1);
        let c = lerpColor(color(20, 20, 30), color(10, 10, 20), inter);
        stroke(c);
        line(0, i, width, i);
    }

    // Get audio level for user microphone
    if (isListening && micAnalyser) {
        let bufferLength = micAnalyser.frequencyBinCount;
        let dataArray = new Uint8Array(bufferLength);
        micAnalyser.getByteFrequencyData(dataArray);
        let newLevel = dataArray.reduce((sum, value) => sum + value, 0) / bufferLength;
        newLevel = Math.min(newLevel, 255);
        audioLevel = lerp(audioLevel, newLevel, 0.2);
    } else {
        audioLevel = lerp(audioLevel, 0, 0.1);
    }

    // Simulate AI audio level when AI is speaking
    if (isAISpeaking) {
        aiAudioLevel = 80 + sin(frameCount * 0.3) * 30 + cos(frameCount * 0.2) * 20;
    } else {
        aiAudioLevel = lerp(aiAudioLevel, 0, 0.1);
    }

    // Dual speaker visualization
    drawDualSpeakers();
}

function drawDualSpeakers() {
    // Calculate responsive positioning and sizing
    let minMargin = Math.max(80, width * 0.1);
    let maxCircleSize = Math.min(120, width * 0.15);
    let minCircleSize = Math.max(40, width * 0.08);
    
    // Calculate positions with equal margins
    let leftSpeakerX = minMargin + maxCircleSize;
    let rightSpeakerX = width - minMargin - maxCircleSize;
    
    // Ensure minimum distance between speakers
    let minDistance = maxCircleSize * 3;
    if (rightSpeakerX - leftSpeakerX < minDistance) {
        let centerX = width / 2;
        leftSpeakerX = centerX - minDistance / 2;
        rightSpeakerX = centerX + minDistance / 2;
    }
    
    // User speaker (left side)
    push();
    translate(leftSpeakerX, height / 2);
    
    let userSize = map(audioLevel, 0, 255, minCircleSize, maxCircleSize);
    let userPulse = isSpeaking ? 1.5 : 1.0;
    userSize *= userPulse;
    
    // User speaker colors (blue theme)
    let userColor = color(59, 130, 246);
    let userActiveColor = color(34, 197, 94);
    let currentUserColor = isSpeaking ? userActiveColor : userColor;
    
    // User glow effect
    noStroke();
    for(let i = 0; i < 6; i++) {
        fill(red(currentUserColor), green(currentUserColor), blue(currentUserColor), 25 - i * 4);
        ellipse(0, 0, userSize + i * 12, userSize + i * 12);
    }
    
    // User main circle
    fill(red(currentUserColor), green(currentUserColor), blue(currentUserColor), 120 + audioLevel * 0.2);
    ellipse(0, 0, userSize, userSize);
    
    // User inner pulse
    let userInnerSize = userSize * 0.5 + sin(frameCount * 0.15) * 8;
    fill(255, 255, 255, 60);
    ellipse(0, 0, userInnerSize, userInnerSize);
    
    // User label
    fill(255, 255, 255, 150);
    textAlign(CENTER, CENTER);
    textSize(12);
    text("You", 0, userSize/2 + 25);
    
    pop();

    // AI speaker (right side)
    push();
    translate(rightSpeakerX, height / 2);
    
    let aiSize = map(aiAudioLevel, 0, 255, minCircleSize, maxCircleSize * 0.9);
    let aiPulse = isAISpeaking ? 1.5 : 1.0;
    aiSize *= aiPulse;
    
    // AI speaker colors (orange/purple theme)
    let aiColor = color(147, 51, 234);
    let aiActiveColor = color(249, 115, 22);
    let currentAIColor = isAISpeaking ? aiActiveColor : aiColor;
    
    // AI glow effect
    noStroke();
    for(let i = 0; i < 6; i++) {
        fill(red(currentAIColor), green(currentAIColor), blue(currentAIColor), 25 - i * 4);
        ellipse(0, 0, aiSize + i * 12, aiSize + i * 12);
    }
    
    // AI main circle
    fill(red(currentAIColor), green(currentAIColor), blue(currentAIColor), 120 + aiAudioLevel * 0.2);
    ellipse(0, 0, aiSize, aiSize);
    
    // AI inner pulse with different pattern
    let aiInnerSize = aiSize * 0.5 + cos(frameCount * 0.12) * 10;
    fill(255, 255, 255, 60);
    ellipse(0, 0, aiInnerSize, aiInnerSize);
    
    // AI activity rings when speaking
    if (isAISpeaking) {
        strokeWeight(3);
        stroke(red(currentAIColor), green(currentAIColor), blue(currentAIColor), 120);
        noFill();
        for(let i = 0; i < 3; i++) {
            let ringSize = aiSize + 20 + i * 15 + sin(frameCount * 0.2 + i) * 5;
            ellipse(0, 0, ringSize, ringSize);
        }
    }
    
    // AI label
    fill(255, 255, 255, 150);
    textAlign(CENTER, CENTER);
    textSize(12);
    text("AI", 0, aiSize/2 + 25);
    
    pop();

    // Connection line between speakers when active
    if (isSpeaking || isAISpeaking) {
        push();
        let lineAlpha = (isSpeaking || isAISpeaking) ? 80 : 0;
        strokeWeight(2);
        stroke(255, 255, 255, lineAlpha);
        line(leftSpeakerX, height / 2, rightSpeakerX, height / 2);
        
        // Animated dots along the connection
        for(let i = 0; i < 5; i++) {
            let x = map(i, 0, 4, leftSpeakerX, rightSpeakerX);
            let offset = sin(frameCount * 0.1 + i * 0.5) * 3;
            fill(255, 255, 255, lineAlpha);
            noStroke();
            ellipse(x, height / 2 + offset, 4, 4);
        }
        pop();
    }
}

// Event listeners
connectBtn.addEventListener('click', connect);
startBtn.addEventListener('click', startRecording);
stopBtn.addEventListener('click', stopRecording);

