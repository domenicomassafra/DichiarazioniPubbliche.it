(() => {
      const root = document.querySelector<HTMLElement>("[data-source-story]");
      if (!root) return;
      const controls = [...root.querySelectorAll<HTMLButtonElement>("[data-content-select]")];
      const details = [...root.querySelectorAll<HTMLElement>("[data-content-detail]")];
      const valid = new Set(details.map((detail) => detail.dataset.contentDetail));
      const eventRows = [...root.querySelectorAll<HTMLElement>("[data-content-event]")];
      const tabs = [...root.querySelectorAll<HTMLButtonElement>("[data-source-tab]")];
      const panels = [...root.querySelectorAll<HTMLElement>("[data-source-panel]")];
      const announcement = root.querySelector<HTMLElement>("[data-source-selection]");
      const selectTab = (which: string, focus = false) => {
        for (const tab of tabs) {
          const selected = tab.dataset.sourceTab === which;
          tab.setAttribute("aria-selected", String(selected));
          tab.tabIndex = selected ? 0 : -1;
          if (selected && focus) tab.focus();
        }
        for (const panel of panels) panel.hidden = panel.dataset.sourcePanel !== which;
      };
      const select = (id?: string, updateUrl = true) => {
        if (!id || !valid.has(id)) return;
        selectTab("claims");
        for (const item of controls) {
          const selected = item.dataset.contentSelect === id;
          if (selected) item.setAttribute("aria-current", "true");
          else item.removeAttribute("aria-current");
          if (item.hasAttribute("aria-expanded")) item.setAttribute("aria-expanded", String(selected));
        }
        for (const detail of details) detail.hidden = detail.dataset.contentDetail !== id;
        for (const row of eventRows) row.classList.toggle("is-current", row.querySelector("[data-content-select]")?.getAttribute("data-content-select") === id);
        const selectedRow = eventRows.find((row) => row.classList.contains("is-current"));
        if (announcement && selectedRow) announcement.textContent = `Dichiarazione selezionata: ${selectedRow.querySelector(".source-story__claim-text")?.textContent?.trim() ?? ""}`;
        if (updateUrl) {
          const params = new URLSearchParams(location.search);
          params.set("momento", id);
          history.replaceState(null, "", `${location.pathname}?${params}${location.hash}`);
        }
      };
      for (const control of controls) control.addEventListener("click", () => {
        select(control.dataset.contentSelect);
        if (control.closest(".source-story__timeline-track")) {
          root.querySelector("[data-content-detail]:not([hidden])")?.scrollIntoView({
            behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth",
            block: "center",
          });
        }
      });
      for (const tab of tabs) {
        tab.addEventListener("click", () => selectTab(tab.dataset.sourceTab ?? "claims"));
        tab.addEventListener("keydown", (event) => {
          if (!["ArrowRight", "ArrowLeft", "Home", "End"].includes(event.key)) return;
          event.preventDefault();
          const index = tabs.indexOf(tab);
          const next = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1
            : (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
          selectTab(tabs[next].dataset.sourceTab ?? "claims", true);
        });
      }
      const initial = new URLSearchParams(location.search).get("momento");
      if (initial && valid.has(initial)) select(initial, false);
    })();
