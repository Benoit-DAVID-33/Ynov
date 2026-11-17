// Small SVG charts for the admin console: stacked columns, lines, horizontal bars.
// Every chart has a hover tooltip, a legend when it shows 2+ series, and a data table
// (the light aqua slot is under 3:1 contrast: the table is its required relief).
const Charts = (() => {
  const NS = "http://www.w3.org/2000/svg";
  const HEIGHT = 220;
  const MARGIN = { top: 12, right: 12, bottom: 26, left: 44 };

  function svg(tag, attrs = {}) {
    const node = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    return node;
  }

  // Clean ticks; counts (integer) never get a fractional step such as 0.5.
  function niceScale(max, integer) {
    if (!(max > 0)) return { max: 1, step: 1 };
    const rough = max / 4;
    const power = 10 ** Math.floor(Math.log10(rough));
    let step = [1, 2, 2.5, 5, 10].map((m) => m * power).find((s) => s >= rough);
    if (integer) step = Math.max(1, Math.ceil(step));
    return { max: Math.ceil(max / step) * step, step };
  }

  // Path of a bar anchored on the baseline: 4px rounded data-end, square at the base.
  function columnPath(x, y, w, h, rounded) {
    const r = rounded ? Math.min(4, w / 2, h) : 0;
    return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`;
  }

  function rowPath(x, y, w, h) {
    const r = Math.min(4, h / 2, w);
    return `M${x},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h - r}Q${x + w},${y + h} ${x + w - r},${y + h}H${x}Z`;
  }

  function legend(series, kind) {
    if (series.length < 2) return null;
    return el("div", { className: "legend" }, ...series.map((s) => {
      const key = el("i", { className: kind === "line" ? "line" : "" });
      key.style.background = `var(${s.color})`;
      return el("span", {}, key, s.name);
    }));
  }

  function table(head, rows) {
    const t = el("table", {}, el("thead", {}, el("tr", {}, ...head.map((h, i) => el("th", { className: i ? "num" : "", textContent: h })))));
    const body = t.createTBody();
    for (const row of rows) {
      const tr = body.insertRow();
      row.forEach((v, i) => tr.append(el("td", { className: i ? "num" : "", textContent: v })));
    }
    return el("details", { className: "chart-table" }, el("summary", { textContent: "Voir les données" }), el("div", { className: "scroll" }, t));
  }

  function tooltip(box) {
    const tip = el("div", { className: "tooltip", hidden: true });
    box.append(tip);
    return {
      show(title, rows, x, y) {
        tip.replaceChildren(el("div", { className: "t-title", textContent: title }), ...rows.map(([color, name, value]) => {
          const key = el("span", { className: "t-key" });
          key.style.background = color ? `var(${color})` : "transparent";
          return el("div", { className: "t-row" }, key, el("b", { textContent: value }), el("span", { className: "muted", textContent: name }));
        }));
        tip.hidden = false;
        const width = box.clientWidth;
        const left = Math.min(Math.max(x + 12, 0), width - tip.offsetWidth - 4);
        tip.style.left = `${x + 12 + tip.offsetWidth > width ? Math.max(x - tip.offsetWidth - 12, 0) : left}px`;
        tip.style.top = `${Math.max(y - tip.offsetHeight / 2, 0)}px`;
      },
      hide() { tip.hidden = true; },
    };
  }

  function frame(container, maxValue, format, integer) {
    const width = Math.max(container.clientWidth, 280);
    const inner = { w: width - MARGIN.left - MARGIN.right, h: HEIGHT - MARGIN.top - MARGIN.bottom };
    const root = svg("svg", { viewBox: `0 0 ${width} ${HEIGHT}`, role: "img" });
    const plot = svg("g", { transform: `translate(${MARGIN.left},${MARGIN.top})` });
    root.append(plot);
    const scale = niceScale(maxValue, integer);
    const y = (v) => inner.h - (v / scale.max) * inner.h;
    for (let v = 0; v <= scale.max + 1e-9; v += scale.step) {
      plot.append(svg("line", { class: v ? "gridline" : "baseline", x1: 0, x2: inner.w, y1: y(v), y2: y(v) }));
      const label = svg("text", { class: "tick", x: -8, y: y(v) + 4, "text-anchor": "end" });
      label.textContent = format(v);
      plot.append(label);
    }
    return { root, plot, inner, y, width };
  }

  function xLabels(plot, inner, categories, xOf) {
    const every = Math.max(1, Math.ceil(categories.length / Math.floor(inner.w / 56)));
    categories.forEach((c, i) => {
      if (i % every && i !== categories.length - 1) return;
      if (i !== categories.length - 1 && categories.length - 1 - i < every) return;
      const t = svg("text", { class: "tick", x: xOf(i), y: inner.h + 18, "text-anchor": "middle" });
      t.textContent = c;
      plot.append(t);
    });
  }

  function mount(container, spec, draw) {
    // Redrawn on resize so that text keeps its size at any width.
    container.replaceChildren();
    if (!spec.series?.some((s) => s.values?.some((v) => v)) && !spec.items?.length) {
      container.append(el("p", { className: "empty-chart", textContent: spec.empty ?? "Aucune donnée sur la période." }));
      return false;
    }
    const box = el("div", { className: "chart" });
    container.append(box);
    const render = () => draw(box);
    render();
    container._observer?.disconnect();
    let lastWidth = box.clientWidth;
    container._observer = new ResizeObserver(() => {
      if (Math.abs(box.clientWidth - lastWidth) > 8) { lastWidth = box.clientWidth; render(); }
    });
    container._observer.observe(box);
    return true;
  }

  // Stacked columns, one per category; the hover target is the whole band.
  function columns(container, spec) {
    const { categories, series, format = String, titles = categories } = spec;
    const drawn = mount(container, spec, (box) => {
      box.replaceChildren();
      const totals = categories.map((_, i) => series.reduce((sum, s) => sum + (s.values[i] || 0), 0));
      const { root, plot, inner, y } = frame(box, Math.max(...totals), format, spec.integer);
      const band = inner.w / categories.length;
      const barW = Math.min(24, band * 0.7);
      const tip = tooltip(box);
      categories.forEach((_, i) => {
        const x = i * band + (band - barW) / 2;
        let base = 0;
        const marks = [];
        const visible = series.filter((s) => s.values[i] > 0);
        for (const s of series) {
          const v = s.values[i] || 0;
          if (!v) continue;
          const top = y(base + v);
          const bottom = y(base);
          const isTop = s === visible[visible.length - 1];
          // 2px surface gap between stacked segments.
          const h = Math.max(bottom - top - (base ? 2 : 0), 1);
          const mark = svg("path", { class: "mark", d: columnPath(x, top, barW, h, isTop), fill: `var(${s.color})` });
          marks.push(mark);
          plot.append(mark);
          base += v;
        }
        const hit = svg("rect", { class: "hit", x: i * band, y: 0, width: band, height: inner.h, tabindex: 0 });
        const show = () => {
          marks.forEach((m) => m.classList.add("hover"));
          tip.show(titles[i], [
            ...series.map((s) => [s.color, s.name, format(s.values[i] || 0)]),
            ...(series.length > 1 ? [[null, "Total", format(totals[i])]] : []),
          ], MARGIN.left + i * band + band / 2, MARGIN.top + y(totals[i]));
        };
        const hide = () => { marks.forEach((m) => m.classList.remove("hover")); tip.hide(); };
        hit.addEventListener("pointerenter", show);
        hit.addEventListener("focus", show);
        hit.addEventListener("pointerleave", hide);
        hit.addEventListener("blur", hide);
        plot.append(hit);
      });
      xLabels(plot, inner, categories, (i) => i * band + band / 2);
      root.setAttribute("aria-label", spec.label ?? "");
      box.append(root);
    });
    if (!drawn) return;
    container.append(...[legend(series, "rect"), table(["Jour", ...series.map((s) => s.name)],
      categories.map((_, i) => [titles[i], ...series.map((s) => format(s.values[i] || 0))]))].filter(Boolean));
  }

  // Lines over time; a crosshair snaps to the nearest day and lists every series.
  function lines(container, spec) {
    const { categories, series, format = String, titles = categories } = spec;
    const drawn = mount(container, spec, (box) => {
      box.replaceChildren();
      const max = Math.max(...series.flatMap((s) => s.values));
      const { root, plot, inner, y } = frame(box, max, format, spec.integer);
      const step = categories.length > 1 ? inner.w / (categories.length - 1) : 0;
      const xOf = (i) => (categories.length > 1 ? i * step : inner.w / 2);
      for (const s of series) {
        const d = s.values.map((v, i) => `${i ? "L" : "M"}${xOf(i)},${y(v || 0)}`).join("");
        plot.append(svg("path", { d, fill: "none", stroke: `var(${s.color})`, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }));
        const last = s.values.length - 1;
        plot.append(svg("circle", { cx: xOf(last), cy: y(s.values[last] || 0), r: 4, fill: `var(${s.color})`, stroke: "var(--card)", "stroke-width": 2 }));
      }
      const cross = svg("line", { class: "crosshair", y1: 0, y2: inner.h, visibility: "hidden" });
      plot.append(cross);
      const tip = tooltip(box);
      const overlay = svg("rect", { class: "hit", x: -step / 2, y: 0, width: inner.w + step, height: inner.h });
      overlay.addEventListener("pointermove", (event) => {
        const bounds = overlay.getBoundingClientRect();
        const i = Math.min(Math.max(Math.round(((event.clientX - bounds.left) / bounds.width) * (inner.w + step) / (step || 1) - 0.5), 0), categories.length - 1);
        cross.setAttribute("x1", xOf(i));
        cross.setAttribute("x2", xOf(i));
        cross.setAttribute("visibility", "visible");
        const top = Math.min(...series.map((s) => y(s.values[i] || 0)));
        tip.show(titles[i], series.map((s) => [s.color, s.name, format(s.values[i] || 0)]), MARGIN.left + xOf(i), MARGIN.top + top);
      });
      overlay.addEventListener("pointerleave", () => { cross.setAttribute("visibility", "hidden"); tip.hide(); });
      plot.append(overlay);
      xLabels(plot, inner, categories, xOf);
      root.setAttribute("aria-label", spec.label ?? "");
      box.append(root);
    });
    if (!drawn) return;
    container.append(...[legend(series, "line"), table(["Jour", ...series.map((s) => s.name)],
      categories.map((_, i) => [titles[i], ...series.map((s) => format(s.values[i] || 0))]))].filter(Boolean));
  }

  // Horizontal bars (one series): name on the left, value at the tip.
  function hbars(container, spec) {
    const { items, format = String, color = "--series-1", valueName = "Valeur" } = spec;
    const drawn = mount(container, spec, (box) => {
      box.replaceChildren();
      const width = Math.max(box.clientWidth, 280);
      const labelW = Math.min(170, width * 0.38);
      const valueW = 56;
      const rowH = 30;
      const barH = 16;
      const height = items.length * rowH;
      const root = svg("svg", { viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": spec.label ?? "" });
      const max = Math.max(...items.map((it) => it.value), 1);
      const tip = tooltip(box);
      items.forEach((item, i) => {
        const y = i * rowH + (rowH - barH) / 2;
        const name = svg("text", { class: "tick", x: labelW - 8, y: y + barH / 2 + 4, "text-anchor": "end" });
        name.textContent = item.label;
        const w = Math.max(((width - labelW - valueW) * item.value) / max, item.value ? 2 : 0);
        const mark = svg("path", { class: "mark", d: rowPath(labelW, y, w, barH), fill: `var(${color})` });
        const value = svg("text", { class: "value-label", x: labelW + w + 6, y: y + barH / 2 + 4 });
        value.textContent = format(item.value);
        const hit = svg("rect", { class: "hit", x: 0, y: i * rowH, width, height: rowH, tabindex: 0 });
        const show = () => { mark.classList.add("hover"); tip.show(item.label, [[color, valueName, format(item.value)], ...(item.extra ?? [])], labelW + w, y); };
        const hide = () => { mark.classList.remove("hover"); tip.hide(); };
        hit.addEventListener("pointerenter", show);
        hit.addEventListener("focus", show);
        hit.addEventListener("pointerleave", hide);
        hit.addEventListener("blur", hide);
        root.append(name, mark, value, hit);
      });
      box.append(root);
    });
    if (drawn) {
      container.append(table(["", valueName], items.map((it) => [it.label, format(it.value)])));
    }
  }

  return { columns, lines, hbars };
})();
