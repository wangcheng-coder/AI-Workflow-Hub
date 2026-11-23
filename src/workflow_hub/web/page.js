function body() {
  return JSON.stringify({yaml: document.getElementById("yaml").value, inputs: {}});
}
document.getElementById("validate").addEventListener("click", () => run(() => api("/api/workflows/validate", {method:"POST", headers:{"Content-Type":"application/json"}, body: body()})));
document.getElementById("dry").addEventListener("click", () => run(() => api("/api/workflows/dry-run", {method:"POST", headers:{"Content-Type":"application/json"}, body: body()})));
document.getElementById("start").addEventListener("click", () => run(async () => {
  const started = await api("/api/runs", {method:"POST", headers:{"Content-Type":"application/json"}, body: body()});
  document.getElementById("run").value = started.id || "";
  return started;
}));
document.getElementById("runs").addEventListener("click", () => run(() => api("/api/runs")));
document.getElementById("resume").addEventListener("click", () => run(() => api("/api/runs/" + encodeURIComponent(document.getElementById("run").value) + "/resume", {
  method: "POST",
  headers: {"Content-Type": "application/json"},
  body: JSON.stringify({approvals: {}})
})));
