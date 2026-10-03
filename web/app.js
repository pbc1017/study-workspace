"use strict";
const app = document.querySelector("#app");
const state = {
  projects: [],
  project: null,
  session: null,
  index: 0,
  reviewFilter: "all",
  busy: false,
};
let timer = null,
  noticeTimer = null;
const h = (x) =>
  String(x ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const date = (x) =>
  x
    ? new Date(x).toLocaleString("ko-KR", {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "—";
const profile = (x) =>
  ({
    general: "자유 학습",
    school: "고등학교",
    university: "대학교",
    certification: "자격증",
    "aws-aif": "AWS 자격증",
  })[x] || x;
function notify(message) {
  const n = document.querySelector("#notice");
  n.textContent = message;
  n.classList.add("visible");
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => n.classList.remove("visible"), 5000);
}
async function api(path, method = "GET", body) {
  const r = await fetch("/api" + path, {
    method,
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await r.json();
  if (!r.ok) throw Error(data.error || "요청 실패");
  return data;
}
function go(path) {
  history.pushState({}, "", path);
  state.index = 0;
  state.reviewFilter = "all";
  render();
}
function projectPath(tab = "home") {
  return `/projects/${state.project.id}/${tab}`;
}
function inline(s) {
  return h(s)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
}
function md(s) {
  let code = false,
    list = false,
    table = false,
    out = "";
  for (const line of String(s || "").split("\n")) {
    if (line.startsWith("```")) {
      if (list) {
        out += "</ul>";
        list = false;
      }
      out += code ? "</code></pre>" : "<pre><code>";
      code = !code;
      continue;
    }
    if (code) {
      out += h(line) + "\n";
      continue;
    }
    if (line.startsWith("|")) {
      if (!table) {
        out += "<table><tbody>";
        table = true;
      }
      if (!/^\|[\s:|\-]+\|?$/.test(line))
        out +=
          "<tr>" +
          line
            .replace(/^\||\|$/g, "")
            .split("|")
            .map((x) => "<td>" + inline(x.trim()) + "</td>")
            .join("") +
          "</tr>";
      continue;
    }
    if (table) {
      out += "</tbody></table>";
      table = false;
    }
    if (/^[-*] /.test(line)) {
      if (!list) {
        out += "<ul>";
        list = true;
      }
      out += "<li>" + inline(line.slice(2)) + "</li>";
      continue;
    }
    if (list) {
      out += "</ul>";
      list = false;
    }
    const heading = line.match(/^(#{1,6}) (.+)/);
    if (heading)
      out += `<h${Math.min(heading[1].length + 1, 4)}>${inline(heading[2])}</h${Math.min(heading[1].length + 1, 4)}>`;
    else if (line.startsWith("> "))
      out += "<blockquote>" + inline(line.slice(2)) + "</blockquote>";
    else if (line.trim() && line !== "---")
      out += "<p>" + inline(line) + "</p>";
  }
  return (
    out +
    (code ? "</code></pre>" : "") +
    (list ? "</ul>" : "") +
    (table ? "</tbody></table>" : "")
  );
}
function empty(title, description, action = "") {
  return `<div class="empty"><h2>${h(title)}</h2><p>${h(description)}</p>${action}</div>`;
}
function shell(content, tab = "") {
  const p = state.project;
  app.innerHTML = `<div class="shell"><aside class="sidebar"><a class="brand" href="/" data-link><span class="logo">s</span> Study Workspace</a><div class="side-label">${p ? "LEARNING PROJECT" : "YOUR LIBRARY"}</div>${p ? `<div class="project-name">${h(p.title)}</div>` : ""}<nav>${
    p
      ? [
          ["home", "프로젝트 홈"],
          ["materials", "학습 자료"],
          ["concepts", "개념 학습"],
          ["practice", "연습 · 모의고사"],
          ["review", "오답 · 복습"],
          ["history", "학습 기록"],
        ]
          .map(
            ([key, name]) =>
              `<a data-link href="${projectPath(key)}" class="${tab === key ? "active" : ""}">${name}</a>`,
          )
          .join("") + '<a data-link href="/">← 모든 프로젝트</a>'
      : '<a class="active" data-link href="/">학습 프로젝트</a>'
  }</nav><div class="side-footer">차근차근, 나만의 속도로.<br>자료와 학습 기록은 이 기기에 저장됩니다.<br><br>STUDY WORKSPACE · 0.1</div></aside><main class="main"><div class="topbar"><span>${p ? "내 프로젝트 / " + h(p.title) : "나만의 학습 라이브러리"}</span><span class="status"><i class="dot"></i> 로컬 저장</span></div>${content}</main></div>`;
}
async function render() {
  clearInterval(timer);
  state.session = null;
  const path = location.pathname.split("/").filter(Boolean);
  try {
    if (path[0] !== "projects") {
      state.project = null;
      await library();
      return;
    }
    state.project = await api("/projects/" + path[1]);
    const tab = path[2] || "home";
    if (tab === "session") {
      await sessionView(path[3]);
      return;
    }
    const views = {
      home,
      materials,
      concepts,
      practice,
      review,
      history: historyView,
    };
    await (views[tab] || home)(path[3]);
  } catch (e) {
    shell(
      empty(
        "화면을 열 수 없습니다",
        e.message,
        '<a class="link" data-link href="/">프로젝트 목록으로</a>',
      ),
    );
  }
}
async function library() {
  state.projects = await api("/projects");
  shell(
    `<div class="hero"><div><div class="eyebrow">A space to understand</div><h1>배움을 쌓는 나만의 공간</h1><p>강의 노트부터 자격증까지. 자료를 정리하고, 직접 풀어보고,<br>다시 떠올리며 하나씩 내 것으로 만드세요.</p></div><button class="primary" data-action="new-project">＋ 새 프로젝트</button></div><div class="section-title"><h2>학습 프로젝트 <small>${state.projects.length}</small></h2><small>프로젝트마다 독립된 자료와 기록</small></div>${state.projects.length ? `<div class="grid">${state.projects.map((p) => `<a class="card project-card" data-link href="/projects/${p.id}/home"><span class="badge">${h(profile(p.profile))}</span><h2>${h(p.title)}</h2><p>${h(p.description || "내 목표에 맞게 학습을 시작해 보세요.")}</p><footer><span>개념 ${p.topic_count} · 문제 ${p.question_count}</span><span>이어가기 ↗</span></footer></a>`).join("")}</div>` : empty("첫 번째 학습 프로젝트를 만들어 보세요", "과목, 학기, 시험 범위에 맞춰 자유롭게 나눌 수 있어요.", '<button data-action="new-project">프로젝트 만들기</button>')}<div class="card space"><div class="eyebrow">With your local agent</div><h3>자료 준비는 에이전트와, 공부는 여기에서.</h3><p class="muted">Codex 또는 Claude Code에 “이 자료로 학습 프로젝트 만들어줘”라고 요청하세요.<br>개념 설명과 문제를 준비하고, 이곳에 남긴 학습 기록을 바탕으로 다음 복습을 도와줍니다.</p></div>`,
  );
}
function newProject() {
  const d = document.createElement("dialog");
  d.innerHTML = `<h2>새 학습 프로젝트</h2><form id="create-project" class="stack"><label>프로젝트 이름<input name="title" placeholder="예: 2학기 선형대수" required maxlength="200" autofocus></label><label>학습 유형<select name="profile"><option value="general">자유 학습</option><option value="school">고등학교</option><option value="university">대학교</option><option value="certification">자격증</option><option value="aws-aif">AWS AI Practitioner</option></select></label><label>학습 목표<textarea name="description" placeholder="어떤 내용을 이해하고 싶은가요?"></textarea></label><div class="row"><button class="primary" type="submit">프로젝트 만들기</button><button type="button" data-action="close-dialog">취소</button></div></form>`;
  document.body.append(d);
  d.addEventListener("close", () => d.remove());
  d.showModal();
}
async function home() {
  const p = state.project;
  const [stats, topics, qs, history] = await Promise.all([
    api(`/projects/${p.id}/progress`),
    api(`/projects/${p.id}/topics`),
    api(`/projects/${p.id}/questions`),
    api(`/projects/${p.id}/history`),
  ]);
  const active = history.filter((s) => s.status === "in_progress");
  shell(
    `<div class="hero"><div><div class="eyebrow">${h(profile(p.profile))}</div><h1>${h(p.title)}</h1><p>${h(p.description || "조금씩 이해하고, 직접 설명하고, 다시 풀어보세요.")}</p></div><button class="primary" data-action="navigate" data-to="practice">학습 시작 ↗</button></div><div class="grid"><div class="card"><small>준비된 학습 내용</small><div class="number">${topics.length}<small> 개념</small></div><small>연습 문제 ${qs.length}개</small></div><div class="card"><small>완료한 학습</small><div class="number">${stats.completed}<small> 회</small></div><small>학습 근거가 차곡차곡 쌓이고 있어요</small></div><div class="card"><small>오늘 복습할 문제</small><div class="number">${stats.dueCount}<small> 개</small></div><small>복습 목록 전체 ${stats.reviewCount}개</small></div></div>${
      active.length
        ? `<div class="section-title"><h2>이어서 학습하기</h2></div><div class="list">${active
            .slice(0, 3)
            .map(
              (s) =>
                `<a class="list-item row between" data-link href="${projectPath("session")}/${s.id}"><span>${s.mode === "exam" ? "모의고사" : "연습"} · ${date(s.started_at)}</span><span class="link">계속하기 →</span></a>`,
            )
            .join("")}</div>`
        : ""
    }<div class="section-title"><h2>개념별 학습 현황</h2><a data-link class="link" href="${projectPath("concepts")}">전체 개념 →</a></div>${
      stats.topics.length
        ? `<div class="grid two">${stats.topics
            .slice(0, 6)
            .map(
              (t) =>
                `<a class="card" data-link href="${projectPath("concepts")}/${encodeURIComponent(t.id)}"><h3>${h(t.title)}</h3><div class="row between"><small>${t.attempts}회 시도 · 서로 다른 ${t.uniqueQuestions}문항</small><b>${t.percentage === null ? "시작 전" : t.percentage + "%"}</b></div><progress max="100" value="${t.percentage || 0}" aria-label="${h(t.title)} 정답률"></progress><small>힌트 사용 ${t.assisted}회${t.pending ? " · 채점 대기 " + t.pending + "개" : ""}</small></a>`,
            )
            .join("")}</div>`
        : empty(
            "자료를 학습 내용으로 바꿔보세요",
            "에이전트에게 자료를 전달하거나, 준비된 학습 팩을 가져올 수 있어요.",
            `<a class="link" data-link href="${projectPath("materials")}">자료 관리로 →</a>`,
          )
    }<p class="muted space"><small>정답률은 확인된 답안 기준입니다. 시도 횟수와 문제 다양성도 함께 살펴보세요.</small></p>`,
    "home",
  );
}
async function materials() {
  const [sources, qs] = await Promise.all([
    api(`/projects/${state.project.id}/sources`),
    api(`/projects/${state.project.id}/questions`),
  ]);
  shell(
    `<div class="hero"><div><div class="eyebrow">Learning materials</div><h1>자료에서 시작하는 배움</h1><p>원본 자료는 에이전트를 통해 등록하고, 준비된 개념과 문제는 학습 팩으로 가져옵니다.</p></div></div><div class="grid two"><section class="card"><h2>학습 팩 가져오기</h2><p class="muted">에이전트가 만든 JSON 학습 팩을 선택하세요. 가져오기 전에 문항과 정답 형식을 검증합니다.</p><form id="import-pack" class="stack"><label>학습 팩 파일<input type="file" name="file" accept=".json,application/json" required></label><button class="primary">검증하고 가져오기</button></form><small>현재 활성 문제 ${qs.length}개 · 동일한 파일은 중복 등록하지 않습니다.</small></section><section class="card"><h2>에이전트에게 요청하기</h2><div class="reading"><blockquote>“이 프로젝트에 강의 노트를 추가하고, 출처가 연결된 개념 정리와 확인 문제를 만들어줘.”</blockquote></div><p class="muted">Markdown·TXT·텍스트 PDF를 지원합니다. PDF 추출에는 Poppler가 필요합니다. 스캔 자료는 먼저 텍스트로 변환해 주세요.</p><button data-action="export">프로젝트 내보내기 ↓</button></section></div><div class="section-title"><h2>등록한 원본 자료</h2><small>${sources.length}개</small></div>${sources.length ? '<div class="list">' + sources.map((s) => `<div class="list-item"><h3>${h(s.title)}</h3><small>${h(s.kind.toUpperCase())} · ${date(s.created_at)} · 원본과 추출 텍스트 로컬 보관</small></div>`).join("") + "</div>" : empty("등록된 원본 자료가 없어요", "에이전트에게 로컬 파일을 전달해 등록할 수 있습니다. 학습 팩의 출처 표시는 각 개념과 문제에서 확인할 수 있어요.")}`,
    "materials",
  );
}
async function concepts(id) {
  const topics = await api(`/projects/${state.project.id}/topics`);
  if (!topics.length) {
    shell(
      empty(
        "아직 개념이 없어요",
        "학습 자료를 등록하고 에이전트에게 단원별 개념 정리를 요청하세요.",
      ),
      "concepts",
    );
    return;
  }
  const t =
    topics.find((x) => x.id === decodeURIComponent(id || "")) || topics[0];
  const qs = await api(
    `/projects/${state.project.id}/questions?topic=${encodeURIComponent(t.id)}`,
  );
  shell(
    `<div class="hero"><div><div class="eyebrow">Understand & connect</div><h1>개념 학습</h1><p>읽은 뒤에는 자료를 덮고, 자신의 말로 설명해 보세요.</p></div></div><div class="topic-layout"><nav class="topic-list" aria-label="단원">${topics.map((x) => `<a data-link class="${x.id === t.id ? "active" : ""}" href="${projectPath("concepts")}/${encodeURIComponent(x.id)}">${h(x.title)}</a>`).join("")}</nav><article class="card"><span class="badge">관련 문제 ${qs.length}개</span><h2 class="space">${h(t.title)}</h2>${t.objectives.length ? `<div class="alert"><b>학습 목표</b><ul>${t.objectives.map((o) => "<li>" + h(o) + "</li>").join("")}</ul></div>` : ""}<div class="reading">${md(t.body)}</div>${t.source_refs.length ? `<p><small>출처: ${t.source_refs.map(h).join(" · ")}</small></p>` : ""}<div class="row space"><button class="primary" data-action="topic-practice" data-topic="${h(t.id)}" data-count="${Math.min(qs.length, 10)}" ${qs.length ? "" : "disabled"}>이 개념 연습하기 (${Math.min(qs.length, 10)})</button></div></article></div>`,
    "concepts",
  );
}
async function practice() {
  const [qs, topics] = await Promise.all([
    api(`/projects/${state.project.id}/questions`),
    api(`/projects/${state.project.id}/topics`),
  ]);
  const policy = state.project.policy;
  shell(
    `<div class="hero"><div><div class="eyebrow">Recall & apply</div><h1>직접 풀어보는 시간</h1><p>정답을 보기 전에 먼저 생각해 보세요. 막히는 지점이 다음 학습의 출발점입니다.</p></div></div><div class="grid two"><section class="card"><span class="badge">내 속도에 맞게</span><h2 class="space">자유 연습</h2><form id="practice" class="stack"><label>학습 범위<select name="topic"><option value="">전체 개념</option>${topics.map((t) => `<option value="${h(t.id)}">${h(t.title)}</option>`).join("")}</select></label><label>문항 수<input type="number" name="count" min="1" max="1000" value="${Math.min(20, qs.length) || 1}" required list="practice-counts"><datalist id="practice-counts"><option value="20"><option value="30"><option value="50"><option value="100"></datalist></label><small>전체 ${qs.length}문항 · 시간 제한 없음</small><button class="primary" ${qs.length ? "" : "disabled"}>연습 시작 →</button></form></section><section class="card"><span class="badge amber">시간 제한 연습</span><h2 class="space">모의고사</h2>${policy.count ? `<p>${policy.count}문항 · ${policy.minutes}분<br>채점 ${policy.scored}문항 / 비채점 ${policy.count - policy.scored}문항<br>모의 점수 ${policy.maxScore}점 만점 · ${policy.passingScore}점 합격</p><p class="muted"><small>앱 내부 환산 점수입니다. 공식 시험 점수를 예측하지 않습니다.</small></p><button data-action="exam" class="primary">모의고사 시작 →</button>` : '<p class="muted">현재 프로젝트는 자유 연습을 사용합니다. AWS AI Practitioner 프로젝트에는 65문항 모의고사 프리셋이 제공됩니다.</p>'}</section></div><div class="section-title"><h2>전체 문제 모아보기</h2><small>정답과 해설 포함 · ${qs.length}문항</small></div><label class="sr-only" for="question-search">문제 검색</label><input id="question-search" placeholder="문제 검색…" type="search"><div class="list space" id="question-bank">${qs.map((q) => `<details class="list-item bank-item" data-search="${h(q.prompt.toLowerCase())}"><summary><span class="badge">${h(q.number || q.id)}</span> ${h(q.prompt.slice(0, 130))}</summary>${questionDetails(q)}<button data-action="mark" data-qid="${h(q.id)}">헷갈림으로 저장</button></details>`).join("")}</div>`,
    "practice",
  );
}
function questionDetails(q) {
  return `<div class="reading">${md(q.prompt)}</div>${(q.options || []).map((o) => `<p><b>${h(o.label)}.</b> ${h(o.text)} ${(q.answer || []).includes(o.label) ? '<span class="badge">정답</span>' : ""}</p>`).join("")}${q.type === "short" ? "<p>허용 정답: " + q.answer.map(h).join(" / ") + "</p>" : ""}<div class="reading">${md(q.explanation || q.rubric || "")}</div><p><small>${q.origin === "original" ? "원문 문제" : "생성 문제"} · ${(q.sourceRefs || []).map(h).join(" · ") || "출처 미지정"}</small></p>`;
}
async function start(config) {
  config.requestKey = crypto.randomUUID();
  const s = await api(`/projects/${state.project.id}/sessions`, "POST", config);
  go(projectPath("session") + "/" + s.id);
}
async function sessionView(sid) {
  const s = await api("/sessions/" + sid);
  if (s.project_id !== state.project.id)
    throw Error("다른 프로젝트의 학습 기록입니다.");
  state.session = s;
  if (s.status !== "in_progress") {
    results(s);
    return;
  }
  state.index = Math.min(state.index, s.items.length - 1);
  drawSession();
  if (s.expires_at) {
    timer = setInterval(async () => {
      const left = Math.max(
        0,
        Math.ceil((Date.parse(s.expires_at) - Date.now()) / 1000),
      );
      const t = document.querySelector("#timer");
      if (t)
        t.textContent =
          Math.floor(left / 60) + ":" + String(left % 60).padStart(2, "0");
      if (left === 0) {
        clearInterval(timer);
        try {
          await api("/sessions/" + sid + "/submit", "POST", {});
          await sessionView(sid);
        } catch (e) {
          notify(e.message);
        }
      }
    }, 1000);
  }
}
function drawSession() {
  const s = state.session,
    item = s.items[state.index],
    q = item.question;
  const answered = s.items.filter(
    (i) =>
      i.answer !== null && i.answer !== "" && JSON.stringify(i.answer) !== "[]",
  ).length;
  const visible = s.items.filter(
    (i) =>
      state.reviewFilter === "all" ||
      (state.reviewFilter === "flagged" && i.flagged) ||
      (state.reviewFilter === "unanswered" &&
        (i.answer === null ||
          i.answer === "" ||
          JSON.stringify(i.answer) === "[]")),
  );
  shell(
    `<div class="hero"><div><div class="eyebrow">${s.mode === "exam" ? "Mock exam" : "Practice session"}</div><h1>${s.mode === "exam" ? "모의고사" : "학습 세션"}</h1><p>${answered} / ${s.items.length} 답변 완료 · 변경 내용은 자동 저장됩니다.</p></div><button class="primary" data-action="submit-session">제출하고 확인</button></div><div class="exam-layout"><section class="card"><div class="row between"><span class="badge">문제 ${state.index + 1} / ${s.items.length}</span><button data-action="flag">${item.flagged ? "★ 검토 표시됨" : "☆ 검토 표시"}</button></div><div class="question">${h(q.prompt)}</div>${q.type === "single" || q.type === "multiple" ? q.options.map((o) => `<label class="option ${(item.answer || []).includes(o.label) ? "selected" : ""}"><input type="${q.type === "single" ? "radio" : "checkbox"}" name="answer" value="${h(o.label)}" ${(item.answer || []).includes(o.label) ? "checked" : ""}><b>${h(o.label)}</b><span>${h(o.text)}</span></label>`).join("") : `<label>내 답안<textarea id="text-answer" placeholder="자신의 말로 답해 보세요.">${h(item.answer || "")}</textarea></label><small>입력을 마치고 다른 곳을 누르면 저장됩니다.${q.type === "essay" ? " 제출 후 루브릭으로 자기 채점합니다." : ""}</small>`}<div class="row space"><label>자기 확신 <select id="confidence"><option value="">미기록</option>${[1, 2, 3, 4, 5].map((n) => `<option value="${n}" ${item.confidence === n ? "selected" : ""}>${n} / 5</option>`).join("")}</select></label><label><input type="checkbox" id="assisted" ${item.hints ? "checked" : ""}> 외부 힌트·자료를 참고했어요</label></div><div class="row between space"><button data-action="previous" ${state.index === 0 ? "disabled" : ""}>← 이전</button><small id="save-status">저장됨</small><button data-action="next" ${state.index === s.items.length - 1 ? "disabled" : ""}>다음 →</button></div></section><aside class="card exam-side"><small>${s.expires_at ? "남은 시간" : "시간 제한 없음"}</small><p class="timer" id="timer">${s.expires_at ? "계산 중…" : "∞"}</p><label>문제 필터<select id="review-filter">${[
      ["all", "전체"],
      ["unanswered", "미답변"],
      ["flagged", "검토 표시"],
    ]
      .map(
        ([v, t]) =>
          `<option value="${v}" ${state.reviewFilter === v ? "selected" : ""}>${t}</option>`,
      )
      .join(
        "",
      )}</select></label><div class="navigator space">${visible.map((i) => `<button aria-label="문제 ${i.position + 1}" data-action="jump" data-index="${i.position}" class="${i.position === state.index ? "current " : ""}${i.answer !== null && i.answer !== "" && JSON.stringify(i.answer) !== "[]" ? "answered " : ""}${i.flagged ? "flagged" : ""}">${i.position + 1}</button>`).join("")}</div><p class="space"><small><span class="kbd">A–E</span> 선택<br><span class="kbd">← →</span> 문제 이동<br><span class="kbd">F</span> 검토 표시 · <span class="kbd">R</span> 미답변 필터</small></p></aside></div>`,
    "practice",
  );
}
let saving = Promise.resolve();
async function saveAnswer(changes) {
  const s = state.session;
  if (!s || s.status !== "in_progress") return;
  const item = s.items[state.index];
  const operation = async () => {
    const status = document.querySelector("#save-status");
    if (status) status.textContent = "저장 중…";
    try {
      const res = await api(`/sessions/${s.id}/answers/${item.id}`, "PUT", {
        answer:
          item.answer ??
          (item.question.type === "single" || item.question.type === "multiple"
            ? []
            : ""),
        ...changes,
        version: item.version,
      });
      Object.assign(item, changes, { version: res.version });
      if (status) status.textContent = "저장됨";
    } catch (e) {
      notify(e.message);
      await sessionView(s.id);
      throw e;
    }
  };
  saving = saving.catch(() => {}).then(operation);
  return saving;
}
function results(s) {
  const r = s.result;
  shell(
    `<div class="hero"><div><div class="eyebrow">Reflect & grow</div><h1>오늘의 학습 기록</h1><p>${date(s.finished_at)} · ${s.status === "timed_out" ? "시간이 종료되어 제출되었습니다." : "학습을 마쳤습니다."}</p></div><button data-action="navigate" data-to="review">오답 복습 →</button></div><div class="grid"><div class="card"><small>${s.mode === "exam" ? "모의 환산 점수" : "확정 답안 기준 점수"}</small><div class="result-score">${r.pending ? "대기" : s.mode === "exam" ? r.scaledScore : r.percentage + "%"}</div><span class="badge ${r.passed === false ? "red" : ""}">${r.pending ? `${r.pending}문항 자기 채점 필요` : r.passed === null ? "학습 완료" : r.passed ? "합격 기준 도달" : "다시 도전해 보세요"}</span></div><div class="card"><small>정답 문항</small><div class="number">${r.correct} / ${r.scoredCount}</div><small>채점 대상 기준 · 전체 ${r.totalCount}문항</small></div><div class="card"><small>획득 배점</small><div class="number">${r.earned} / ${r.maximum}</div><small>힌트 사용은 별도로 기록됩니다.</small></div></div><div class="section-title"><h2>답안과 피드백</h2></div><div class="list">${s.items.map((i, n) => `<details class="card result-card ${i.score === 0 ? "wrong" : ""}" ${i.grade_status === "pending" ? "open" : ""}><summary>${n + 1}. ${h(i.question.prompt.slice(0, 110))} <span class="badge ${i.score === 0 ? "red" : ""}">${i.grade_status === "pending" ? "자기 채점 대기" : i.score + "/" + (i.question.points || 1)}${i.scored ? "" : " · 비채점"}</span></summary><p>내 답안: <b>${h(Array.isArray(i.answer) ? i.answer.join(", ") : i.answer) || "미답변"}</b></p>${questionDetails(i.question)}${i.hints ? '<p class="muted">힌트 또는 자료를 참고한 답안입니다.</p>' : ""}${i.grade_status === "pending" ? `<form class="self-grade row" data-item="${i.id}"><label>자기 평가 점수<input type="number" name="score" min="0" max="${i.question.points || 1}" step="0.1" required></label><label>판단 근거<input name="feedback" placeholder="어떤 기준을 충족했나요?"></label><button>평가 저장</button></form>` : ""}<button data-action="mark" data-qid="${h(i.question_id)}">헷갈림으로 저장</button></details>`).join("")}</div>`,
    "history",
  );
}
async function review() {
  const marks = await api(`/projects/${state.project.id}/marks`);
  const active = marks.filter((m) => !m.resolved);
  shell(
    `<div class="hero"><div><div class="eyebrow">Make it stick</div><h1>다시 떠올리는 연습</h1><p>틀린 이유를 남기고, 시간을 두고 다시 풀어보세요. 정답을 외우기보다 이해했는지 확인합니다.</p></div><button class="primary" data-action="review-start" data-count="${Math.min(active.length, 20)}" ${active.length ? "" : "disabled"}>복습 시작 (${Math.min(active.length, 20)}) →</button></div>${marks.length ? `<div class="list">${marks.map((m) => `<details class="card"><summary><span class="badge ${m.resolved ? "" : "amber"}">${m.resolved ? "해결함" : "복습 예정"}</span> ${h(m.question.prompt.slice(0, 120))}</summary><div class="tags">${m.tags.map((t) => '<span class="badge">' + h(t) + "</span>").join("")}</div><p><small>다음 복습 ${date(m.due_at)} · 독립 정답 연속 ${m.streak}회</small></p>${questionDetails(m.question)}<form class="mark-form stack" data-qid="${h(m.question_id)}"><label>오답 원인 · 다음에 기억할 것<textarea name="memo">${h(m.memo)}</textarea></label><label>태그 (쉼표로 구분)<input name="tags" value="${h(m.tags.join(", "))}" placeholder="개념 부족, 조건 오독, 계산 실수"></label><label><input type="checkbox" name="resolved" ${m.resolved ? "checked" : ""}> 해결한 항목으로 표시</label><button>메모 저장</button></form></details>`).join("")}</div>` : empty("복습할 항목이 아직 없어요", "연습에서 틀린 문제와 직접 표시한 헷갈리는 문제가 이곳에 모입니다.")}`,
    "review",
  );
}
function scoreChart(sessions) {
  const step = 760 / sessions.length;
  return `<svg class="score-chart" viewBox="0 0 800 160" role="img" aria-label="최근 학습 점수 추이"><line x1="20" y1="138" x2="780" y2="138"/>${sessions
    .map((s, i) => {
      const v = s.result.percentage,
        x = 20 + i * step + step / 2,
        w = Math.min(step * 0.6, 48),
        height = Math.max(1, v * 1.05);
      return `<g><title>${h(date(s.finished_at))}: ${v}%</title><rect x="${x - w / 2}" y="${138 - height}" width="${w}" height="${height}" rx="4"/><text x="${x}" y="${130 - height}" text-anchor="middle">${v}%</text></g>`;
    })
    .join("")}</svg>`;
}
async function historyView() {
  const sessions = await api(`/projects/${state.project.id}/history`);
  const done = sessions
    .filter((s) => s.result && !s.result.pending)
    .slice(0, 15)
    .reverse();
  shell(
    `<div class="hero"><div><div class="eyebrow">Evidence of learning</div><h1>쌓여가는 학습 기록</h1><p>한 번의 점수보다 여러 번의 시도에서 달라지는 모습을 살펴보세요.</p></div><button data-action="export">내보내기 ↓</button></div>${done.length ? `<div class="card"><h3>최근 학습 점수 (%)</h3>${scoreChart(done)}</div>` : ""}<div class="section-title"><h2>학습 세션</h2><small>${sessions.length}회</small></div>${sessions.length ? `<div class="list">${sessions.map((s) => `<a data-link class="list-item row between" href="${projectPath("session")}/${s.id}"><div><h3>${s.mode === "exam" ? "모의고사" : s.mode === "review" ? "오답 복습" : "자유 연습"}</h3><small>${date(s.started_at)}</small></div><span class="badge">${s.result ? (s.result.pending ? "채점 대기" : s.mode === "exam" ? s.result.scaledScore + "점" : s.result.percentage + "%") : "진행 중 →"}</span></a>`).join("")}</div>` : empty("첫 학습을 시작해 보세요", "문제를 풀면 답안, 점수와 피드백이 이곳에 저장됩니다.")}`,
    "history",
  );
}
document.addEventListener("click", async (e) => {
  const link = e.target.closest("[data-link]");
  if (link) {
    e.preventDefault();
    await saving.catch(() => {});
    go(link.getAttribute("href"));
    return;
  }
  const b = e.target.closest("[data-action]");
  if (!b) return;
  const action = b.dataset.action;
  try {
    if (action === "new-project") return newProject();
    if (action === "close-dialog") return b.closest("dialog").close();
    if (action === "navigate") return go(projectPath(b.dataset.to));
    if (action === "topic-practice")
      return await start({
        mode: "practice",
        topic: b.dataset.topic,
        count: Number(b.dataset.count),
      });
    if (action === "exam") return await start({ mode: "exam" });
    if (action === "review-start")
      return await start({ mode: "review", count: Number(b.dataset.count) });
    if (action === "mark") {
      const marks = await api(`/projects/${state.project.id}/marks`);
      const old = marks.find((m) => m.question_id === b.dataset.qid);
      await api(
        `/projects/${state.project.id}/marks/${encodeURIComponent(b.dataset.qid)}`,
        "PUT",
        {
          tags: [...new Set([...(old?.tags || []), "confused"])],
          memo: old?.memo || "",
          resolved: false,
        },
      );
      return notify("복습 목록에 저장했어요.");
    }
    if (action === "export") {
      const data = await api(`/projects/${state.project.id}/export`);
      const url = URL.createObjectURL(
        new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
      );
      const a = document.createElement("a");
      a.href = url;
      a.download = "study-project-" + state.project.id + ".json";
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      return;
    }
    await saving;
    if (action === "flag") {
      await saveAnswer({ flagged: !state.session.items[state.index].flagged });
      drawSession();
    }
    if (["next", "previous", "jump"].includes(action)) {
      state.index =
        action === "jump"
          ? Number(b.dataset.index)
          : state.index + (action === "next" ? 1 : -1);
      drawSession();
    }
    if (action === "submit-session") {
      const missing = state.session.items.filter(
        (i) =>
          i.answer === null ||
          i.answer === "" ||
          JSON.stringify(i.answer) === "[]",
      ).length;
      if (
        !confirm(
          missing
            ? `${missing}문항에 답하지 않았습니다. 제출할까요?`
            : "답안을 제출하고 결과를 확인할까요?",
        )
      )
        return;
      await api("/sessions/" + state.session.id + "/submit", "POST", {});
      await sessionView(state.session.id);
    }
  } catch (err) {
    notify(err.message);
  }
});
document.addEventListener("submit", async (e) => {
  e.preventDefault();
  const f = e.target,
    button = f.querySelector("button");
  if (button) button.disabled = true;
  const data = new FormData(f);
  try {
    if (f.id === "create-project") {
      const p = await api("/projects", "POST", Object.fromEntries(data));
      f.closest("dialog").close();
      go("/projects/" + p.id + "/home");
    } else if (f.id === "practice")
      await start({
        mode: "practice",
        count: Number(data.get("count")),
        topic: data.get("topic") || null,
      });
    else if (f.id === "import-pack") {
      const pack = JSON.parse(await data.get("file").text());
      const report = await api(
        `/projects/${state.project.id}/imports`,
        "POST",
        { pack, dryRun: true },
      );
      if (
        confirm(
          `개념 ${report.topics}개 · 문제 ${report.questions}개 (초안 ${report.drafts}개)를 가져올까요?`,
        )
      ) {
        await api(`/projects/${state.project.id}/imports`, "POST", { pack });
        notify("학습 팩을 가져왔어요.");
        await materials();
      }
    } else if (f.classList.contains("mark-form")) {
      await api(
        `/projects/${state.project.id}/marks/${encodeURIComponent(f.dataset.qid)}`,
        "PUT",
        {
          memo: data.get("memo"),
          tags: data
            .get("tags")
            .split(",")
            .map((x) => x.trim())
            .filter(Boolean),
          resolved: data.has("resolved"),
        },
      );
      notify("메모를 저장했어요.");
    } else if (f.classList.contains("self-grade")) {
      await api(
        `/sessions/${state.session.id}/assess/${f.dataset.item}`,
        "POST",
        { score: Number(data.get("score")), feedback: data.get("feedback") },
      );
      await sessionView(state.session.id);
    }
  } catch (err) {
    notify(err.message);
  } finally {
    if (button) button.disabled = false;
  }
});
document.addEventListener("change", async (e) => {
  try {
    if (e.target.name === "answer") {
      const q = state.session.items[state.index].question;
      await saveAnswer({
        answer: [...document.querySelectorAll("[name=answer]:checked")].map(
          (x) => x.value,
        ),
      });
      if (q.type === "single" || q.type === "multiple") drawSession();
    }
    if (e.target.id === "text-answer")
      await saveAnswer({ answer: e.target.value });
    if (e.target.id === "confidence")
      await saveAnswer({
        confidence: e.target.value ? Number(e.target.value) : null,
      });
    if (e.target.id === "assisted")
      await saveAnswer({ hints: e.target.checked ? 1 : 0 });
    if (e.target.id === "review-filter") {
      state.reviewFilter = e.target.value;
      drawSession();
    }
  } catch (err) {
    notify(err.message);
  }
});
document.addEventListener("input", (e) => {
  if (e.target.id === "question-search")
    document
      .querySelectorAll(".bank-item")
      .forEach(
        (x) =>
          (x.hidden = !x.dataset.search.includes(e.target.value.toLowerCase())),
      );
});
document.addEventListener("keydown", (e) => {
  if (
    !state.session ||
    state.session.status !== "in_progress" ||
    /INPUT|TEXTAREA|SELECT/.test(e.target.tagName) ||
    e.metaKey ||
    e.ctrlKey ||
    e.altKey
  )
    return;
  const actions = { ArrowLeft: "previous", ArrowRight: "next", f: "flag" };
  if (actions[e.key]) {
    const b = document.querySelector(`[data-action=${actions[e.key]}]`);
    if (b && !b.disabled) {
      e.preventDefault();
      b.click();
    }
  }
  if (e.key.toLowerCase() === "r") {
    state.reviewFilter =
      state.reviewFilter === "unanswered" ? "all" : "unanswered";
    drawSession();
  }
  if (/^[a-e]$/i.test(e.key)) {
    const input = [...document.querySelectorAll("[name=answer]")].find(
      (x) => x.value === e.key.toUpperCase(),
    );
    if (input) {
      e.preventDefault();
      input.click();
    }
  }
});
window.addEventListener("popstate", render);
render();
