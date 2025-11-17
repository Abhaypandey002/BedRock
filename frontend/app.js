const promptInput = document.getElementById('prompt');
const charCount = document.getElementById('char-count');
const generateBtn = document.getElementById('generate-btn');
const statusText = document.getElementById('status-text');
const videoEl = document.getElementById('result-video');
const videoSection = document.getElementById('video-section');
const downloadLink = document.getElementById('download-link');

const MAX_CHAR = parseInt(promptInput.getAttribute('maxlength'), 10);
let pollInterval = null;

promptInput.addEventListener('input', () => {
  const length = promptInput.value.length;
  charCount.textContent = `${length} / ${MAX_CHAR}`;
});

function setLoadingState(isLoading) {
  generateBtn.disabled = isLoading;
  generateBtn.textContent = isLoading ? 'Generating…' : 'Generate Video';
}

async function startVideoJob() {
  const prompt = promptInput.value.trim();
  if (!prompt) {
    statusText.textContent = 'Please enter a prompt before generating a video.';
    return;
  }

  setLoadingState(true);
  videoSection.classList.add('hidden');
  statusText.textContent = 'Starting video generation job…';

  try {
    const response = await fetch('/api/generate-video', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt }),
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(error.detail || 'Failed to start video job');
    }

    const data = await response.json();
    statusText.textContent = 'Video generation started. This may take a couple of minutes…';
    pollJobStatus(data.job_id);
  } catch (error) {
    statusText.textContent = error.message || 'Unable to start video generation job.';
    setLoadingState(false);
  }
}

async function fetchJobStatus(jobId) {
  const response = await fetch(`/api/video-status/${jobId}`);
  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(err.detail || 'Failed to fetch job status');
  }
  return response.json();
}

function pollJobStatus(jobId) {
  if (pollInterval) {
    clearInterval(pollInterval);
  }

  const checkStatus = async () => {
    try {
      const data = await fetchJobStatus(jobId);
      statusText.textContent = data.detail || `Current status: ${data.status}`;

      if (data.status === 'completed' && data.video_url) {
        clearInterval(pollInterval);
        pollInterval = null;
        setLoadingState(false);
        videoEl.src = data.video_url;
        videoSection.classList.remove('hidden');
        downloadLink.href = data.video_url;
        statusText.textContent = 'Video ready!';
      } else if (data.status === 'failed') {
        clearInterval(pollInterval);
        pollInterval = null;
        setLoadingState(false);
        statusText.textContent = data.detail || 'Video generation failed.';
      }
    } catch (error) {
      clearInterval(pollInterval);
      pollInterval = null;
      setLoadingState(false);
      statusText.textContent = error.message || 'Unable to get job status.';
    }
  };

  pollInterval = setInterval(checkStatus, 5000);
  checkStatus();
}

generateBtn.addEventListener('click', () => {
  if (promptInput.value.length > MAX_CHAR) {
    statusText.textContent = 'Prompt exceeds maximum length.';
    return;
  }
  startVideoJob();
});
