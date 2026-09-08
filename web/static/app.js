(() => {
  const $ = (id) => document.getElementById(id);
  const lobby = $("lobby");
  const table = $("table");
  const boardEl = $("board");
  const statusEl = $("status");
  const commentEl = $("comment");
  const movesEl = $("moves");
  const shareUrl = $("shareUrl");
  const roomMeta = $("roomMeta");
  const poolBox = $("poolBox");
  const poolEl = $("pool");
  const modeBadge = $("modeBadge");
  const lobbyHint = $("lobbyHint");
  const engineHint = $("engineHint");
  const tableEngine = $("tableEngine");
  const phaseHint = $("phaseHint");

  let catalog = null;
  let ws = null;
  let mode = "jieqi";
  let state = null;
  let role = "spectator";
  let selected = null;
  let flipped = false;
  let roomId = new URLSearchParams(location.search).get("room") || "";
  let pendingDest = null;

  const FILES = "abcdefghi";
  const SIM_NAMES = { r: "车", n: "马", c: "炮", a: "仕", b: "相", p: "兵" };
  const GUESS_NAMES = { k: "将帅", r: "车", n: "马", c: "炮", a: "仕", b: "相", p: "兵" };

  fetch("/api/modes")
    .then((r) => r.json())
    .then((meta) => {
      catalog = meta;
      buildLobby(meta);
    })
    .catch(() => buildLobby({
      default_mode: "jieqi",
      modes: [
        { id: "jieqi", name: "揭棋", short: "默认玩法", rules: ["将帅明放，其余扣放，走子翻开。"], rules_title: "揭棋", diagram: "start-dark" },
        { id: "xiangqi", name: "中国象棋", short: "传统规则", rules: ["红先黑后。"], rules_title: "中国象棋", diagram: "start-full" },
      ],
      levels: [...Array(10)].map((_, i) => ({ value: i + 1, label: String(i + 1) })).concat([{ value: 99, label: "ZZH" }]),
    }));

  function buildLobby(meta) {
    const grid = $("modeGrid");
    grid.innerHTML = "";
    (meta.modes || []).forEach((m, i) => {
      const btn = document.createElement("button");
      btn.className = "mode-card" + (m.id === "jieqi" ? " jieqi" : "") + (m.group === "imbalance" ? " imbalance" : "");
      if ((meta.default_mode || "jieqi") === m.id || (!meta.default_mode && i === 0)) btn.classList.add("active");
      btn.dataset.mode = m.id;
      btn.innerHTML = `<strong>${m.name}</strong><span>${m.short || ""}</span>`;
      btn.onclick = () => selectMode(m);
      grid.appendChild(btn);
    });
    mode = meta.default_mode || "jieqi";
    const title = meta.title || (meta.name ? `${meta.name} — ${meta.developer || "ZZH"}` : "");
    if (title) {
      document.title = title;
      const h1 = document.querySelector(".brand h1");
      if (h1) h1.textContent = title;
    }
    if (meta.github) {
      const gl = document.getElementById("githubLink");
      if (gl) gl.href = meta.github;
    }
    fillLevelSelect($("level"), meta.levels, 5);
    fillLevelSelect($("levelRed"), meta.levels, 5);
    fillLevelSelect($("levelBlack"), meta.levels, 8);
    $("level").onchange = () => {
      updateEngineHint();
      if (state) send({ type: "level", level: Number($("level").value) });
    };
    updateEngineHint();
    loadAis(mode);
    if (!roomId) {
      const m = (meta.modes || []).find((x) => x.id === mode);
      if (m) showRules(m, true);
    }
  }

  function fillLevelSelect(sel, levels, prefer) {
    if (!sel) return;
    sel.innerHTML = "";
    (levels || []).forEach((lv) => {
      const o = document.createElement("option");
      o.value = lv.value;
      o.textContent = lv.label;
      if (lv.value === prefer) o.selected = true;
      sel.appendChild(o);
    });
  }

  function loadAis(md) {
    fetch("/api/ais?mode=" + encodeURIComponent(md || mode || "jieqi"))
      .then((r) => r.json())
      .then((data) => {
        const ids = (data.engines || []).map((e) => e.id);
        const pick = (...cands) => cands.find((id) => ids.includes(id)) || "auto";
        fillEngineSelect($("aiRed"), data.engines, pick("selftrain", "variant-search", "heuristic"));
        fillEngineSelect($("aiBlack"), data.engines, pick("pikafish", "variant-search", "heuristic"));
        document.querySelectorAll(".seat-engine").forEach((sel) => {
          const cur = sel.value;
          fillEngineSelect(sel, data.engines, cur || "auto");
        });
      })
      .catch(() => {});
  }

  function fillEngineSelect(sel, engines, prefer) {
    if (!sel) return;
    const keep = prefer || sel.value;
    sel.innerHTML = "";
    const auto = document.createElement("option");
    auto.value = "auto";
    auto.textContent = "自动";
    sel.appendChild(auto);
    (engines || []).forEach((e) => {
      if (!e.available && e.kind !== "selftrain") return;
      const o = document.createElement("option");
      o.value = e.id;
      o.textContent = e.name + (e.available ? "" : "（未接入）");
      sel.appendChild(o);
    });
    const ids = [...sel.options].map((o) => o.value);
    sel.value = ids.includes(keep) ? keep : (ids.includes("selftrain") ? "selftrain" : "auto");
  }

  function selectMode(m) {
    document.querySelectorAll(".mode-card").forEach((b) => b.classList.toggle("active", b.dataset.mode === m.id));
    mode = m.id;
    updateEngineHint();
    loadAis(mode);
    showRules(m, false);
  }

  function updateEngineHint() {
    if (!catalog) return;
    const lv = Number($("level").value || 5);
    const m = (catalog.modes || []).find((x) => x.id === mode);
    const name = m ? m.name : mode;
    fetch("/api/info")
      .then((r) => r.json())
      .then((info) => {
        const modes = info.modes || [];
        const hit = modes.find((x) => x.id === mode);
        engineHint.textContent = `${name} · 难度 ${lv === 99 ? "自训练" : lv}（引擎与参数在对局侧栏同步显示）`;
        if (hit) engineHint.textContent = `${name} · 点选难度后，对局中会显示当前引擎名称、算法与搜索参数`;
      })
      .catch(() => {
        engineHint.textContent = `${name} · 难度 ${lv === 99 ? "自训练" : lv}`;
      });
  }

  function showRules(m, silentFirst) {
    $("ruleTitle").textContent = m.rules_title || m.name;
    $("ruleList").innerHTML = (m.rules || []).map((t) => `<li>${t}</li>`).join("");
    $("ruleDiagram").innerHTML = diagramHtml(m.diagram, m.id);
    if (silentFirst && mode === "jieqi") {
      /* 默认揭棋：仍弹出一次，方便上手 */
    }
    $("ruleModal").hidden = false;
  }

  $("ruleOk").onclick = () => {
    $("ruleModal").hidden = true;
  };

  function diagramHtml(kind, id) {
    if (kind === "anqi") {
      return `<div class="mini-board anqi">${cells(8, 4, true)}</div><p class="tiny">4×8 全扣放，翻子或走一格</p>`;
    }
    if (kind === "manchu") {
      return `<div class="mini-board">${cells(9, 10, false, "manchu")}</div><p class="tiny">红方仅一枚满洲车（车马炮）</p>`;
    }
    if (kind === "bawang") {
      return `<div class="mini-board">${cells(9, 10, false, "bawang")}</div><p class="tiny">红方帅+车，车可连走两步</p>`;
    }
    if (kind === "wuhu") {
      return `<div class="mini-board">${cells(9, 10, false, "wuhu")}</div><p class="tiny">红方五兵仕相，兵可连动</p>`;
    }
    const dark = kind === "start-dark" || id === "jieqi" || id === "zhencha";
    return `<div class="mini-board">${cells(9, 10, dark)}</div><p class="tiny">${dark ? "将帅明放，其余可扣" : "开局全明"}</p>`;
  }

  function cells(files, ranks, dark, variant) {
    let html = "";
    for (let r = ranks - 1; r >= 0; r--) {
      for (let f = 0; f < files; f++) {
        let cls = "c";
        if (variant === "manchu" && r === 0 && f === 0) cls += " super";
        if (variant === "bawang" && r === 0 && (f === 0 || f === 4)) cls += " keep";
        if (variant === "wuhu" && r === 3 && f % 2 === 0) cls += " pawn";
        if (dark && !(files === 9 && ((r === 0 || r === 9) && f === 4))) cls += " dk";
        html += `<i class="${cls}"></i>`;
      }
    }
    return html;
  }

  $("btnAi").onclick = () => startGame("ai");
  $("btnAiMatch").onclick = () => startGame("aivsai");
  $("btnRoom").onclick = () => startGame("human");
  $("btnPickAi").onclick = () => $("aiFile").click();
  $("aiFile").onchange = () => {
    const f = $("aiFile").files && $("aiFile").files[0];
    if (!f) return;
    $("aiFileName").value = f.name;
    const body = new FormData();
    body.append("file", f);
    fetch("/api/local-ai", { method: "POST", body })
      .then((r) => r.json())
      .then((res) => {
        if (!res.ok) {
          lobbyHint.textContent = res.message || "上传失败";
          return;
        }
        lobbyHint.textContent = "已加入本地 AI：" + res.name;
        loadAis(mode);
        setTimeout(() => {
          $("aiRed").value = res.id;
          $("aiBlack").value = res.id;
        }, 200);
      })
      .catch(() => (lobbyHint.textContent = "上传失败"));
  };
  $("btnJoin").onclick = () => joinGame(($("joinCode").value || "").trim());
  $("btnCopy").onclick = async () => {
    try {
      await navigator.clipboard.writeText(shareUrl.value);
      $("btnCopy").textContent = "已复制";
      setTimeout(() => ($("btnCopy").textContent = "复制"), 1200);
    } catch {
      shareUrl.select();
    }
  };
  $("btnLobby").onclick = () => (location.href = location.pathname);
  $("btnResign").onclick = () => send({ type: "resign" });
  $("btnNew").onclick = () => send({ type: "new_game", mode });
  $("btnReady").onclick = () => send({ type: "move", iccs: "ready" });
  document.querySelectorAll(".seat button").forEach((btn) => {
    btn.onclick = () => send({ type: "seat", color: btn.dataset.seat, kind: btn.dataset.kind });
  });
  document.querySelectorAll(".seat-engine").forEach((sel) => {
    sel.onchange = () => send({
      type: "seat",
      color: sel.dataset.seatEngine,
      kind: "ai",
      engine: sel.value,
    });
  });

  if (roomId) {
    $("joinCode").value = roomId.toUpperCase();
    connect(() => send({ type: "join", room: roomId, name: nick() }));
  }

  function nick() {
    return ($("nick").value || "棋友").trim() || "棋友";
  }

  function startGame(vs) {
    const active = document.querySelector(".mode-card.active");
    mode = (active && active.dataset.mode) || "jieqi";
    connect(() => {
      const payload = {
        type: "create",
        mode,
        vs,
        color: $("color").value,
        level: Number($("level").value),
        name: nick(),
        engine: Number($("level").value) === 99 ? "selftrain" : "auto",
      };
      if (vs === "aivsai") {
        payload.w_engine = $("aiRed").value;
        payload.b_engine = $("aiBlack").value;
        payload.w_level = Number($("levelRed").value);
        payload.b_level = Number($("levelBlack").value);
        payload.engine = payload.w_engine;
      }
      send(payload);
    });
  }

  function joinGame(code) {
    if (!code) {
      lobbyHint.textContent = "请输入房间号";
      return;
    }
    connect(() => send({ type: "join", room: code, name: nick(), color: $("color").value }));
  }

  function connect(onOpen) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      onOpen && onOpen();
      return;
    }
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/ws`);
    ws.onopen = () => onOpen && onOpen();
    ws.onclose = () => {
      if (table.hidden === false) statusEl.textContent = "连接已断开，请刷新";
    };
    ws.onerror = () => (lobbyHint.textContent = "无法连接服务器");
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.type === "hello" && msg.info) catalog = Object.assign(catalog || {}, msg.info);
      if (msg.type === "error") {
        lobbyHint.textContent = msg.message;
        commentEl.textContent = msg.message;
        return;
      }
      if (msg.type === "joined") {
        role = msg.role;
        roomId = msg.room;
        showTable();
        const u = new URL(location.href);
        u.searchParams.set("room", msg.room);
        history.replaceState(null, "", u);
        shareUrl.value = absUrl(msg.share_url);
        return;
      }
      if (msg.type === "state") {
        state = msg;
        showTable();
        render();
        return;
      }
      if (msg.type === "ai_comment") {
        const who = msg.side === "b" ? "黑" : "红";
        const name = msg.engine_name || msg.engine;
        commentEl.textContent = `${who}/${name}${msg.fallback ? "（兜底）" : ""}：${msg.comment || msg.move}`;
      }
    };
  }

  function send(obj) {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      lobbyHint.textContent = "尚未连接";
      return;
    }
    ws.send(JSON.stringify(obj));
  }

  function absUrl(path) {
    if (!path) return location.href;
    if (path.startsWith("http")) return path;
    return location.origin + path;
  }

  function showTable() {
    lobby.hidden = true;
    table.hidden = false;
    $("btnLobby").hidden = false;
  }

  function boardSpec() {
    const b = (state && state.board) || { files: 9, ranks: 10 };
    return { files: b.files || 9, ranks: b.ranks || 10, river: b.river !== false, palace: b.palace !== false };
  }

  function iccsOf(f, r) {
    return FILES[f] + r;
  }

  function canMove() {
    if (!state || state.over) return false;
    const seat = state.seats[state.side];
    if (seat.kind === "ai") return false;
    if (role === state.side) return true;
    if (!seat.occupied) return true;
    return false;
  }

  function render() {
    if (!state) return;
    mode = state.mode;
    const spec = boardSpec();
    modeBadge.textContent = state.mode_name || mode;
    modeBadge.className = "badge " + (mode === "jieqi" ? "jieqi" : "xiangqi");
    boardEl.classList.toggle("jieqi-board", mode === "jieqi" || mode === "zhencha");
    boardEl.classList.toggle("board-anqi", spec.ranks === 4);
    boardEl.style.aspectRatio = `${spec.files} / ${spec.ranks + 0.15}`;
    flipped = role === "b";
    selected = selected;
    drawBoard();
    drawPieces();
    $("seatW").textContent = labelSeat(state.seats.w);
    $("seatB").textContent = labelSeat(state.seats.b);
    syncSeatEngine("w");
    syncSeatEngine("b");
    shareUrl.value = absUrl(state.share_url);
    roomMeta.textContent = `房间 ${state.room} · 在线 ${state.viewers} · 你是${roleText(role)}`;
    statusEl.textContent = statusText();
    if (state.ai_profile) {
      const p = state.ai_profile;
      tableEngine.textContent = `${p.label} · ${p.engine} · ${p.params}`;
    }
    movesEl.innerHTML = "";
    (state.history || []).forEach((mv, i) => {
      const li = document.createElement("li");
      li.textContent = `${i % 2 === 0 ? "红" : "黑"} ${mv}`;
      movesEl.appendChild(li);
    });
    movesEl.scrollTop = movesEl.scrollHeight;
    if (state.pool) {
      poolBox.hidden = false;
      poolEl.textContent = `红 ${fmtPool(state.pool.w)}  |  黑 ${fmtPool(state.pool.b)}`;
    } else poolBox.hidden = true;
    phaseHint.textContent = state.hint || "";
    $("btnReady").hidden = !(state.phase === "setup" && canMove());
    if (state.banner) commentEl.textContent = state.banner;
    if (state.last_event && state.last_event.flip) {
      const n = (state.names || {})[state.last_event.flip] || state.last_event.flip;
      commentEl.textContent = (state.banner ? state.banner + " · " : "") + `翻开「${n}」`;
    }
  }

  function syncSeatEngine(color) {
    const sel = document.querySelector(`[data-seat-engine="${color}"]`);
    if (!sel || !state || !state.seats) return;
    const want = state.seats[color].engine_id || "auto";
    if (state.engines && sel.dataset.modeKey !== state.mode) {
      fillEngineSelect(sel, state.engines, want);
      sel.dataset.modeKey = state.mode;
    } else if ([...sel.options].some((o) => o.value === want)) {
      sel.value = want;
    }
  }

  function labelSeat(seat) {
    if (seat.kind === "ai") {
      const lv = seat.level === 99 ? "自训练" : (seat.level || "");
      return (seat.name || "AI") + (lv ? ` · ${lv}` : "");
    }
    return seat.occupied ? seat.name : "空位/本机可走";
  }

  function roleText(r) {
    if (r === "w") return "红方";
    if (r === "b") return "黑方";
    return "观战";
  }

  function statusText() {
    if (!state) return "";
    if (state.over) {
      if (state.winner === "draw") return "和棋";
      return (state.winner === "w" ? "红方" : "黑方") + "胜";
    }
    if (state.phase === "setup") return "布阵阶段";
    if (state.phase === "first-flip") return "先手翻子定色";
    const turn = state.side === "w" ? "红方" : "黑方";
    const chk = state.check ? "（将军）" : "";
    const extra = state.actions_left > 1 ? `（本回合余 ${state.actions_left} 步）` : "";
    const who = state.seats[state.side].kind === "ai" ? "AI 思考中" : "行棋";
    return `${turn}${who}${chk}${extra}`;
  }

  function fmtPool(p) {
    const names = { R: "车", N: "马", B: "相", A: "仕", C: "炮", P: "兵" };
    return Object.entries(p || {})
      .filter(([, n]) => n > 0)
      .map(([k, n]) => `${names[k] || k}${n}`)
      .join(" ");
  }

  function vis(file, rank) {
    const { files, ranks } = boardSpec();
    if (!flipped) return { x: file, y: ranks - 1 - rank };
    return { x: files - 1 - file, y: rank };
  }

  function posStyle(file, rank) {
    const { files, ranks } = boardSpec();
    const v = vis(file, rank);
    const left = ((v.x + 0.5) / files) * 100;
    const top = ((v.y + 0.5) / ranks) * 100;
    return `left:${left}%;top:${top}%;`;
  }

  function pt(file, rank) {
    const v = vis(file, rank);
    return [v.x + 0.5, v.y + 0.5];
  }

  function drawBoard() {
    const spec = boardSpec();
    const { files, ranks, river, palace } = spec;
    const ns = "http://www.w3.org/2000/svg";
    boardEl.innerHTML = "";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("class", "grid-svg");
    svg.setAttribute("viewBox", `0 0 ${files} ${ranks}`);
    svg.setAttribute("preserveAspectRatio", "none");
    const add = (name, attrs) => {
      const el = document.createElementNS(ns, name);
      for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
      svg.appendChild(el);
    };
    const line = (f1, r1, f2, r2, w = 0.04) => {
      const a = pt(f1, r1), b = pt(f2, r2);
      add("line", { x1: a[0], y1: a[1], x2: b[0], y2: b[1], stroke: "#5c3317", "stroke-width": w });
    };
    const lastF = files - 1, lastR = ranks - 1;
    for (let r = 0; r < ranks; r++) line(0, r, lastF, r);
    if (river && ranks === 10) {
      for (let f = 0; f < files; f++) {
        line(f, 0, f, 4);
        line(f, 5, f, 9);
      }
      line(0, 0, 0, 9, 0.05);
      line(lastF, 0, lastF, 9, 0.05);
    } else {
      for (let f = 0; f < files; f++) line(f, 0, f, lastR);
    }
    if (palace && ranks === 10 && files === 9) {
      line(3, 0, 5, 2);
      line(5, 0, 3, 2);
      line(3, 9, 5, 7);
      line(5, 9, 3, 7);
    }
    if (river && ranks === 10) {
      const riverEl = document.createElementNS(ns, "text");
      const mid = pt(4, 4), mid2 = pt(4, 5);
      riverEl.setAttribute("x", String(files / 2));
      riverEl.setAttribute("y", String((mid[1] + mid2[1]) / 2 + 0.12));
      riverEl.setAttribute("text-anchor", "middle");
      riverEl.setAttribute("fill", "#7a1f1f");
      riverEl.setAttribute("font-size", "0.42");
      riverEl.textContent = flipped ? "漢界    楚河" : "楚河    漢界";
      svg.appendChild(riverEl);
    }
    boardEl.appendChild(svg);
  }

  function legalKeys() {
    return state.legal || [];
  }

  function destsFrom(sel) {
    const map = {};
    legalKeys().forEach((mv) => {
      const core = mv.split(":")[0];
      if (core.slice(0, 2) !== sel) return;
      const dest = core.slice(2, 4);
      (map[dest] || (map[dest] = [])).push(mv);
    });
    return map;
  }

  function drawPieces() {
    const spec = boardSpec();
    const last = (state.last_move || "").split(":")[0];
    const from = last.slice(0, 2);
    const to = last.slice(2, 4);
    (state.pieces || []).forEach((p) => {
      const el = document.createElement("div");
      const color = p.color === "w" ? "red" : "black";
      el.className = `piece ${color}${p.dark ? " dark" : ""}${p.super ? " super" : ""}`;
      if (!p.dark) el.textContent = p.name;
      el.style.cssText = posStyle(p.file, p.rank);
      if (spec.ranks === 4) {
        el.style.width = "11.5%";
        el.style.height = "22%";
      }
      const sq = iccsOf(p.file, p.rank);
      if (selected && selected === sq) el.classList.add("selected");
      if (sq === from || sq === to) el.classList.add("last");
      el.onclick = (ev) => {
        ev.stopPropagation();
        onClickSquare(p.file, p.rank);
      };
      boardEl.appendChild(el);
    });
    if (selected) {
      const dmap = destsFrom(selected);
      Object.keys(dmap).forEach((dest) => {
        const f = FILES.indexOf(dest[0]);
        const r = Number(dest.slice(1));
        const mark = document.createElement("div");
        const occ = (state.pieces || []).some((p) => p.file === f && p.rank === r);
        mark.className = "marker" + (occ ? " cap" : "");
        mark.style.cssText = posStyle(f, r);
        boardEl.appendChild(mark);
      });
    }
    boardEl.onclick = (ev) => {
      if (ev.target !== boardEl && !ev.target.classList.contains("grid-svg") && ev.target.tagName !== "line" && ev.target.tagName !== "svg" && ev.target.tagName !== "rect" && ev.target.tagName !== "text") {
        return;
      }
      const spec2 = boardSpec();
      const rect = boardEl.getBoundingClientRect();
      const px = (ev.clientX - rect.left) / rect.width;
      const py = (ev.clientY - rect.top) / rect.height;
      let vx = Math.round(px * spec2.files - 0.5);
      let vy = Math.round(py * spec2.ranks - 0.5);
      vx = Math.max(0, Math.min(spec2.files - 1, vx));
      vy = Math.max(0, Math.min(spec2.ranks - 1, vy));
      const file = flipped ? spec2.files - 1 - vx : vx;
      const rank = flipped ? vy : spec2.ranks - 1 - vy;
      onClickSquare(file, rank);
    };
  }

  function onClickSquare(file, rank) {
    if (!canMove()) return;
    const sq = iccsOf(file, rank);
    if (state.phase === "setup") {
      const tog = `toggle:${sq}`;
      if ((state.legal || []).includes(tog)) {
        send({ type: "move", iccs: tog });
        beep();
      }
      return;
    }
    const flipMv = sq + sq;
    const legal = state.legal || [];
    if (!selected && legal.some((m) => m.split(":")[0] === flipMv)) {
      send({ type: "move", iccs: flipMv });
      beep();
      return;
    }
    if (selected) {
      const dmap = destsFrom(selected);
      const cands = dmap[sq] || [];
      if (cands.length === 1) {
        sendMove(cands[0]);
        selected = null;
        return;
      }
      if (cands.length > 1) {
        pickMove(cands);
        return;
      }
    }
    const mine = (state.pieces || []).find((p) => p.file === file && p.rank === rank && p.color === state.side);
    if (mine) {
      selected = sq;
      render();
    } else {
      selected = null;
      render();
    }
  }

  function sendMove(iccs) {
    send({ type: "move", iccs });
    selected = null;
    pendingDest = null;
    beep();
  }

  function pickMove(cands) {
    const types = [...new Set(cands.map((c) => (c.split(":")[1] || "")))];
    const needGuess = cands.some((c) => c.split(":").length >= 3);
    const title = needGuess && types.length <= 1 ? "猜对方暗子真身" : "选择伪装兵种";
    $("pickTitle").textContent = title;
    const box = $("pickBtns");
    box.innerHTML = "";
    const firstKey = needGuess && types.length === 1 ? 2 : 1;
    const keys = [...new Set(cands.map((c) => c.split(":")[firstKey] || c.split(":")[1]))];
    keys.forEach((k) => {
      const btn = document.createElement("button");
      btn.textContent = (firstKey === 2 ? GUESS_NAMES : SIM_NAMES)[k] || k;
      btn.onclick = () => {
        const next = cands.filter((c) => (c.split(":")[firstKey] || c.split(":")[1]) === k);
        $("pickModal").hidden = true;
        if (next.length === 1) sendMove(next[0]);
        else if (next.length > 1 && firstKey === 1) {
          const gtitle = "猜对方暗子真身";
          $("pickTitle").textContent = gtitle;
          box.innerHTML = "";
          const guesses = [...new Set(next.map((c) => c.split(":")[2]))];
          guesses.forEach((g) => {
            const b2 = document.createElement("button");
            b2.textContent = GUESS_NAMES[g] || g;
            b2.onclick = () => {
              $("pickModal").hidden = true;
              const hit = next.find((c) => c.split(":")[2] === g);
              if (hit) sendMove(hit);
            };
            box.appendChild(b2);
          });
          $("pickModal").hidden = false;
        } else sendMove(next[0]);
      };
      box.appendChild(btn);
    });
    $("pickModal").hidden = false;
  }

  function beep() {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const o = ctx.createOscillator();
      const g = ctx.createGain();
      o.frequency.value = 520;
      o.connect(g);
      g.connect(ctx.destination);
      g.gain.value = 0.04;
      o.start();
      o.stop(ctx.currentTime + 0.07);
    } catch (_) {}
  }
})();
