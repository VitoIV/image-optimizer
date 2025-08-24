const BASE = "/imgopt";

const uploadForm = document.getElementById("uploadForm");
const fileInput   = document.getElementById("fileInput");
const uploadBtn   = document.getElementById("uploadBtn");
const uploadMsg   = document.getElementById("uploadMsg");
const refreshBtn  = document.getElementById("refreshBtn");
const batchesBody = document.getElementById("batchesBody");

const POLL_MS = 2000;

function badge(status) {
  const variants = {
    uploaded:  "bg-slate-100 text-slate-700",
    queued:    "bg-amber-100 text-amber-800",
    processing:"bg-blue-100 text-blue-800",
    done:      "bg-emerald-100 text-emerald-800",
    failed:    "bg-rose-100 text-rose-800",
    cancelled: "bg-gray-200 text-gray-700",
    deleted:   "bg-gray-100 line-through text-gray-500"
  };
  const cls = variants[status] || "bg-slate-100 text-slate-700";
  return `<span class="px-2 py-1 rounded-lg text-xs font-medium ${cls}">${status}</span>`;
}

function progressBar(pct) {
  const p = Math.max(0, Math.min(100, pct|0));
  return `
    <div class="w-48 bg-slate-100 rounded-lg overflow-hidden">
      <div class="h-2 bg-emerald-500 transition-all duration-300" style="width:${p}%"></div>
    </div>`;
}

function rowActions(b) {
  const dl = (b.status === "done" && b.result_zip)
    ? `<a class="text-indigo-600 hover:underline" href="${BASE}/api/batches/${b.id}/download">Stáhnout</a>`
    : "";
  const del = `<button data-id="${b.id}" class="delBtn text-rose-600 hover:underline">Smazat</button>`;
  const cancel = (b.status === "processing")
    ? `<button data-id="${b.id}" class="cancelBtn text-amber-600 hover:underline ml-2">Zrušit</button>`
    : "";
  return `${dl}${dl && (del||cancel) ? " · " : ""}${del}${cancel ? " · " + cancel : ""}`;
}

function renderBatches(items) {
  batchesBody.innerHTML = items.map(b => {
    const pct = b.total > 0 ? Math.round((b.processed / b.total) * 100) : 0;
    const created = new Date(b.created_at).toLocaleString();
    const trCls = b.status === "deleted" ? "opacity-60 line-through" : "";
    return `<tr class="${trCls}">
      <td class="p-3 font-mono text-xs">${b.id}</td>
      <td class="p-3">${badge(b.status)}</td>
      <td class="p-3 flex items-center gap-3">${progressBar(pct)}<span class="text-xs">${b.processed}/${b.total} (${pct}%)</span></td>
      <td class="p-3">${b.original_filename || ""}</td>
      <td class="p-3">${created}</td>
      <td class="p-3 flex items-center gap-2">${rowActions(b)}</td>
    </tr>`;
  }).join("");

  // Akce
  document.querySelectorAll(".delBtn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-id");
      await fetch(`${BASE}/api/batches/${id}`, { method:"DELETE" });
      fetchBatches();
    });
  });
  document.querySelectorAll(".cancelBtn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-id");
      await fetch(`${BASE}/api/batches/${id}/cancel`, { method:"POST" });
      fetchBatches();
    });
  });
}

async function fetchBatches() {
  const r = await fetch(`${BASE}/api/batches`);
  const data = await r.json();
  renderBatches((data && data.batches) || []);
}
window.fetchBatches = fetchBatches;

uploadForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = fileInput.files[0];
  if (!f) { uploadMsg.textContent = "Vyberte XLSX soubor."; return; }
  uploadBtn.disabled = true;
  uploadMsg.textContent = "Nahrávám…";

  const fd = new FormData();
  fd.append("file", f); 
  const mode = (document.getElementById("modeHidden")?.value || "A");
  fd.append("mode", mode);

  const r = await fetch(`${BASE}/api/batches`, { method: "POST", body: fd });
  if (r.ok) {
    uploadMsg.textContent = "Dávka zařazena do fronty.";
    fileInput.value = "";
    fetchBatches();
  } else {
    const t = await r.text().catch(()=>"");
    uploadMsg.textContent = "Nahrání selhalo. " + t;
  }
  uploadBtn.disabled = false;
});

if (refreshBtn) refreshBtn.addEventListener("click", fetchBatches);
setInterval(fetchBatches, POLL_MS);
fetchBatches();
