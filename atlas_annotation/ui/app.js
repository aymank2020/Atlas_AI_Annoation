"use strict";
const form = document.querySelector("#review-form");
const status = document.querySelector("#status");
const resultSection = document.querySelector("#review-result");
const reviewButton = document.querySelector("#review-button");
const downloadButton = document.querySelector("#download-report");
const fileInputs = ["live-file", "source-file", "plan-file"].map((id) =>
  document.getElementById(id),
);
let report = null;
let revision = 0;
let activeRequest = null;

function invalidate() {
  revision += 1;
  activeRequest?.abort();
  activeRequest = null;
  report = null;
  downloadButton.disabled = true;
  reviewButton.disabled = false;
  resultSection.hidden = true;
  status.textContent = "تغيرت المدخلات؛ أعد المراجعة.";
}
for (const input of [...fileInputs, document.querySelector("#tolerance")])
  input.addEventListener("change", invalidate);
document.querySelector("#tolerance").addEventListener("input", invalidate);
form.addEventListener("reset", invalidate);

function appendText(parent, tag, text) {
  const element = document.createElement(tag);
  element.textContent = text;
  parent.append(element);
  return element;
}
function populateList(id, items, emptyText) {
  const list = document.getElementById(id);
  list.replaceChildren();
  for (const text of items.length ? items : [emptyText])
    appendText(list, "li", text);
}
function segmentCell(cell, segments) {
  if (!segments.length) return appendText(cell, "p", "غير موجود");
  for (const item of segments) {
    appendText(cell, "p", `${item.start_sec} → ${item.end_sec} ثانية`);
    if (item.label) appendText(cell, "p", item.label);
  }
}
function render(value) {
  const states = {
    matched: "متسق",
    blocked: "منع",
    duplicate: "معرف مكرر",
    missing_live: "مفقود من DOM",
    missing_source: "زائد عن المصدر",
    warning: "تحذير",
  };
  const titles = {
    matched: "اللقطتان متسقتان",
    blocked: "توجد أسباب تمنع الاتساق",
    input_error: "تعذر قراءة المدخلات",
  };
  status.textContent = `${titles[value.status]} — رمز CLI: ${value.exit_code}`;
  document.querySelector("#counts").textContent = value.segment_counts
    ? `DOM: ${value.segment_counts.live} مقطع — المصدر: ${value.segment_counts.source} مقطع`
    : "لم تُبنَ لقطات صالحة للمقارنة.";
  const checksums = document.querySelector("#checksums");
  checksums.replaceChildren();
  for (const [title, digest] of [
    ["بصمة مقاطع DOM", value.live_checksum],
    ["بصمة مقاطع المصدر", value.source_checksum],
    ["SHA256 لنص ملف DOM الخام", value.files.live.raw_sha256],
    ["SHA256 لنص ملف المصدر الخام", value.files.source.raw_sha256],
  ]) {
    appendText(checksums, "dt", title);
    appendText(checksums, "dd", digest || "غير متاحة");
  }
  populateList(
    "blocking",
    value.error ? [value.error] : value.blocking_mismatches || [],
    "لا أسباب منع.",
  );
  populateList("warnings", value.warnings || [], "لا تحذيرات.");
  const rows = document.querySelector("#segment-rows");
  rows.replaceChildren();
  for (const item of value.rows) {
    const row = document.createElement("tr");
    row.dataset.state = item.state;
    appendText(row, "th", item.segment_index).scope = "row";
    appendText(row, "td", states[item.state] || item.state);
    for (const group of [item.live, item.source, item.plan])
      segmentCell(appendText(row, "td", ""), group);
    appendText(
      row,
      "td",
      `البداية: ${item.drift.start_sec ?? "غير متاح"}؛ النهاية: ${item.drift.end_sec ?? "غير متاح"} ثانية`,
    );
    const reasons = appendText(row, "td", "");
    for (const text of [...item.blocking_mismatches, ...item.warnings])
      appendText(reasons, "p", text);
    rows.append(row);
  }
  document.querySelector("#table-caption").textContent =
    `المقاطع حسب المعرف — ${value.rows.length} صف`;
  resultSection.hidden = false;
  downloadButton.disabled = false;
}
async function rawFile(input) {
  const file = input.files[0];
  if (!file) return null;
  if (file.size > 256 * 1024) throw new Error("كل ملف يجب ألا يتجاوز 256 KiB.");
  // Preserve BOM and NaN/Infinity text; Python alone parses the snapshots.
  return new TextDecoder("utf-8", { fatal: true, ignoreBOM: true }).decode(
    await file.arrayBuffer(),
  );
}
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  invalidate();
  const currentRevision = revision;
  const controller = new AbortController();
  activeRequest = controller;
  reviewButton.disabled = true;
  status.textContent = "تجري مراجعة اللقطات محليًا…";
  try {
    const [live, source, plan] = await Promise.all(fileInputs.map(rawFile));
    if (currentRevision !== revision) return;
    const body = JSON.stringify({
      live_json: live,
      source_json: source,
      plan_json: plan,
      tolerance_sec: document.querySelector("#tolerance").value,
    });
    const response = await fetch("/api/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      signal: controller.signal,
    });
    const value = await response.json();
    if (currentRevision !== revision) return;
    if (!response.ok)
      throw new Error(value.error || "تعذر الاتصال بالمراجع المحلي.");
    if (
      value.scope !== "snapshot_integrity" ||
      value.submit_authorized !== false ||
      ![0, 1, 2].includes(value.exit_code) ||
      !Array.isArray(value.rows)
    )
      throw new Error("استجابة المراجع غير صالحة.");
    report = value;
    render(value);
  } catch (error) {
    if (currentRevision === revision)
      status.textContent = `تعذرت المراجعة: ${error.message}`;
  } finally {
    if (currentRevision === revision) {
      reviewButton.disabled = false;
      activeRequest = null;
    }
  }
});
downloadButton.addEventListener("click", () => {
  if (!report) return;
  const link = document.createElement("a");
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(report, null, 2) + "\n"], {
      type: "application/json",
    }),
  );
  link.href = url;
  link.download = "atlas-snapshot-review.json";
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
