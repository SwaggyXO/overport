(function () {
  const api = (window.OVERPORT_API || "").replace(/\/$/, "");

  function base() {
    if (api) return api;
    if (location.hostname === "127.0.0.1" || location.hostname === "localhost") {
      return "";
    }
    return "";
  }

  const root = base();
  function wire(id, path) {
    const el = document.getElementById(id);
    if (el && root) el.href = root + path;
  }
  wire("live-api-link", "/docs");
  wire("nav-docs", "/docs");
  wire("nav-portal", "/legacy/login");
  wire("nav-health", "/health");
  wire("docs-profiles", "/docs#/profiles/get_profile_v1_profiles_get");
  wire("portal-link", "/legacy/login");

  async function pretty(path, options) {
    const response = await fetch(root + path, options);
    const raw = await response.text();
    let body = raw;
    try {
      body = JSON.stringify(JSON.parse(raw), null, 2);
    } catch (_) {
      /* keep raw */
    }
    return { status: response.status, body: body };
  }

  function bind(buttonId, statusId, outId, runner) {
    const button = document.getElementById(buttonId);
    const status = document.getElementById(statusId);
    const out = document.getElementById(outId);
    if (!button) return;
    button.onclick = async function () {
      status.textContent = "Calling " + root + " ...";
      out.textContent = "Loading...";
      try {
        const result = await runner();
        status.textContent = "HTTP " + result.status + " from " + root;
        out.textContent = result.body;
      } catch (err) {
        status.textContent = "Request failed";
        out.textContent = String(err);
      }
    };
  }

  bind("btn-1001", "status-claim", "out-claim", function () {
    return pretty("/v1/claims/CLM-1001");
  });
  bind("btn-1002", "status-claim", "out-claim", function () {
    return pretty("/v1/claims/CLM-1002");
  });
  bind("btn-health", "status-claim", "out-claim", function () {
    return pretty("/health");
  });
  bind("btn-note", "status-claim", "out-claim", function () {
    return pretty("/v1/notes", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ claim_id: "CLM-1001", text: "Note from the public demo." }),
    });
  });
  bind("btn-profile", "status-profile", "out-profile", function () {
    const raw = (document.getElementById("vanity").value || "jane-doe").trim();
    const looksLikeUrl = raw.indexOf("linkedin.com") !== -1 || raw.indexOf("http") === 0;
    if (looksLikeUrl) {
      return pretty("/v1/profiles?url=" + encodeURIComponent(raw));
    }
    return pretty("/v1/profiles?vanity=" + encodeURIComponent(raw));
  });

  const sampleBtn = document.getElementById("btn-profile-sample");
  if (sampleBtn) {
    sampleBtn.onclick = async function () {
      document.getElementById("status-profile").textContent =
        "Offline mapped sample (not a live LinkedIn fetch)";
      const response = await fetch("assets/profile-sample.json");
      const body = JSON.stringify(await response.json(), null, 2);
      document.getElementById("out-profile").textContent = body;
    };
  }
})();
