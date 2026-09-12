const fragmentToken = location.hash.slice(1);
if (fragmentToken) {
  sessionStorage.setItem("formatador-session-token", fragmentToken);
  history.replaceState(null, "", location.pathname + location.search);
}
const sessionToken = sessionStorage.getItem("formatador-session-token");
const form = document.querySelector("#processing-form");
const result = document.querySelector("#result");
const status = document.querySelector("#status");
const summary = document.querySelector("#summary");
const downloads = document.querySelector("#downloads");

function profileBytes() {
  const ruleGroups = [];
  for (const group of document.querySelectorAll(".rule-grid")) {
    const ruleEntries = [];
    for (const control of group.querySelectorAll("[data-property]")) {
      const property = control.dataset.property;
      if (control.value !== "") {
        const value = property === "alignment"
          ? JSON.stringify(control.value)
          : property === "bold" ? control.value : control.value.trim();
        ruleEntries.push(`${JSON.stringify(property)}:{"mode":"exact","value":${value}}`);
      }
    }
    if (ruleEntries.length) {
      ruleGroups.push(`${JSON.stringify(group.dataset.target)}:{${ruleEntries.join(",")}}`);
    }
  }
  return new TextEncoder().encode(
    `{"schema_version":"0.3","profile":{"id":"web-interface","version":"1"},"rules":{${ruleGroups.join(",")}}}`
  );
}

function appendSummary(value) {
  summary.replaceChildren();
  for (const [key, item] of Object.entries(value)) {
    const term = document.createElement("dt");
    term.textContent = key;
    const description = document.createElement("dd");
    description.textContent = typeof item === "object" ? JSON.stringify(item) : String(item);
    summary.append(term, description);
  }
}

function downloadFile(file) {
  const raw = atob(file.content_base64);
  const bytes = Uint8Array.from(raw, character => character.charCodeAt(0));
  const blob = new Blob([bytes], { type: file.media_type });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = file.filename;
  link.textContent = `Baixar ${file.filename}`;
  link.addEventListener("click", () => setTimeout(() => URL.revokeObjectURL(link.href), 1000), { once: true });
  downloads.append(link);
}

form.addEventListener("submit", async event => {
  event.preventDefault();
  const file = document.querySelector("#document").files[0];
  const hasRule = [...document.querySelectorAll("[data-property]")].some(control => control.value !== "");
  if (!hasRule) {
    result.hidden = false;
    result.classList.add("error");
    status.textContent = "Declare pelo menos uma regra antes de processar.";
    return;
  }
  if (!sessionToken) {
    result.hidden = false;
    result.classList.add("error");
    status.textContent = "Token ausente. Abra a URL fornecida pelo servidor.";
    return;
  }
  const body = new FormData();
  body.append("document", file, file.name);
  body.append("profile", new Blob([profileBytes()], { type: "application/json" }), "profile.json");
  body.append("max_applied_operations", document.querySelector("#max-operations").value);
  const button = form.querySelector("button");
  button.disabled = true;
  result.hidden = false;
  result.classList.remove("error");
  status.textContent = "Processando...";
  summary.replaceChildren();
  downloads.replaceChildren();
  try {
    const response = await fetch("/api/process", {
      method: "POST",
      headers: { "X-Formatador-Session": sessionToken },
      body
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "processamento rejeitado");
    if (payload.session_status === "quiescent") {
      status.textContent = "Processamento concluído. Nenhuma alteração automática segura foi necessária. Isso não significa conformidade integral.";
    } else if (payload.session_status === "operation_limit_reached") {
      status.textContent = "Limite de alterações atingido. O processamento parou antes de concluir todas as alterações seguras.";
    } else if (payload.session_status === "quiescent_with_unapplied") {
      status.textContent = "Processamento concluído com ressalvas. Permaneceram itens que não foram aplicados automaticamente.";
    } else {
      status.textContent = `Processamento concluído. Status técnico da sessão: ${payload.session_status}.`;
    }
    appendSummary(payload.summary);
    for (const output of payload.files) downloadFile(output);
  } catch (error) {
    result.classList.add("error");
    status.textContent = error instanceof Error ? error.message : "erro de comunicação";
  } finally {
    button.disabled = false;
  }
});
