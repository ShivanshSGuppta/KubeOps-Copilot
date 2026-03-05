(function () {
  const form = document.getElementById("nlqForm");
  if (!form) return;

  const out = document.getElementById("nlqOut");
  const pre = document.getElementById("nlqJson");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const promptEl = document.getElementById("prompt");
    const prompt = promptEl.value;

    const fd = new FormData();
    fd.append("prompt", prompt);

    pre.textContent = "Running...";
    out.classList.remove("hidden");

    try {
      const res = await fetch("/api/nlq", { method: "POST", body: fd });
      const json = await res.json();
      pre.textContent = JSON.stringify(json, null, 2);
    } catch (err) {
      pre.textContent = String(err);
    }
  });
})();
