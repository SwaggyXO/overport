(function () {
  const out = document.getElementById("out");
  const live = document.getElementById("live-api-link");
  const api = (window.OVERPORT_API || "").replace(/\/$/, "");
  const onAppHost =
    location.port === "8000" ||
    location.port === "8080" ||
    location.port === "8085" ||
    Boolean(api);

  if (api) {
    live.href = api + "/docs";
    live.textContent = "Live API";
  } else if (onAppHost && !location.pathname.includes("overport")) {
    live.href = "/docs";
  } else {
    live.href = "https://github.com/SwaggyXO/overport";
    live.textContent = "API source";
  }

  function origin() {
    if (api) return api;
    if (onAppHost && !location.hostname.includes("github.io")) return "";
    return null;
  }

  async function show(label, runner) {
    out.textContent = "Loading " + label + " ...";
    try {
      const text = await runner();
      out.textContent = text;
    } catch (err) {
      out.textContent = String(err);
    }
  }

  async function getJson(path, fallback) {
    const base = origin();
    if (base === null) {
      const sample = await fetch(fallback);
      const body = await sample.text();
      return body + "\n\n(static sample from this site; set OVERPORT_API for live calls)";
    }
    const response = await fetch(base + path);
    const body = await response.text();
    try {
      return JSON.stringify(JSON.parse(body), null, 2);
    } catch (_) {
      return body;
    }
  }

  document.getElementById("btn-1001").onclick = function () {
    show("CLM-1001", function () {
      return getJson("/v1/claims/CLM-1001", "assets/claim-paid.json");
    });
  };
  document.getElementById("btn-1002").onclick = function () {
    show("CLM-1002", function () {
      return getJson("/v1/claims/CLM-1002", "assets/claim-pending.json");
    });
  };
  document.getElementById("btn-health").onclick = function () {
    show("health", async function () {
      const base = origin();
      if (base === null) {
        return JSON.stringify(
          { service: "overport", status: "ok", linkedin_session_present: false },
          null,
          2
        );
      }
      const response = await fetch(base + "/health");
      return JSON.stringify(await response.json(), null, 2);
    });
  };
})();
