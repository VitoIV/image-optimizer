async function loadWorkers() {
  const r = await fetch("api/admin/workers");
  const data = await r.json();
  document.getElementById("workersCount").value = data.desired;
  document.getElementById("threadsCount").value = data.threads;
  document.getElementById("retentionDays").value = data.retention_days;
  document.getElementById("autoPurge").checked = !!data.auto_purge;
}
document.getElementById("setWorkersBtn").addEventListener("click", async () => {
  const n = parseInt(document.getElementById("workersCount").value || "0", 10);
  await fetch(`api/admin/workers/set/${n}`, { method: "POST" });
  loadWorkers();
});
document.getElementById("setThreadsBtn").addEventListener("click", async () => {
  const n = parseInt(document.getElementById("threadsCount").value || "1", 10);
  await fetch(`api/admin/threads/set/${n}`, { method: "POST" });
  alert("Nastaveno. Platí pro nové dávky.");
});
document.getElementById("saveRetentionBtn").addEventListener("click", async () => {
  const days = parseInt(document.getElementById("retentionDays").value || "30", 10);
  await fetch(`api/admin/retention/set/${days}`, { method: "POST" });
  await fetch(`api/admin/auto-purge/${document.getElementById("autoPurge").checked ? "true":"false"}`, { method: "POST" });
  alert("Uloženo.");
});
document.getElementById("purgeBtn").addEventListener("click", async () => {
  await fetch("api/admin/purge", { method: "POST" });
  alert("Úklid spuštěn.");
});
document.getElementById("logoutForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  await fetch("api/admin/logout", { method: "POST" });
  location.href = "/imgopt/admin";
});
loadWorkers();
