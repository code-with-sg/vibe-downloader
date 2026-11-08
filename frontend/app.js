// ==============================================================
// VibeDownloader — app.js
// SKY GRIT (SG)
//
// HOW THIS CONNECTS TO THE BACKEND (Beginner Explanation):
// ---------------------------------------------------------
// 1. User pastes a URL and clicks "Get Download Links"
// 2. We call our Python Flask backend at /api/info
// 3. The backend uses yt-dlp to find download links
// 4. It sends back JSON with title, thumbnail, and direct URLs
// 5. We display everything in the result card
// ==============================================================


// ==============================================================
// ⚠️ IMPORTANT: Set your backend URL here.
//
// LOCAL TESTING:  'http://localhost:5000'
// AFTER DEPLOYING TO RENDER: 'https://vibe-downloader.onrender.com/'
//
// Steps:
// 1. While testing on your computer: use localhost:5000
// 2. After you deploy to Render: replace with your Render URL
// 3. Make sure there is NO trailing slash at the end
// ==============================================================
const BACKEND_URL = 'https://vibe-downloader.onrender.com/';


// --- Grab all the HTML elements we need to interact with ---
const urlInput     = document.getElementById('url-input');
const fetchBtn     = document.getElementById('fetch-btn');
const btnText      = document.getElementById('btn-text');
const btnSpinner   = document.getElementById('btn-spinner');
const errorBox     = document.getElementById('error-box');
const resultSec    = document.getElementById('result-section');
const resultThumb  = document.getElementById('result-thumb');
const resultBadge  = document.getElementById('result-platform-badge');
const resultDur    = document.getElementById('result-duration');
const resultUpload = document.getElementById('result-uploader');
const resultTitle  = document.getElementById('result-title');
const dlHD         = document.getElementById('dl-hd');
const dlSD         = document.getElementById('dl-sd');
const dlAudio      = document.getElementById('dl-audio');


// ==============================================================
// HELPER: Show or hide the loading spinner on the button
// ==============================================================
function setLoading(isLoading) {
  if (isLoading) {
    btnText.textContent = 'Fetching…';
    btnSpinner.classList.remove('hidden');
    fetchBtn.disabled = true;
  } else {
    btnText.textContent = 'Get Download Links';
    btnSpinner.classList.add('hidden');
    fetchBtn.disabled = false;
  }
}


// ==============================================================
// HELPER: Show an error message to the user
// ==============================================================
function showError(message) {
  errorBox.textContent = message;
  errorBox.classList.remove('hidden');
  resultSec.classList.add('hidden');  // Hide old results
}

function clearError() {
  errorBox.textContent = '';
  errorBox.classList.add('hidden');
}


// ==============================================================
// HELPER: Show or hide individual download buttons
// If a URL exists for that format, show the button and set its href
// If not (some platforms don't have all formats), hide the button
// ==============================================================
function setDownloadBtn(element, url) {
  if (url) {
    element.href = url;
    element.style.display = 'inline-flex';
  } else {
    element.style.display = 'none';
  }
}


