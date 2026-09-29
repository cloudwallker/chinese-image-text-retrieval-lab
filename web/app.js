"use strict";

(() => {
  const $ = (id) => document.getElementById(id);
  const methodLabels = {caption: "人工描述基线", clip: "原始图文相似度", negative: "排除条件教学实验"};
  const state = {status: null, connected: false, gallery: [], galleryExpanded: false, lastSearch: null, report: null, searching: false, startingTask: false, pendingTask: "", taskStartedAt: null, notesDirty: false, savingNotes: false, reportLoading: false, pollTimer: null, toastTimer: null};

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function showError(id, message) {
    const node = $(id);
    node.textContent = message || "";
    node.hidden = !message;
  }

  function toast(message) {
    clearTimeout(state.toastTimer);
    $("toast").textContent = message;
    $("toast").hidden = false;
    state.toastTimer = setTimeout(() => { $("toast").hidden = true; }, 4500);
  }

  async function api(path, body, timeoutMs = 120000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const options = {signal: controller.signal, cache: "no-store"};
      if (body !== undefined) {
        options.method = "POST";
        options.headers = {"Content-Type": "application/json"};
        options.body = JSON.stringify(body);
      }
      const response = await fetch(path, options);
      let data;
      try { data = await response.json(); }
      catch (_) { throw new Error("本地服务返回了无法解析的响应，请检查服务终端。"); }
      if (!response.ok) throw new Error(data.error || `请求失败（HTTP ${response.status}）`);
      return data;
    } catch (error) {
      if (error.name === "AbortError") throw new Error("请求超时。CPU 任务可能仍在运行，请查看本地运行状态后重试。");
      if (error instanceof TypeError) throw new Error("无法连接本地服务。请确认启动脚本仍在运行，然后刷新页面。");
      throw error;
    } finally { clearTimeout(timer); }
  }

  function formatTime(value) {
    if (!value) return "未提供时间";
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString("zh-CN", {hour12: false});
  }

  function duration(value) {
    const number = Number(value);
    if (!Number.isFinite(number)) return "—";
    return number < 1000 ? `${number.toFixed(0)} ms` : `${(number / 1000).toFixed(2)} s`;
  }

  function metric(value) {
    const number = Number(value);
    return value !== null && value !== undefined && Number.isFinite(number) ? `${(number * 100).toFixed(1)}%` : "—";
  }

  function rawScore(value) {
    const number = Number(value);
    return value !== null && value !== undefined && Number.isFinite(number) ? number.toFixed(6) : "—";
  }

  function safeExternalURL(value) {
    if (typeof value !== "string" || !value.trim()) return null;
    try {
      const url = new URL(value);
      return ["https:", "http:"].includes(url.protocol) ? url.href : null;
    } catch (_) { return null; }
  }

  function imageURL(file) {
    if (typeof file !== "string" || !file) return null;
    try {
      const url = new URL(`/${file.replace(/^\/+/, "")}`, window.location.origin);
      return url.origin === window.location.origin && url.pathname.startsWith("/data/images/") ? url.href : null;
    } catch (_) { return null; }
  }

  function licenseURL(item) {
    const supplied = safeExternalURL(item.license_url);
    if (supplied) return supplied;
    const license = String(item.license || "");
    if (/CC0/i.test(license)) return "https://creativecommons.org/publicdomain/zero/1.0/";
    if (/public domain|公有领域/i.test(license)) return "https://creativecommons.org/publicdomain/mark/1.0/";
    return null;
  }

  function externalLink(text, url, className) {
    const link = element("a", className, text);
    link.href = url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    return link;
  }

  function createImage(item, className) {
    const frame = element("div", className);
    const url = imageURL(item.file);
    if (!url) {
      frame.append(element("span", "image-fallback", "图片路径不可用"));
      return frame;
    }
    const image = element("img");
    image.src = url;
    image.alt = item.caption || item.title || "图库图片";
    image.loading = "lazy";
    image.decoding = "async";
    image.addEventListener("error", () => {
      image.remove();
      frame.append(element("span", "image-fallback", "图片未能加载"));
    }, {once: true});
    frame.append(image);
    return frame;
  }

  function imageCard(item, rank) {
    const card = element("article", "image-card");
    const frame = createImage(item, "image-frame");
    if (rank !== undefined) frame.append(element("span", `rank-label${rank === 1 ? " first" : ""}`, `TOP ${rank}`));
    const content = element("div", "card-content");
    const title = element("div", "card-title-row");
    title.append(element("h3", "", item.title || item.id || "未命名图片"), element("span", "card-id", item.id));
    const caption = element("p", "card-caption", item.caption);
    caption.title = item.caption || "";
    content.append(title, caption);
    if (Array.isArray(item.tags) && item.tags.length) {
      const tags = element("div", "card-tags");
      item.tags.slice(0, 3).forEach((tag) => tags.append(element("span", "", tag)));
      content.append(tags);
    }
    if (rank !== undefined) {
      const score = element("div", "card-score");
      const value = element("strong", "", rawScore(item.score));
      value.title = `服务返回的原始分数：${item.score}`;
      score.append(element("span", "", "原始检索分数"), value);
      content.append(score);
    }
    const links = element("div", "card-links");
    const source = safeExternalURL(item.source_url);
    if (source) {
      const link = externalLink("图片来源 ↗", source);
      link.setAttribute("aria-label", `${item.title || item.id}：图片来源（新窗口）`);
      links.append(link);
    } else links.append(element("span", "", item.source_url ? "来源链接不可用" : "来源未提供"));
    const license = licenseURL(item);
    if (license) links.append(externalLink(item.license || "查看许可", license, "card-license"));
    else links.append(element("span", "card-license", item.license || "许可未提供"));
    content.append(links);
    card.append(frame, content);
    return card;
  }

  function switchView(view) {
    if (!["retrieval", "experiments", "notes"].includes(view)) view = "retrieval";
    const titles = {retrieval: "图文检索", experiments: "对照实验", notes: "学习笔记"};
    document.querySelectorAll(".view").forEach((section) => { section.hidden = section.id !== `view-${view}`; });
    document.querySelectorAll(".nav-item").forEach((button) => {
      const active = button.dataset.view === view;
      button.classList.toggle("active", active);
      if (active) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    });
    $("view-title").textContent = titles[view];
    document.title = `${titles[view]} · 本地学习实验室`;
    if (window.location.hash !== `#${view}`) history.replaceState(null, "", `#${view}`);
  }

  function selectedMethod() {
    return document.querySelector('input[name="method"]:checked').value;
  }

  function updateControls() {
    const status = state.status;
    const busy = Boolean(status && status.busy) || state.startingTask || Boolean(state.pendingTask);
    const ready = Boolean(status && status.index_ready);
    document.querySelectorAll('input[name="method"]').forEach((input) => { input.disabled = input.value !== "caption" && !ready; });
    document.querySelectorAll(".model-method-tag").forEach((tag) => {
      tag.textContent = ready ? status.model_ready ? "已就绪" : "缓存可用" : "需建库";
      tag.classList.toggle("available", ready);
    });
    $("negative-control").hidden = selectedMethod() !== "negative";
    $("search-button").disabled = state.searching || busy || !state.connected || (selectedMethod() !== "caption" && !ready);
    $("search-button").querySelector("span").textContent = state.searching ? "检索中…" : "开始检索";
    $("prepare-button").disabled = busy || state.searching || !state.connected;
    $("prepare-button").querySelector("span").textContent = busy && (state.pendingTask === "prepare" || status?.task === "prepare") ? "正在构建向量…" : ready ? "检查 / 重建向量" : "构建图片向量";
    $("evaluate-button").disabled = busy || state.searching || !state.connected;
    $("evaluate-button").querySelector("span").textContent = busy && (state.pendingTask === "evaluate" || status?.task === "evaluate") ? "实验运行中…" : "运行实验";
    $("search-form").classList.toggle("loading", state.searching);
  }

  function renderStatus(status) {
    state.connected = true;
    $("connection-pill").className = "connection-pill connected";
    $("connection-text").textContent = "本地服务已连接";
    $("side-status-dot").className = "status-dot ready";
    $("side-status-text").textContent = status.busy ? "后台任务运行中" : "本地服务在线";
    showError("global-alert", "");
    $("gallery-count").textContent = `${status.gallery_count ?? "—"} 张图片`;
    $("model-status").textContent = status.model_ready ? "RN50 · 已加载" : status.model_file_present ? "RN50 · 尚未加载" : "RN50 · 权重未就绪";
    $("model-status").classList.toggle("ready", Boolean(status.model_ready));
    $("index-status").textContent = status.index_ready ? "已就绪" : "尚未构建";
    $("index-status").classList.toggle("ready", Boolean(status.index_ready));
    const memory = Number(status.memory_available_mb);
    $("memory-status").textContent = status.memory_available_mb !== null && status.memory_available_mb !== undefined && Number.isFinite(memory) ? `${(memory / 1024).toFixed(2)} GB` : "无法读取";
    const ready = status.index_ready;
    $("readiness-icon").className = `readiness-icon${status.error ? " error" : ready ? "" : " waiting"}`;
    $("readiness-icon").textContent = status.error ? "!" : status.busy ? "↻" : ready ? "✓" : "◇";
    $("readiness-title").textContent = status.busy ? status.task === "evaluate" ? "正在运行对照评估" : "正在构建图片向量" : ready ? status.model_ready ? "模型检索已就绪" : "图片向量缓存可用" : "人工描述基线可用";
    $("readiness-subtitle").textContent = ready ? status.model_ready ? `${status.model_name || "Chinese-CLIP RN50"} · CPU` : "首次模型查询时加载 RN50" : "模型方法需要真实图片向量";
    $("status-message").textContent = status.message || "图库和人工描述基线无需加载模型。模型检索需要先构建图片向量。";
    showError("status-error", status.error || "");
    $("build-progress").hidden = !status.busy;
    const progress = Math.min(1, Math.max(0, Number(status.progress) || 0));
    $("progress-bar").value = progress;
    $("progress-value").textContent = `${Math.round(progress * 100)}%`;
    $("build-task-label").textContent = status.task === "evaluate" ? "对照评估进度" : "图片向量构建进度";
    $("build-elapsed").textContent = state.taskStartedAt ? `本次等待 ${Math.max(0, Math.floor((Date.now() - state.taskStartedAt) / 1000))} 秒` : "服务正在处理后台任务";
    const evaluating = status.busy && status.task === "evaluate";
    $("experiment-progress").hidden = !evaluating;
    $("experiment-progress").textContent = evaluating ? `实验正在运行 · ${Math.round(progress * 100)}%${state.report ? " · 下方保留上一次报告，完成后更新。" : ""}` : "";
    updateControls();
  }

  async function refreshStatus() {
    const previous = state.status;
    try {
      const status = await api("/api/status", undefined, 15000);
      state.status = status;
      const taskFinished = !status.busy && (previous?.busy || state.pendingTask);
      const finishedTask = state.pendingTask || previous?.task;
      if (status.busy) state.pendingTask = "";
      else if (taskFinished) state.pendingTask = "";
      renderStatus(status);
      if (taskFinished) {
        state.taskStartedAt = null;
        if (status.error) {
          showError(finishedTask === "evaluate" ? "evaluate-error" : "status-error", status.error);
        } else if (finishedTask === "evaluate" && status.report_ready) {
          if (await loadReport()) toast("实验已完成，报告已更新。");
        } else if (finishedTask === "prepare") {
          await loadGallery();
          if (status.index_ready) toast("图片向量已就绪，可以使用模型检索。");
        }
      } else if (status.report_ready && !state.report && !state.reportLoading) await loadReport();
    } catch (error) {
      state.connected = false;
      $("connection-pill").className = "connection-pill disconnected";
      $("connection-text").textContent = "连接中断";
      $("side-status-dot").className = "status-dot error";
      $("side-status-text").textContent = "无法连接本地服务";
      showError("global-alert", error.message);
      updateControls();
    }
  }

  async function pollStatus() {
    clearTimeout(state.pollTimer);
    await refreshStatus();
    state.pollTimer = setTimeout(pollStatus, state.status?.busy || state.pendingTask ? 1200 : 5000);
  }

  function renderGallery() {
    if (state.lastSearch) return;
    $("results-heading").textContent = "探索演示图库";
    $("results-description").textContent = "真实图片、中文描述与可追溯来源。选择一句描述，开始观察检索行为。";
    $("result-badge").textContent = `${state.gallery.length} 张图库图片`;
    $("reset-gallery").hidden = true;
    $("parsed-query").hidden = true;
    $("result-context").hidden = true;
    $("image-grid").replaceChildren(...(state.galleryExpanded ? state.gallery : state.gallery.slice(0, 8)).map((item) => imageCard(item)));
    $("image-grid").setAttribute("aria-busy", "false");
    $("gallery-empty").hidden = state.gallery.length > 0;
    $("gallery-empty").querySelector("h3").textContent = "还没有可浏览的图片";
    $("gallery-empty").querySelector("p").textContent = "请检查本地图库数据是否已准备完成。";
    $("show-all-gallery").hidden = state.gallery.length <= 8;
    $("show-all-gallery").textContent = state.galleryExpanded ? "收起图库" : `查看全部 ${state.gallery.length} 张图片`;
  }

  async function loadGallery() {
    try {
      const data = await api("/api/gallery", undefined, 20000);
      if (!Array.isArray(data.items)) throw new Error("本地服务返回的图库格式不正确。");
      state.gallery = data.items;
      renderGallery();
    } catch (error) {
      if (!state.lastSearch) {
        $("image-grid").replaceChildren();
        $("image-grid").setAttribute("aria-busy", "false");
        $("result-badge").textContent = "图库加载失败";
        $("gallery-empty").hidden = false;
        $("gallery-empty").querySelector("h3").textContent = "图库未能加载";
        $("gallery-empty").querySelector("p").textContent = error.message;
      }
    }
  }

  async function search(event) {
    event.preventDefault();
    if (state.searching || $("search-button").disabled) return;
    const query = $("query").value.trim();
    if (!query) { showError("search-error", "请输入一段中文描述。"); $("query").focus(); return; }
    const method = selectedMethod();
    const body = {query, method, top_k: Number(document.querySelector('input[name="top_k"]:checked').value), negative_weight: Number($("negative-weight").value)};
    state.searching = true;
    showError("search-error", "");
    updateControls();
    $("image-grid").setAttribute("aria-busy", "true");
    try {
      const data = await api("/api/search", body);
      if (!Array.isArray(data.results)) throw new Error("本地服务返回的检索结果格式不正确。");
      state.lastSearch = {data, query};
      $("results-heading").textContent = "检索结果";
      $("results-description").textContent = `「${query}」 · ${methodLabels[data.method] || data.method} · 耗时 ${duration(data.elapsed_ms)}`;
      $("result-badge").textContent = `${data.results.length} 项实际结果`;
      $("reset-gallery").hidden = false;
      $("show-all-gallery").hidden = true;
      $("image-grid").replaceChildren(...data.results.map((item, index) => imageCard(item, index + 1)));
      $("gallery-empty").hidden = data.results.length > 0;
      $("gallery-empty").querySelector("h3").textContent = "没有返回结果";
      $("gallery-empty").querySelector("p").textContent = "请检查图库状态，或换一个更明确的描述。";
      $("parsed-query").hidden = data.method !== "negative";
      $("positive-query").textContent = data.parsed?.positive || "（空）";
      $("negative-query").textContent = data.parsed?.negative || "（未提供）";
      const descriptions = {caption: "本次结果来自人工描述的词项匹配，没有进行图片向量编码。", clip: "本次使用真实 Chinese-CLIP 图文向量的余弦相似度。", negative: "本次使用正向分数减去排除权重 × 排除项分数。它是免训练的启发式教学实验。"};
      $("result-context").hidden = false;
      $("result-context").textContent = [descriptions[data.method] || "", data.message || ""].filter(Boolean).join("\n");
    } catch (error) { showError("search-error", error.message); }
    finally {
      state.searching = false;
      $("image-grid").setAttribute("aria-busy", "false");
      updateControls();
    }
  }

  async function startTask(task, body) {
    if (state.startingTask || state.status?.busy || state.pendingTask) return;
    const errorId = task === "evaluate" ? "evaluate-error" : "status-error";
    showError(errorId, "");
    state.startingTask = true;
    updateControls();
    try {
      const data = await api(`/api/${task}`, body || {});
      if (!data.started) throw new Error("本地服务没有确认任务启动，请查看服务终端。");
      state.pendingTask = task;
      state.taskStartedAt = Date.now();
      if (task === "evaluate") {
        $("experiment-progress").hidden = false;
        $("experiment-progress").textContent = "实验已启动，正在读取后台进度…";
      }
      await refreshStatus();
    } catch (error) { showError(errorId, error.message); }
    finally { state.startingTask = false; updateControls(); }
  }

  function overviewCard(label, value, note, longValue = false) {
    const card = element("div", "overview-card");
    card.append(element("span", "", label), element("strong", longValue ? "long-value" : "", value), element("small", "", note));
    return card;
  }

  function reportMethods() { return Array.isArray(state.report?.methods) ? state.report.methods : []; }

  function renderReport(report) {
    state.report = report;
    $("report-empty").hidden = true;
    $("report-content").hidden = false;
    $("report-time").textContent = `实际运行时间：${formatTime(report.created_at)}`;
    const warnings = Array.isArray(report.warnings) ? report.warnings : [];
    $("report-warnings").hidden = warnings.length === 0;
    $("report-warnings").replaceChildren(...warnings.map((warning) => element("p", "", warning)));
    $("report-overview").replaceChildren(
      overviewCard("完整图库", `${report.gallery_count ?? "—"} 张`, "本次实验实际使用"),
      overviewCard("标注查询", `${report.query_count ?? "—"} 条`, `划分：${report.split || "未提供"}`),
      overviewCard("报告模型", report.model || "未提供", "以服务记录为准", true),
      overviewCard("排除权重", report.negative_weight ?? "—", "正向分数 − 权重 × 排除分数")
    );
    const methods = reportMethods();
    const rows = methods.map((method) => {
      const row = element("tr");
      const name = element("td", "", method.label || methodLabels[method.method] || method.method);
      name.append(element("span", "method-table-label", method.method === "caption" ? "人工描述词项匹配" : method.method === "negative" ? "启发式教学方法 · 真实向量" : "真实图文向量"));
      row.append(name);
      ["hit_at_1", "hit_at_5", "recall_at_5", "map_at_5"].forEach((key) => {
        const cell = element("td", "", metric(method.metrics?.[key]));
        cell.title = `原始值：${method.metrics?.[key] ?? "未提供"}`;
        row.append(cell);
      });
      row.append(element("td", "", duration(method.elapsed_ms)));
      return row;
    });
    $("metrics-body").replaceChildren(...rows);
    $("comparison-bars").replaceChildren(...methods.map((method) => {
      const bar = element("div", "comparison-bar");
      const title = element("div");
      title.append(element("span", "", method.label || methodLabels[method.method]), element("strong", "", metric(method.metrics?.hit_at_5)));
      const track = element("div", "bar-track");
      const fill = element("div", `bar-fill ${["clip", "negative"].includes(method.method) ? method.method : ""}`);
      fill.style.width = `${Math.max(0, Math.min(1, Number(method.metrics?.hit_at_5) || 0)) * 100}%`;
      track.append(fill);
      bar.append(title, track);
      return bar;
    }));
    const selected = $("report-method").value;
    $("report-method").replaceChildren(...methods.map((method) => {
      const option = element("option", "", method.label || methodLabels[method.method]);
      option.value = method.method;
      return option;
    }));
    if (methods.some((method) => method.method === selected)) $("report-method").value = selected;
    renderMethodDetails();
  }

  function renderMethodDetails() {
    const method = reportMethods().find((item) => item.method === $("report-method").value);
    const categories = Array.isArray(method?.categories) ? method.categories : [];
    $("categories-body").replaceChildren(...categories.map((category) => {
      const row = element("tr");
      [category.category, category.count, metric(category.metrics?.hit_at_5), metric(category.metrics?.recall_at_5)].forEach((value) => row.append(element("td", "", value)));
      return row;
    }));
    const rows = Array.isArray(method?.rows) ? method.rows : [];
    const failures = rows.filter((row) => Number(row.hit_at_1) === 0);
    $("failure-count").textContent = `${failures.length} / ${rows.length} 条 Top-1 未命中`;
    $("failure-list").replaceChildren(...failures.map((row) => {
      const details = element("details", "failure-card");
      const summary = element("summary");
      summary.append(element("span", "", row.text), element("small", "", `${row.category || "未分类"} · ${row.id}`));
      const content = element("div", "failure-content");
      const meta = element("p", "failure-meta");
      meta.append(element("strong", "", "标注正例："), document.createTextNode(Array.isArray(row.relevant_ids) ? row.relevant_ids.join("、") : "未提供"));
      meta.append(element("br"), document.createTextNode(`Hit@1 ${metric(row.hit_at_1)} · Hit@5 ${metric(row.hit_at_5)} · Recall@5 ${metric(row.recall_at_5)} · AP@5 ${metric(row.map_at_5)}`));
      const thumbnails = element("div", "failure-thumbnails");
      (Array.isArray(row.top_results) ? row.top_results.slice(0, 5) : []).forEach((item, index) => {
        const card = element("div", "failure-thumbnail");
        card.append(createImage(item, "failure-image"), element("strong", "", `${index + 1}. ${item.title || item.id}`), element("span", "", `分数 ${rawScore(item.score)}`));
        thumbnails.append(card);
      });
      content.append(meta, thumbnails);
      details.append(summary, content);
      return details;
    }));
    if (!failures.length) $("failure-list").append(element("p", "failure-none", rows.length ? "当前方法在这组查询的首项均为标注正例。" : "报告中没有可展示的逐查询记录。"));
  }

  async function loadReport() {
    if (state.reportLoading) return false;
    state.reportLoading = true;
    try { renderReport(await api("/api/report")); return true; }
    catch (error) { showError("evaluate-error", error.message); return false; }
    finally { state.reportLoading = false; }
  }

  function download(content, type, filename) {
    const url = URL.createObjectURL(new Blob([content], {type}));
    const link = element("a");
    link.href = url;
    link.download = filename;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function filenameDate() { return new Date().toISOString().slice(0, 10); }
  function mdCell(value) { return String(value ?? "—").replace(/\|/g, "\\|").replace(/[\r\n]+/g, " "); }

  function reportMarkdown(report) {
    const lines = ["# 本地中文图文检索实验报告", "", `- 运行时间：${report.created_at || "未提供"}`, `- 完整图库：${report.gallery_count ?? "未提供"} 张`, `- 标注查询：${report.query_count ?? "未提供"} 条`, `- 查询划分：${report.split || "未提供"}`, `- 模型：${report.model || "未提供"}`, `- 排除权重：${report.negative_weight ?? "未提供"}`, "", "这是自建教学图库上的实际实验，不是论文标准基准；分数不是概率。", ""];
    if (Array.isArray(report.warnings) && report.warnings.length) lines.push("## 运行限制", "", ...report.warnings.map((warning) => `- ${warning}`), "");
    lines.push("## 方法对比", "", "| 方法 | Hit@1 | Hit@5 | Recall@5 | mAP@5 | 耗时 |", "| --- | ---: | ---: | ---: | ---: | ---: |");
    (Array.isArray(report.methods) ? report.methods : []).forEach((method) => {
      const values = [method.label || methodLabels[method.method] || method.method, ...["hit_at_1", "hit_at_5", "recall_at_5", "map_at_5"].map((key) => metric(method.metrics?.[key])), duration(method.elapsed_ms)];
      lines.push(`| ${values.map(mdCell).join(" | ")} |`);
    });
    lines.push("", "Hit@K：前 K 项至少命中一个正例的查询比例。Recall@K：前 K 项覆盖的正例比例。mAP@K：考虑正例排名的平均检索质量。", "");
    (Array.isArray(report.methods) ? report.methods : []).forEach((method) => {
      lines.push(`## ${method.label || methodLabels[method.method] || method.method}`, "", "| 查询类型 | 数量 | Hit@5 | Recall@5 |", "| --- | ---: | ---: | ---: |");
      (Array.isArray(method.categories) ? method.categories : []).forEach((category) => lines.push(`| ${[category.category, category.count, metric(category.metrics?.hit_at_5), metric(category.metrics?.recall_at_5)].map(mdCell).join(" | ")} |`));
      lines.push("", "### 逐查询记录", "", "| ID | 查询 | 类型 | 标注正例 | 返回排序 | Hit@5 | Recall@5 | mAP@5 |", "| --- | --- | --- | --- | --- | ---: | ---: | ---: |");
      (Array.isArray(method.rows) ? method.rows : []).forEach((row) => {
        const values = [row.id, row.text, row.category, Array.isArray(row.relevant_ids) ? row.relevant_ids.join(", ") : "", Array.isArray(row.ranked_ids) ? row.ranked_ids.join(", ") : "", metric(row.hit_at_5), metric(row.recall_at_5), metric(row.map_at_5)];
        lines.push(`| ${values.map(mdCell).join(" | ")} |`);
      });
      lines.push("");
    });
    return lines.join("\n");
  }

  async function loadNotes() {
    $("notes-content").disabled = true;
    try {
      const data = await api("/api/notes", undefined, 20000);
      $("notes-content").value = typeof data.content === "string" ? data.content : "";
      $("notes-save-status").textContent = data.updated_at ? `上次保存：${formatTime(data.updated_at)}` : "尚无已保存笔记";
      state.notesDirty = false;
    } catch (error) {
      showError("notes-error", error.message);
      $("notes-save-status").textContent = "未能读取笔记；保存前请确认本地服务状态";
    } finally { $("notes-content").disabled = false; }
  }

  function markNotesDirty() {
    state.notesDirty = true;
    $("notes-save-status").textContent = "有尚未保存的修改";
  }

  async function saveNotes() {
    if (state.savingNotes) return;
    if ($("notes-content").value.length > 30000) { showError("notes-error", "笔记应为不超过 30000 字的文本。"); return; }
    state.savingNotes = true;
    $("save-notes").disabled = true;
    $("save-notes").textContent = "保存中…";
    showError("notes-error", "");
    const submitted = $("notes-content").value;
    try {
      const data = await api("/api/notes", {content: submitted}, 20000);
      state.notesDirty = $("notes-content").value !== submitted;
      $("notes-save-status").textContent = state.notesDirty ? "刚才的内容已保存；仍有新的修改" : data.updated_at ? `已保存：${formatTime(data.updated_at)}` : "已保存到本地";
      toast("笔记已保存到本地。");
    } catch (error) { showError("notes-error", error.message); }
    finally { state.savingNotes = false; $("save-notes").disabled = false; $("save-notes").textContent = "保存笔记"; }
  }

  function bindEvents() {
    document.querySelectorAll(".nav-item").forEach((button) => button.addEventListener("click", () => switchView(button.dataset.view)));
    window.addEventListener("hashchange", () => switchView(window.location.hash.slice(1)));
    document.querySelectorAll("[data-example]").forEach((button) => button.addEventListener("click", () => {
      $("query").value = button.dataset.example;
      $("query-count").textContent = `${$("query").value.length} / 300`;
      $("query").focus();
    }));
    $("query").addEventListener("input", () => { $("query-count").textContent = `${$("query").value.length} / 300`; });
    $("query").addEventListener("keydown", (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") { event.preventDefault(); $("search-form").requestSubmit(); }
    });
    document.querySelectorAll('input[name="method"]').forEach((input) => input.addEventListener("change", updateControls));
    $("negative-weight").addEventListener("input", () => { $("negative-weight-value").textContent = Number($("negative-weight").value).toFixed(2); });
    $("search-form").addEventListener("submit", search);
    $("prepare-button").addEventListener("click", () => startTask("prepare", {}));
    $("evaluate-form").addEventListener("submit", (event) => {
      event.preventDefault();
      if ($("evaluate-button").disabled) return;
      const weight = Number($("evaluation-weight").value);
      if (!Number.isFinite(weight) || weight < 0 || weight > 1) { showError("evaluate-error", "排除权重必须在 0 到 1 之间。"); return; }
      startTask("evaluate", {negative_weight: weight, split: $("evaluation-split").value});
    });
    $("reset-gallery").addEventListener("click", () => { state.lastSearch = null; renderGallery(); });
    $("show-all-gallery").addEventListener("click", () => { state.galleryExpanded = !state.galleryExpanded; renderGallery(); });
    $("report-method").addEventListener("change", renderMethodDetails);
    $("export-json").addEventListener("click", async () => {
      showError("evaluate-error", "");
      try { const report = await api("/api/export"); download(JSON.stringify(report, null, 2), "application/json;charset=utf-8", `retrieval-report-${filenameDate()}.json`); }
      catch (error) { showError("evaluate-error", error.message); }
    });
    $("export-report-md").addEventListener("click", () => { if (state.report) download(reportMarkdown(state.report), "text/markdown;charset=utf-8", `retrieval-report-${filenameDate()}.md`); });
    $("notes-content").addEventListener("input", markNotesDirty);
    $("save-notes").addEventListener("click", saveNotes);
    $("export-notes").addEventListener("click", () => download($("notes-content").value, "text/markdown;charset=utf-8", `learning-notes-${filenameDate()}.md`));
    $("insert-template").addEventListener("click", () => {
      const template = "## 问题\n我想验证什么？\n\n## 假设\n预期结果是什么，为什么？\n\n## 实验配置\n查询：\n方法 / Top K / 排除权重：\n图库 / 查询划分：\n\n## 观察\n记录实际结果、失败案例与反例：\n\n## 下一步\n下次改变哪个条件，如何检验？\n";
      const editor = $("notes-content");
      const content = editor.value ? `${editor.value}\n\n${template}` : template;
      if (content.length > 30000) { showError("notes-error", "加入模板会超过 30000 字，请先缩短笔记内容。"); return; }
      editor.value = content;
      markNotesDirty();
      editor.focus();
      toast("已插入思考提示，请填写你实际观察到的证据。");
    });
    window.addEventListener("beforeunload", (event) => {
      if (state.notesDirty) { event.preventDefault(); event.returnValue = ""; }
    });
  }

  async function initialize() {
    bindEvents();
    switchView(window.location.hash.slice(1));
    updateControls();
    $("image-grid").replaceChildren(...Array.from({length: 4}, () => element("div", "skeleton-card")));
    await Promise.allSettled([loadGallery(), loadNotes(), pollStatus()]);
  }

  initialize();
})();
