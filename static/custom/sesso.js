/* neo-datasette v1.9 */
(function () {
  function pad(n) { return String(n).padStart(2, "0"); }

  function setDefaults() {
    const inputs = document.querySelectorAll("input[data-default-expr]");
    const now = new Date();

    inputs.forEach((el) => {
      const expr = (el.getAttribute("data-default-expr") || "").trim();
      const mode = (el.getAttribute("data-default-mode") || "").trim();
      if (!expr || mode !== "expr") return;
      if (el.value) return;

      if (expr === "today" && el.type === "date") {
        el.value = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
      }
      if (expr === "now_local" && el.type === "datetime-local") {
        el.value = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}`;
      }
    });
  }

  async function submitForm(form) {
    const msg = document.getElementById("msg");
    msg.textContent = "Salvataggio…";

    const fd = new FormData(form);
    const res = await fetch(form.action, { method: "POST", body: fd });
    let data = null;
    try { data = await res.json(); } catch (e) {}

    if (!res.ok || !data || data.ok !== true) {
      msg.textContent = "Errore: " + (data && data.error ? data.error : "submit fallito");
      return;
    }

    msg.textContent = "OK. Apro la tabella…";
    // Requisito: premendo Invio (submit) deve visualizzare la tabella sesso
    window.location.href = (data && data.table_url) ? data.table_url : `/${data.db_name || "output"}/sesso?_sort_desc=id`;
  }

  document.addEventListener("DOMContentLoaded", () => {
    setDefaults();

    const form = document.getElementById("sessoForm");
    if (!form) return;

    form.addEventListener("submit", (ev) => {
      ev.preventDefault();
      submitForm(form);
    });
  });
})();
