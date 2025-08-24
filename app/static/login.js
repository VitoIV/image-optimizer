document.getElementById("loginForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData();
  fd.append("password", document.getElementById("password").value);
  const r = await fetch("api/admin/login", { method: "POST", body: fd });
  if (r.ok) location.href = "/imgopt/admin";
  else alert("Chybné heslo.");
});
