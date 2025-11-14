// Theme toggle (shared)
(function () {
    const root = document.documentElement;
    const KEY = "sg-theme";

    function apply(mode) {
        if (mode === "light") {
            root.classList.add("light");
        } else {
            root.classList.remove("light");
        }
        localStorage.setItem(KEY, mode);
    }

    const saved = localStorage.getItem(KEY);
    if (saved) {
        apply(saved);
    } else if (
        window.matchMedia &&
        window.matchMedia("(prefers-color-scheme: light)").matches
    ) {
        apply("light");
    }

    document
        .querySelectorAll("[data-theme-toggle]")
        .forEach((btn) =>
            btn.addEventListener("click", (e) => {
                e.preventDefault();
                const next = root.classList.contains("light") ? "dark" : "light";
                apply(next);
            })
        );
})();

// Smooth scroll for in-page anchors
document.querySelectorAll('a[href^="#"]').forEach((a) => {
    a.addEventListener("click", (e) => {
        const href = a.getAttribute("href");
        if (!href || href === "#") return;
        const id = href.slice(1);
        const el = document.getElementById(id);
        if (!el) return;
        e.preventDefault();
        el.scrollIntoView({ behavior: "smooth", block: "start" });
    });
});

// Code block copy buttons (both pages)
document.querySelectorAll("pre").forEach((pre) => {
    const btn = document.createElement("button");
    btn.textContent = "Copy";
    btn.className = "copy-btn";
    btn.style.float = "right";
    btn.style.margin = "0 0 6px 6px";
    btn.style.fontSize = "11px";
    btn.style.padding = "4px 8px";
    btn.style.borderRadius = "999px";
    btn.style.border = "1px solid var(--border)";
    btn.style.background = "var(--panel)";
    btn.style.color = "var(--muted)";
    btn.style.cursor = "pointer";

    btn.addEventListener("click", async () => {
        try {
            await navigator.clipboard.writeText(pre.innerText);
            const old = btn.textContent;
            btn.textContent = "Copied";
            setTimeout(() => (btn.textContent = old), 1200);
        } catch {
            btn.textContent = "Error";
        }
    });

    pre.prepend(btn);
});

// Docs-only helpers (safe no-op on index.html)
(function () {
    // Architecture tabs
    const tabButtons = document.querySelectorAll(".tab-btn");
    if (tabButtons.length) {
        tabButtons.forEach((btn) => {
            btn.addEventListener("click", () => {
                const tab = btn.dataset.tab;
                document
                    .querySelectorAll(".tab-btn")
                    .forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
                document
                    .querySelectorAll("[data-tab-panel]")
                    .forEach((panel) =>
                        panel.classList.toggle(
                            "active",
                            panel.dataset.tabPanel === tab
                        )
                    );
            });
        });
    }

    // TOC highlighting
    const tocLinks = Array.from(document.querySelectorAll(".toc-link"));
    if (tocLinks.length) {
        const sections = tocLinks
            .map((link) => document.getElementById(link.getAttribute("href").slice(1)))
            .filter(Boolean);

        const onScroll = () => {
            const y = window.scrollY || window.pageYOffset;
            let activeId = null;
            sections.forEach((sec) => {
                const top = sec.getBoundingClientRect().top + window.scrollY;
                if (top - 90 <= y) {
                    activeId = sec.id;
                }
            });
            tocLinks.forEach((link) => {
                const targetId = link.getAttribute("href").slice(1);
                link.classList.toggle("active", targetId === activeId);
            });
        };

        document.addEventListener("scroll", onScroll, { passive: true });
        onScroll();
    }

    // Back-to-top
    const backToTop = document.getElementById("backToTop");
    if (backToTop) {
        window.addEventListener("scroll", () => {
            const y = window.scrollY || window.pageYOffset;
            if (y > 300) {
                backToTop.classList.add("visible");
            } else {
                backToTop.classList.remove("visible");
            }
        });
        backToTop.addEventListener("click", () => {
            window.scrollTo({ top: 0, behavior: "smooth" });
        });
    }
})();