// ==============================================================
// MAIN FUNCTION: fetchMediaInfo
// Called when user clicks the button or presses Enter
// ==============================================================
async function fetchMediaInfo() {

  // --- Step 1: Read what the user typed ---
  const rawUrl = urlInput.value.trim();

  // --- Step 2: Validate the input ---
  if (!rawUrl) {
    showError('Please paste a video or audio URL first.');
    return;
  }
  if (!rawUrl.startsWith('http')) {
    showError('That doesn\'t look like a valid URL. It should start with https://');
    return;
  }

  // --- Step 3: Clear any previous errors and show loading state ---
  clearError();
  setLoading(true);

  try {
    // ==========================================================
    // Step 4: Send the URL to our Flask backend using fetch()
    //
    // What is fetch()?
    // ----------------
    // fetch() is a built-in browser function to make HTTP requests.
    // It's how JavaScript "calls" a backend server.
    //
    // We're making a POST request (sending data TO the server).
    // The body is JSON — we convert our JS object to a JSON string
    // using JSON.stringify().
    //
    // 'await' makes JavaScript WAIT for the server to respond
    // before continuing to the next line.
    // ==========================================================
    const response = await fetch(`${BACKEND_URL}/api/info`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',  // "I'm sending JSON"
        'Accept': 'application/json',        // "I want JSON back"
      },
      body: JSON.stringify({ url: rawUrl }),  // Convert object → JSON string
    });

    // ==========================================================
    // Step 5: Parse the response
    //
    // response.json() reads the server's reply and converts the
    // JSON string back into a JavaScript object we can use.
    //
    // We also check response.ok — if the server returned a 4xx
    // or 5xx status code, response.ok will be false.
    // ==========================================================
    const data = await response.json();

    // Check if the server returned an error
    if (!response.ok || data.error) {
      throw new Error(data.error || `Server error (status ${response.status})`);
    }

    // ==========================================================
    // Step 6: Display the results
    //
    // At this point, 'data' looks like:
    // {
    //   title: "Some Video Title",
    //   thumbnail: "https://...",
    //   platform: "Youtube",
    //   duration: "3:45",
    //   uploader: "Channel Name",
    //   video_url: "https://...",       ← HD download link
    //   video_sd_url: "https://...",    ← SD download link
    //   audio_url: "https://...",       ← MP3 link
    // }
    // ==========================================================

    // Set thumbnail image
    if (data.thumbnail) {
      resultThumb.src = data.thumbnail;
      resultThumb.onerror = () => {
        // If thumbnail fails to load, show a placeholder
        resultThumb.src = 'https://placehold.co/210x136/2A1E4D/5A3B8C?text=No+Preview';
      };
    } else {
      resultThumb.src = 'https://placehold.co/210x136/2A1E4D/5A3B8C?text=No+Preview';
    }

    // Set platform badge and duration
    resultBadge.textContent = data.platform || '';
    resultDur.textContent   = data.duration  || '';

    // Show/hide duration badge
    if (!data.duration) resultDur.style.display = 'none';
    else resultDur.style.display = '';

    // Set uploader name and title
    resultUpload.textContent = data.uploader ? `by ${data.uploader}` : '';
    resultTitle.textContent  = data.title    || 'Untitled Media';

    // Set download buttons (hide buttons where no URL exists)
    setDownloadBtn(dlHD,    data.video_url);
    setDownloadBtn(dlSD,    data.video_sd_url);
    setDownloadBtn(dlAudio, data.audio_url);

    // Show the result card (remove the 'hidden' class)
    resultSec.classList.remove('hidden');

    // Smoothly scroll down to the result card
    resultSec.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

  } catch (err) {
    // ==========================================================
    // Step 7: Handle errors
    //
    // This catch block runs if:
    //   - The backend is not running (connection refused)
    //   - The backend returned an error (private video, etc.)
    //   - The internet is down
    //   - Any other unexpected problem
    // ==========================================================

    let userMessage = err.message;

    // Give friendlier messages for common errors
    if (err.message.includes('Failed to fetch') || err.message.includes('NetworkError')) {
      userMessage = 'Could not reach the server. Make sure your backend is running at: ' + BACKEND_URL;
    }

    showError(userMessage);

  } finally {
    // ==========================================================
    // 'finally' always runs — whether the fetch succeeded or failed.
    // We use it to always turn off the loading spinner.
    // ==========================================================
    setLoading(false);
  }
}


// ==============================================================
// EVENT LISTENERS
// These attach our function to user actions
// ==============================================================

// When the Download button is clicked
fetchBtn.addEventListener('click', fetchMediaInfo);

// When the user presses Enter inside the input box
urlInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') fetchMediaInfo();
});

// Clear error message when user starts editing the URL
urlInput.addEventListener('input', () => {
  if (!errorBox.classList.contains('hidden')) clearError();
});