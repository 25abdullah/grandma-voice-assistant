//constants 
const recordButton = document.getElementById('record-start-btn')
const stopButton = document.getElementById('record-stop-btn')
const listContainer = document.getElementById('message-list-id')
const statusIndicator = document.getElementById('status-indicator');
const loadingIndicator = document.getElementById('loader')

//initializing the audio
 playedAudioFiles = []
 let mediaRecorder = null
 let audioChunks = []

//audio
const recording_start = new Audio("sounds/recording-in-progress.mp3");
const recording_ding_stop = new Audio("sounds/ding.mp3");

const ws = new WebSocket("ws://localhost:8000/ws");



//load messages when we open 
async function loadMessages() {

    const response = await fetch('http://localhost:8000/getmessagelog/')
    const data = await response.json()
    listContainer.innerHTML = '' 


    for (let i = 0; i < data.length; i++) {
      const row = data[i];
    const newItem = document.createElement('li'); 
    newItem.innerHTML = `${row.username}<br> <br> ${row.message}`
    if (row.audio_file !== null && !playedAudioFiles.includes(row.audio_file)) { //if we have not played audio file, play it 
        const audio = new Audio(`http://localhost:8000/audio/${row.audio_file}`);
        audio.play();
        playedAudioFiles.push(row.audio_file)
    }
    if (row.username === 'AI') {
        newItem.style.backgroundColor = '#e8f5e9';  
        newItem.style.borderLeft = '4px solid #4caf50';
        newItem.style.marginLeft = 'auto';  // Push to right
        newItem.style.marginRight = '25px';  // Space from edge
    } else {
        newItem.style.backgroundColor = '#fff3e0'; 
        newItem.style.borderLeft = '4px solid #ff9800';  
        newItem.style.marginRight = 'auto';  // Push to left
        newItem.style.marginLeft = '25px';  // Space from edge
    }

    listContainer.appendChild(newItem);        
    }
}

ws.onmessage = function(event) {
    if (event.data === "done") {
        loadMessages();
    statusIndicator.style.display = "none";
     loadingIndicator.style.display = "none";
     recordButton.disabled = false;
    }
};

//when record button is hit 
recordButton.addEventListener('click', async () =>  {
    recordButton.disabled = true;
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        recordButton.textContent = "Recording";
        recording_start.play();

        //collect audio chunks 
        mediaRecorder.ondataavailable = (event) => {
            audioChunks.push(event.data);
        };
        mediaRecorder.onstop = async () => {
             statusIndicator.textContent = "AI is thinking...";
             statusIndicator.style.display = "block";
             loadingIndicator.style.display = "block";
             const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
            const arrayBuffer = await audioBlob.arrayBuffer();
            ws.send(arrayBuffer);
}

        mediaRecorder.start()   
})

//when the stop button is clicked 
stopButton.addEventListener('click', async () => {
mediaRecorder.stop()
recording_ding_stop.play();
recordButton.textContent = "Start Recording";
})