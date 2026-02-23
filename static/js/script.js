let abortController = null;

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("commitForm");
  if (form) {
    form.addEventListener("submit", handleFormSubmit);
  }
});

function stopGeneration() {
  if (abortController) {
    abortController.abort();
    abortController = null;
    const loadingText = document.getElementById("loadingText");
    const stopButton = document.getElementById("stopButton");

    loadingText.innerText = "Generation Stopped by User.";
    loadingText.style.color = "#e74c3c";

    if (stopButton) {
      stopButton.style.display = "none";
    }

    setTimeout(() => {
      const overlay = document.getElementById("loadingOverlay");
      overlay.classList.remove("active");
      window.location.reload();
    }, 2000);
  }
}

async function handleFormSubmit(e) {
  e.preventDefault();

  const overlay = document.getElementById("loadingOverlay");
  const loadingText = document.getElementById("loadingText");
  const stopButton = document.getElementById("stopButton");
  const inputElement = document.getElementById("commitInput");
  const inputVal = parseInt(inputElement.value) || 0;

  const existingError = document.querySelector(".alert-error");
  if (existingError) existingError.remove();

  if (inputVal < 1) {
    alert("Jumlah commit minimal 1");
    return;
  }

  if (overlay) overlay.classList.add("active");
  if (loadingText) loadingText.innerText = "Connecting...";

  await new Promise((r) => setTimeout(r, 20));

  if (abortController) {
    abortController.abort();
  }
  abortController = new AbortController();
  const signal = abortController.signal;

  if (stopButton) {
    stopButton.style.display = "block";
  }

  await new Promise((r) => setTimeout(r, 10));

  try {
    const response = await fetch("/stream_commits", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ jumlah: inputVal }),
      signal: signal,
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || "Gagal menghubungi server");
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      let lines = buffer.split("\n");

      buffer = lines.pop();

      for (const line of lines) {
        if (line.trim()) {
          try {
            const data = JSON.parse(line);
            if (data.status === "progress") {
              loadingText.innerText = `Processing: ${data.current} / ${data.total} commit`;
              loadingText.style.transform = "scale(1.05)";
              setTimeout(() => (loadingText.style.transform = "scale(1)"), 100);
            } else if (data.status === "init") {
              loadingText.innerText = data.message;
            } else if (data.status === "warning") {
              loadingText.innerText = "Warning: " + data.message;
              loadingText.style.color = "#ffdd57";
            } else if (data.status === "done") {
              loadingText.innerText = "Selesai! Menyegarkan halaman...";
              loadingText.style.color = "#48c774";
              if (stopButton) stopButton.style.display = "none";
              setTimeout(() => {
                window.location.reload();
              }, 1500);
            }
          } catch (e) {
            console.log("JSON Parse Error chunk:", line);
          }
        }
      }
    }
  } catch (error) {
    if (error.name === "AbortError") {
      console.log("Fetch aborted by user");
    } else {
      console.error(error);
      alert("Terjadi kesalahan: " + error.message);
      overlay.classList.remove("active");
      loadingText.innerText = "Error occurred";
      if (stopButton) stopButton.style.display = "none";
    }
  } finally {
    abortController = null;
  }
}
